from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from statistics import mean
from uuid import UUID

from db.models.entities import AttendanceLog
from db.repositories.attendance import AttendanceRepository
from db.schemas.recognition import RecognitionRequest, RecognitionResponse
from services.recognition.types import RecognitionFrameDecision


class RecognitionAuditLogger:
    def __init__(self, attendance_repository: AttendanceRepository) -> None:
        self.attendance_repository = attendance_repository

    async def log(
        self,
        response: RecognitionResponse,
        request: RecognitionRequest,
        person_id: UUID | None,
        template_id: UUID | None,
        event_type: str,
        frame_decisions: list[RecognitionFrameDecision],
    ) -> None:
        session_record = await self.attendance_repository.get_session(request.session_code) if request.session_code else None
        await self.attendance_repository.add_log(
            AttendanceLog(
                session_id=session_record.id if session_record else None,
                person_id=person_id,
                matched_template_id=template_id,
                device_code=request.device_code,
                event_type=event_type,
                decision=response.decision,
                reason=response.reason,
                confidence=response.confidence,
                liveness_score=self._mean_liveness(frame_decisions),
                frame_count=len(request.frames),
                payload_json={
                    "top_candidates": [item.model_dump(mode="json") for item in response.top_candidates],
                    "frame_decisions": [self._jsonable(asdict(item)) for item in frame_decisions],
                    "quality_summary": self._quality_summary(frame_decisions),
                },
            )
        )

    @staticmethod
    def _mean_liveness(frame_decisions: list[RecognitionFrameDecision]) -> float | None:
        if not frame_decisions:
            return None
        return float(mean(item.quality.liveness_score for item in frame_decisions))

    @classmethod
    def _quality_summary(cls, frame_decisions: list[RecognitionFrameDecision]) -> dict[str, object]:
        if not frame_decisions:
            return {"accepted_frames": 0, "rejected_frames": 0, "reasons": {}}
        reasons = Counter(item.reason for item in frame_decisions)
        return {
            "accepted_frames": sum(1 for item in frame_decisions if item.quality.accepted),
            "rejected_frames": sum(1 for item in frame_decisions if not item.quality.accepted),
            "reasons": dict(reasons),
            "mean_liveness_score": cls._mean_liveness(frame_decisions),
        }

    @classmethod
    def _jsonable(cls, value: object) -> object:
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, list):
            return [cls._jsonable(item) for item in value]
        if isinstance(value, dict):
            return {key: cls._jsonable(item) for key, item in value.items()}
        return value
