from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.routes.attendance import router as attendance_router
from app.api.routes.recognition import router as recognition_router
from app.core.dependencies import (
    get_attendance_read_service,
    get_current_admin_user,
    get_recognition_service,
)


class FakeRecognitionService:
    async def recognize(self, request, event_type: str, require_session: bool = False):
        return {"decision": "accepted", "reason": "multi_frame_confirm_passed", "recognition_status": "recognized", "confirmed_frames": 2, "device_code": request.device_code, "session_code": request.session_code, "person": {"person_id": str(uuid4()), "student_id": "ST-1001", "full_name": "Ada Lovelace", "template_id": str(uuid4())}, "confidence": 0.82, "top_candidates": []}


class FakeAttendanceReadService:
    async def status(self, session_code: str):
        return {"session_code": session_code, "session_name": "Morning Gate", "is_active": True, "total_logs": 3, "recognized": 2, "cooldown": 1, "unknown": 0, "last_event_at": datetime.now(timezone.utc).isoformat()}

    async def logs(self, session_code: str):
        return {"session_code": session_code, "items": [{"id": str(uuid4()), "student_id": "ST-1001", "full_name": "Ada Lovelace", "decision": "accepted", "reason": "multi_frame_confirm_passed", "confidence": 0.82, "device_code": "gate-a01", "event_type": "checkin", "created_at": datetime.now(timezone.utc).isoformat()}]}


def build_app(*, signed_in: bool = True) -> FastAPI:
    app = FastAPI()
    app.include_router(recognition_router)
    app.include_router(attendance_router)
    app.dependency_overrides[get_recognition_service] = lambda: FakeRecognitionService()
    app.dependency_overrides[get_attendance_read_service] = lambda: FakeAttendanceReadService()
    if signed_in:
        app.dependency_overrides[get_current_admin_user] = lambda: SimpleNamespace(
            id=uuid4(), role="admin", lecturer_id=None, username="tester"
        )
    else:
        # Stands in for "no session cookie", which is what the real dependency
        # raises. The genuine chain needs app.state.container, which this bare
        # test app deliberately does not build.
        def _no_session():
            raise HTTPException(status_code=401, detail="Login admin diperlukan.")

        app.dependency_overrides[get_current_admin_user] = _no_session
    return app


FRAMES = [{"frame_b64": "ZmFrZS1mcmFtZS1ieXRlcy1mYWtlLWZyYW1lLWJ5dGVz", "pose_hint": None}] * 3


def test_kiosk_endpoints_stay_open_for_the_camera() -> None:
    # The kiosk runs unauthenticated by design: these three are what it needs.
    client = TestClient(build_app(signed_in=False))
    checkin = client.post(
        "/attendance/checkin",
        json={"session_code": "morning-gate", "device_code": "gate-a01", "frames": FRAMES},
    )
    assert checkin.status_code == 200
    assert client.get("/attendance/status/morning-gate").status_code == 200


def test_roster_endpoints_require_a_signed_in_account() -> None:
    # They return student names and IDs, and the kiosk origin is public.
    client = TestClient(build_app(signed_in=False))
    assert client.get("/attendance/logs/morning-gate").status_code == 401
    assert client.get(f"/attendance/sessions/{uuid4()}/today-logs").status_code == 401


def test_roster_endpoints_work_once_signed_in() -> None:
    client = TestClient(build_app())
    logs = client.get("/attendance/logs/morning-gate")
    assert logs.status_code == 200
    assert logs.json()["items"][0]["full_name"] == "Ada Lovelace"
