from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean
from uuid import UUID

from db.repositories.face_templates import TemplateMatch
from db.schemas.common import PersonSummary
from db.schemas.recognition import CandidateSummary, RecognitionRequest, RecognitionResponse
from services.attendance.cache import RedisStateCache
from services.recognition.types import RecognitionFrameDecision


class MultiFrameDecisionEngine:
    def __init__(self, cache: RedisStateCache) -> None:
        self.cache = cache

    async def decide(
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
            return (
                RecognitionResponse(
                    decision="rejected" if reason == "all_frames_rejected" else "unknown",
                    reason=reason,
                    confirmed_frames=0,
                    device_code=request.device_code,
                    session_code=request.session_code,
                    top_candidates=top_candidates,
                ),
                None,
                None,
            )
        matched_person_id, confirmed_frames = counts.most_common(1)[0]
        agreeing_frames = [item for item in successful if item.matched_person_id == matched_person_id]
        if confirmed_frames < multi_frame_confirm:
            return (
                RecognitionResponse(
                    decision="unknown",
                    reason="multi_frame_confirm_failed",
                    confirmed_frames=confirmed_frames,
                    device_code=request.device_code,
                    session_code=request.session_code,
                    top_candidates=top_candidates,
                ),
                None,
                None,
            )
        reference_frame = agreeing_frames[0]
        confidence = float(mean(item.confidence or 0.0 for item in agreeing_frames))
        person = PersonSummary(
            person_id=reference_frame.matched_person_id,
            student_id=reference_frame.student_id or "",
            full_name=reference_frame.full_name or "",
            template_id=reference_frame.matched_template_id,
        )
        if request.session_code and await self.cache.is_on_cooldown(request.session_code, reference_frame.matched_person_id):
            return (
                RecognitionResponse(
                    decision="cooldown",
                    reason="person_on_cooldown",
                    confirmed_frames=confirmed_frames,
                    device_code=request.device_code,
                    session_code=request.session_code,
                    person=person,
                    confidence=confidence,
                    top_candidates=top_candidates,
                ),
                reference_frame.matched_person_id,
                reference_frame.matched_template_id,
            )
        if request.session_code:
            await self.cache.set_cooldown(request.session_code, reference_frame.matched_person_id, cooldown_seconds)
        await self.cache.set_recent_match(
            request.device_code,
            {"student_id": person.student_id, "person_id": str(person.person_id), "confidence": confidence},
        )
        return (
            RecognitionResponse(
                decision="recognized",
                reason="multi_frame_confirm_passed",
                confirmed_frames=confirmed_frames,
                device_code=request.device_code,
                session_code=request.session_code,
                person=person,
                confidence=confidence,
                top_candidates=top_candidates,
            ),
            reference_frame.matched_person_id,
            reference_frame.matched_template_id,
        )

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
