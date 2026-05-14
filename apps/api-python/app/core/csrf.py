from __future__ import annotations

import secrets
import time
import logging
from typing import Any

from fastapi import HTTPException, Request, status
from redis.asyncio import Redis

LOGGER = logging.getLogger(__name__)

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"


class CsrfProtection:
    def __init__(self, redis: Redis | None, secret_key: str, ttl_seconds: int = 3600) -> None:
        self._redis = redis
        self._secret_key = secret_key
        self._ttl_seconds = ttl_seconds
        self._local_store: dict[str, float] = {}

    async def generate_token(self) -> str:
        token = secrets.token_urlsafe(32)
        if self._redis is not None:
            await self._redis.setex(f"csrf:{token}", self._ttl_seconds, "1")
        else:
            self._local_store[token] = time.time() + self._ttl_seconds
        return token

    async def validate_token(self, token: str) -> bool:
        if not token:
            return False
        if self._redis is not None:
            exists = await self._redis.get(f"csrf:{token}")
            return exists is not None
        expiry = self._local_store.get(token, 0.0)
        return expiry >= time.time()

    async def invalidate_token(self, token: str) -> None:
        if not token:
            return
        if self._redis is not None:
            await self._redis.delete(f"csrf:{token}")
        else:
            self._local_store.pop(token, None)


async def csrf_dependency(request: Request) -> None:
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return

    csrf_header = request.headers.get(CSRF_HEADER_NAME, "")
    csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME, "")

    container = getattr(request.app.state, "container", None)
    csrf = getattr(container, "csrf_protection", None)
    if csrf is None:
        return

    if not csrf_header or not csrf_cookie or csrf_header != csrf_cookie:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token tidak valid. Silakan login ulang.",
        )

    if not await csrf.validate_token(csrf_header):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token tidak valid. Silakan login ulang.",
        )
