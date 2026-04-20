from __future__ import annotations

import asyncio
from uuid import uuid4

from db.repositories.face_templates import TemplateMatch
from db.schemas.recognition import RecognitionRequest
from services.recognition.decision_engine import MultiFrameDecisionEngine
from services.recognition.types import QualityResult, RecognitionFrameDecision


class FakeCache:
    def __init__(self) -> None:
        self.cooldowns = set()
        self.recent_matches = []

    async def is_on_cooldown(self, session_code, person_id) -> bool:
        return (session_code, person_id) in self.cooldowns

    async def set_cooldown(self, session_code, person_id, seconds) -> None:
        self.cooldowns.add((session_code, person_id))

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
        TemplateMatch(template_id=template_id, person_id=person_id, student_id="ST-1001", full_name="Ada Lovelace", distance=0.12),
        TemplateMatch(template_id=template_id, person_id=person_id, student_id="ST-1001", full_name="Ada Lovelace", distance=0.14),
    ]
    response, matched_person_id, matched_template_id = asyncio.run(
        engine.decide(request, frame_decisions, candidates, multi_frame_confirm=2, cooldown_seconds=30)
    )
    assert response.decision == "recognized"
    assert matched_person_id == person_id
    assert matched_template_id == template_id
    assert len(cache.recent_matches) == 1
    assert ("morning-gate", person_id) in cache.cooldowns


def test_decision_engine_returns_cooldown_when_person_already_cached() -> None:
    cache = FakeCache()
    engine = MultiFrameDecisionEngine(cache)
    person_id = uuid4()
    template_id = uuid4()
    cache.cooldowns.add(("morning-gate", person_id))
    request = RecognitionRequest(device_code="gate-a01", session_code="morning-gate", frames=[{"frame_b64": "ZmFrZS1mcmFtZS1ieXRlcy1mYWtlLWZyYW1lLWJ5dGVz", "pose_hint": None}] * 3)
    frame_decisions = [
        RecognitionFrameDecision(True, "match_candidate", person_id, template_id, "ST-1001", "Ada Lovelace", 0.12, 0.88, accepted_quality()),
        RecognitionFrameDecision(True, "match_candidate", person_id, template_id, "ST-1001", "Ada Lovelace", 0.13, 0.87, accepted_quality()),
    ]
    response, _, _ = asyncio.run(engine.decide(request, frame_decisions, [], multi_frame_confirm=2, cooldown_seconds=30))
    assert response.decision == "cooldown"
    assert response.reason == "person_on_cooldown"
