from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from statistics import mean
from uuid import UUID

from db.domain.attendance import normalize_attendance_decision, normalize_attendance_event_type, normalize_attendance_reason
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
        captured_image_uri: str | None = None,
    ) -> None:
        session_record = await self.attendance_repository.get_session(request.session_code) if request.session_code else None
        decision = normalize_attendance_decision(response.decision, response.reason)
        reason = normalize_attendance_reason(response.reason)
        await self.attendance_repository.add_log(
            AttendanceLog(
                session_id=session_record.id if session_record else None,
                person_id=person_id,
                matched_template_id=template_id,
                device_code=request.device_code,
                event_type=normalize_attendance_event_type(event_type),
                decision=decision,
                reason=reason,
                confidence=response.confidence,
                liveness_score=self._mean_liveness(frame_decisions),
                captured_image_uri=captured_image_uri,
                frame_count=len(request.frames),
                payload_json={
                    "top_candidates": [item.model_dump(mode="json") for item in response.top_candidates],
                    "matching_diagnostics": {
                        "top1_distance": response.top1_distance,
                        "top2_distance": response.top2_distance,
                        "candidate_margin": response.candidate_margin,
                        "similarity_threshold": response.similarity_threshold,
                        "confidence_threshold": response.confidence_threshold,
                        "margin_threshold": response.margin_threshold,
                        "required_confirmed_frames": response.required_confirmed_frames,
                    },
                    "recognition_status": response.recognition_status,
                    "recognition_decision": response.decision,
                    "frame_decisions": [self._jsonable(asdict(item)) for item in frame_decisions],
                    "quality_summary": (
                        response.quality_summary.model_dump(mode="json")
                        if response.quality_summary is not None
                        else self._quality_summary(frame_decisions)
                    ),
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
