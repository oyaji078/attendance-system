from __future__ import annotations

import fnmatch
import json
from uuid import uuid4

import pytest

from services.attendance.cache import RedisStateCache


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self._scan_cursor: int = 0
        self._fail_next: bool = False

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        if self._fail_next:
            self._fail_next = False
            raise ConnectionError("Redis unavailable")
        self.store[key] = value

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def delete(self, *keys: str) -> None:
        if self._fail_next:
            self._fail_next = False
            raise ConnectionError("Redis unavailable")
        for key in keys:
            self.store.pop(key, None)

    async def exists(self, key: str) -> int:
        return int(key in self.store)

    async def ttl(self, key: str) -> int:
        return 10 if key in self.store else -2

    async def scan(self, cursor: int = 0, match: str = "*", count: int = 100) -> tuple[int, list[bytes]]:
        if self._fail_next:
            self._fail_next = False
            raise ConnectionError("Redis unavailable")
        all_keys = list(self.store.keys())
        pattern = match.replace("*", "*")
        matched = [k for k in all_keys if fnmatch.fnmatch(k, pattern)]
        start = cursor
        end = min(start + count, len(matched))
        batch = matched[start:end]
        next_cursor = end if end < len(matched) else 0
        return next_cursor, [k.encode() for k in batch]

    def fail_next_operation(self) -> None:
        self._fail_next = True


@pytest.mark.asyncio
async def test_invalidate_prefix_deletes_all_matching_keys() -> None:
    fake_redis = FakeRedis()
    cache = RedisStateCache(fake_redis, heartbeat_ttl_seconds=30, recent_match_ttl_seconds=15)

    await cache.set_cached("persons:25:0", {"items": []}, 30)
    await cache.set_cached("persons:50:0", {"items": []}, 30)
    await cache.set_cached("persons:75:150", {"items": []}, 30)
    await cache.set_cached("persons:100:200", {"items": []}, 30)
    await cache.set_cached("lecturers:25:0", {"items": []}, 30)

    await cache.invalidate_prefix("persons:")

    assert await cache.get_cached("persons:25:0") is None
    assert await cache.get_cached("persons:50:0") is None
    assert await cache.get_cached("persons:75:150") is None
    assert await cache.get_cached("persons:100:200") is None
    assert await cache.get_cached("lecturers:25:0") is not None


@pytest.mark.asyncio
async def test_invalidate_prefix_does_not_delete_unrelated_keys() -> None:
    fake_redis = FakeRedis()
    cache = RedisStateCache(fake_redis, heartbeat_ttl_seconds=30, recent_match_ttl_seconds=15)

    await cache.set_cached("persons:25:0", {"items": []}, 30)
    await cache.set_cached("metrics", {"total": 10}, 15)
    await cache.set_cached("devices_configs", [], 30)

    await cache.invalidate_prefix("lecturers:")

    assert await cache.get_cached("persons:25:0") is not None
    assert await cache.get_cached("metrics") is not None
    assert await cache.get_cached("devices_configs") is not None


@pytest.mark.asyncio
async def test_invalidate_prefix_handles_arbitrary_limit_offset() -> None:
    fake_redis = FakeRedis()
    cache = RedisStateCache(fake_redis, heartbeat_ttl_seconds=30, recent_match_ttl_seconds=15)

    arbitrary_keys = [
        "persons:1:0",
        "persons:75:150",
        "persons:33:66",
        "persons:100:500",
    ]
    for key in arbitrary_keys:
        await cache.set_cached(key, {"items": []}, 30)

    await cache.invalidate_prefix("persons:")

    for key in arbitrary_keys:
        assert await cache.get_cached(key) is None


@pytest.mark.asyncio
async def test_invalidate_prefix_redis_failure_does_not_raise() -> None:
    fake_redis = FakeRedis()
    cache = RedisStateCache(fake_redis, heartbeat_ttl_seconds=30, recent_match_ttl_seconds=15)

    await cache.set_cached("persons:25:0", {"items": []}, 30)
    fake_redis.fail_next_operation()

    await cache.invalidate_prefix("persons:")

    assert await cache.get_cached("persons:25:0") is not None


@pytest.mark.asyncio
async def test_prefix_invalidation_devices_configs() -> None:
    fake_redis = FakeRedis()
    cache = RedisStateCache(fake_redis, heartbeat_ttl_seconds=30, recent_match_ttl_seconds=15)

    await cache.set_cached("devices_configs", [], 30)
    await cache.set_cached("devices:gate-a01", {"code": "gate-a01"}, 30)
    await cache.set_cached("metrics", {"total": 10}, 15)

    await cache.invalidate_prefix("devices_configs")
    await cache.invalidate_prefix("devices:")

    assert await cache.get_cached("devices_configs") is None
    assert await cache.get_cached("devices:gate-a01") is None
    assert await cache.get_cached("metrics") is not None


@pytest.mark.asyncio
async def test_invalidate_prefix_empty_pattern() -> None:
    fake_redis = FakeRedis()
    cache = RedisStateCache(fake_redis, heartbeat_ttl_seconds=30, recent_match_ttl_seconds=15)

    await cache.set_cached("persons:25:0", {"items": []}, 30)

    await cache.invalidate_prefix("nonexistent:")

    assert await cache.get_cached("persons:25:0") is not None
