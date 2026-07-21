from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from db.schemas.attendance import AttendanceConfirmRequest
from services.recognition.recognition_service import RecognitionService


class FakeSession:
    def __init__(self) -> None:
        self.commit_calls = 0
        self.rollback_calls = 0

    async def commit(self) -> None:
        self.commit_calls += 1

    async def rollback(self) -> None:
        self.rollback_calls += 1

    async def refresh(self, _instance) -> None:
        pass

    async def execute(self, statement):
        class FakeResult:
            def one_or_none(self):
                return None

            def scalar_one_or_none(self):
                return None

        return FakeResult()


class FakeDeviceRepository:
    async def get_by_code_cached(self, device_code, cache=None):
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


class FakeCache:
    async def cooldown_ttl_seconds(self, session_code, person_id):
        return None

    async def set_cooldown(self, *args, **kwargs):
        pass

    async def set_recent_match(self, *args, **kwargs):
        pass


def _make_session(class_id, session_code="ABS-1"):
    return type(
        "AttendanceSession",
        (),
        {
            "id": uuid4(),
            "session_code": session_code,
            "session_name": "Sesi Pagi",
            "class_id": class_id,
            "lecturer_id": None,
            "device_code": "gate-a01",
            "is_active": True,
            "is_deleted": False,
            "cooldown_seconds": 30,
            "starts_at": datetime.now(timezone.utc) - timedelta(hours=1),
            "ends_at": datetime.now(timezone.utc) + timedelta(hours=1),
            "repeat_days": None,
            "start_time": None,
            "end_time": None,
            "timezone": "Asia/Makassar",
        },
    )()


class FakeAttendanceRepository:
    def __init__(self, session_record, already_today: bool = False):
        self._session_record = session_record
        self.already_today = already_today
        self.add_log_calls = 0
        self.last_added_log = None

    async def get_session(self, session_code):
        if self._session_record.session_code == session_code:
            return self._session_record
        return None

    @staticmethod
    def availability_reason(session, now=None):
        if session.is_deleted:
            return "attendance_session_deleted"
        if not session.is_active:
            return "attendance_session_inactive"
        return None

    async def has_accepted_log_in_window(self, *, session_id, person_id, window_start, window_end):
        return self.already_today

    async def add_log(self, log):
        self.add_log_calls += 1
        log.id = uuid4()
        log.created_at = datetime.now(timezone.utc)
        log.decision = "accepted"
        log.reason = "confirmed_by_user"
        log.event_type = "checkin"
        self.last_added_log = log
        return log


def _make_service(repository, person):
    service = RecognitionService(
        session=FakeSession(),
        device_repository=FakeDeviceRepository(),
        attendance_repository=repository,
        frame_processor=None,
        decision_engine=None,
        audit_logger=None,
        cache=FakeCache(),
    )

    async def fake_person_summary(person_id, template_id):
        return person

    service._person_summary = fake_person_summary  # type: ignore[assignment]

    async def fake_resolved(record):
        return None

    service._resolved_session_from_record = fake_resolved  # type: ignore[assignment]

    async def fake_validate_token(token, **kwargs):
        return True

    service._validate_pending_token = fake_validate_token  # type: ignore[assignment]

    async def fake_store_image(req):
        return None

    service._store_confirmed_attendance_image = fake_store_image  # type: ignore[assignment]
    return service


def _make_person(class_id):
    return type(
        "PersonSummary",
        (),
        {
            "person_id": uuid4(),
            "student_id": "ST-1",
            "full_name": "Ada Lovelace",
            "email": None,
            "class_id": class_id,
            "class_code": "TI5A",
            "class_name": "TI5A",
            "template_id": uuid4(),
        },
    )()


def test_confirm_rejects_duplicate_same_person_session_today() -> None:
    class_id = uuid4()
    session_record = _make_session(class_id)
    person = _make_person(class_id)
    repository = FakeAttendanceRepository(session_record, already_today=True)
    service = _make_service(repository, person)
    request = AttendanceConfirmRequest(
        person_id=person.person_id,
        session_code=session_record.session_code,
        device_code="gate-a01",
        confidence=0.91,
        recognition_token="any-token",
    )
    response = asyncio.run(service.confirm_attendance(request))
    assert response.decision == "rejected"
    assert response.reason == "duplicate_attendance_today"
    assert repository.add_log_calls == 0


def test_confirm_converts_unique_index_violation_to_duplicate_response() -> None:
    """Concurrent confirms that race past the SELECT dedup must surface as a
    duplicate rejection, not a 500, when the daily-unique index fires."""
    from sqlalchemy.exc import IntegrityError

    class RacingRepository(FakeAttendanceRepository):
        async def add_log(self, log):
            raise IntegrityError(
                "INSERT INTO attendance_logs ...",
                {},
                Exception('duplicate key value violates unique constraint "uq_attendance_logs_accepted_once_per_day"'),
            )

    class_id = uuid4()
    session_record = _make_session(class_id)
    person = _make_person(class_id)
    repository = RacingRepository(session_record, already_today=False)
    service = _make_service(repository, person)
    request = AttendanceConfirmRequest(
        person_id=person.person_id,
        session_code=session_record.session_code,
        device_code="gate-a01",
        confidence=0.91,
        recognition_token="any-token",
    )
    response = asyncio.run(service.confirm_attendance(request))
    assert response.decision == "rejected"
    assert response.reason == "duplicate_attendance_today"
    assert service.session.rollback_calls == 1
    assert service.session.commit_calls == 0


def test_confirm_saves_log_when_not_duplicate() -> None:
    class_id = uuid4()
    session_record = _make_session(class_id)
    person = _make_person(class_id)
    repository = FakeAttendanceRepository(session_record, already_today=False)
    service = _make_service(repository, person)
    request = AttendanceConfirmRequest(
        person_id=person.person_id,
        session_code=session_record.session_code,
        device_code="gate-a01",
        confidence=0.91,
        recognition_token="any-token",
    )
    response = asyncio.run(service.confirm_attendance(request))
    assert response.decision == "accepted"
    assert response.reason == "confirmed_by_user"
    assert repository.add_log_calls == 1
    assert response.attendance is not None
    assert response.attendance.status == "Hadir"
