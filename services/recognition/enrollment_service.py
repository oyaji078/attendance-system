from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime, timezone
from time import perf_counter
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from db.models.entities import FaceSample
from db.repositories.device_configs import DeviceConfigRepository
from db.repositories.face_samples import FaceSampleRepository
from db.repositories.face_templates import FaceTemplateRepository
from db.repositories.persons import PersonRepository
from db.schemas.common import REQUIRED_POSES, QualitySnapshot
from db.schemas.enrollment import EnrollmentFinishRequest, EnrollmentFinishResponse, EnrollmentFrameRequest, EnrollmentFrameResponse, EnrollmentStartRequest, EnrollmentStartResponse
from services.attendance.cache import RedisStateCache
from services.liveness.color_challenge import ChallengeResult, ColorChallengeService
from services.liveness.service import HeuristicPassiveLivenessService
from services.quality.service import QualityGate
from services.recognition.frame_codec import decode_frame_b64
from services.recognition.face_crop import crop_face_jpeg
from services.recognition.pipeline import InsightFaceEmbeddingPipeline
from services.recognition.pose_validator import PoseValidator
from services.recognition.template_builder import TemplateBuilder
from services.recognition.types import EnrollmentState
from services.storage.object_storage import LocalObjectStorage

LOGGER = logging.getLogger(__name__)


class EnrollmentService:
    def __init__(
        self,
        session: AsyncSession,
        device_repository: DeviceConfigRepository,
        person_repository: PersonRepository,
        face_sample_repository: FaceSampleRepository,
        face_template_repository: FaceTemplateRepository,
        cache: RedisStateCache,
        pipeline: InsightFaceEmbeddingPipeline,
        liveness_service: HeuristicPassiveLivenessService,
        quality_gate: QualityGate,
        template_builder: TemplateBuilder,
        object_storage: LocalObjectStorage,
        pose_validator: PoseValidator | None = None,
        challenge_service: ColorChallengeService | None = None,
    ) -> None:
        self.session = session
        self.device_repository = device_repository
        self.person_repository = person_repository
        self.face_sample_repository = face_sample_repository
        self.face_template_repository = face_template_repository
        self.cache = cache
        self.pipeline = pipeline
        self.liveness_service = liveness_service
        self.quality_gate = quality_gate
        self.template_builder = template_builder
        self.object_storage = object_storage
        self.pose_validator = pose_validator or PoseValidator()
        self.challenge_service = challenge_service

    async def start(self, request: EnrollmentStartRequest) -> EnrollmentStartResponse:
        device = await self.device_repository.get_by_code(request.device_code)
        if device is None or not device.is_enabled:
            raise LookupError(f"device config not found for {request.device_code}")
        person = await self.person_repository.get_or_create(request.student_id, request.full_name, request.email, request.class_id)
        state = EnrollmentState(
            enrollment_session_id=uuid4(),
            person_id=person.id,
            student_id=person.student_id,
            full_name=person.full_name,
            device_code=request.device_code,
            accepted_counts={pose: 0 for pose in REQUIRED_POSES},
            rejected_counts={pose: 0 for pose in REQUIRED_POSES},
            started_at=datetime.now(timezone.utc),
        )
        await self.cache.set_enrollment_state(state)
        await self.session.commit()
        LOGGER.info("enrollment_started", extra={"student_id": person.student_id, "person_id": person.id, "device_code": request.device_code})
        return EnrollmentStartResponse(
            enrollment_session_id=state.enrollment_session_id,
            person_id=state.person_id,
            required_poses=list(REQUIRED_POSES),
            accepted_per_pose=device.accepted_per_pose,
            remaining_per_pose={pose: device.accepted_per_pose for pose in REQUIRED_POSES},
        )

    async def process_frame(self, request: EnrollmentFrameRequest) -> EnrollmentFrameResponse:
        started_at = perf_counter()
        state = await self.cache.get_enrollment_state(request.enrollment_session_id)
        if state is None:
            raise LookupError(f"enrollment session {request.enrollment_session_id} not found")
        if state.device_code != request.device_code:
            raise ValueError("device code mismatch for enrollment session")
        device = await self.device_repository.get_by_code(request.device_code)
        if device is None or not device.is_enabled:
            raise LookupError(f"device config not found for {request.device_code}")
        pose_count = state.accepted_counts[request.pose]
        if pose_count >= device.accepted_per_pose:
            quality = QualitySnapshot(
                brightness_score=0.0,
                blur_score=0.0,
                contrast_score=0.0,
                overexposed_ratio=0.0,
                underexposed_ratio=0.0,
                liveness_score=0.0,
                face_width_px=0,
                face_center_offset_x=0.0,
                face_center_offset_y=0.0,
                pose_yaw=0.0,
                pose_pitch=0.0,
                pose_roll=0.0,
                pose_valid=False,
                accepted=False,
                reason="pose_quota_reached",
                ui_hint="Pose ini sudah selesai. Lanjut ke pose berikutnya.",
                flags={"pose_quota_reached": True},
            )
            return EnrollmentFrameResponse(
                enrollment_session_id=state.enrollment_session_id,
                accepted=False,
                reason="pose_quota_reached",
                pose=request.pose,
                expected_pose=request.pose,
                pose_accepted_count=pose_count,
                total_accepted_count=sum(state.accepted_counts.values()),
                remaining_per_pose=self._remaining_per_pose(state.accepted_counts, device.accepted_per_pose),
                next_pose=self._next_pose(state.accepted_counts, device.accepted_per_pose),
                pose_valid=False,
                pose_yaw=quality.pose_yaw,
                pose_pitch=quality.pose_pitch,
                pose_roll=quality.pose_roll,
                pose_status="pose_quota_reached",
                guidance_direction=None,
                rejected_count_for_pose=state.rejected_counts.get(request.pose, 0),
                ui_hint=quality.ui_hint,
                progress_percent=self._progress_percent(state.accepted_counts, device.accepted_per_pose),
                capture_status="pose_complete",
                quality=quality,
            )
        if request.challenge_id is not None and self.challenge_service is not None:
            liveness_result: ChallengeResult = self.challenge_service.verify(
                request.challenge_id, request.frame_b64
            )
            if not liveness_result.passed:
                LOGGER.warning(
                    "enrollment_active_liveness_rejected",
                    extra={
                        "enrollment_session_id": str(request.enrollment_session_id),
                        "device_code": request.device_code,
                        "reason": liveness_result.reason,
                    },
                )
                quality = QualitySnapshot(
                    brightness_score=0.0, blur_score=0.0, contrast_score=0.0,
                    overexposed_ratio=0.0, underexposed_ratio=0.0,
                    liveness_score=0.0, face_width_px=0,
                    face_center_offset_x=0.0, face_center_offset_y=0.0,
                    pose_yaw=0.0, pose_pitch=0.0, pose_roll=0.0,
                    pose_valid=False, accepted=False,
                    reason=f"liveness_challenge_{liveness_result.reason}",
                    ui_hint="Tantangan liveness gagal. Silakan coba lagi.",
                    flags={"liveness_challenge_failed": True},
                )
                rejected_count = self._record_rejection(state, request.pose)
                await self.cache.set_enrollment_state(state)
                return EnrollmentFrameResponse(
                    enrollment_session_id=state.enrollment_session_id,
                    accepted=False,
                    reason=quality.reason,
                    pose=request.pose,
                    expected_pose=request.pose,
                    pose_accepted_count=pose_count,
                    total_accepted_count=sum(state.accepted_counts.values()),
                    remaining_per_pose=self._remaining_per_pose(state.accepted_counts, device.accepted_per_pose),
                    next_pose=self._next_pose(state.accepted_counts, device.accepted_per_pose),
                    pose_valid=False, pose_yaw=0.0, pose_pitch=0.0, pose_roll=0.0,
                    pose_status="liveness_failed",
                    guidance_direction=None,
                    rejected_count_for_pose=rejected_count,
                    ui_hint=quality.ui_hint,
                    progress_percent=self._progress_percent(state.accepted_counts, device.accepted_per_pose),
                    capture_status="rejected",
                    quality=quality,
                )

        frame_bytes = decode_frame_b64(request.frame_b64)
        pipeline_started_at = perf_counter()
        analysis = await self.pipeline.analyze(frame_bytes=frame_bytes, det_thresh=device.det_thresh, det_size=(device.det_size_width, device.det_size_height), max_faces=device.max_faces)
        pipeline_ms = (perf_counter() - pipeline_started_at) * 1000.0
        liveness_started_at = perf_counter()
        liveness = await self.liveness_service.score(analysis.frame)
        liveness_ms = (perf_counter() - liveness_started_at) * 1000.0
        quality_started_at = perf_counter()
        quality = self.quality_gate.evaluate(
            frame=analysis.frame,
            faces=analysis.faces,
            max_faces=device.max_faces,
            min_face_width_px=device.min_face_width_px,
            min_brightness=device.min_brightness,
            min_blur_score=device.min_blur_score,
            liveness=liveness,
            liveness_threshold=device.liveness_threshold,
        )
        quality_ms = (perf_counter() - quality_started_at) * 1000.0
        pose_validation = self.pose_validator.validate(request.pose, analysis.faces[0]) if analysis.faces else None
        pose_status = pose_validation.pose_status if pose_validation is not None else "no_face"
        guidance_direction = pose_validation.guidance_direction if pose_validation is not None else None
        if pose_validation is not None and (not quality.accepted or not pose_validation.is_valid):
            quality.pose_valid = pose_validation.is_valid
            quality.reason = pose_validation.reason if quality.accepted else quality.reason
            quality.ui_hint = pose_validation.ui_hint if quality.accepted else quality.ui_hint
            quality.accepted = quality.accepted and pose_validation.is_valid
        elif pose_validation is None:
            quality.pose_valid = False
        if not quality.accepted:
            rejected_count = self._record_rejection(state, request.pose)
            quality.ui_hint = self._adaptive_rejection_hint(request.pose, quality.reason, quality.ui_hint, rejected_count)
            retry_after_ms = 1100 if rejected_count >= 8 else None
            await self.cache.set_enrollment_state(state)
            LOGGER.info(
                "enrollment_frame_rejected",
                extra={
                    "student_id": state.student_id,
                    "pose": request.pose,
                    "reason": quality.reason,
                    "pose_yaw": quality.pose_yaw,
                    "pose_pitch": quality.pose_pitch,
                    "pose_roll": quality.pose_roll,
                    "pose_status": pose_status,
                    "guidance_direction": guidance_direction,
                    "rejected_count_for_pose": rejected_count,
                    "pipeline_ms": round(pipeline_ms, 2),
                    "liveness_ms": round(liveness_ms, 2),
                    "quality_ms": round(quality_ms, 2),
                    "db_write_ms": 0.0,
                    "total_ms": round((perf_counter() - started_at) * 1000.0, 2),
                },
            )
            return EnrollmentFrameResponse(
                enrollment_session_id=state.enrollment_session_id,
                accepted=False,
                reason=quality.reason,
                pose=request.pose,
                expected_pose=request.pose,
                pose_accepted_count=pose_count,
                total_accepted_count=sum(state.accepted_counts.values()),
                remaining_per_pose=self._remaining_per_pose(state.accepted_counts, device.accepted_per_pose),
                next_pose=self._next_pose(state.accepted_counts, device.accepted_per_pose),
                pose_valid=quality.pose_valid,
                pose_yaw=quality.pose_yaw,
                pose_pitch=quality.pose_pitch,
                pose_roll=quality.pose_roll,
                pose_status=pose_status,
                guidance_direction=guidance_direction,
                rejected_count_for_pose=rejected_count,
                retry_after_ms=retry_after_ms,
                ui_hint=quality.ui_hint,
                progress_percent=self._progress_percent(state.accepted_counts, device.accepted_per_pose),
                capture_status="stuck_adjust" if rejected_count >= 8 else "rejected",
                quality=QualitySnapshot(**asdict(quality)),
            )
        sample_id = uuid4()
        crop_started_at = perf_counter()
        face_crop_bytes = crop_face_jpeg(analysis.frame, analysis.faces[0].bbox)
        crop_ms = (perf_counter() - crop_started_at) * 1000.0
        write_started_at = perf_counter()
        image_uri = await self.object_storage.put_bytes(f"enrollment/{state.person_id}/{state.enrollment_session_id}/{sample_id}.jpg", face_crop_bytes)
        embedding = analysis.faces[0].embedding
        try:
            await self.face_sample_repository.add(
                FaceSample(
                    id=sample_id,
                    person_id=state.person_id,
                    enrollment_session_id=state.enrollment_session_id,
                    pose=request.pose,
                    embedding=embedding,
                    image_uri=image_uri,
                    source_device_code=request.device_code,
                    brightness_score=quality.brightness_score,
                    blur_score=quality.blur_score,
                    liveness_score=quality.liveness_score,
                    face_width_px=quality.face_width_px,
                    quality_flags=quality.flags,
                )
            )
            sample_write_ms = (perf_counter() - write_started_at) * 1000.0
        except Exception as exc:
            rollback = getattr(self.session, "rollback", None)
            if rollback is not None:
                await rollback()
            LOGGER.exception(
                "enrollment_sample_store_failed",
                extra={
                    "student_id": state.student_id,
                    "person_id": str(state.person_id),
                    "enrollment_session_id": str(state.enrollment_session_id),
                    "pose": request.pose,
                    "embedding_type": type(embedding).__name__,
                    "embedding_length": self._safe_len(embedding),
                    "error_type": type(exc).__name__,
                },
            )
            raise RuntimeError("Accepted frame could not be stored.") from exc
        state.accepted_counts[request.pose] += 1
        state.rejected_counts[request.pose] = 0
        await self.cache.set_enrollment_state(state)
        commit_started_at = perf_counter()
        await self.session.commit()
        db_commit_ms = (perf_counter() - commit_started_at) * 1000.0
        LOGGER.info(
            "enrollment_frame_accepted",
            extra={
                "student_id": state.student_id,
                "pose": request.pose,
                "total_accepted_count": sum(state.accepted_counts.values()),
                "pipeline_ms": round(pipeline_ms, 2),
                "liveness_ms": round(liveness_ms, 2),
                "quality_ms": round(quality_ms, 2),
                "crop_ms": round(crop_ms, 2),
                "db_write_ms": round(sample_write_ms, 2),
                "db_commit_ms": round(db_commit_ms, 2),
                "total_ms": round((perf_counter() - started_at) * 1000.0, 2),
            },
        )
        return EnrollmentFrameResponse(
            enrollment_session_id=state.enrollment_session_id,
            accepted=True,
            reason=quality.reason,
            pose=request.pose,
            expected_pose=request.pose,
            pose_accepted_count=state.accepted_counts[request.pose],
            total_accepted_count=sum(state.accepted_counts.values()),
            remaining_per_pose=self._remaining_per_pose(state.accepted_counts, device.accepted_per_pose),
            next_pose=self._next_pose(state.accepted_counts, device.accepted_per_pose),
            pose_valid=True,
            pose_yaw=quality.pose_yaw,
            pose_pitch=quality.pose_pitch,
            pose_roll=quality.pose_roll,
            pose_status=pose_status,
            guidance_direction=None,
            rejected_count_for_pose=0,
            ui_hint=self._acceptance_hint(request.pose, state.accepted_counts, device.accepted_per_pose),
            progress_percent=self._progress_percent(state.accepted_counts, device.accepted_per_pose),
            capture_status="accepted",
            quality=QualitySnapshot(**asdict(quality)),
            sample_image_uri=image_uri,
            face_crop_uri=image_uri,
        )

    async def finish(self, request: EnrollmentFinishRequest) -> EnrollmentFinishResponse:
        state = await self.cache.get_enrollment_state(request.enrollment_session_id)
        if state is None:
            raise LookupError(f"enrollment session {request.enrollment_session_id} not found")
        device = await self.device_repository.get_by_code(state.device_code)
        if device is None:
            raise LookupError(f"device config not found for {state.device_code}")
        if any(count < device.accepted_per_pose for count in state.accepted_counts.values()):
            raise ValueError("pose belum lengkap untuk menyelesaikan pendaftaran")
        samples = await self.face_sample_repository.list_for_enrollment_session(request.enrollment_session_id)
        if len(samples) < len(REQUIRED_POSES) * device.accepted_per_pose:
            raise ValueError("sampel wajah belum cukup untuk membuat profil")
        template = await self.face_template_repository.upsert_active(
            person_id=state.person_id,
            embedding=self.template_builder.build([sample.embedding for sample in samples]),
            sample_count=len(samples),
            built_from_session_id=request.enrollment_session_id,
            metadata_json={"poses": state.accepted_counts, "student_id": state.student_id},
        )
        await self.person_repository.activate(state.person_id, template.id)
        await self.cache.clear_enrollment_state(request.enrollment_session_id)
        await self.session.commit()
        LOGGER.info("enrollment_finished", extra={"student_id": state.student_id, "person_id": state.person_id, "template_id": template.id})
        return EnrollmentFinishResponse(
            enrollment_session_id=request.enrollment_session_id,
            person_id=state.person_id,
            template_id=template.id,
            total_samples=len(samples),
            activated=True,
        )

    async def rebuild_template(self, person_id: UUID) -> EnrollmentFinishResponse:
        samples = await self.face_sample_repository.list_for_person(person_id)
        if not samples:
            raise LookupError(f"no face samples found for person {person_id}")
        template = await self.face_template_repository.upsert_active(
            person_id=person_id,
            embedding=self.template_builder.build([sample.embedding for sample in samples]),
            sample_count=len(samples),
            built_from_session_id=samples[-1].enrollment_session_id,
            metadata_json={"rebuild": True},
        )
        await self.person_repository.activate(person_id, template.id)
        await self.session.commit()
        LOGGER.info("template_rebuilt", extra={"person_id": person_id, "template_id": template.id})
        return EnrollmentFinishResponse(
            enrollment_session_id=samples[-1].enrollment_session_id,
            person_id=person_id,
            template_id=template.id,
            total_samples=len(samples),
            activated=True,
        )

    @staticmethod
    def _record_rejection(state: EnrollmentState, pose: str) -> int:
        state.rejected_counts[pose] = state.rejected_counts.get(pose, 0) + 1
        return state.rejected_counts[pose]

    @staticmethod
    def _adaptive_rejection_hint(pose: str, reason: str, base_hint: str, rejected_count: int) -> str:
        if rejected_count < 8:
            return base_hint
        if reason.startswith("pose_mismatch_left_20") or pose == "left_20":
            return "Putar sedikit lagi ke kiri, pastikan wajah tetap di dalam oval."
        if reason.startswith("pose_mismatch_right_20") or pose == "right_20":
            return "Putar sedikit lagi ke kanan, pastikan wajah tetap di dalam oval."
        if reason.startswith("pose_mismatch_up_or_down") or pose == "up_or_down":
            return "Naikkan atau turunkan dagu sedikit lagi, lalu tahan di dalam oval."
        if reason == "face_not_centered":
            return "Tetap di dalam oval sebelum menahan wajah."
        return f"{base_hint} Tahan wajah di dalam oval untuk rekaman berikutnya."

    @staticmethod
    def _safe_len(value: object) -> int | None:
        try:
            return len(value)  # type: ignore[arg-type]
        except TypeError:
            return None

    @staticmethod
    def _remaining_per_pose(accepted_counts: dict[str, int], accepted_per_pose: int) -> dict[str, int]:
        return {
            pose: max(accepted_per_pose - accepted_counts.get(pose, 0), 0)
            for pose in REQUIRED_POSES
        }

    @staticmethod
    def _next_pose(accepted_counts: dict[str, int], accepted_per_pose: int):
        for pose in REQUIRED_POSES:
            if accepted_counts.get(pose, 0) < accepted_per_pose:
                return pose
        return None

    @staticmethod
    def _progress_percent(accepted_counts: dict[str, int], accepted_per_pose: int) -> float:
        total_required = len(REQUIRED_POSES) * accepted_per_pose
        total_done = sum(accepted_counts.values())
        if total_required <= 0:
            return 0.0
        return round((total_done / total_required) * 100.0, 2)

    @staticmethod
    def _acceptance_hint(pose: str, accepted_counts: dict[str, int], accepted_per_pose: int) -> str:
        if accepted_counts.get(pose, 0) >= accepted_per_pose:
            return "Berhasil direkam. Lanjut ke pose berikutnya."
        return "Bagus, tetap diam."
