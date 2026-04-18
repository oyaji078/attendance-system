from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.admin import router as admin_router
from app.api.routes.devices import router as devices_router
from app.core.dependencies import get_container, get_session
from db.repositories.device_configs import DeviceConfigRepository


class FakeCache:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.last = {"device_code": "gate-a01", "agent_version": "0.1.0", "queue_depth": 0, "captured_at": now, "seen_at": now}

    async def set_device_heartbeat(self, device_code: str, queue_depth: int, agent_version: str, captured_at: datetime) -> None:
        self.last = {"device_code": device_code, "agent_version": agent_version, "queue_depth": queue_depth, "captured_at": captured_at.isoformat(), "seen_at": datetime.now(timezone.utc).isoformat()}

    async def get_device_heartbeat(self, device_code: str) -> dict[str, object]:
        payload = dict(self.last)
        payload["device_code"] = device_code
        return payload


class FakeSession:
    async def commit(self) -> None: return None
    async def refresh(self, _: object) -> None: return None


def fake_config() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(), device_code="gate-a01", device_name="Main Gate A01", location_hint="North gate",
        det_thresh=0.60, det_size_width=320, det_size_height=320, max_faces=1, min_face_width_px=160,
        min_brightness=75.0, min_blur_score=90.0, similarity_threshold=0.45, liveness_threshold=0.70,
        multi_frame_confirm=2, accepted_per_pose=4, cooldown_seconds=30, is_enabled=True, updated_at=datetime.now(timezone.utc)
    )


def build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(devices_router)
    app.include_router(admin_router)
    app.dependency_overrides[get_container] = lambda: SimpleNamespace(cache=FakeCache())

    async def override_session():
        yield FakeSession()

    app.dependency_overrides[get_session] = override_session
    return app


def test_device_config_get_put_and_heartbeat(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_by_code(self, device_code: str):
        assert device_code == "gate-a01"
        return fake_config()

    async def fake_upsert(self, device_code: str, payload: dict[str, object]):
        cfg = fake_config()
        cfg.device_code = device_code
        cfg.device_name = str(payload["device_name"])
        return cfg

    monkeypatch.setattr(DeviceConfigRepository, "get_by_code", fake_get_by_code)
    monkeypatch.setattr(DeviceConfigRepository, "upsert", fake_upsert)

    client = TestClient(build_app())
    assert client.get("/devices/config/gate-a01").status_code == 200
    heartbeat = client.post("/devices/heartbeat/gate-a01", json={"agent_version": "0.1.0", "queue_depth": 2, "captured_at": datetime.now(timezone.utc).isoformat()})
    updated = client.put("/admin/devices/config/gate-a01", json={"device_name": "Updated Gate", "location_hint": "North gate", "det_thresh": 0.60, "det_size": [320, 320], "max_faces": 1, "min_face_width_px": 160, "min_brightness": 75, "min_blur_score": 90, "similarity_threshold": 0.45, "liveness_threshold": 0.70, "multi_frame_confirm": 2, "accepted_per_pose": 4, "cooldown_seconds": 30, "is_enabled": True})
    assert heartbeat.status_code == 200
    assert heartbeat.json()["queue_depth"] == 2
    assert updated.status_code == 200

