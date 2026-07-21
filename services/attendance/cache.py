from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from redis.asyncio import Redis

from services.recognition.types import EnrollmentState

logger = logging.getLogger(__name__)

SCAN_BATCH_SIZE = 100
DELETE_BATCH_SIZE = 50


class RedisStateCache:
    def __init__(self, redis: Redis, heartbeat_ttl_seconds: int, recent_match_ttl_seconds: int) -> None:
        self.redis = redis
        self.heartbeat_ttl_seconds = heartbeat_ttl_seconds
        self.recent_match_ttl_seconds = recent_match_ttl_seconds

    async def set_enrollment_state(self, state: EnrollmentState, ttl_seconds: int = 3600) -> None:
        payload = {
            "enrollment_session_id": str(state.enrollment_session_id),
            "person_id": str(state.person_id),
            "student_id": state.student_id,
            "full_name": state.full_name,
            "device_code": state.device_code,
            "accepted_counts": state.accepted_counts,
            "rejected_counts": state.rejected_counts,
            "started_at": state.started_at.isoformat(),
        }
        await self.redis.set(self._enrollment_key(state.enrollment_session_id), json.dumps(payload), ex=ttl_seconds)

    async def get_enrollment_state(self, enrollment_session_id: UUID) -> EnrollmentState | None:
        raw = await self.redis.get(self._enrollment_key(enrollment_session_id))
        if raw is None:
            return None
        payload = json.loads(raw)
        return EnrollmentState(
            enrollment_session_id=UUID(payload["enrollment_session_id"]),
            person_id=UUID(payload["person_id"]),
            student_id=payload["student_id"],
            full_name=payload["full_name"],
            device_code=payload["device_code"],
            accepted_counts={key: int(value) for key, value in payload["accepted_counts"].items()},
            started_at=datetime.fromisoformat(payload["started_at"]),
            rejected_counts={key: int(value) for key, value in payload.get("rejected_counts", {}).items()},
        )

    async def clear_enrollment_state(self, enrollment_session_id: UUID) -> None:
        await self.redis.delete(self._enrollment_key(enrollment_session_id))

    async def set_cooldown(self, session_code: str, person_id: UUID, seconds: int) -> None:
        await self.redis.set(self._cooldown_key(session_code, person_id), "1", ex=seconds)

    async def acquire_cooldown(self, session_code: str, person_id: UUID, seconds: int) -> bool:
        """Atomically start a cooldown; False when one is already active.

        SET NX closes the check-then-set race where two concurrent requests
        both observe "no cooldown" and both proceed as accepted.
        """
        result = await self.redis.set(self._cooldown_key(session_code, person_id), "1", ex=seconds, nx=True)
        return result is not None

    async def cooldown_ttl_seconds(self, session_code: str, person_id: UUID) -> int | None:
        ttl = await self.redis.ttl(self._cooldown_key(session_code, person_id))
        return ttl if ttl > 0 else None

    async def set_recent_match(self, device_code: str, payload: dict[str, object]) -> None:
        await self.redis.set(self._recent_match_key(device_code), json.dumps(payload), ex=self.recent_match_ttl_seconds)

    async def get_recent_match(self, device_code: str) -> dict[str, object] | None:
        raw = await self.redis.get(self._recent_match_key(device_code))
        return None if raw is None else json.loads(raw)

    async def set_device_heartbeat(self, device_code: str, queue_depth: int, agent_version: str, captured_at: datetime) -> None:
        payload = {
            "device_code": device_code,
            "queue_depth": queue_depth,
            "agent_version": agent_version,
            "captured_at": captured_at.isoformat(),
            "seen_at": datetime.now(timezone.utc).isoformat(),
        }
        await self.redis.set(self._device_key(device_code), json.dumps(payload), ex=self.heartbeat_ttl_seconds)

    async def get_device_heartbeat(self, device_code: str) -> dict[str, object] | None:
        raw = await self.redis.get(self._device_key(device_code))
        return None if raw is None else json.loads(raw)

    @staticmethod
    def _enrollment_key(enrollment_session_id: UUID) -> str:
        return f"enrollment:{enrollment_session_id}"

    @staticmethod
    def _cooldown_key(session_code: str, person_id: UUID) -> str:
        return f"cooldown:{session_code}:{person_id}"

    @staticmethod
    def _recent_match_key(device_code: str) -> str:
        return f"recent-match:{device_code}"

    @staticmethod
    def _device_key(device_code: str) -> str:
        return f"device:{device_code}"

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

    async def invalidate_cached(self, key: str) -> None:
        try:
            await self.redis.delete(f"admin-cache:{key}")
        except Exception:
            pass

    async def invalidate_prefix(self, prefix: str) -> None:
        try:
            pattern = f"admin-cache:{prefix}*"
            cursor = 0
            while True:
                cursor, keys = await self.redis.scan(cursor=cursor, match=pattern, count=SCAN_BATCH_SIZE)
                if keys:
                    decoded = [k.decode() if isinstance(k, bytes) else k for k in keys]
                    for i in range(0, len(decoded), DELETE_BATCH_SIZE):
                        batch = decoded[i : i + DELETE_BATCH_SIZE]
                        await self.redis.delete(*batch)
                if cursor == 0:
                    break
        except Exception:
            logger.warning("Failed to invalidate cache prefix: %s", prefix)

    async def get_device_config_cached(self, device_code: str) -> dict | None:
        try:
            raw = await self.redis.get(f"device-config:{device_code}")
            return json.loads(raw) if raw else None
        except Exception:
            logger.warning("Failed to read device config cache for %s", device_code)
            return None

    async def set_device_config_cached(self, device_code: str, data: dict, ttl: int = 60) -> None:
        try:
            await self.redis.set(f"device-config:{device_code}", json.dumps(data, default=str), ex=ttl)
        except Exception:
            logger.warning("Failed to write device config cache for %s", device_code)

    async def invalidate_device_config_cached(self, device_code: str) -> None:
        try:
            await self.redis.delete(f"device-config:{device_code}")
        except Exception:
            logger.warning("Failed to invalidate device config cache for %s", device_code)

    async def set_color_challenge(self, challenge_id: str, data: dict, ttl: int) -> None:
        try:
            await self.redis.set(f"color-challenge:{challenge_id}", json.dumps(data, default=str), ex=ttl)
        except Exception:
            logger.warning("Failed to store color challenge %s", challenge_id)
            raise

    async def get_color_challenge(self, challenge_id: str) -> dict | None:
        try:
            raw = await self.redis.get(f"color-challenge:{challenge_id}")
            return json.loads(raw) if raw else None
        except Exception:
            logger.warning("Failed to read color challenge %s", challenge_id)
            raise

    async def delete_color_challenge(self, challenge_id: str) -> None:
        try:
            await self.redis.delete(f"color-challenge:{challenge_id}")
        except Exception:
            logger.warning("Failed to delete color challenge %s", challenge_id)
