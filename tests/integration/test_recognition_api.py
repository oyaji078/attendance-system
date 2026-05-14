from __future__ import annotations

from uuid import uuid4

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.recognition import router as recognition_router
from app.core.dependencies import get_recognition_service


class FakeRecognitionService:
    async def recognize(self, request, event_type: str, require_session: bool = False):
        assert event_type == "recognition_attempt"
        assert require_session is False
        assert len(request.frames) == 3
        return {"decision": "accepted", "reason": "multi_frame_confirm_passed", "recognition_status": "recognized", "confirmed_frames": 2, "device_code": request.device_code, "session_code": request.session_code, "person": {"person_id": str(uuid4()), "student_id": "ST-1001", "full_name": "Ada Lovelace", "template_id": str(uuid4())}, "confidence": 0.91, "top_candidates": []}


def build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(recognition_router)
    app.dependency_overrides[get_recognition_service] = lambda: FakeRecognitionService()
    return app


def test_recognition_endpoint_uses_three_frames() -> None:
    client = TestClient(build_app())
    response = client.post("/recognize", json={"device_code": "gate-a01", "session_code": None, "frames": [{"frame_b64": "ZmFrZS1mcmFtZS1ieXRlcy1mYWtlLWZyYW1lLWJ5dGVz", "pose_hint": None}, {"frame_b64": "ZmFrZS1mcmFtZS1ieXRlcy1mYWtlLWZyYW1lLWJ5dGVz", "pose_hint": None}, {"frame_b64": "ZmFrZS1mcmFtZS1ieXRlcy1mYWtlLWZyYW1lLWJ5dGVz", "pose_hint": None}]})
    assert response.status_code == 200
    assert response.json()["decision"] == "accepted"
    assert response.json()["recognition_status"] == "recognized"
