from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI, Request, status
from fastapi.testclient import TestClient

from app.api.routes.attendance import router as attendance_router
from app.core.dependencies import get_attendance_read_service, get_recognition_service
from app.core.rate_limiter import rate_limit_attendance_dependency


class FakeRecognitionService:
    async def preview_attendance(self, request):
        return {
            "decision": "accepted",
            "reason": "multi_frame_confirm_passed",
            "recognition_status": "recognized",
            "confirmed_frames": 2,
            "device_code": request.device_code,
            "session_code": None,
            "person": {"person_id": str(uuid4()), "student_id": "ST-1001", "full_name": "Ada Lovelace", "template_id": str(uuid4())},
            "confidence": 0.82,
            "top_candidates": [],
            "session_resolution": "resolved",
            "resolved_session": {"session_id": str(uuid4()), "session_code": "morning-gate", "session_name": "Morning Gate"},
        }

    async def confirm_attendance(self, request):
        return {
            "decision": "accepted",
            "reason": "confirmed_by_user",
            "device_code": request.device_code,
            "confidence": request.confidence,
            "cooldown_remaining_seconds": 30,
            "person": {"person_id": str(request.person_id), "student_id": "ST-1001", "full_name": "Ada Lovelace", "template_id": str(uuid4())},
            "resolved_session": {"session_id": str(uuid4()), "session_code": request.session_code, "session_name": "Morning Gate"},
            "attendance": {
                "log_id": str(uuid4()),
                "student_id": "ST-1001",
                "full_name": "Ada Lovelace",
                "decision": "accepted",
                "status": "Hadir",
                "confidence": request.confidence,
                "device_code": request.device_code,
                "session_code": request.session_code,
                "session_name": "Morning Gate",
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        }


class FakeAttendanceReadService:
    async def status(self, session_code: str):
        return {"session_code": session_code, "session_name": "Morning Gate", "is_active": True, "total_logs": 3, "recognized": 2, "cooldown": 1, "unknown": 0, "last_event_at": datetime.now(timezone.utc).isoformat()}

    async def logs(self, session_code: str):
        return {"session_code": session_code, "items": []}


def build_app(attendance_limit: int = 3, attendance_window: int = 60) -> FastAPI:
    from app.core.rate_limiter import InMemoryRateLimiter

    limiter = InMemoryRateLimiter(max_attempts=attendance_limit, window_seconds=attendance_window)

    async def fake_rate_limit(request: Request) -> None:
        from fastapi import HTTPException
        client_ip = request.client.host if request.client else "unknown"
        if not limiter.is_allowed(f"attendance:{client_ip}"):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many attendance requests. Please try again later.",
            )

    app = FastAPI()
    app.include_router(attendance_router)
    app.dependency_overrides[get_recognition_service] = lambda: FakeRecognitionService()
    app.dependency_overrides[get_attendance_read_service] = lambda: FakeAttendanceReadService()
    app.dependency_overrides[rate_limit_attendance_dependency] = fake_rate_limit
    return app


def test_attendance_preview_normal_request() -> None:
    client = TestClient(build_app())
    frames = [{"frame_b64": "ZmFrZS1mcmFtZS1ieXRlcy1mYWtlLWZyYW1lLWJ5dGVz", "pose_hint": None}] * 3
    response = client.post("/attendance/preview", json={
        "device_code": "gate-a01",
        "frames": frames,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["recognition_status"] == "recognized"


def test_attendance_confirm_normal_request() -> None:
    client = TestClient(build_app())
    response = client.post("/attendance/confirm", json={
        "person_id": str(uuid4()),
        "session_code": "morning-gate",
        "device_code": "gate-a01",
        "confidence": 0.82,
        "captured_face_b64_or_uri": None,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "accepted"


def test_attendance_preview_rate_limit_exceeded() -> None:
    client = TestClient(build_app(attendance_limit=3, attendance_window=60))
    frames = [{"frame_b64": "ZmFrZS1mcmFtZS1ieXRlcy1mYWtlLWZyYW1lLWJ5dGVz", "pose_hint": None}] * 3
    for _ in range(3):
        resp = client.post("/attendance/preview", json={
            "device_code": "gate-a01",
            "frames": frames,
        })
        assert resp.status_code == 200

    resp = client.post("/attendance/preview", json={
        "device_code": "gate-a01",
        "frames": frames,
    })
    assert resp.status_code == 429
    assert "Too many attendance requests" in resp.json()["detail"]


def test_attendance_confirm_rate_limit_exceeded() -> None:
    client = TestClient(build_app(attendance_limit=2, attendance_window=60))
    for _ in range(2):
        resp = client.post("/attendance/confirm", json={
            "person_id": str(uuid4()),
            "session_code": "morning-gate",
            "device_code": "gate-a01",
            "confidence": 0.82,
            "captured_face_b64_or_uri": None,
        })
        assert resp.status_code == 200

    resp = client.post("/attendance/confirm", json={
        "person_id": str(uuid4()),
        "session_code": "morning-gate",
        "device_code": "gate-a01",
        "confidence": 0.82,
        "captured_face_b64_or_uri": None,
    })
    assert resp.status_code == 429


def test_attendance_rate_limit_separate_endpoints_share_counter() -> None:
    client = TestClient(build_app(attendance_limit=3, attendance_window=60))
    frames = [{"frame_b64": "ZmFrZS1mcmFtZS1ieXRlcy1mYWtlLWZyYW1lLWJ5dGVz", "pose_hint": None}] * 3
    resp1 = client.post("/attendance/preview", json={
        "device_code": "gate-a01",
        "frames": frames,
    })
    resp2 = client.post("/attendance/confirm", json={
        "person_id": str(uuid4()),
        "session_code": "morning-gate",
        "device_code": "gate-a01",
        "confidence": 0.82,
        "captured_face_b64_or_uri": None,
    })
    resp3 = client.post("/attendance/preview", json={
        "device_code": "gate-a01",
        "frames": frames,
    })
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp3.status_code == 200

    resp4 = client.post("/attendance/confirm", json={
        "person_id": str(uuid4()),
        "session_code": "morning-gate",
        "device_code": "gate-a01",
        "confidence": 0.82,
        "captured_face_b64_or_uri": None,
    })
    assert resp4.status_code == 429
