from __future__ import annotations

from uuid import uuid4

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.enrollment import router as enrollment_router
from app.core.dependencies import get_enrollment_service


class FakeEnrollmentService:
    async def start(self, request):
        return {"enrollment_session_id": str(uuid4()), "person_id": str(uuid4()), "required_poses": ["front", "left_20", "right_20", "up_or_down"], "accepted_per_pose": 4, "remaining_per_pose": {"front": 4, "left_20": 4, "right_20": 4, "up_or_down": 4}}

    async def process_frame(self, request):
        return {
            "enrollment_session_id": str(request.enrollment_session_id),
            "accepted": True,
            "reason": "accepted",
            "pose": request.pose,
            "pose_accepted_count": 1,
            "total_accepted_count": 1,
            "remaining_per_pose": {"front": 3, "left_20": 4, "right_20": 4, "up_or_down": 4},
            "next_pose": "front",
            "pose_valid": True,
            "ui_hint": "Good capture. Hold steady and capture again.",
            "progress_percent": 6.25,
            "capture_status": "accepted",
            "quality": {
                "brightness_score": 100.0,
                "blur_score": 120.0,
                "contrast_score": 42.0,
                "overexposed_ratio": 0.02,
                "underexposed_ratio": 0.01,
                "liveness_score": 0.80,
                "face_width_px": 180,
                "face_center_offset_x": 0.03,
                "face_center_offset_y": 0.02,
                "pose_yaw": 0.0,
                "pose_pitch": 0.0,
                "pose_roll": 0.0,
                "pose_valid": True,
                "accepted": True,
                "reason": "accepted",
                "ui_hint": "Good lighting and pose.",
                "flags": {"exactly_one_face": True},
            },
        }

    async def finish(self, request):
        return {"enrollment_session_id": str(request.enrollment_session_id), "person_id": str(uuid4()), "template_id": str(uuid4()), "total_samples": 16, "activated": True}

    async def rebuild_template(self, person_id):
        return {"enrollment_session_id": str(uuid4()), "person_id": str(person_id), "template_id": str(uuid4()), "total_samples": 16, "activated": True}


def build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(enrollment_router)
    app.dependency_overrides[get_enrollment_service] = lambda: FakeEnrollmentService()
    return app


def test_enrollment_api_flow() -> None:
    client = TestClient(build_app())
    start = client.post("/enroll/start", json={"student_id": "ST-1001", "full_name": "Ada Lovelace", "email": "ada@example.edu", "device_code": "gate-a01"})
    session_id = start.json()["enrollment_session_id"]
    frame = client.post("/enroll/frame", json={"enrollment_session_id": session_id, "device_code": "gate-a01", "pose": "front", "frame_b64": "ZmFrZS1mcmFtZS1ieXRlcy1mYWtlLWZyYW1lLWJ5dGVz"})
    finish = client.post("/enroll/finish", json={"enrollment_session_id": session_id})
    assert start.status_code == 200
    assert frame.status_code == 200
    assert finish.status_code == 200


def test_template_rebuild_endpoint() -> None:
    client = TestClient(build_app())
    person_id = str(uuid4())
    response = client.post(f"/enroll/rebuild-template/{person_id}")
    assert response.status_code == 200
    assert response.json()["person_id"] == person_id
