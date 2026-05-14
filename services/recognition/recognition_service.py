from __future__ import annotations

import asyncio
import logging
import base64
import binascii
from datetime import datetime, timezone
from time import perf_counter
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.entities import AttendanceLog, AttendanceSession, ClassGroup, FaceTemplate, Person
from db.repositories.attendance import AttendanceRepository
from db.repositories.device_configs import DeviceConfigRepository
from db.schemas.attendance import AttendanceConfirmRequest, AttendanceConfirmResponse, AttendancePreviewRequest, AttendanceRecordRead
from db.schemas.attendance_sessions import ResolvedAttendanceSession
from db.schemas.common import PersonSummary
from db.schemas.recognition import RecognitionRequest, RecognitionResponse
from services.attendance.cache import RedisStateCache
from services.recognition.decision_engine import MultiFrameDecisionEngine
from services.recognition.frame_processor import RecognitionFrameProcessor
from services.liveness.color_challenge import ColorChallengeService, ChallengeResult
from services.recognition.logger import RecognitionAuditLogger
from services.recognition.types import RecognitionFrameDecision
from services.storage.object_storage import LocalObjectStorage

LOGGER = logging.getLogger(__name__)


class RecognitionService:
    def __init__(
        self,
        session: AsyncSession,
        device_repository: DeviceConfigRepository,
        attendance_repository: AttendanceRepository,
        frame_processor: RecognitionFrameProcessor,
        decision_engine: MultiFrameDecisionEngine,
        audit_logger: RecognitionAuditLogger,
        cache: RedisStateCache | None = None,
        object_storage: LocalObjectStorage | None = None,
        slow_request_ms: int = 2500,
        challenge_service: ColorChallengeService | None = None,
    ) -> None:
        self.session = session
        self.device_repository = device_repository
        self.attendance_repository = attendance_repository
        self.frame_processor = frame_processor
        self.decision_engine = decision_engine
        self.audit_logger = audit_logger
        self.cache = cache or getattr(decision_engine, "cache", None)
        self.object_storage = object_storage
        self.slow_request_ms = slow_request_ms
        self.challenge_service = challenge_service

    async def recognize(self, request: RecognitionRequest, event_type: str, require_session: bool = False) -> RecognitionResponse:
        started_at = perf_counter()
        device = await self.device_repository.get_by_code(request.device_code)
        if device is None or not device.is_enabled:
            raise LookupError(f"device config not found for {request.device_code}")
        session_record = await self._resolve_session(request.session_code, require_session=require_session)
        availability_reason = None if session_record is None else self.attendance_repository.availability_reason(
            session_record,
            now=datetime.now(timezone.utc),
        )
        if availability_reason is not None:
            response = RecognitionResponse(
                decision="rejected",
                reason=availability_reason,
                recognition_status="session_inactive",
                confirmed_frames=0,
                device_code=request.device_code,
                session_code=request.session_code,
            )
            await self.audit_logger.log(response, request, None, None, event_type, frame_decisions=[])
            await self.session.commit()
            return response

        challenge_result: ChallengeResult | None = None
        if request.challenge_id is not None and self.challenge_service is not None and request.frames:
            challenge_result = self.challenge_service.verify(request.challenge_id, request.frames[0].frame_b64)
            if not challenge_result.passed:
                LOGGER.warning(
                    "active_liveness_rejected",
                    extra={"device_code": request.device_code, "challenge_id": request.challenge_id, "reason": challenge_result.reason},
                )
                response = RecognitionResponse(
                    decision="rejected",
                    reason=f"active_liveness_{challenge_result.reason}",
                    recognition_status="rejected",
                    confirmed_frames=0,
                    device_code=request.device_code,
                    session_code=request.session_code,
                    active_liveness_score=challenge_result.liveness_score,
                    active_liveness_passed=False,
                )
                await self.audit_logger.log(response, request, None, None, event_type, frame_decisions=[])
                await self.session.commit()
                return response

        processing_started_at = perf_counter()
        processed_frames = await asyncio.gather(*[self.frame_processor.process(frame_input, device) for frame_input in request.frames])
        frame_processing_ms = (perf_counter() - processing_started_at) * 1000.0
        frame_decisions = [item.decision for item in processed_frames]
        candidate_rows = [candidate for item in processed_frames for candidate in item.candidates]
        decision_started_at = perf_counter()
        response, person_id, template_id = await self.decision_engine.decide(
            request=request,
            frame_decisions=frame_decisions,
            candidate_rows=candidate_rows,
            multi_frame_confirm=device.multi_frame_confirm,
            cooldown_seconds=device.cooldown_seconds if session_record is None else session_record.cooldown_seconds,
            similarity_threshold=device.similarity_threshold,
            candidate_margin_threshold=device.candidate_margin_threshold,
        )
        decision_ms = (perf_counter() - decision_started_at) * 1000.0
        if challenge_result is not None:
            response.active_liveness_score = challenge_result.liveness_score
            response.active_liveness_passed = True
        captured_face_jpeg = self._lazy_face_crop(processed_frames)
        if captured_face_jpeg is not None and response.recognition_status in {"recognized", "cooldown"}:
            response.captured_face_b64 = base64.b64encode(captured_face_jpeg).decode("ascii")
        captured_image_uri = await self._store_attendance_image(request, response, event_type, captured_face_jpeg)
        audit_started_at = perf_counter()
        await self.audit_logger.log(response, request, person_id, template_id, event_type, frame_decisions=frame_decisions, captured_image_uri=captured_image_uri)
        audit_ms = (perf_counter() - audit_started_at) * 1000.0
        commit_started_at = perf_counter()
        await self.session.commit()
        db_commit_ms = (perf_counter() - commit_started_at) * 1000.0
        total_ms = (perf_counter() - started_at) * 1000.0
        LOGGER.info(
            "recognition_completed",
            extra={
                "device_code": request.device_code,
                "decision": response.decision,
                "recognition_status": response.recognition_status,
                "reason": response.reason,
                "person_id": person_id,
                "frame_processing_ms": round(frame_processing_ms, 2),
                "decision_ms": round(decision_ms, 2),
                "audit_write_ms": round(audit_ms, 2),
                "db_commit_ms": round(db_commit_ms, 2),
                "total_request_ms": round(total_ms, 2),
                "slow_request": total_ms >= self.slow_request_ms,
            },
        )
        return response

    async def preview_attendance(self, request: AttendancePreviewRequest) -> RecognitionResponse:
        recognition_request = RecognitionRequest(device_code=request.device_code, frames=request.frames, session_code=None)
        response = await self._recognize_preview_only(recognition_request)
        if response.recognition_status != "recognized" or response.person is None:
            return response

        person = await self._person_summary(response.person.person_id, response.person.template_id)
        if person is not None:
            response.person = person
        resolution, resolved_session, _matches = await self._resolve_session_for_person(response.person)
        response.session_resolution = resolution
        response.resolved_session = resolved_session
        if resolved_session is not None:
            response.session_code = resolved_session.session_code
            return response
        if resolution == "multiple_matching_sessions":
            response.decision = "rejected"
            response.reason = "multiple_matching_sessions"
            response.recognition_status = "multiple_matching_sessions"
        else:
            response.decision = "rejected"
            response.reason = "no_matching_session"
            response.recognition_status = "no_matching_session"
        response.session_code = None
        return response

    async def confirm_attendance(self, request: AttendanceConfirmRequest) -> AttendanceConfirmResponse:
        device = await self.device_repository.get_by_code(request.device_code)
        if device is None or not device.is_enabled:
            raise LookupError(f"Data perangkat tidak ditemukan untuk {request.device_code}.")
        person = await self._person_summary(request.person_id, None)
        if person is None:
            raise LookupError("Mahasiswa tidak ditemukan.")
        if person.template_id is None:
            raise ValueError("Wajah mahasiswa belum terdaftar.")
        session_record = await self.attendance_repository.get_session(request.session_code)
        if session_record is None:
            raise LookupError("Sesi absensi tidak ditemukan.")
        availability_reason = self.attendance_repository.availability_reason(session_record, now=datetime.now(timezone.utc))
        if availability_reason is not None:
            raise ValueError("Sesi absensi tidak aktif untuk waktu saat ini.")
        if session_record.class_id is None or person.class_id is None or session_record.class_id != person.class_id:
            raise ValueError("Tidak ada sesi absensi yang sesuai untuk kelas dan waktu saat ini.")

        resolved_session = await self._resolved_session_from_record(session_record)
        cooldown_remaining = await self._cooldown_remaining(request.session_code, request.person_id)
        if cooldown_remaining > 0:
            return AttendanceConfirmResponse(
                decision="rejected",
                reason="cooldown",
                device_code=request.device_code,
                confidence=request.confidence,
                cooldown_remaining_seconds=cooldown_remaining,
                person=person,
                resolved_session=resolved_session,
            )

        captured_image_uri = await self._store_confirmed_attendance_image(request)
        log = await self.attendance_repository.add_log(
            AttendanceLog(
                session_id=session_record.id,
                person_id=request.person_id,
                matched_template_id=person.template_id,
                device_code=request.device_code,
                event_type="checkin",
                decision="accepted",
                reason="confirmed_by_user",
                confidence=request.confidence,
                liveness_score=None,
                captured_image_uri=captured_image_uri,
                frame_count=0,
                payload_json={
                    "confirmed_by_user": True,
                    "recognition_token": request.recognition_token,
                    "auto_resolved_session": resolved_session.model_dump(mode="json") if resolved_session else None,
                },
            )
        )
        if self.cache is not None:
            await self.cache.set_cooldown(request.session_code, request.person_id, session_record.cooldown_seconds)
            await self.cache.set_recent_match(
                request.device_code,
                {"student_id": person.student_id, "person_id": str(person.person_id), "confidence": request.confidence},
            )
        await self.session.commit()
        await self.session.refresh(log)
        return AttendanceConfirmResponse(
            decision="accepted",
            reason="confirmed_by_user",
            device_code=request.device_code,
            confidence=request.confidence,
            cooldown_remaining_seconds=session_record.cooldown_seconds,
            person=person,
            resolved_session=resolved_session,
            attendance=AttendanceRecordRead(
                log_id=log.id,
                student_id=person.student_id,
                full_name=person.full_name,
                email=person.email,
                class_id=person.class_id,
                class_name=person.class_name,
                session_code=session_record.session_code,
                session_name=session_record.session_name,
                lecturer_name=resolved_session.lecturer_name if resolved_session else None,
                decision=log.decision,
                status="Hadir",
                confidence=log.confidence,
                device_code=log.device_code,
                created_at=log.created_at,
            ),
        )

    async def _recognize_preview_only(self, request: RecognitionRequest) -> RecognitionResponse:
        started_at = perf_counter()
        device = await self.device_repository.get_by_code(request.device_code)
        if device is None or not device.is_enabled:
            raise LookupError(f"device config not found for {request.device_code}")
        processing_started_at = perf_counter()
        processed_frames = [await self.frame_processor.process(frame_input, device) for frame_input in request.frames]
        frame_processing_ms = (perf_counter() - processing_started_at) * 1000.0
        frame_decisions: list[RecognitionFrameDecision] = [item.decision for item in processed_frames]
        candidate_rows = [candidate for item in processed_frames for candidate in item.candidates]
        decision_started_at = perf_counter()
        response, person_id, _template_id = await self.decision_engine.decide(
            request=request,
            frame_decisions=frame_decisions,
            candidate_rows=candidate_rows,
            multi_frame_confirm=device.multi_frame_confirm,
            cooldown_seconds=device.cooldown_seconds,
            similarity_threshold=device.similarity_threshold,
            candidate_margin_threshold=device.candidate_margin_threshold,
        )
        decision_ms = (perf_counter() - decision_started_at) * 1000.0
        captured_face_jpeg = self._lazy_face_crop(processed_frames)
        if captured_face_jpeg is not None and response.recognition_status in {"recognized", "cooldown"}:
            response.captured_face_b64 = base64.b64encode(captured_face_jpeg).decode("ascii")
        LOGGER.info(
            "attendance_preview_completed",
            extra={
                "device_code": request.device_code,
                "decision": response.decision,
                "recognition_status": response.recognition_status,
                "reason": response.reason,
                "person_id": person_id,
                "frame_processing_ms": round(frame_processing_ms, 2),
                "decision_ms": round(decision_ms, 2),
                "total_request_ms": round((perf_counter() - started_at) * 1000.0, 2),
            },
        )
        return response

    @staticmethod
    def _lazy_face_crop(processed_frames: list[object]) -> bytes | None:
        for pf in processed_frames:
            frame = getattr(pf, "frame", None)
            bbox = getattr(pf, "face_bbox", None)
            if frame is not None and bbox is not None:
                try:
                    from services.recognition.face_crop import crop_face_jpeg
                    return crop_face_jpeg(frame, bbox)
                except Exception:
                    LOGGER.exception("lazy_face_crop_failed")
                    return None
        return None

    async def _store_attendance_image(
        self,
        request: RecognitionRequest,
        response: RecognitionResponse,
        event_type: str,
        captured_face_jpeg: bytes | None,
    ) -> str | None:
        if self.object_storage is None or event_type != "checkin" or response.recognition_status not in {"recognized", "cooldown"}:
            return None
        if not captured_face_jpeg:
            return None
        try:
            object_key = f"attendance/{request.session_code or 'no-session'}/{request.device_code}/{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}.jpg"
            return await self.object_storage.put_bytes(object_key, captured_face_jpeg)
        except Exception:
            LOGGER.exception("attendance_capture_store_failed", extra={"device_code": request.device_code, "session_code": request.session_code})
            return None

    async def _resolve_session(self, session_code: str | None, require_session: bool) -> object | None:
        session_record = await self.attendance_repository.get_session(session_code) if session_code else None
        if require_session and session_record is None:
            raise LookupError(f"attendance session {session_code} not found")
        return session_record

    async def _person_summary(self, person_id: UUID, template_id: UUID | None) -> PersonSummary | None:
        result = await self.session.execute(
            select(Person, ClassGroup)
            .outerjoin(ClassGroup, ClassGroup.id == Person.class_id)
            .where(Person.id == person_id, Person.is_active.is_(True), Person.is_deleted.is_(False))
        )
        row = result.one_or_none()
        if row is None:
            return None
        person, class_group = row
        active_template_id = template_id
        if active_template_id is None and person.primary_template_id is not None:
            template_result = await self.session.execute(
                select(FaceTemplate.id).where(
                    FaceTemplate.id == person.primary_template_id,
                    FaceTemplate.person_id == person.id,
                    FaceTemplate.is_active.is_(True),
                    FaceTemplate.deleted_at.is_(None),
                )
            )
            active_template_id = template_result.scalar_one_or_none()
        return PersonSummary(
            person_id=person.id,
            student_id=person.student_id,
            full_name=person.full_name,
            email=person.email,
            class_id=person.class_id,
            class_code=class_group.class_code if class_group else None,
            class_name=class_group.class_name if class_group else None,
            template_id=active_template_id,
        )

    async def _resolve_session_for_person(
        self,
        person: PersonSummary,
    ) -> tuple[str, ResolvedAttendanceSession | None, list[ResolvedAttendanceSession]]:
        if person.class_id is None:
            return "no_matching_session", None, []
        projections = await self.attendance_repository.list_available_session_projections_for_class(person.class_id, datetime.now(timezone.utc))
        matches = [self._resolved_session_from_projection(projection) for projection in projections]
        if len(matches) == 1:
            return "resolved", matches[0], matches
        if not matches:
            return "no_matching_session", None, []
        return "multiple_matching_sessions", None, matches

    async def _resolved_session_from_record(self, session_record: AttendanceSession) -> ResolvedAttendanceSession | None:
        projection = await self.attendance_repository.get_session_projection(session_record.id)
        if projection is None:
            return None
        return self._resolved_session_from_projection(projection)

    @staticmethod
    def _resolved_session_from_projection(projection) -> ResolvedAttendanceSession:
        return ResolvedAttendanceSession(
            session_id=projection.session.id,
            session_code=projection.session.session_code,
            session_name=projection.session.session_name,
            class_id=projection.session.class_id,
            class_name=projection.class_name,
            lecturer_id=projection.session.lecturer_id,
            lecturer_name=projection.lecturer_name,
            start_time=projection.session.starts_at,
            end_time=projection.session.ends_at,
        )

    async def _cooldown_remaining(self, session_code: str, person_id: UUID) -> int:
        if self.cache is None:
            return 0
        ttl = await self.cache.cooldown_ttl_seconds(session_code, person_id)
        return ttl if ttl is not None else 0

    async def _store_confirmed_attendance_image(self, request: AttendanceConfirmRequest) -> str | None:
        if self.object_storage is None or not request.captured_face_b64_or_uri:
            return None
        payload = request.captured_face_b64_or_uri
        if payload.startswith(("data:image/jpeg;base64,", "data:image/png;base64,")):
            payload = payload.split(",", maxsplit=1)[1]
        try:
            image_bytes = base64.b64decode(payload, validate=True)
        except (binascii.Error, ValueError):
            return None
        if not image_bytes:
            return None
        try:
            object_key = f"attendance/{request.session_code}/{request.device_code}/{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}.jpg"
            return await self.object_storage.put_bytes(object_key, image_bytes)
        except Exception:
            LOGGER.exception("attendance_confirm_capture_store_failed", extra={"device_code": request.device_code, "session_code": request.session_code})
            return None
