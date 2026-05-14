from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from db.schemas.recognition import RecognitionResponse
from services.recognition.logger import RecognitionAuditLogger
from services.recognition.types import QualityResult, RecognitionFrameDecision


class FakeAttendanceRepository:
    def __init__(self) -> None:
        self.logs = []
        self.session = type("SessionRecord", (), {"id": uuid4()})()

    async def get_session(self, session_code):
        return self.session if session_code else None

    async def add_log(self, log):
        self.logs.append(log)
        return log


def build_quality(liveness_score: float, accepted: bool = True, reason: str = "accepted") -> QualityResult:
    return QualityResult(
        brightness_score=100.0,
        blur_score=120.0,
        contrast_score=45.0,
        overexposed_ratio=0.02,
        underexposed_ratio=0.01,
        liveness_score=liveness_score,
        face_width_px=180,
        face_center_offset_x=0.01,
        face_center_offset_y=0.01,
        pose_yaw=0.0,
        pose_pitch=0.0,
        pose_roll=0.0,
        pose_valid=True,
        accepted=accepted,
        reason=reason,
        ui_hint=reason,
        flags={"exactly_one_face": True},
    )


def test_audit_logger_persists_liveness_and_quality_summary() -> None:
    repository = FakeAttendanceRepository()
    logger = RecognitionAuditLogger(repository)
    request = type(
        "Request",
        (),
        {
            "device_code": "gate-a01",
            "session_code": "morning-gate",
            "frames": [{"frame_b64": "ZmFrZS1mcmFtZS1ieXRlcy1mYWtlLWZyYW1lLWJ5dGVz", "pose_hint": None}] * 3,
        },
    )()
    response = RecognitionResponse(
        decision="recognized",
        reason="multi_frame_confirm_passed",
        confirmed_frames=2,
        device_code="gate-a01",
        session_code="morning-gate",
        person=None,
        confidence=0.87,
        top_candidates=[],
    )
    frame_decisions = [
        RecognitionFrameDecision(True, "match_candidate", uuid4(), uuid4(), "ST-1001", "Ada Lovelace", 0.11, 0.89, build_quality(0.8)),
        RecognitionFrameDecision(False, "frame_too_blurry", None, None, None, None, None, None, build_quality(0.6, accepted=False, reason="frame_too_blurry")),
    ]
    asyncio.run(logger.log(response, request, None, None, "checkin", frame_decisions))
    assert len(repository.logs) == 1
    log = repository.logs[0]
    assert log.decision == "accepted"
    assert log.reason == "multi_frame_confirm_passed"
    assert log.liveness_score == pytest.approx(0.7)
    assert log.payload_json["quality_summary"]["accepted_frames"] == 1
    assert log.payload_json["quality_summary"]["rejected_frames"] == 1
    assert log.payload_json["quality_summary"]["reasons"]["match_candidate"] == 1
    assert log.payload_json["quality_summary"]["reasons"]["frame_too_blurry"] == 1
