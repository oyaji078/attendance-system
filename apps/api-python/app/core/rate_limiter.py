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


# Multiple kiosks often share one public IP (NAT/tunnel). ML and attendance
# quotas are therefore keyed per device_code when the payload carries one, so
# one busy kiosk cannot starve the others. A wider per-IP umbrella (this
# multiplier x the device quota) still caps a client that rotates fake device
# codes from a single address.
IP_UMBRELLA_MULTIPLIER = 5


async def _request_device_code(request: Request) -> str | None:
    if request.method not in ("POST", "PUT", "PATCH"):
        return None
    try:
        payload = await request.json()
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    device_code = payload.get("device_code")
    if isinstance(device_code, str) and 0 < len(device_code) <= 64:
        return device_code
    return None


async def _enforce_device_scoped_limit(
    request: Request,
    *,
    scope: str,
    max_attempts: int,
    window_seconds: int,
    detail: str,
) -> None:
    client_ip = client_ip_for(request)
    device_code = await _request_device_code(request)
    limiter = _build_rate_limiter(request, max_attempts, window_seconds)
    primary_key = f"{scope}:device:{device_code}" if device_code else f"{scope}:{client_ip}"
    if not await _async_is_allowed(limiter, primary_key):
        LOGGER.warning("rate_limit_exceeded", extra={"client_ip": client_ip, "key_type": scope, "device_code": device_code})
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)
    if device_code:
        umbrella = _build_rate_limiter(request, max_attempts * IP_UMBRELLA_MULTIPLIER, window_seconds)
        if not await _async_is_allowed(umbrella, f"{scope}:ip-umbrella:{client_ip}"):
            LOGGER.warning("rate_limit_exceeded", extra={"client_ip": client_ip, "key_type": f"{scope}-ip-umbrella"})
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)


def client_ip_for(request: Request) -> str:
    """The address rate limits are counted against.

    Reads X-Forwarded-For only when ``TRUST_PROXY_HEADERS`` is on, because an
    untrusted client can set that header to any value it likes.
    """
    from app.core.config import get_settings

    direct = request.client.host if request.client else "unknown"
    if not get_settings().trust_proxy_headers:
        return direct
    forwarded = request.headers.get("x-forwarded-for") or ""
    first_hop = forwarded.split(",")[0].strip()
    return first_hop or direct


async def rate_limit_login_dependency(request: Request) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    client_ip = client_ip_for(request)
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
    await _enforce_device_scoped_limit(
        request,
        scope="ml",
        max_attempts=settings.ml_rate_limit_max,
        window_seconds=settings.ml_rate_limit_window_seconds,
        detail="Too many requests. Please try again later.",
    )


async def rate_limit_enrollment_dependency(request: Request) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    client_ip = client_ip_for(request)
    limiter = _build_rate_limiter(request, settings.enrollment_rate_limit_max, settings.enrollment_rate_limit_window_seconds)
    if not await _async_is_allowed(limiter, f"enrollment:{client_ip}"):
        LOGGER.warning("rate_limit_exceeded", extra={"client_ip": client_ip, "key_type": "enrollment"})
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
        )


async def rate_limit_attendance_dependency(request: Request) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    await _enforce_device_scoped_limit(
        request,
        scope="attendance",
        max_attempts=settings.attendance_rate_limit_max,
        window_seconds=settings.attendance_rate_limit_window_seconds,
        detail="Too many attendance requests. Please try again later.",
    )
