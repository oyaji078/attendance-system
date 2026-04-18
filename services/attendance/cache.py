from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

from redis.asyncio import Redis

from services.recognition.types import EnrollmentState


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
        )

    async def clear_enrollment_state(self, enrollment_session_id: UUID) -> None:
        await self.redis.delete(self._enrollment_key(enrollment_session_id))

    async def set_cooldown(self, session_code: str, person_id: UUID, seconds: int) -> None:
        await self.redis.set(self._cooldown_key(session_code, person_id), "1", ex=seconds)

    async def is_on_cooldown(self, session_code: str, person_id: UUID) -> bool:
        return await self.redis.exists(self._cooldown_key(session_code, person_id)) == 1

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

