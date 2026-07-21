from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from db.schemas.attendance import AttendancePreviewRequest
from db.schemas.recognition import RecognitionRequest
from services.recognition.recognition_service import RecognitionService


class FakeSession:
    def __init__(self) -> None:
        self.commit_calls = 0

    async def commit(self) -> None:
        self.commit_calls += 1

    async def execute(self, statement):
        class FakeResult:
            def one_or_none(self):
                return None
            def scalar_one_or_none(self):
                return None
        return FakeResult()


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
                "similarity_threshold": 0.45,
                "candidate_margin_threshold": 0.05,
            },
        )()

    async def get_by_code_cached(self, device_code, cache=None):
        return await self.get_by_code(device_code)


class FakeAttendanceRepository:
    def __init__(self, sessions=None) -> None:
        self._sessions = sessions or {}

    async def get_session(self, session_code):
        for s in self._sessions.values():
            if s.session_code == session_code:
                return s
        return None

    async def get_session_by_id(self, session_id):
        return self._sessions.get(str(session_id))

    @staticmethod
    def availability_reason(session, now=None):
        timestamp = now or datetime.now(timezone.utc)
        if session.is_deleted:
            return "attendance_session_deleted"
        if not session.is_active:
            return "attendance_session_inactive"
        if session.starts_at is not None and timestamp < session.starts_at:
            return "attendance_session_not_started"
        if session.ends_at is not None and timestamp > session.ends_at:
            return "attendance_session_ended"
        return None


class FakeFrameProcessor:
    def __init__(self, candidates=None, person_id=None) -> None:
        self._candidates = candidates or []
        self._person_id = person_id
        self.processed_with_class_id = None

    async def process(self, frame_input, device, class_id=None):
        self.processed_with_class_id = class_id
        decision = type(
            "RecognitionFrameDecision",
            (),
            {
                "quality": type("QualityResult", (), {"accepted": True, "reason": None})(),
                "matched_person_id": self._person_id,
                "matched_template_id": uuid4(),
                "student_id": "ST-1001",
                "full_name": "Ada Lovelace",
                "distance": 0.3,
                "confidence": 0.82,
            },
        )()
        return type(
            "ProcessedRecognitionFrame",
            (),
            {"decision": decision, "candidates": self._candidates},
        )()


class FakeDecisionEngine:
    async def decide(self, **kwargs):
        person_id = uuid4()
        response = type(
            "RecognitionResponse",
            (),
            {
                "decision": "accepted",
                "reason": "multi_frame_confirm_passed",
                "recognition_status": "recognized",
                "confirmed_frames": 2,
                "device_code": kwargs.get("request").device_code,
                "session_code": kwargs.get("request").session_code,
                "person": type(
                    "PersonSummary",
                    (),
                    {
                        "person_id": person_id,
                        "student_id": "ST-1001",
                        "full_name": "Ada Lovelace",
                        "class_id": uuid4(),
                        "class_code": "CS-101",
                        "class_name": "Computer Science 101",
                        "template_id": uuid4(),
                        "email": "ada@example.com",
                    },
                )(),
                "confidence": 0.82,
                "top_candidates": [],
                "captured_face_b64": None,
                "resolved_session": None,
                "session_resolution": None,
            },
        )()
        return response, person_id, uuid4()


class FakeAuditLogger:
    def __init__(self) -> None:
        self.logged = []

    async def log(self, response, request, person_id, template_id, event_type, frame_decisions=None, captured_image_uri=None):
        self.logged.append((response, request, event_type))


class FakeCache:
    async def cooldown_ttl_seconds(self, session_code, person_id):
        return None

    async def set_cooldown(self, session_code, person_id, seconds):
        pass

    async def set_recent_match(self, device_code, data):
        pass


def _make_session(session_id=None, session_code="test-session", class_id=None, is_active=True, starts_at=None, ends_at=None, is_deleted=False):
    sid = session_id or uuid4()
    return type(
        "AttendanceSession",
        (),
        {
            "id": sid,
            "session_code": session_code,
            "session_name": "Test Session",
            "class_id": class_id,
            "lecturer_id": None,
            "device_code": "gate-a01",
            "is_active": is_active,
            "is_deleted": is_deleted,
            "cooldown_seconds": 30,
            "starts_at": starts_at,
            "ends_at": ends_at,
        },
    )()


def test_preview_rejects_missing_session_id() -> None:
    """When session_id is provided but not found, preview should reject."""
    now = datetime.now(timezone.utc)
    attendance_repository = FakeAttendanceRepository(sessions={})
    audit_logger = FakeAuditLogger()
    service = RecognitionService(
        session=FakeSession(),
        device_repository=FakeDeviceRepository(),
        attendance_repository=attendance_repository,
        frame_processor=FakeFrameProcessor(),
        decision_engine=FakeDecisionEngine(),
        audit_logger=audit_logger,
        cache=FakeCache(),
    )
    request = AttendancePreviewRequest(
        device_code="gate-a01",
        frames=[{"frame_b64": "ZmFrZS1mcmFtZS1ieXRlcy1mYWtlLWZyYW1lLWJ5dGVz", "pose_hint": None}] * 3,
        session_id=str(uuid4()),
    )
    with pytest.raises(ValueError, match="Sesi absensi tidak ditemukan"):
        asyncio.run(service.preview_attendance(request))


def test_preview_rejects_inactive_session() -> None:
    """When session_id is provided but session is inactive, preview should reject."""
    now = datetime.now(timezone.utc)
    session = _make_session(session_code="inactive-session", is_active=False)
    attendance_repository = FakeAttendanceRepository(sessions={str(session.id): session})
    audit_logger = FakeAuditLogger()
    service = RecognitionService(
        session=FakeSession(),
        device_repository=FakeDeviceRepository(),
        attendance_repository=attendance_repository,
        frame_processor=FakeFrameProcessor(),
        decision_engine=FakeDecisionEngine(),
        audit_logger=audit_logger,
        cache=FakeCache(),
    )
    request = AttendancePreviewRequest(
        device_code="gate-a01",
        frames=[{"frame_b64": "ZmFrZS1mcmFtZS1ieXRlcy1mYWtlLWZyYW1lLWJ5dGVz", "pose_hint": None}] * 3,
        session_id=str(session.id),
    )
    response = asyncio.run(service.preview_attendance(request))
    assert response.decision == "rejected"
    assert response.recognition_status == "session_inactive"
    assert "inactive" in response.reason


def test_preview_rejects_expired_session() -> None:
    """When session_id is provided but session has ended, preview should reject."""
    now = datetime.now(timezone.utc)
    session = _make_session(
        session_code="expired-session",
        is_active=True,
        starts_at=now - timedelta(hours=2),
        ends_at=now - timedelta(minutes=10),
    )
    attendance_repository = FakeAttendanceRepository(sessions={str(session.id): session})
    audit_logger = FakeAuditLogger()
    service = RecognitionService(
        session=FakeSession(),
        device_repository=FakeDeviceRepository(),
        attendance_repository=attendance_repository,
        frame_processor=FakeFrameProcessor(),
        decision_engine=FakeDecisionEngine(),
        audit_logger=audit_logger,
        cache=FakeCache(),
    )
    request = AttendancePreviewRequest(
        device_code="gate-a01",
        frames=[{"frame_b64": "ZmFrZS1mcmFtZS1ieXRlcy1mYWtlLWZyYW1lLWJ5dGVz", "pose_hint": None}] * 3,
        session_id=str(session.id),
    )
    response = asyncio.run(service.preview_attendance(request))
    assert response.decision == "rejected"
    assert response.recognition_status == "session_inactive"
    assert "ended" in response.reason


def test_preview_rejects_not_started_session() -> None:
    """When session_id is provided but session has not started, preview should reject."""
    now = datetime.now(timezone.utc)
    session = _make_session(
        session_code="future-session",
        is_active=True,
        starts_at=now + timedelta(minutes=30),
        ends_at=now + timedelta(hours=2),
    )
    attendance_repository = FakeAttendanceRepository(sessions={str(session.id): session})
    audit_logger = FakeAuditLogger()
    service = RecognitionService(
        session=FakeSession(),
        device_repository=FakeDeviceRepository(),
        attendance_repository=attendance_repository,
        frame_processor=FakeFrameProcessor(),
        decision_engine=FakeDecisionEngine(),
        audit_logger=audit_logger,
        cache=FakeCache(),
    )
    request = AttendancePreviewRequest(
        device_code="gate-a01",
        frames=[{"frame_b64": "ZmFrZS1mcmFtZS1ieXRlcy1mYWtlLWZyYW1lLWJ5dGVz", "pose_hint": None}] * 3,
        session_id=str(session.id),
    )
    response = asyncio.run(service.preview_attendance(request))
    assert response.decision == "rejected"
    assert response.recognition_status == "session_inactive"
    assert "not_started" in response.reason


def test_preview_without_session_id_works_as_before() -> None:
    """When session_id is not provided, preview should work as before (auto-resolution)."""
    class_id = uuid4()
    session = _make_session(session_code="auto-session", class_id=class_id, is_active=True, starts_at=datetime.now(timezone.utc) - timedelta(hours=1), ends_at=datetime.now(timezone.utc) + timedelta(hours=1))

    class FakeAttendanceRepositoryWithResolution(FakeAttendanceRepository):
        async def list_available_session_projections_for_class(self, cid, now):
            if cid == class_id:
                return [type("Projection", (), {"session": session, "total_logs": 0, "recognized": 0, "cooldown": 0, "unknown": 0, "last_event_at": None, "class_code": "CS-101", "class_name": "Computer Science 101", "lecturer_name": "Dr. Test"})()]
            return []

    attendance_repository = FakeAttendanceRepositoryWithResolution(sessions={str(session.id): session})
    audit_logger = FakeAuditLogger()

    person_class_id = class_id
    person_id = uuid4()
    template_id = uuid4()

    class FakeFrameProcessorWithClass(FakeFrameProcessor):
        pass

    class FakeDecisionEngineWithPerson(FakeDecisionEngine):
        async def decide(self, **kwargs):
            response = type(
                "RecognitionResponse",
                (),
                {
                    "decision": "accepted",
                    "reason": "multi_frame_confirm_passed",
                    "recognition_status": "recognized",
                    "confirmed_frames": 2,
                    "device_code": kwargs.get("request").device_code,
                    "session_code": kwargs.get("request").session_code,
                    "person": type(
                        "PersonSummary",
                        (),
                        {
                            "person_id": person_id,
                            "student_id": "ST-1001",
                            "full_name": "Ada Lovelace",
                            "class_id": person_class_id,
                            "class_code": "CS-101",
                            "class_name": "Computer Science 101",
                            "template_id": template_id,
                            "email": "ada@example.com",
                        },
                    )(),
                    "confidence": 0.82,
                    "top_candidates": [],
                    "captured_face_b64": None,
                    "resolved_session": None,
                    "session_resolution": None,
                },
            )()
            return response, person_id, template_id

    service = RecognitionService(
        session=FakeSession(),
        device_repository=FakeDeviceRepository(),
        attendance_repository=attendance_repository,
        frame_processor=FakeFrameProcessorWithClass(),
        decision_engine=FakeDecisionEngineWithPerson(),
        audit_logger=audit_logger,
        cache=FakeCache(),
    )

    fake_person = type(
        "PersonSummary",
        (),
        {
            "person_id": person_id,
            "student_id": "ST-1001",
            "full_name": "Ada Lovelace",
            "class_id": person_class_id,
            "class_code": "CS-101",
            "class_name": "Computer Science 101",
            "template_id": template_id,
            "email": "ada@example.com",
        },
    )()

    async def fake_person_summary(pid, tid):
        return fake_person

    service._person_summary = fake_person_summary  # type: ignore[assignment]

    async def fake_generate_token(**kwargs):
        return "pending-token-123"

    service._generate_pending_token = fake_generate_token  # type: ignore[assignment]

    request = AttendancePreviewRequest(
        device_code="gate-a01",
        frames=[{"frame_b64": "ZmFrZS1mcmFtZS1ieXRlcy1mYWtlLWZyYW1lLWJ5dGVz", "pose_hint": None}] * 3,
        session_id=None,
    )
    response = asyncio.run(service.preview_attendance(request))
    assert response.recognition_status == "recognized"
    assert response.resolved_session is not None
    assert response.pending_attendance_token == "pending-token-123"
