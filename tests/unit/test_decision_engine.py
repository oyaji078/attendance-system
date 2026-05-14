from __future__ import annotations

import asyncio
from uuid import uuid4

from db.repositories.face_templates import TemplateMatch
from db.schemas.recognition import RecognitionRequest
from services.recognition.decision_engine import MultiFrameDecisionEngine
from services.recognition.types import QualityResult, RecognitionFrameDecision


class FakeCache:
    def __init__(self) -> None:
        self.cooldowns: dict[tuple[str, str], int] = {}
        self.recent_matches = []

    async def cooldown_ttl_seconds(self, session_code, person_id) -> int | None:
        return self.cooldowns.get((session_code, person_id))

    async def set_cooldown(self, session_code, person_id, seconds) -> None:
        self.cooldowns[(session_code, person_id)] = seconds

    async def set_recent_match(self, device_code, payload) -> None:
        self.recent_matches.append((device_code, payload))


def accepted_quality() -> QualityResult:
    return QualityResult(
        brightness_score=100.0,
        blur_score=120.0,
        contrast_score=45.0,
        overexposed_ratio=0.02,
        underexposed_ratio=0.01,
        liveness_score=0.91,
        face_width_px=180,
        face_center_offset_x=0.01,
        face_center_offset_y=0.01,
        pose_yaw=0.0,
        pose_pitch=0.0,
        pose_roll=0.0,
        pose_valid=True,
        accepted=True,
        reason="accepted",
        ui_hint="accepted",
        flags={"exactly_one_face": True},
    )


def rejected_quality(reason: str, face_width_px: int = 118) -> QualityResult:
    return QualityResult(
        brightness_score=100.0,
        blur_score=120.0,
        contrast_score=45.0,
        overexposed_ratio=0.02,
        underexposed_ratio=0.01,
        liveness_score=0.91,
        face_width_px=face_width_px,
        face_center_offset_x=0.01,
        face_center_offset_y=0.01,
        pose_yaw=0.0,
        pose_pitch=0.0,
        pose_roll=0.0,
        pose_valid=True,
        accepted=False,
        reason=reason,
        ui_hint=reason,
        flags={"exactly_one_face": True, "min_face_width": False},
        face_count=1,
        max_faces=1,
        min_face_width_px=160,
        min_blur_score=90.0,
        min_brightness=45.0,
        liveness_threshold=0.6,
        quality_mode="normal",
    )


def test_decision_engine_recognizes_and_sets_cooldown() -> None:
    cache = FakeCache()
    engine = MultiFrameDecisionEngine(cache)
    person_id = uuid4()
    template_id = uuid4()
    request = RecognitionRequest(device_code="gate-a01", session_code="morning-gate", frames=[{"frame_b64": "ZmFrZS1mcmFtZS1ieXRlcy1mYWtlLWZyYW1lLWJ5dGVz", "pose_hint": None}] * 3)
    frame_decisions = [
        RecognitionFrameDecision(True, "match_candidate", person_id, template_id, "ST-1001", "Ada Lovelace", 0.12, 0.88, accepted_quality()),
        RecognitionFrameDecision(True, "match_candidate", person_id, template_id, "ST-1001", "Ada Lovelace", 0.14, 0.86, accepted_quality()),
        RecognitionFrameDecision(True, "distance_above_threshold", None, None, None, None, 0.61, 0.39, accepted_quality()),
    ]
    candidates = [
        TemplateMatch(template_id=template_id, person_id=person_id, student_id="ST-1001", full_name="Ada Lovelace", class_code=None, class_name=None, distance=0.12),
        TemplateMatch(template_id=template_id, person_id=person_id, student_id="ST-1001", full_name="Ada Lovelace", class_code=None, class_name=None, distance=0.14),
    ]
    response, matched_person_id, matched_template_id = asyncio.run(
        engine.decide(request, frame_decisions, candidates, multi_frame_confirm=2, cooldown_seconds=30)
    )
    assert response.decision == "accepted"
    assert response.recognition_status == "recognized"
    assert matched_person_id == person_id
    assert matched_template_id == template_id
    assert len(cache.recent_matches) == 1
    assert ("morning-gate", person_id) in cache.cooldowns
    assert cache.cooldowns[("morning-gate", person_id)] == 30


def test_decision_engine_returns_cooldown_when_person_already_cached() -> None:
    cache = FakeCache()
    engine = MultiFrameDecisionEngine(cache)
    person_id = uuid4()
    template_id = uuid4()
    cache.cooldowns[("morning-gate", person_id)] = 30
    request = RecognitionRequest(device_code="gate-a01", session_code="morning-gate", frames=[{"frame_b64": "ZmFrZS1mcmFtZS1ieXRlcy1mYWtlLWZyYW1lLWJ5dGVz", "pose_hint": None}] * 3)
    frame_decisions = [
        RecognitionFrameDecision(True, "match_candidate", person_id, template_id, "ST-1001", "Ada Lovelace", 0.12, 0.88, accepted_quality()),
        RecognitionFrameDecision(True, "match_candidate", person_id, template_id, "ST-1001", "Ada Lovelace", 0.13, 0.87, accepted_quality()),
    ]
    response, _, _ = asyncio.run(engine.decide(request, frame_decisions, [], multi_frame_confirm=2, cooldown_seconds=30))
    assert response.decision == "rejected"
    assert response.recognition_status == "cooldown"
    assert response.reason == "cooldown"
    assert response.cooldown_remaining_seconds == 30


def test_decision_engine_rejects_close_candidate_margin() -> None:
    cache = FakeCache()
    engine = MultiFrameDecisionEngine(cache, candidate_margin_threshold=0.05)
    person_id = uuid4()
    template_id = uuid4()
    other_person_id = uuid4()
    other_template_id = uuid4()
    request = RecognitionRequest(device_code="gate-a01", session_code="morning-gate", frames=[{"frame_b64": "ZmFrZS1mcmFtZS1ieXRlcy1mYWtlLWZyYW1lLWJ5dGVz", "pose_hint": None}] * 3)
    frame_decisions = [
        RecognitionFrameDecision(True, "match_candidate", person_id, template_id, "001", "IRLAND", 0.118409, 0.881591, accepted_quality()),
        RecognitionFrameDecision(True, "match_candidate", person_id, template_id, "001", "IRLAND", 0.118409, 0.881591, accepted_quality()),
        RecognitionFrameDecision(True, "match_candidate", person_id, template_id, "001", "IRLAND", 0.118409, 0.881591, accepted_quality()),
    ]
    candidates = [
        TemplateMatch(template_id=template_id, person_id=person_id, student_id="001", full_name="IRLAND", class_code="TIA", class_name="TI A", distance=0.118409),
        TemplateMatch(template_id=other_template_id, person_id=other_person_id, student_id="st002", full_name="ojik", class_code="TIA", class_name="TI A", distance=0.140835),
    ]

    response, matched_person_id, matched_template_id = asyncio.run(
        engine.decide(
            request,
            frame_decisions,
            candidates,
            multi_frame_confirm=3,
            cooldown_seconds=30,
            similarity_threshold=0.45,
        )
    )

    assert response.decision == "rejected"
    assert response.reason == "candidate_margin_too_small"
    assert matched_person_id is None
    assert matched_template_id is None
    assert response.top1_distance == 0.118409
    assert response.top2_distance == 0.140835
    assert response.candidate_margin is not None
    assert response.candidate_margin < 0.05
    assert response.margin_threshold == 0.05
    assert response.required_confirmed_frames == 3


def test_decision_engine_exposes_quality_summary_when_all_frames_rejected() -> None:
    cache = FakeCache()
    engine = MultiFrameDecisionEngine(cache)
    request = RecognitionRequest(
        device_code="web-kiosk-a01",
        session_code="VAL-071657",
        frames=[{"frame_b64": "ZmFrZS1mcmFtZS1ieXRlcy1mYWtlLWZyYW1lLWJ5dGVz", "pose_hint": None}] * 3,
    )
    frame_decisions = [
        RecognitionFrameDecision(False, "face_too_small", None, None, None, None, None, None, rejected_quality("face_too_small", 118)),
        RecognitionFrameDecision(False, "face_too_small", None, None, None, None, None, None, rejected_quality("face_too_small", 115)),
        RecognitionFrameDecision(False, "face_too_small", None, None, None, None, None, None, rejected_quality("face_too_small", 115)),
    ]

    response, matched_person_id, matched_template_id = asyncio.run(
        engine.decide(
            request,
            frame_decisions,
            [],
            multi_frame_confirm=3,
            cooldown_seconds=30,
            similarity_threshold=0.45,
        )
    )

    assert response.decision == "rejected"
    assert response.reason == "all_frames_rejected"
    assert matched_person_id is None
    assert matched_template_id is None
    assert response.quality_summary is not None
    assert response.quality_summary.dominant_reason == "face_too_small"
    assert response.quality_summary.reason_counts == {"face_too_small": 3}
    assert response.quality_summary.accepted_frames == 0
    assert response.quality_summary.rejected_frames == 3
    assert response.quality_summary.quality_mode == "normal"
    assert response.quality_summary.frames[0].face_width_px == 118
    assert response.quality_summary.frames[0].min_face_width_px == 160
    assert response.quality_summary.frames[0].face_count == 1
