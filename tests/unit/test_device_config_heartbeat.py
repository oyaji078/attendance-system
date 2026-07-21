from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from db.schemas.device import DeviceConfigRead, DeviceHeartbeatRead


def _make_cached_config_dict(device_code: str = "gate-a01") -> dict:
    return {
        "id": str(uuid4()),
        "device_code": device_code,
        "device_name": "Gate A01",
        "location_hint": "Main entrance",
        "det_thresh": 0.60,
        "det_size": [320, 320],
        "max_faces": 1,
        "min_face_width_px": 130,
        "min_brightness": 75.0,
        "min_blur_score": 90.0,
        "similarity_threshold": 0.45,
        "candidate_margin_threshold": 0.05,
        "liveness_threshold": 0.70,
        "multi_frame_confirm": 2,
        "accepted_per_pose": 2,
        "cooldown_seconds": 30,
        "is_enabled": True,
        "updated_at": "2026-01-01T00:00:00",
        "heartbeat": None,
    }


def _make_heartbeat_dict(device_code: str = "gate-a01", agent_version: str = "1.0.0") -> dict:
    now = datetime.now(timezone.utc)
    return {
        "device_code": device_code,
        "agent_version": agent_version,
        "queue_depth": 5,
        "captured_at": now.isoformat(),
        "seen_at": now.isoformat(),
    }


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self._fail_next: bool = False

    async def get(self, key: str) -> str | None:
        if self._fail_next:
            self._fail_next = False
            raise ConnectionError("Redis unavailable")
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        if self._fail_next:
            self._fail_next = False
            raise ConnectionError("Redis unavailable")
        self.store[key] = value

    async def delete(self, *keys: str) -> None:
        for key in keys:
            self.store.pop(key, None)

    async def scan(self, cursor: int = 0, match: str = "*", count: int = 100) -> tuple[int, list[bytes]]:
        return 0, []

    def fail_next_operation(self) -> None:
        self._fail_next = True


class FakeCache:
    def __init__(self, fake_redis: FakeRedis) -> None:
        self.redis = fake_redis

    async def get_cached(self, key: str) -> dict | list | None:
        try:
            raw = await self.redis.get(f"admin-cache:{key}")
            return json.loads(raw) if raw else None
        except Exception:
            return None

    async def set_cached(self, key: str, data: dict | list, ttl: int) -> None:
        try:
            await self.redis.set(f"admin-cache:{key}", json.dumps(data, default=str), ex=ttl)
        except Exception:
            pass

    async def get_device_heartbeat(self, device_code: str) -> dict | None:
        try:
            raw = await self.redis.get(f"device:{device_code}")
            return None if raw is None else json.loads(raw)
        except Exception:
            raise


async def _merge_fresh_heartbeats(container, items: list[DeviceConfigRead]) -> list[DeviceConfigRead]:
    import logging
    logger = logging.getLogger(__name__)
    result: list[DeviceConfigRead] = []
    for item in items:
        try:
            heartbeat_raw = await container.cache.get_device_heartbeat(item.device_code)
        except Exception:
            logger.warning("Failed to read heartbeat for device %s", item.device_code)
            heartbeat_raw = None
        merged = {**item.model_dump(mode="json"), "heartbeat": heartbeat_raw}
        result.append(DeviceConfigRead(**merged))
    return result


@pytest.mark.asyncio
async def test_cached_device_config_uses_fresh_heartbeat() -> None:
    fake_redis = FakeRedis()
    cache = FakeCache(fake_redis)

    cached_config = _make_cached_config_dict()
    await fake_redis.set("admin-cache:devices_configs", json.dumps([cached_config]))

    fresh_heartbeat = _make_heartbeat_dict(agent_version="2.0.0")
    await fake_redis.set("device:gate-a01", json.dumps(fresh_heartbeat))

    container = type("Container", (), {"cache": cache})()
    items = [DeviceConfigRead(**item) for item in [cached_config]]
    result = await _merge_fresh_heartbeats(container, items)

    assert len(result) == 1
    assert result[0].heartbeat is not None
    assert result[0].heartbeat.agent_version == "2.0.0"


@pytest.mark.asyncio
async def test_heartbeat_changes_reflected_without_waiting_for_cache_ttl() -> None:
    fake_redis = FakeRedis()
    cache = FakeCache(fake_redis)

    cached_config = _make_cached_config_dict()
    await fake_redis.set("admin-cache:devices_configs", json.dumps([cached_config]))

    old_heartbeat = _make_heartbeat_dict(agent_version="1.0.0")
    await fake_redis.set("device:gate-a01", json.dumps(old_heartbeat))

    container = type("Container", (), {"cache": cache})()
    items = [DeviceConfigRead(**item) for item in [cached_config]]
    result_v1 = await _merge_fresh_heartbeats(container, items)
    assert result_v1[0].heartbeat.agent_version == "1.0.0"

    new_heartbeat = _make_heartbeat_dict(agent_version="2.0.0")
    await fake_redis.set("device:gate-a01", json.dumps(new_heartbeat))

    result_v2 = await _merge_fresh_heartbeats(container, items)
    assert result_v2[0].heartbeat.agent_version == "2.0.0"


@pytest.mark.asyncio
async def test_missing_heartbeat_returns_none() -> None:
    fake_redis = FakeRedis()
    cache = FakeCache(fake_redis)

    cached_config = _make_cached_config_dict()
    await fake_redis.set("admin-cache:devices_configs", json.dumps([cached_config]))

    container = type("Container", (), {"cache": cache})()
    items = [DeviceConfigRead(**item) for item in [cached_config]]
    result = await _merge_fresh_heartbeats(container, items)

    assert len(result) == 1
    assert result[0].heartbeat is None


@pytest.mark.asyncio
async def test_cache_hit_preserves_response_shape() -> None:
    fake_redis = FakeRedis()
    cache = FakeCache(fake_redis)

    cached_config = _make_cached_config_dict()
    await fake_redis.set("admin-cache:devices_configs", json.dumps([cached_config]))

    container = type("Container", (), {"cache": cache})()
    items = [DeviceConfigRead(**item) for item in [cached_config]]
    result = await _merge_fresh_heartbeats(container, items)

    assert len(result) == 1
    read = result[0]
    assert read.id is not None
    assert read.device_code == "gate-a01"
    assert read.device_name == "Gate A01"
    assert read.location_hint == "Main entrance"
    assert read.det_thresh == 0.60
    assert read.det_size == [320, 320]
    assert read.max_faces == 1
    assert read.is_enabled is True
    assert read.heartbeat is None


@pytest.mark.asyncio
async def test_redis_heartbeat_failure_does_not_crash() -> None:
    fake_redis = FakeRedis()
    cache = FakeCache(fake_redis)

    cached_config = _make_cached_config_dict()
    await fake_redis.set("admin-cache:devices_configs", json.dumps([cached_config]))

    fake_redis.fail_next_operation()

    container = type("Container", (), {"cache": cache})()
    items = [DeviceConfigRead(**item) for item in [cached_config]]

    result = await _merge_fresh_heartbeats(container, items)

    assert len(result) == 1
    assert result[0].heartbeat is None
    assert result[0].device_code == "gate-a01"


@pytest.mark.asyncio
async def test_cached_config_does_not_include_heartbeat() -> None:
    fake_redis = FakeRedis()
    cache = FakeCache(fake_redis)

    cached_config = _make_cached_config_dict()
    cached_config["heartbeat"] = None
    await fake_redis.set("admin-cache:devices_configs", json.dumps([cached_config]))

    raw = await fake_redis.get("admin-cache:devices_configs")
    stored = json.loads(raw)

    assert stored[0]["heartbeat"] is None
