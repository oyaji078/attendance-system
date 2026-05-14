from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field

from fastapi import HTTPException, Request, status
from redis.asyncio import Redis

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class InMemoryRateLimiter:
    max_attempts: int
    window_seconds: int
    _buckets: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        window_start = now - self.window_seconds
        timestamps = self._buckets.get(key, [])
        timestamps = [t for t in timestamps if t > window_start]
        if len(timestamps) >= self.max_attempts:
            self._buckets[key] = timestamps
            return False
        timestamps.append(now)
        self._buckets[key] = timestamps
        return True


class RedisRateLimiter:
    def __init__(self, redis: Redis, max_attempts: int, window_seconds: int) -> None:
        self._redis = redis
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds

    async def is_allowed(self, key: str) -> bool:
        now = int(time.time())
        window_key = f"ratelimit:{key}:{now // self.window_seconds}"
        count = await self._redis.incr(window_key)
        if count == 1:
            await self._redis.expire(window_key, self.window_seconds + 1)
        return count <= self.max_attempts


def _build_rate_limiter(
    request: Request, max_attempts: int, window_seconds: int
) -> InMemoryRateLimiter | RedisRateLimiter:
    container = getattr(request.app.state, "container", None)
    cache = getattr(container, "cache", None)
    redis_client = getattr(cache, "redis", None)
    if redis_client is not None:
        return RedisRateLimiter(redis_client, max_attempts, window_seconds)
    return InMemoryRateLimiter(max_attempts, window_seconds)


async def _async_is_allowed(limiter: InMemoryRateLimiter | RedisRateLimiter, key: str) -> bool:
    if isinstance(limiter, InMemoryRateLimiter):
        return limiter.is_allowed(key)
    return await limiter.is_allowed(key)


async def rate_limit_login_dependency(request: Request) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    client_ip = request.client.host if request.client else "unknown"
    limiter = _build_rate_limiter(request, settings.login_rate_limit_max, settings.login_rate_limit_window_seconds)
    if not await _async_is_allowed(limiter, f"ip:{client_ip}"):
        LOGGER.warning("rate_limit_exceeded", extra={"client_ip": client_ip, "key_type": "ip"})
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Terlalu banyak percobaan login. Silakan coba lagi nanti.",
        )


async def rate_limit_ml_dependency(request: Request) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    client_ip = request.client.host if request.client else "unknown"
    limiter = _build_rate_limiter(request, settings.ml_rate_limit_max, settings.ml_rate_limit_window_seconds)
    if not await _async_is_allowed(limiter, f"ml:{client_ip}"):
        LOGGER.warning("rate_limit_exceeded", extra={"client_ip": client_ip, "key_type": "ml"})
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
        )


async def rate_limit_enrollment_dependency(request: Request) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    client_ip = request.client.host if request.client else "unknown"
    limiter = _build_rate_limiter(request, settings.enrollment_rate_limit_max, settings.enrollment_rate_limit_window_seconds)
    if not await _async_is_allowed(limiter, f"enrollment:{client_ip}"):
        LOGGER.warning("rate_limit_exceeded", extra={"client_ip": client_ip, "key_type": "enrollment"})
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
        )
