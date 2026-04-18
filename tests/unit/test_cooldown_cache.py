from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from services.attendance.cache import RedisStateCache


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)

    async def exists(self, key: str) -> int:
        return int(key in self.store)


@pytest.mark.asyncio
async def test_cooldown_round_trip() -> None:
    cache = RedisStateCache(FakeRedis(), heartbeat_ttl_seconds=30, recent_match_ttl_seconds=15)
    person_id = uuid4()
    assert await cache.is_on_cooldown("session-a", person_id) is False
    await cache.set_cooldown("session-a", person_id, seconds=10)
    assert await cache.is_on_cooldown("session-a", person_id) is True


@pytest.mark.asyncio
async def test_device_heartbeat_round_trip() -> None:
    cache = RedisStateCache(FakeRedis(), heartbeat_ttl_seconds=30, recent_match_ttl_seconds=15)
    captured_at = datetime.now(timezone.utc)
    await cache.set_device_heartbeat("gate-a01", queue_depth=2, agent_version="0.1.0", captured_at=captured_at)
    heartbeat = await cache.get_device_heartbeat("gate-a01")
    assert heartbeat is not None
    assert heartbeat["agent_version"] == "0.1.0"

