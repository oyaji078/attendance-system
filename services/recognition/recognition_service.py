from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict
import logging
from statistics import mean
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from db.models.entities import AttendanceLog
from db.repositories.attendance import AttendanceRepository
from db.repositories.device_configs import DeviceConfigRepository
from db.repositories.face_templates import FaceTemplateRepository, TemplateMatch
from db.schemas.common import PersonSummary
from db.schemas.recognition import CandidateSummary, RecognitionRequest, RecognitionResponse
from services.attendance.cache import RedisStateCache
from services.liveness.service import HeuristicPassiveLivenessService
from services.quality.service import QualityGate
from services.recognition.frame_codec import decode_frame_b64
from services.recognition.pipeline import InsightFaceEmbeddingPipeline
from services.recognition.types import QualityResult, RecognitionFrameDecision

LOGGER = logging.getLogger(__name__)


class RecognitionService:
    def __init__(
        self,
        session: AsyncSession,
        device_repository: DeviceConfigRepository,
        template_repository: FaceTemplateRepository,
        attendance_repository: AttendanceRepository,
        cache: RedisStateCache,
        pipeline: InsightFaceEmbeddingPipeline,
        liveness_service: HeuristicPassiveLivenessService,
        quality_gate: QualityGate,
    ) -> None:
        self.session = session
        self.device_repository = device_repository
        self.template_repository = template_repository
        self.attendance_repository = attendance_repository
        self.cache = cache
        self.pipeline = pipeline
        self.liveness_service = liveness_service
        self.quality_gate = quality_gate

    async def recognize(self, request: RecognitionRequest, event_type: str, require_session: bool = False) -> RecognitionResponse:
        device = await self.device_repository.get_by_code(request.device_code)
        if device is None or not device.is_enabled:
            raise LookupError(f"device config not found for {request.device_code}")
        session_record = await self.attendance_repository.get_session(request.session_code) if request.session_code else None
        if require_session and session_record is None:
            raise LookupError(f"attendance session {request.session_code} not found")
        if session_record is not None and not session_record.is_active:
            response = RecognitionResponse(decision="session_inactive", reason="attendance_session_inactive", confirmed_frames=0, device_code=request.device_code, session_code=request.session_code)
            await self._log_decision(response, request, None, None, event_type)
            await self.session.commit()
            return response

        frame_decisions: list[RecognitionFrameDecision] = []
        candidate_rows: list[TemplateMatch] = []
        for frame_input in request.frames:
            analysis = await self.pipeline.analyze(
                frame_bytes=decode_frame_b64(frame_input.frame_b64),
                det_thresh=device.det_thresh,
                det_size=(device.det_size_width, device.det_size_height),
                max_faces=device.max_faces,
            )
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
                frame_decisions.append(self._rejected_frame(quality))
                continue
            candidates = await self.template_repository.search_active(analysis.faces[0].embedding, limit=3)
            candidate_rows.extend(candidates)
            frame_decisions.append(self._frame_match(candidates, quality, device.similarity_threshold))

        response, person_id, template_id = await self._aggregate(
            request=request,
            frame_decisions=frame_decisions,
            candidate_rows=candidate_rows,
            multi_frame_confirm=device.multi_frame_confirm,
            cooldown_seconds=device.cooldown_seconds if session_record is None else session_record.cooldown_seconds,
        )
        await self._log_decision(response, request, person_id, template_id, event_type, {"frame_decisions": [asdict(item) for item in frame_decisions]})
        await self.session.commit()
        LOGGER.info("recognition_completed", extra={"device_code": request.device_code, "decision": response.decision, "reason": response.reason, "person_id": person_id})
        return response

    async def _aggregate(
        self,
        request: RecognitionRequest,
        frame_decisions: list[RecognitionFrameDecision],
        candidate_rows: list[TemplateMatch],
        multi_frame_confirm: int,
        cooldown_seconds: int,
    ) -> tuple[RecognitionResponse, UUID | None, UUID | None]:
        successful = [item for item in frame_decisions if item.matched_person_id is not None]
        counts = Counter(item.matched_person_id for item in successful)
        top_candidates = self._candidate_summaries(candidate_rows)
        if not counts:
            reason = "all_frames_rejected" if all(not item.quality.accepted for item in frame_decisions) else "no_match_within_threshold"
            return RecognitionResponse(decision="rejected" if reason == "all_frames_rejected" else "unknown", reason=reason, confirmed_frames=0, device_code=request.device_code, session_code=request.session_code, top_candidates=top_candidates), None, None
        matched_person_id, confirmed_frames = counts.most_common(1)[0]
        agreeing_frames = [item for item in successful if item.matched_person_id == matched_person_id]
        if confirmed_frames < multi_frame_confirm:
            return RecognitionResponse(decision="unknown", reason="multi_frame_confirm_failed", confirmed_frames=confirmed_frames, device_code=request.device_code, session_code=request.session_code, top_candidates=top_candidates), None, None
        reference_frame = agreeing_frames[0]
        confidence = float(mean(item.confidence or 0.0 for item in agreeing_frames))
        person = PersonSummary(person_id=reference_frame.matched_person_id, student_id=reference_frame.student_id or "", full_name=reference_frame.full_name or "", template_id=reference_frame.matched_template_id)
        if request.session_code and await self.cache.is_on_cooldown(request.session_code, reference_frame.matched_person_id):
            return RecognitionResponse(decision="cooldown", reason="person_on_cooldown", confirmed_frames=confirmed_frames, device_code=request.device_code, session_code=request.session_code, person=person, confidence=confidence, top_candidates=top_candidates), reference_frame.matched_person_id, reference_frame.matched_template_id
        if request.session_code:
            await self.cache.set_cooldown(request.session_code, reference_frame.matched_person_id, cooldown_seconds)
        await self.cache.set_recent_match(request.device_code, {"student_id": person.student_id, "person_id": str(person.person_id), "confidence": confidence})
        return RecognitionResponse(decision="recognized", reason="multi_frame_confirm_passed", confirmed_frames=confirmed_frames, device_code=request.device_code, session_code=request.session_code, person=person, confidence=confidence, top_candidates=top_candidates), reference_frame.matched_person_id, reference_frame.matched_template_id

    async def _log_decision(self, response: RecognitionResponse, request: RecognitionRequest, person_id: UUID | None, template_id: UUID | None, event_type: str, frame_payload: dict[str, object] | None = None) -> None:
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
                liveness_score=None,
                frame_count=len(request.frames),
                payload_json={"top_candidates": [item.model_dump(mode="json") for item in response.top_candidates], "frame_payload": self._jsonable(frame_payload or {})},
            )
        )

    @staticmethod
    def _frame_match(candidates: list[TemplateMatch], quality: QualityResult, similarity_threshold: float) -> RecognitionFrameDecision:
        if not candidates:
            return RecognitionFrameDecision(True, "no_candidates", None, None, None, None, None, None, quality)
        top = candidates[0]
        if top.distance > similarity_threshold:
            return RecognitionFrameDecision(True, "distance_above_threshold", None, None, None, None, top.distance, max(0.0, 1.0 - top.distance), quality)
        return RecognitionFrameDecision(True, "match_candidate", top.person_id, top.template_id, top.student_id, top.full_name, top.distance, max(0.0, 1.0 - top.distance), quality)

    @staticmethod
    def _rejected_frame(quality: QualityResult) -> RecognitionFrameDecision:
        return RecognitionFrameDecision(False, quality.reason, None, None, None, None, None, None, quality)

    @staticmethod
    def _candidate_summaries(candidates: list[TemplateMatch]) -> list[CandidateSummary]:
        unique: dict[UUID, CandidateSummary] = {}
        grouped: defaultdict[UUID, list[float]] = defaultdict(list)
        for candidate in candidates:
            grouped[candidate.template_id].append(candidate.distance)
            unique.setdefault(
                candidate.template_id,
                CandidateSummary(
                    template_id=candidate.template_id,
                    person_id=candidate.person_id,
                    student_id=candidate.student_id,
                    full_name=candidate.full_name,
                    distance=candidate.distance,
                    confidence=max(0.0, 1.0 - candidate.distance),
                ),
            )
        summaries: list[CandidateSummary] = []
        for template_id, summary in unique.items():
            summary.distance = float(mean(grouped[template_id]))
            summary.confidence = max(0.0, 1.0 - summary.distance)
            summaries.append(summary)
        return sorted(summaries, key=lambda item: item.distance)[:3]

    @classmethod
    def _jsonable(cls, value: object) -> object:
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, list):
            return [cls._jsonable(item) for item in value]
        if isinstance(value, dict):
            return {key: cls._jsonable(item) for key, item in value.items()}
        return value

