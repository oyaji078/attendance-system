from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.admin import router as admin_router
from app.core.dependencies import get_attendance_session_service, get_session


class DummySession:
    async def commit(self) -> None:
        return None


class FakeAttendanceSessionService:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.items = {}
        self.created_id = None
        self.now = now

    async def list_sessions(self):
        return list(self.items.values())

    async def get_session(self, session_id):
        return self.items.get(str(session_id))

    async def create_session(self, request):
        session_id = str(uuid4())
        self.created_id = session_id
        payload = {
            "session_id": session_id,
            "session_code": request.session_code,
            "session_name": request.session_name,
            "session_kind": request.session_kind,
            "is_active": request.is_active,
            "cooldown_seconds": request.cooldown_seconds,
            "starts_at": request.starts_at.isoformat() if request.starts_at else None,
            "ends_at": request.ends_at.isoformat() if request.ends_at else None,
            "total_logs": 0,
            "recognized": 0,
            "cooldown": 0,
            "unknown": 0,
            "last_event_at": None,
            "created_at": self.now,
            "updated_at": self.now,
        }
        self.items[session_id] = payload
        return payload

    async def update_session(self, session_id, request):
        payload = self.items[str(session_id)]
        payload.update(
            {
                "session_code": request.session_code,
                "session_name": request.session_name,
                "session_kind": request.session_kind,
                "is_active": request.is_active,
                "cooldown_seconds": request.cooldown_seconds,
                "starts_at": request.starts_at.isoformat() if request.starts_at else None,
                "ends_at": request.ends_at.isoformat() if request.ends_at else None,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return payload

    async def activate_session(self, session_id):
        payload = self.items[str(session_id)]
        payload["is_active"] = True
        return payload

    async def close_session(self, session_id):
        payload = self.items[str(session_id)]
        payload["is_active"] = False
        payload["ends_at"] = datetime.now(timezone.utc).isoformat()
        return payload


def build_app(service: FakeAttendanceSessionService) -> FastAPI:
    app = FastAPI()
    app.include_router(admin_router)

    async def override_session():
        yield DummySession()

    app.dependency_overrides[get_attendance_session_service] = lambda: service
    app.dependency_overrides[get_session] = override_session
    return app


def test_attendance_session_admin_lifecycle() -> None:
    service = FakeAttendanceSessionService()
    client = TestClient(build_app(service))
    create = client.post(
        "/admin/attendance-sessions",
        json={
            "session_code": "morning-gate",
            "session_name": "Morning Gate",
            "session_kind": "checkin",
            "cooldown_seconds": 45,
            "starts_at": None,
            "ends_at": None,
            "is_active": True,
        },
    )
    session_id = create.json()["session_id"]
    listing = client.get("/admin/attendance-sessions")
    detail = client.get(f"/admin/attendance-sessions/{session_id}")
    update = client.put(
        f"/admin/attendance-sessions/{session_id}",
        json={
            "session_code": "morning-gate-updated",
            "session_name": "Morning Gate Updated",
            "session_kind": "checkin",
            "cooldown_seconds": 60,
            "starts_at": None,
            "ends_at": None,
            "is_active": True,
        },
    )
    close = client.patch(f"/admin/attendance-sessions/{session_id}/close")
    activate = client.patch(f"/admin/attendance-sessions/{session_id}/activate")
    assert create.status_code == 201
    assert listing.status_code == 200
    assert detail.status_code == 200
    assert update.status_code == 200
    assert close.status_code == 200
    assert activate.status_code == 200
    assert update.json()["session_code"] == "morning-gate-updated"
    assert close.json()["is_active"] is False
    assert activate.json()["is_active"] is True
