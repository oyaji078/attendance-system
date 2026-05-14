from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.attendance import router as attendance_router
from app.api.routes.recognition import router as recognition_router
from app.core.dependencies import get_attendance_read_service, get_recognition_service


class FakeRecognitionService:
    async def recognize(self, request, event_type: str, require_session: bool = False):
        return {"decision": "accepted", "reason": "multi_frame_confirm_passed", "recognition_status": "recognized", "confirmed_frames": 2, "device_code": request.device_code, "session_code": request.session_code, "person": {"person_id": str(uuid4()), "student_id": "ST-1001", "full_name": "Ada Lovelace", "template_id": str(uuid4())}, "confidence": 0.82, "top_candidates": []}


class FakeAttendanceReadService:
    async def status(self, session_code: str):
        return {"session_code": session_code, "session_name": "Morning Gate", "is_active": True, "total_logs": 3, "recognized": 2, "cooldown": 1, "unknown": 0, "last_event_at": datetime.now(timezone.utc).isoformat()}

    async def logs(self, session_code: str):
        return {"session_code": session_code, "items": [{"id": str(uuid4()), "student_id": "ST-1001", "full_name": "Ada Lovelace", "decision": "accepted", "reason": "multi_frame_confirm_passed", "confidence": 0.82, "device_code": "gate-a01", "event_type": "checkin", "created_at": datetime.now(timezone.utc).isoformat()}]}


def build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(recognition_router)
    app.include_router(attendance_router)
    app.dependency_overrides[get_recognition_service] = lambda: FakeRecognitionService()
    app.dependency_overrides[get_attendance_read_service] = lambda: FakeAttendanceReadService()
    return app


def test_attendance_endpoints() -> None:
    client = TestClient(build_app())
    checkin = client.post("/attendance/checkin", json={"session_code": "morning-gate", "device_code": "gate-a01", "frames": [{"frame_b64": "ZmFrZS1mcmFtZS1ieXRlcy1mYWtlLWZyYW1lLWJ5dGVz", "pose_hint": None}, {"frame_b64": "ZmFrZS1mcmFtZS1ieXRlcy1mYWtlLWZyYW1lLWJ5dGVz", "pose_hint": None}, {"frame_b64": "ZmFrZS1mcmFtZS1ieXRlcy1mYWtlLWZyYW1lLWJ5dGVz", "pose_hint": None}]})
    status = client.get("/attendance/status/morning-gate")
    logs = client.get("/attendance/logs/morning-gate")
    assert checkin.status_code == 200
    assert status.status_code == 200
    assert logs.status_code == 200
