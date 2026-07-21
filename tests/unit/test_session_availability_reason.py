from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from types import SimpleNamespace

from db.repositories.attendance import AttendanceRepository

WITA_TZ = timezone(timedelta(hours=8))


def _session(**overrides):
    base = {
        "is_deleted": False,
        "is_active": True,
        "starts_at": None,
        "ends_at": None,
        "repeat_days": None,
        "start_time": None,
        "end_time": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_open_ended_session_with_null_window_is_available() -> None:
    """Regression: sessions with NULL starts_at/ends_at (e.g. open-ended or
    recurring sessions from migration 0010) crashed availability_reason with
    AttributeError instead of evaluating availability."""
    assert AttendanceRepository.availability_reason(_session()) is None


def test_recurring_session_null_starts_at_scheduled_today() -> None:
    now = datetime.now(timezone.utc)
    now_wita = now.astimezone(WITA_TZ)
    day_name = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][now_wita.weekday()]
    session = _session(repeat_days=[day_name], start_time=time(0, 0), end_time=time(23, 59))
    assert AttendanceRepository.availability_reason(session, now=now) is None


def test_recurring_session_not_scheduled_today() -> None:
    now = datetime.now(timezone.utc)
    now_wita = now.astimezone(WITA_TZ)
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    other_day = days[(now_wita.weekday() + 1) % 7]
    session = _session(repeat_days=[other_day], start_time=time(0, 0), end_time=time(23, 59))
    assert AttendanceRepository.availability_reason(session, now=now) == "attendance_session_not_scheduled_today"


def test_window_session_before_start_and_after_end() -> None:
    now = datetime.now(timezone.utc)
    not_started = _session(starts_at=now + timedelta(hours=1), ends_at=now + timedelta(hours=2))
    ended = _session(starts_at=now - timedelta(hours=2), ends_at=now - timedelta(hours=1))
    assert AttendanceRepository.availability_reason(not_started, now=now) == "attendance_session_not_started"
    assert AttendanceRepository.availability_reason(ended, now=now) == "attendance_session_ended"


def test_open_start_or_open_end_windows() -> None:
    now = datetime.now(timezone.utc)
    open_start = _session(starts_at=None, ends_at=now + timedelta(hours=1))
    open_end = _session(starts_at=now - timedelta(hours=1), ends_at=None)
    assert AttendanceRepository.availability_reason(open_start, now=now) is None
    assert AttendanceRepository.availability_reason(open_end, now=now) is None


def test_deleted_and_inactive_take_priority() -> None:
    assert AttendanceRepository.availability_reason(_session(is_deleted=True)) == "attendance_session_deleted"
    assert AttendanceRepository.availability_reason(_session(is_active=False)) == "attendance_session_inactive"
