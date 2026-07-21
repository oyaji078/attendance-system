from __future__ import annotations

from datetime import datetime, timezone, time, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.attendance import router as attendance_router
from app.core.dependencies import get_attendance_session_service
from db.schemas.attendance_sessions import AttendanceSessionPublicRead


WITA_TZ = timezone(timedelta(hours=8))

# Stable class ids reused across grouping assertions (must be real UUIDs to
# satisfy the AttendanceSessionPublicRead contract the service returns).
C1 = str(uuid4())
C2 = str(uuid4())


def _make_session(**kwargs):
    defaults = {
        "session_id": str(uuid4()),
        "session_code": "ABS-TEST",
        "session_name": "Test Session",
        "session_kind": "lecture",
        "class_id": str(uuid4()),
        "class_code": "TI5A",
        "class_name": "TI5A",
        "lecturer_name": "Test Lecturer",
        "is_active": True,
        "is_deleted": False,
        "starts_at": None,
        "ends_at": None,
        "repeat_days": None,
        "start_time": None,
        "end_time": None,
        "timezone": "Asia/Makassar",
    }
    defaults.update(kwargs)
    return defaults


class FakeAttendanceSessionService:
    def __init__(self) -> None:
        self.sessions = []

    async def list_active_sessions(self):
        now = datetime.now(timezone.utc)
        # Mirror the production contract: the real service returns pydantic
        # session models, never raw dicts.
        return [
            AttendanceSessionPublicRead(**{k: v for k, v in s.items() if k in AttendanceSessionPublicRead.model_fields})
            for s in self.sessions
            if self._is_active(s, now)
        ]

    def _is_active(self, session: dict, now: datetime) -> bool:
        if not session.get("is_active") or session.get("is_deleted"):
            return False
        if session.get("repeat_days") and session.get("start_time"):
            now_wita = now.astimezone(WITA_TZ)
            day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            today_wita = day_names[now_wita.weekday()]
            current_time_wita = now_wita.time()
            if today_wita not in session["repeat_days"]:
                return False
            if session["start_time"] and current_time_wita < session["start_time"]:
                return False
            if session["end_time"] and current_time_wita > session["end_time"]:
                return False
            return True
        starts_at = session.get("starts_at")
        ends_at = session.get("ends_at")
        if starts_at and starts_at > now:
            return False
        if ends_at and ends_at < now:
            return False
        return True


def build_app(service: FakeAttendanceSessionService) -> FastAPI:
    app = FastAPI()
    app.include_router(attendance_router)
    app.dependency_overrides[get_attendance_session_service] = lambda: service
    return app


def test_classes_active_returns_classes_with_active_sessions() -> None:
    service = FakeAttendanceSessionService()
    service.sessions = [
        _make_session(class_id=C1, class_code="TI5A", class_name="TI5A"),
        _make_session(class_id=C1, class_code="TI5A", class_name="TI5A"),
        _make_session(class_id=C2, class_code="TI5B", class_name="TI5B"),
    ]
    client = TestClient(build_app(service))
    resp = client.get("/attendance/classes/active")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    codes = [c["class_code"] for c in data]
    assert "TI5A" in codes
    assert "TI5B" in codes
    ti5a = next(c for c in data if c["class_code"] == "TI5A")
    assert ti5a["active_session_count"] == 2


def test_classes_active_excludes_null_class_id() -> None:
    service = FakeAttendanceSessionService()
    service.sessions = [
        _make_session(class_id=None),
        _make_session(class_id=C1, class_code="TI5A", class_name="TI5A"),
    ]
    client = TestClient(build_app(service))
    resp = client.get("/attendance/classes/active")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["class_code"] == "TI5A"


def test_classes_active_excludes_inactive_sessions() -> None:
    service = FakeAttendanceSessionService()
    service.sessions = [
        _make_session(class_id=C1, class_code="TI5A", class_name="TI5A", is_active=True),
        _make_session(class_id=C1, class_code="TI5A", class_name="TI5A", is_active=False),
        _make_session(class_id=C1, class_code="TI5A", class_name="TI5A", is_deleted=True),
    ]
    client = TestClient(build_app(service))
    resp = client.get("/attendance/classes/active")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["active_session_count"] == 1


def test_classes_active_excludes_sessions_outside_time_window() -> None:
    service = FakeAttendanceSessionService()
    now = datetime.now(timezone.utc)
    service.sessions = [
        _make_session(class_id=C1, class_code="TI5A", class_name="TI5A", starts_at=now.replace(year=now.year + 1)),
        _make_session(class_id=C2, class_code="TI5B", class_name="TI5B", starts_at=None, ends_at=None),
    ]
    client = TestClient(build_app(service))
    resp = client.get("/attendance/classes/active")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["class_code"] == "TI5B"


def test_sessions_for_class_returns_active_sessions_only() -> None:
    class_id = str(uuid4())
    other_class_id = str(uuid4())
    service = FakeAttendanceSessionService()
    service.sessions = [
        _make_session(class_id=class_id, class_code="TI5A", class_name="TI5A", is_active=True),
        _make_session(class_id=class_id, class_code="TI5A", class_name="TI5A", is_active=False),
        _make_session(class_id=other_class_id, class_code="TI5B", class_name="TI5B", is_active=True),
    ]
    client = TestClient(build_app(service))
    resp = client.get(f"/attendance/classes/{class_id}/sessions/active")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["class_id"] == class_id


def test_sessions_for_class_excludes_null_class_id_sessions() -> None:
    class_id = str(uuid4())
    service = FakeAttendanceSessionService()
    service.sessions = [
        _make_session(class_id=class_id, class_code="TI5A", class_name="TI5A", is_active=True),
        _make_session(class_id=None, class_code="TI5X", class_name="TI5X", is_active=True),
    ]
    client = TestClient(build_app(service))
    resp = client.get(f"/attendance/classes/{class_id}/sessions/active")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert all(s["class_id"] == class_id for s in data)


def test_sessions_for_class_invalid_uuid_returns_400() -> None:
    service = FakeAttendanceSessionService()
    client = TestClient(build_app(service))
    resp = client.get("/attendance/classes/not-a-uuid/sessions/active")
    assert resp.status_code == 400


def test_classes_active_empty_when_no_sessions() -> None:
    service = FakeAttendanceSessionService()
    service.sessions = []
    client = TestClient(build_app(service))
    resp = client.get("/attendance/classes/active")
    assert resp.status_code == 200
    assert resp.json() == []
