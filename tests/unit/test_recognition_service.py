from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from db.schemas.recognition import RecognitionRequest
from services.recognition.recognition_service import RecognitionService


class FakeSession:
    def __init__(self) -> None:
        self.commit_calls = 0

    async def commit(self) -> None:
        self.commit_calls += 1


class FakeDeviceRepository:
    async def get_by_code(self, device_code):
        return type(
            "DeviceConfig",
            (),
            {
                "device_code": device_code,
                "is_enabled": True,
                "multi_frame_confirm": 2,
                "cooldown_seconds": 30,
            },
        )()


class FakeAttendanceRepository:
    def __init__(self, session_record) -> None:
        self.session_record = session_record

    async def get_session(self, session_code):
        return self.session_record if session_code else None

    @staticmethod
    def availability_reason(session, now=None):
        timestamp = now or datetime.now(timezone.utc)
        if not session.is_active:
            return "attendance_session_inactive"
        if session.starts_at is not None and timestamp < session.starts_at:
            return "attendance_session_not_started"
        if session.ends_at is not None and timestamp > session.ends_at:
            return "attendance_session_ended"
        return None


class FakeFrameProcessor:
    async def process(self, frame_input, device):
        raise AssertionError("frame processing should not run for inactive sessions")


class FakeDecisionEngine:
    async def decide(self, **kwargs):
        raise AssertionError("decision engine should not run for inactive sessions")


class FakeAuditLogger:
    def __init__(self) -> None:
        self.logged = []

    async def log(self, response, request, person_id, template_id, event_type, frame_decisions):
        self.logged.append((response, request, event_type, frame_decisions))


def test_recognition_service_rejects_session_before_start_window() -> None:
    now = datetime.now(timezone.utc)
    attendance_repository = FakeAttendanceRepository(
        type(
            "AttendanceSessionRecord",
            (),
            {
                "is_active": True,
                "cooldown_seconds": 30,
                "starts_at": now + timedelta(minutes=10),
                "ends_at": now + timedelta(hours=1),
            },
        )()
    )
    audit_logger = FakeAuditLogger()
    service = RecognitionService(
        session=FakeSession(),
        device_repository=FakeDeviceRepository(),
        attendance_repository=attendance_repository,
        frame_processor=FakeFrameProcessor(),
        decision_engine=FakeDecisionEngine(),
        audit_logger=audit_logger,
    )
    response = asyncio.run(
        service.recognize(
            RecognitionRequest(
                device_code="gate-a01",
                session_code="morning-gate",
                frames=[{"frame_b64": "ZmFrZS1mcmFtZS1ieXRlcy1mYWtlLWZyYW1lLWJ5dGVz", "pose_hint": None}] * 3,
            ),
            event_type="checkin",
            require_session=True,
        )
    )
    assert response.decision == "session_inactive"
    assert response.reason == "attendance_session_not_started"
    assert len(audit_logger.logged) == 1
