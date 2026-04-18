from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime, timezone
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
from services.liveness.service import HeuristicPassiveLivenessService
from services.quality.service import QualityGate
from services.recognition.frame_codec import decode_frame_b64
from services.recognition.pipeline import InsightFaceEmbeddingPipeline
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

    async def start(self, request: EnrollmentStartRequest) -> EnrollmentStartResponse:
        device = await self.device_repository.get_by_code(request.device_code)
        if device is None or not device.is_enabled:
            raise LookupError(f"device config not found for {request.device_code}")
        person = await self.person_repository.get_or_create(request.student_id, request.full_name, request.email)
        state = EnrollmentState(
            enrollment_session_id=uuid4(),
            person_id=person.id,
            student_id=person.student_id,
            full_name=person.full_name,
            device_code=request.device_code,
            accepted_counts={pose: 0 for pose in REQUIRED_POSES},
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
            quality = QualitySnapshot(brightness_score=0.0, blur_score=0.0, liveness_score=0.0, face_width_px=0, accepted=False, reason="pose_quota_reached", flags={"pose_quota_reached": True})
            return EnrollmentFrameResponse(
                enrollment_session_id=state.enrollment_session_id,
                accepted=False,
                reason="pose_quota_reached",
                pose=request.pose,
                pose_accepted_count=pose_count,
                total_accepted_count=sum(state.accepted_counts.values()),
                quality=quality,
            )
        frame_bytes = decode_frame_b64(request.frame_b64)
        analysis = await self.pipeline.analyze(frame_bytes=frame_bytes, det_thresh=device.det_thresh, det_size=(device.det_size_width, device.det_size_height), max_faces=device.max_faces)
        liveness = await self.liveness_service.score(analysis.frame)
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
        if not quality.accepted:
            LOGGER.info("enrollment_frame_rejected", extra={"student_id": state.student_id, "pose": request.pose, "reason": quality.reason})
            return EnrollmentFrameResponse(
                enrollment_session_id=state.enrollment_session_id,
                accepted=False,
                reason=quality.reason,
                pose=request.pose,
                pose_accepted_count=pose_count,
                total_accepted_count=sum(state.accepted_counts.values()),
                quality=QualitySnapshot(**asdict(quality)),
            )
        sample_id = uuid4()
        image_uri = await self.object_storage.put_bytes(f"enrollment/{state.person_id}/{state.enrollment_session_id}/{sample_id}.jpg", frame_bytes)
        await self.face_sample_repository.add(
            FaceSample(
                id=sample_id,
                person_id=state.person_id,
                enrollment_session_id=state.enrollment_session_id,
                pose=request.pose,
                embedding=analysis.faces[0].embedding,
                image_uri=image_uri,
                source_device_code=request.device_code,
                brightness_score=quality.brightness_score,
                blur_score=quality.blur_score,
                liveness_score=quality.liveness_score,
                face_width_px=quality.face_width_px,
                quality_flags=quality.flags,
            )
        )
        state.accepted_counts[request.pose] += 1
        await self.cache.set_enrollment_state(state)
        await self.session.commit()
        LOGGER.info("enrollment_frame_accepted", extra={"student_id": state.student_id, "pose": request.pose, "total_accepted_count": sum(state.accepted_counts.values())})
        return EnrollmentFrameResponse(
            enrollment_session_id=state.enrollment_session_id,
            accepted=True,
            reason=quality.reason,
            pose=request.pose,
            pose_accepted_count=state.accepted_counts[request.pose],
            total_accepted_count=sum(state.accepted_counts.values()),
            quality=QualitySnapshot(**asdict(quality)),
        )

    async def finish(self, request: EnrollmentFinishRequest) -> EnrollmentFinishResponse:
        state = await self.cache.get_enrollment_state(request.enrollment_session_id)
        if state is None:
            raise LookupError(f"enrollment session {request.enrollment_session_id} not found")
        device = await self.device_repository.get_by_code(state.device_code)
        if device is None:
            raise LookupError(f"device config not found for {state.device_code}")
        if any(count < device.accepted_per_pose for count in state.accepted_counts.values()):
            raise ValueError("enrollment does not yet satisfy required pose counts")
        samples = await self.face_sample_repository.list_for_enrollment_session(request.enrollment_session_id)
        if len(samples) < len(REQUIRED_POSES) * device.accepted_per_pose:
            raise ValueError("insufficient accepted samples for template build")
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

