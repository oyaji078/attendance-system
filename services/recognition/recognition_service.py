from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from db.repositories.attendance import AttendanceRepository
from db.repositories.device_configs import DeviceConfigRepository
from db.schemas.recognition import RecognitionRequest, RecognitionResponse
from services.recognition.decision_engine import MultiFrameDecisionEngine
from services.recognition.frame_processor import RecognitionFrameProcessor
from services.recognition.logger import RecognitionAuditLogger

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
    ) -> None:
        self.session = session
        self.device_repository = device_repository
        self.attendance_repository = attendance_repository
        self.frame_processor = frame_processor
        self.decision_engine = decision_engine
        self.audit_logger = audit_logger

    async def recognize(self, request: RecognitionRequest, event_type: str, require_session: bool = False) -> RecognitionResponse:
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
                decision="session_inactive",
                reason=availability_reason,
                confirmed_frames=0,
                device_code=request.device_code,
                session_code=request.session_code,
            )
            await self.audit_logger.log(response, request, None, None, event_type, frame_decisions=[])
            await self.session.commit()
            return response

        processed_frames = [await self.frame_processor.process(frame_input, device) for frame_input in request.frames]
        frame_decisions = [item.decision for item in processed_frames]
        candidate_rows = [candidate for item in processed_frames for candidate in item.candidates]
        response, person_id, template_id = await self.decision_engine.decide(
            request=request,
            frame_decisions=frame_decisions,
            candidate_rows=candidate_rows,
            multi_frame_confirm=device.multi_frame_confirm,
            cooldown_seconds=device.cooldown_seconds if session_record is None else session_record.cooldown_seconds,
        )
        await self.audit_logger.log(response, request, person_id, template_id, event_type, frame_decisions=frame_decisions)
        await self.session.commit()
        LOGGER.info(
            "recognition_completed",
            extra={
                "device_code": request.device_code,
                "decision": response.decision,
                "reason": response.reason,
                "person_id": person_id,
            },
        )
        return response

    async def _resolve_session(self, session_code: str | None, require_session: bool) -> object | None:
        session_record = await self.attendance_repository.get_session(session_code) if session_code else None
        if require_session and session_record is None:
            raise LookupError(f"attendance session {session_code} not found")
        return session_record
