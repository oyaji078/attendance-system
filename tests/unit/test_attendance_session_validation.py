from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from uuid import uuid4

import pytest

from db.schemas.attendance_sessions import AttendanceSessionCreateRequest, AttendanceSessionRead
from services.attendance.session_service import AttendanceSessionService

WITA_TZ = timezone(timedelta(hours=8))


def _valid_recurring_payload(**overrides) -> dict:
    payload = {
        "session_name": "Sesi Pagi",
        "session_kind": "lecture",
        "class_id": uuid4(),
        "lecturer_id": None,
        "device_code": "gate-a01",
        "cooldown_seconds": 30,
        "repeat_days": ["monday", "tuesday"],
        "start_time": time(7, 30),
        "end_time": time(9, 30),
        "timezone": "Asia/Makassar",
        "is_active": True,
    }
    payload.update(overrides)
    return payload


def test_recurring_session_accepts_full_payload() -> None:
    request = AttendanceSessionCreateRequest(**_valid_recurring_payload())
    assert request.repeat_days == ["monday", "tuesday"]
    assert request.timezone == "Asia/Makassar"


def test_recurring_session_rejects_missing_repeat_days() -> None:
    with pytest.raises(ValueError, match="repeat_days harus berisi minimal satu hari"):
        AttendanceSessionCreateRequest(**_valid_recurring_payload(repeat_days=None))


def test_recurring_session_rejects_empty_repeat_days() -> None:
    with pytest.raises(ValueError, match="repeat_days harus berisi minimal satu hari"):
        AttendanceSessionCreateRequest(**_valid_recurring_payload(repeat_days=[]))


def test_recurring_session_rejects_missing_start_time() -> None:
    with pytest.raises(ValueError, match="start_time wajib diisi"):
        AttendanceSessionCreateRequest(**_valid_recurring_payload(start_time=None))


def test_recurring_session_rejects_missing_end_time() -> None:
    with pytest.raises(ValueError, match="end_time wajib diisi"):
        AttendanceSessionCreateRequest(**_valid_recurring_payload(end_time=None))


def test_recurring_session_rejects_missing_class_id() -> None:
    with pytest.raises(ValueError, match="class_id wajib diisi"):
        AttendanceSessionCreateRequest(**_valid_recurring_payload(class_id=None))


def test_recurring_session_rejects_end_before_start() -> None:
    with pytest.raises(ValueError, match="end_time must be greater than start_time"):
        AttendanceSessionCreateRequest(**_valid_recurring_payload(start_time=time(10, 0), end_time=time(9, 0)))


def test_legacy_session_without_recurring_fields_still_works() -> None:
    request = AttendanceSessionCreateRequest(
        session_name="Legacy Window",
        session_kind="lecture",
        class_id=None,
        starts_at=None,
        ends_at=None,
    )
    assert request.repeat_days is None
    assert request.start_time is None
    assert request.end_time is None


def _make_session_read(**kwargs) -> AttendanceSessionRead:
    base = {
        "session_id": uuid4(),
        "session_code": "ABS-TEST",
        "session_name": "Sesi Tes",
        "session_kind": "lecture",
        "class_id": uuid4(),
        "class_code": "TI5A",
        "class_name": "TI5A",
        "lecturer_id": None,
        "lecturer_name": None,
        "device_code": "gate-a01",
        "is_active": True,
        "is_deleted": False,
        "cooldown_seconds": 30,
        "starts_at": None,
        "ends_at": None,
        "repeat_days": ["monday", "tuesday"],
        "start_time": time(7, 30),
        "end_time": time(9, 30),
        "timezone": "Asia/Makassar",
        "total_logs": 0,
        "recognized": 0,
        "cooldown": 0,
        "unknown": 0,
        "last_event_at": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "deleted_at": None,
    }
    base.update(kwargs)
    return AttendanceSessionRead(**base)


def _wita(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=WITA_TZ)


def test_recurring_session_active_during_window_on_listed_day() -> None:
    session = _make_session_read(repeat_days=["wednesday"], start_time=time(7, 30), end_time=time(9, 30))
    moment = _wita(2026, 5, 20, 8, 0)
    assert AttendanceSessionService._is_currently_available(session, moment.astimezone(timezone.utc)) is True


def test_recurring_session_inactive_when_today_not_listed() -> None:
    session = _make_session_read(repeat_days=["monday"], start_time=time(7, 30), end_time=time(9, 30))
    moment = _wita(2026, 5, 20, 8, 0)
    assert AttendanceSessionService._is_currently_available(session, moment.astimezone(timezone.utc)) is False


def test_recurring_session_inactive_when_before_start() -> None:
    session = _make_session_read(repeat_days=["wednesday"], start_time=time(7, 30), end_time=time(9, 30))
    moment = _wita(2026, 5, 20, 7, 0)
    assert AttendanceSessionService._is_currently_available(session, moment.astimezone(timezone.utc)) is False


def test_recurring_session_inactive_when_after_end() -> None:
    session = _make_session_read(repeat_days=["wednesday"], start_time=time(7, 30), end_time=time(9, 30))
    moment = _wita(2026, 5, 20, 10, 0)
    assert AttendanceSessionService._is_currently_available(session, moment.astimezone(timezone.utc)) is False


def test_recurring_session_inactive_when_is_active_false() -> None:
    session = _make_session_read(is_active=False, repeat_days=["wednesday"], start_time=time(7, 30), end_time=time(9, 30))
    moment = _wita(2026, 5, 20, 8, 0)
    assert AttendanceSessionService._is_currently_available(session, moment.astimezone(timezone.utc)) is False


def test_legacy_session_active_logic_unchanged() -> None:
    now = datetime.now(timezone.utc)
    session = _make_session_read(
        repeat_days=None,
        start_time=None,
        end_time=None,
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(hours=1),
    )
    assert AttendanceSessionService._is_currently_available(session, now) is True
