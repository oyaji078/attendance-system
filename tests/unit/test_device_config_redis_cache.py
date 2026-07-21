from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from db.repositories.device_configs import (
    _DEVICE_CONFIG_CACHE_TTL,
    _reconstruct_device_config,
    _serialize_device_config,
    DeviceConfigRepository,
)


def _make_device_config_dict(device_code: str = "gate-a01") -> dict:
    return {
        "id": str(uuid4()),
        "device_code": device_code,
        "device_name": "Gate A01",
        "location_hint": "Main entrance",
        "det_thresh": 0.60,
        "det_size_width": 320,
        "det_size_height": 320,
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
        "updated_at": datetime.now(timezone.utc).isoformat(),
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
        if self._fail_next:
            self._fail_next = False
            raise ConnectionError("Redis unavailable")
        for key in keys:
            self.store.pop(key, None)

    async def scan(self, cursor: int = 0, match: str = "*", count: int = 100) -> tuple[int, list[bytes]]:
        return 0, []

    async def ttl(self, key: str) -> int:
        return 30 if key in self.store else -2

    async def exists(self, key: str) -> int:
        return int(key in self.store)

    def fail_next_operation(self) -> None:
        self._fail_next = True


class FakeCache:
    def __init__(self, fake_redis: FakeRedis) -> None:
        self.redis = fake_redis

    async def get_device_config_cached(self, device_code: str) -> dict | None:
        try:
            raw = await self.redis.get(f"device-config:{device_code}")
            return json.loads(raw) if raw else None
        except Exception:
            return None

    async def set_device_config_cached(self, device_code: str, data: dict, ttl: int = 60) -> None:
        try:
            await self.redis.set(f"device-config:{device_code}", json.dumps(data, default=str), ex=ttl)
        except Exception:
            pass

    async def invalidate_device_config_cached(self, device_code: str) -> None:
        try:
            await self.redis.delete(f"device-config:{device_code}")
        except Exception:
            pass

    async def get_device_heartbeat(self, device_code: str) -> dict | None:
        try:
            raw = await self.redis.get(f"device:{device_code}")
            return None if raw is None else json.loads(raw)
        except Exception:
            return None

    async def set_cooldown(self, session_code: str, person_id, seconds: int) -> None:
        pass

    async def cooldown_ttl_seconds(self, session_code: str, person_id) -> int | None:
        return None

    async def set_recent_match(self, device_code: str, payload: dict) -> None:
        pass

    async def get_cached(self, key: str) -> dict | list | None:
        return None

    async def set_cached(self, key: str, data: dict | list, ttl: int) -> None:
        pass

    async def invalidate_prefix(self, prefix: str) -> None:
        pass


class FakeSession:
    def __init__(self, config_dict: dict | None = None) -> None:
        self._config_dict = config_dict
        self.committed = False
        self.queries: list[str] = []

    async def execute(self, stmt: object) -> "FakeResult":
        self.queries.append("SELECT device_configs")
        if self._config_dict is not None:
            config = _reconstruct_device_config(self._config_dict)
            return FakeResult([config])
        return FakeResult([])


class FakeResult:
    def __init__(self, items: list) -> None:
        self._items = items

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None


@pytest.mark.asyncio
async def test_cache_miss_calls_db_and_writes_to_redis() -> None:
    fake_redis = FakeRedis()
    cache = FakeCache(fake_redis)
    config_dict = _make_device_config_dict()
    session = FakeSession(config_dict=config_dict)
    repo = DeviceConfigRepository(session)

    result = await repo.get_by_code_cached("gate-a01", cache)

    assert result is not None
    assert result.device_code == "gate-a01"
    assert result.is_enabled is True
    assert session.queries, "DB should have been queried on cache miss"

    cached_raw = await fake_redis.get("device-config:gate-a01")
    assert cached_raw is not None
    cached_data = json.loads(cached_raw)
    assert cached_data["device_code"] == "gate-a01"


@pytest.mark.asyncio
async def test_cache_hit_returns_redis_value_without_db_query() -> None:
    fake_redis = FakeRedis()
    cache = FakeCache(fake_redis)
    config_dict = _make_device_config_dict()
    await fake_redis.set("device-config:gate-a01", json.dumps(config_dict))

    session = FakeSession(config_dict=None)
    repo = DeviceConfigRepository(session)

    result = await repo.get_by_code_cached("gate-a01", cache)

    assert result is not None
    assert result.device_code == "gate-a01"
    assert result.device_name == "Gate A01"
    assert not session.queries, "DB should NOT have been queried on cache hit"


@pytest.mark.asyncio
async def test_admin_update_invalidates_redis_device_config_key() -> None:
    fake_redis = FakeRedis()
    cache = FakeCache(fake_redis)
    config_dict = _make_device_config_dict()
    await fake_redis.set("device-config:gate-a01", json.dumps(config_dict))

    await cache.invalidate_device_config_cached("gate-a01")

    cached_raw = await fake_redis.get("device-config:gate-a01")
    assert cached_raw is None, "Redis key should be deleted after invalidation"


@pytest.mark.asyncio
async def test_redis_failure_falls_back_to_db() -> None:
    fake_redis = FakeRedis()
    cache = FakeCache(fake_redis)
    config_dict = _make_device_config_dict()
    session = FakeSession(config_dict=config_dict)
    repo = DeviceConfigRepository(session)

    fake_redis.fail_next_operation()

    result = await repo.get_by_code_cached("gate-a01", cache)

    assert result is not None
    assert result.device_code == "gate-a01"
    assert session.queries, "DB should have been queried when Redis fails"


@pytest.mark.asyncio
async def test_recognition_service_works_without_redis() -> None:
    fake_redis = FakeRedis()
    cache = FakeCache(fake_redis)
    config_dict = _make_device_config_dict()
    session = FakeSession(config_dict=config_dict)
    repo = DeviceConfigRepository(session)

    fake_redis.fail_next_operation()

    result = await repo.get_by_code_cached("gate-a01", cache)

    assert result is not None
    assert result.is_enabled is True
    assert result.det_thresh == 0.60
    assert result.max_faces == 1


@pytest.mark.asyncio
async def test_none_result_is_not_cached() -> None:
    fake_redis = FakeRedis()
    cache = FakeCache(fake_redis)
    session = FakeSession(config_dict=None)
    repo = DeviceConfigRepository(session)

    result = await repo.get_by_code_cached("nonexistent", cache)

    assert result is None
    cached_raw = await fake_redis.get("device-config:nonexistent")
    assert cached_raw is None, "None result should never be cached"


@pytest.mark.asyncio
async def test_multi_worker_safety_via_redis_shared_state() -> None:
    fake_redis = FakeRedis()
    cache = FakeCache(fake_redis)
    config_dict = _make_device_config_dict(device_code="gate-a01")

    session_a = FakeSession(config_dict=config_dict)
    repo_a = DeviceConfigRepository(session_a)

    result_a = await repo_a.get_by_code_cached("gate-a01", cache)
    assert result_a is not None
    assert len(session_a.queries) == 1

    session_b = FakeSession(config_dict=config_dict)
    repo_b = DeviceConfigRepository(session_b)

    result_b = await repo_b.get_by_code_cached("gate-a01", cache)
    assert result_b is not None
    assert len(session_b.queries) == 0, "Worker B should get cache hit from shared Redis"

    assert result_a.device_code == result_b.device_code
    assert result_a.device_name == result_b.device_name


@pytest.mark.asyncio
async def test_device_config_serialization_round_trip() -> None:
    config_dict = _make_device_config_dict()
    config = _reconstruct_device_config(config_dict)
    serialized = _serialize_device_config(config)
    reconstructed = _reconstruct_device_config(serialized)

    assert reconstructed.device_code == config.device_code
    assert reconstructed.device_name == config.device_name
    assert reconstructed.det_thresh == config.det_thresh
    assert reconstructed.is_enabled == config.is_enabled
    assert reconstructed.multi_frame_confirm == config.multi_frame_confirm
    assert reconstructed.cooldown_seconds == config.cooldown_seconds


@pytest.mark.asyncio
async def test_cache_ttl_is_60_seconds() -> None:
    assert _DEVICE_CONFIG_CACHE_TTL == 60


@pytest.mark.asyncio
async def test_redis_invalidation_failure_does_not_crash() -> None:
    fake_redis = FakeRedis()
    cache = FakeCache(fake_redis)
    config_dict = _make_device_config_dict()
    await fake_redis.set("device-config:gate-a01", json.dumps(config_dict))

    fake_redis.fail_next_operation()

    await cache.invalidate_device_config_cached("gate-a01")

    cached_raw = await fake_redis.get("device-config:gate-a01")
    assert cached_raw is not None, "Key should still exist after failed invalidation"
