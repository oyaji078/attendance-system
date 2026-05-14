from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean
from uuid import UUID

from db.repositories.face_templates import TemplateMatch
from db.schemas.common import PersonSummary
from db.schemas.recognition import CandidateSummary, QualitySummary, RecognitionRequest, RecognitionResponse
from services.attendance.cache import RedisStateCache
from services.recognition.types import RecognitionFrameDecision


class MultiFrameDecisionEngine:
    def __init__(self, cache: RedisStateCache, confidence_threshold: float = 0.55, candidate_margin_threshold: float = 0.05) -> None:
        self.cache = cache
        self.confidence_threshold = confidence_threshold
        self.candidate_margin_threshold = candidate_margin_threshold

    async def decide(
        self,
        request: RecognitionRequest,
        frame_decisions: list[RecognitionFrameDecision],
        candidate_rows: list[TemplateMatch],
        multi_frame_confirm: int,
        cooldown_seconds: int,
        similarity_threshold: float | None = None,
        candidate_margin_threshold: float | None = None,
    ) -> tuple[RecognitionResponse, UUID | None, UUID | None]:
        successful = [item for item in frame_decisions if item.matched_person_id is not None]
        counts = Counter(item.matched_person_id for item in successful)
        top_candidates = self._candidate_summaries(candidate_rows)
        margin_threshold = candidate_margin_threshold if candidate_margin_threshold is not None else self.candidate_margin_threshold
        diagnostics = self._diagnostics(top_candidates, similarity_threshold, multi_frame_confirm, margin_threshold)
        quality_summary = self._quality_summary(frame_decisions)
        if not counts:
            reason = "all_frames_rejected" if all(not item.quality.accepted for item in frame_decisions) else "no_match_within_threshold"
            return (
                RecognitionResponse(
                    decision="rejected",
                    reason=reason,
                    recognition_status="rejected" if reason == "all_frames_rejected" else "unknown",
                    confirmed_frames=0,
                    device_code=request.device_code,
                    session_code=request.session_code,
                    top_candidates=top_candidates,
                    quality_summary=quality_summary,
                    **diagnostics,
                ),
                None,
                None,
            )
        matched_person_id, confirmed_frames = counts.most_common(1)[0]
        agreeing_frames = [item for item in successful if item.matched_person_id == matched_person_id]
        if confirmed_frames < multi_frame_confirm:
            return (
                RecognitionResponse(
                    decision="rejected",
                    reason="multi_frame_confirm_failed",
                    recognition_status="unknown",
                    confirmed_frames=confirmed_frames,
                    device_code=request.device_code,
                    session_code=request.session_code,
                    top_candidates=top_candidates,
                    quality_summary=quality_summary,
                    **diagnostics,
                ),
                None,
                None,
            )
        reference_frame = agreeing_frames[0]
        confidence = float(mean(item.confidence or 0.0 for item in agreeing_frames))
        if confidence < self.confidence_threshold:
            return (
                RecognitionResponse(
                    decision="rejected",
                    reason="confidence_below_threshold",
                    recognition_status="unknown",
                    confirmed_frames=confirmed_frames,
                    device_code=request.device_code,
                    session_code=request.session_code,
                    confidence=confidence,
                    top_candidates=top_candidates,
                    quality_summary=quality_summary,
                    **diagnostics,
                ),
                None,
                None,
            )
        if diagnostics["candidate_margin"] is not None and diagnostics["candidate_margin"] < margin_threshold:
            return (
                RecognitionResponse(
                    decision="rejected",
                    reason="candidate_margin_too_small",
                    recognition_status="unknown",
                    confirmed_frames=confirmed_frames,
                    device_code=request.device_code,
                    session_code=request.session_code,
                    confidence=confidence,
                    top_candidates=top_candidates,
                    quality_summary=quality_summary,
                    **diagnostics,
                ),
                None,
                None,
            )
        person = PersonSummary(
            person_id=reference_frame.matched_person_id,
            student_id=reference_frame.student_id or "",
            full_name=reference_frame.full_name or "",
            email=top_candidates[0].email if top_candidates else None,
            class_id=top_candidates[0].class_id if top_candidates else None,
            class_code=top_candidates[0].class_code if top_candidates else None,
            class_name=top_candidates[0].class_name if top_candidates else None,
            template_id=reference_frame.matched_template_id,
        )
        if request.session_code and reference_frame.matched_person_id:
            cooldown_remaining_seconds = await self.cache.cooldown_ttl_seconds(request.session_code, reference_frame.matched_person_id)
            if cooldown_remaining_seconds is not None and cooldown_remaining_seconds > 0:
                return (
                    RecognitionResponse(
                        decision="rejected",
                        reason="cooldown",
                        recognition_status="cooldown",
                        confirmed_frames=confirmed_frames,
                        device_code=request.device_code,
                        session_code=request.session_code,
                        person=person,
                        confidence=confidence,
                        top_candidates=top_candidates,
                        cooldown_remaining_seconds=cooldown_remaining_seconds,
                        quality_summary=quality_summary,
                        **diagnostics,
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
                decision="accepted",
                reason="multi_frame_confirm_passed",
                recognition_status="recognized",
                confirmed_frames=confirmed_frames,
                device_code=request.device_code,
                session_code=request.session_code,
                person=person,
                confidence=confidence,
                top_candidates=top_candidates,
                cooldown_remaining_seconds=cooldown_seconds if request.session_code else None,
                quality_summary=quality_summary,
                **diagnostics,
            ),
            reference_frame.matched_person_id,
            reference_frame.matched_template_id,
        )

    def _diagnostics(
        self,
        top_candidates: list[CandidateSummary],
        similarity_threshold: float | None,
        required_confirmed_frames: int,
        margin_threshold: float,
    ) -> dict[str, float | int | None]:
        top1_distance = top_candidates[0].distance if len(top_candidates) >= 1 else None
        top2_distance = top_candidates[1].distance if len(top_candidates) >= 2 else None
        candidate_margin = top2_distance - top1_distance if top1_distance is not None and top2_distance is not None else None
        return {
            "top1_distance": top1_distance,
            "top2_distance": top2_distance,
            "candidate_margin": candidate_margin,
            "similarity_threshold": similarity_threshold,
            "confidence_threshold": self.confidence_threshold,
            "margin_threshold": margin_threshold,
            "required_confirmed_frames": required_confirmed_frames,
        }

    @staticmethod
    def _quality_summary(frame_decisions: list[RecognitionFrameDecision]) -> QualitySummary | None:
        if not frame_decisions:
            return None
        reason_counts = Counter(item.quality.reason for item in frame_decisions)
        rejected_counts = Counter(item.quality.reason for item in frame_decisions if not item.quality.accepted)
        dominant_reason = rejected_counts.most_common(1)[0][0] if rejected_counts else None
        liveness_values = [item.quality.liveness_score for item in frame_decisions]
        quality_mode = next((item.quality.quality_mode for item in frame_decisions if item.quality.quality_mode), None)
        return QualitySummary(
            dominant_reason=dominant_reason,
            reason_counts=dict(reason_counts),
            reasons=dict(reason_counts),
            accepted_frames=sum(1 for item in frame_decisions if item.quality.accepted),
            rejected_frames=sum(1 for item in frame_decisions if not item.quality.accepted),
            mean_liveness_score=float(mean(liveness_values)) if liveness_values else None,
            quality_mode=quality_mode,
            frames=[
                {
                    "index": index,
                    "accepted": item.quality.accepted,
                    "reason": item.quality.reason,
                    "face_bbox": item.quality.face_bbox,
                    "face_box_normalized": item.quality.face_box_normalized,
                    "face_center": item.quality.face_center,
                    "face_size_ratio": item.quality.face_size_ratio,
                    "face_width_px": item.quality.face_width_px,
                    "min_face_width_px": item.quality.min_face_width_px,
                    "face_count": item.quality.face_count,
                    "max_faces": item.quality.max_faces,
                    "blur_score": item.quality.blur_score,
                    "min_blur_score": item.quality.min_blur_score,
                    "brightness_score": item.quality.brightness_score,
                    "min_brightness": item.quality.min_brightness,
                    "contrast_score": item.quality.contrast_score,
                    "min_contrast": item.quality.min_contrast,
                    "liveness_score": item.quality.liveness_score,
                    "liveness_threshold": item.quality.liveness_threshold,
                    "face_center_offset_x": item.quality.face_center_offset_x,
                    "face_center_offset_y": item.quality.face_center_offset_y,
                    "max_face_center_offset": item.quality.max_face_center_offset,
                    "overexposed_ratio": item.quality.overexposed_ratio,
                    "max_overexposed_ratio": item.quality.max_overexposed_ratio,
                    "underexposed_ratio": item.quality.underexposed_ratio,
                    "max_underexposed_ratio": item.quality.max_underexposed_ratio,
                    "flags": item.quality.flags,
                }
                for index, item in enumerate(frame_decisions, start=1)
            ],
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
                    email=candidate.email,
                    class_id=candidate.class_id,
                    class_code=candidate.class_code,
                    class_name=candidate.class_name,
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
