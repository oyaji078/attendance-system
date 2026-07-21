from __future__ import annotations

import base64
import json
import time
from unittest.mock import patch

import cv2
import numpy as np
import pytest

from services.liveness.color_challenge import CHALLENGE_TTL_SECONDS, MAX_VERIFY_ATTEMPTS, ColorChallengeService


def _red_jpeg_bytes() -> str:
    arr = np.zeros((200, 200, 3), dtype=np.uint8)
    arr[:, :] = (220, 50, 50)
    _, encoded = cv2.imencode(".jpg", arr, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    return base64.b64encode(encoded.tobytes()).decode("ascii")


def _blue_jpeg_bytes() -> str:
    arr = np.zeros((200, 200, 3), dtype=np.uint8)
    arr[:, :] = (50, 100, 220)
    _, encoded = cv2.imencode(".jpg", arr, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    return base64.b64encode(encoded.tobytes()).decode("ascii")


def _white_jpeg_bytes() -> str:
    arr = np.full((200, 200, 3), 240, dtype=np.uint8)
    _, encoded = cv2.imencode(".jpg", arr, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    return base64.b64encode(encoded.tobytes()).decode("ascii")


class FakeRedisCache:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self._fail_next: bool = False

    async def set_color_challenge(self, challenge_id: str, data: dict, ttl: int) -> None:
        if self._fail_next:
            self._fail_next = False
            raise ConnectionError("Redis unavailable")
        self.store[f"color-challenge:{challenge_id}"] = json.dumps(data)

    async def get_color_challenge(self, challenge_id: str) -> dict | None:
        if self._fail_next:
            self._fail_next = False
            raise ConnectionError("Redis unavailable")
        raw = self.store.get(f"color-challenge:{challenge_id}")
        return json.loads(raw) if raw else None

    async def delete_color_challenge(self, challenge_id: str) -> None:
        if self._fail_next:
            self._fail_next = False
            raise ConnectionError("Redis unavailable")
        self.store.pop(f"color-challenge:{challenge_id}", None)

    def fail_next_operation(self) -> None:
        self._fail_next = True


class TestColorChallengeService:
    @pytest.mark.asyncio
    async def test_generate_creates_challenge(self):
        service = ColorChallengeService()
        challenge = await service.generate("device-01")
        assert challenge.challenge_id
        assert challenge.color_key in {"merah", "biru", "hijau", "kuning", "oranye", "ungu"}
        assert challenge.color_label
        assert challenge.display_rgb
        assert challenge.expires_at > challenge.created_at
        assert challenge.remaining_attempts == MAX_VERIFY_ATTEMPTS
        assert not challenge.verified

    @pytest.mark.asyncio
    async def test_get_valid_challenge(self):
        service = ColorChallengeService()
        challenge = await service.generate("device-01")
        retrieved = await service.get(challenge.challenge_id)
        assert retrieved is not None
        assert retrieved.challenge_id == challenge.challenge_id

    @pytest.mark.asyncio
    async def test_get_expired_challenge_returns_none(self):
        service = ColorChallengeService()
        challenge = await service.generate("device-01")
        retrieved = await service.get(challenge.challenge_id)
        assert retrieved is not None
        challenge.expires_at = time.time() - 1
        retrieved_after = await service.get(challenge.challenge_id)
        assert retrieved_after is None

    @pytest.mark.asyncio
    async def test_verify_red_frame_with_red_challenge_passes(self):
        service = ColorChallengeService()
        challenge = await service.generate("device-01")
        service._challenges[challenge.challenge_id].color_key = "biru"
        service._challenges[challenge.challenge_id].color_label = "Biru"
        frame = _red_jpeg_bytes()
        result = await service.verify(challenge.challenge_id, frame)
        assert result.passed
        assert result.liveness_score > 0.35
        assert result.reason == "passed"

    @pytest.mark.asyncio
    async def test_verify_wrong_color_fails(self):
        service = ColorChallengeService()
        challenge = await service.generate("device-01")
        frame = _white_jpeg_bytes()
        result = await service.verify(challenge.challenge_id, frame)
        assert not result.passed
        assert result.liveness_score < 0.5

    @pytest.mark.asyncio
    async def test_verify_expired_challenge_fails(self):
        service = ColorChallengeService()
        challenge = await service.generate("device-01")
        service._challenges[challenge.challenge_id].expires_at = time.time() - 1
        frame = _red_jpeg_bytes()
        result = await service.verify(challenge.challenge_id, frame)
        assert not result.passed
        assert result.reason == "challenge_expired_or_invalid"

    @pytest.mark.asyncio
    async def test_exhausts_retries_removes_challenge(self):
        service = ColorChallengeService()
        challenge = await service.generate("device-01")
        frame = _white_jpeg_bytes()
        for i in range(MAX_VERIFY_ATTEMPTS):
            result = await service.verify(challenge.challenge_id, frame)
            if i < MAX_VERIFY_ATTEMPTS - 1:
                assert result.remaining_attempts >= 0
        retrieved = await service.get(challenge.challenge_id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_generates_unique_challenge_ids(self):
        service = ColorChallengeService()
        c1 = await service.generate("device-01")
        c2 = await service.generate("device-01")
        assert c1.challenge_id != c2.challenge_id

    @pytest.mark.asyncio
    async def test_get_verified_challenge_returns_none(self):
        service = ColorChallengeService()
        challenge = await service.generate("device-01")
        service._challenges[challenge.challenge_id].verified = True
        retrieved = await service.get(challenge.challenge_id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_verify_synthetic_blue_frame_passes(self):
        service = ColorChallengeService()
        challenge = await service.generate("device-01")
        service._challenges[challenge.challenge_id].color_key = "merah"
        service._challenges[challenge.challenge_id].color_label = "Merah"
        frame = _blue_jpeg_bytes()
        result = await service.verify(challenge.challenge_id, frame)
        assert result.passed

    @pytest.mark.asyncio
    async def test_generate_with_different_device_codes(self):
        service = ColorChallengeService()
        c1 = await service.generate("device-a")
        c2 = await service.generate("device-b")
        assert c1.challenge_id != c2.challenge_id

    @pytest.mark.asyncio
    async def test_verify_invalid_frame_returns_fail(self):
        service = ColorChallengeService()
        challenge = await service.generate("device-01")
        result = await service.verify(challenge.challenge_id, "not-a-valid-base64-frame-data-here")
        assert not result.passed
        assert result.reason == "invalid_frame"


class TestColorChallengeServiceRedis:
    @pytest.mark.asyncio
    async def test_generate_stores_payload_in_redis(self):
        fake_cache = FakeRedisCache()
        service = ColorChallengeService(cache=fake_cache)
        challenge = await service.generate("device-01")
        raw = fake_cache.store.get(f"color-challenge:{challenge.challenge_id}")
        assert raw is not None
        data = json.loads(raw)
        assert data["challenge_id"] == challenge.challenge_id
        assert data["color_key"] == challenge.color_key

    @pytest.mark.asyncio
    async def test_verify_reads_payload_from_redis(self):
        fake_cache = FakeRedisCache()
        service = ColorChallengeService(cache=fake_cache)
        challenge = await service.generate("device-01")
        data = json.loads(fake_cache.store[f"color-challenge:{challenge.challenge_id}"])
        data["color_key"] = "biru"
        data["color_label"] = "Biru"
        fake_cache.store[f"color-challenge:{challenge.challenge_id}"] = json.dumps(data)
        frame = _red_jpeg_bytes()
        result = await service.verify(challenge.challenge_id, frame)
        assert result.passed

    @pytest.mark.asyncio
    async def test_challenge_verifiable_across_two_service_instances(self):
        fake_cache = FakeRedisCache()
        service_a = ColorChallengeService(cache=fake_cache)
        service_b = ColorChallengeService(cache=fake_cache)
        challenge = await service_a.generate("device-01")
        data = json.loads(fake_cache.store[f"color-challenge:{challenge.challenge_id}"])
        data["color_key"] = "biru"
        data["color_label"] = "Biru"
        fake_cache.store[f"color-challenge:{challenge.challenge_id}"] = json.dumps(data)
        frame = _red_jpeg_bytes()
        result = await service_b.verify(challenge.challenge_id, frame)
        assert result.passed

    @pytest.mark.asyncio
    async def test_expired_challenge_fails(self):
        fake_cache = FakeRedisCache()
        service = ColorChallengeService(cache=fake_cache)
        challenge = await service.generate("device-01")
        data = json.loads(fake_cache.store[f"color-challenge:{challenge.challenge_id}"])
        data["expires_at"] = time.time() - 1
        fake_cache.store[f"color-challenge:{challenge.challenge_id}"] = json.dumps(data)
        frame = _red_jpeg_bytes()
        result = await service.verify(challenge.challenge_id, frame)
        assert not result.passed
        assert result.reason == "challenge_expired_or_invalid"

    @pytest.mark.asyncio
    async def test_missing_challenge_fails(self):
        fake_cache = FakeRedisCache()
        service = ColorChallengeService(cache=fake_cache)
        frame = _red_jpeg_bytes()
        result = await service.verify("nonexistent-challenge-id", frame)
        assert not result.passed
        assert result.reason == "challenge_expired_or_invalid"

    @pytest.mark.asyncio
    async def test_redis_failure_fails_closed(self):
        fake_cache = FakeRedisCache()
        service = ColorChallengeService(cache=fake_cache)
        challenge = await service.generate("device-01")
        challenge.color_key = "biru"
        challenge.color_label = "Biru"
        frame = _red_jpeg_bytes()
        fake_cache.fail_next_operation()
        result = await service.verify(challenge.challenge_id, frame)
        assert not result.passed
        assert result.reason == "challenge_expired_or_invalid"

    @pytest.mark.asyncio
    async def test_successful_verify_deletes_challenge_from_redis(self):
        fake_cache = FakeRedisCache()
        service = ColorChallengeService(cache=fake_cache)
        challenge = await service.generate("device-01")
        data = json.loads(fake_cache.store[f"color-challenge:{challenge.challenge_id}"])
        data["color_key"] = "biru"
        data["color_label"] = "Biru"
        fake_cache.store[f"color-challenge:{challenge.challenge_id}"] = json.dumps(data)
        frame = _red_jpeg_bytes()
        result = await service.verify(challenge.challenge_id, frame)
        assert result.passed
        raw = fake_cache.store.get(f"color-challenge:{challenge.challenge_id}")
        assert raw is None

    @pytest.mark.asyncio
    async def test_failed_verify_updates_remaining_attempts_in_redis(self):
        fake_cache = FakeRedisCache()
        service = ColorChallengeService(cache=fake_cache)
        challenge = await service.generate("device-01")
        frame = _white_jpeg_bytes()
        await service.verify(challenge.challenge_id, frame)
        raw = fake_cache.store.get(f"color-challenge:{challenge.challenge_id}")
        assert raw is not None
        data = json.loads(raw)
        assert data["remaining_attempts"] == MAX_VERIFY_ATTEMPTS - 1

    @pytest.mark.asyncio
    async def test_redis_generate_failure_falls_back_to_in_memory(self):
        fake_cache = FakeRedisCache()
        service = ColorChallengeService(cache=fake_cache)
        fake_cache.fail_next_operation()
        challenge = await service.generate("device-01")
        assert challenge.challenge_id is not None
        assert challenge.challenge_id in service._challenges

    @pytest.mark.asyncio
    async def test_ttl_matches_challenge_ttl_constant(self):
        fake_cache = FakeRedisCache()
        service = ColorChallengeService(cache=fake_cache)
        challenge = await service.generate("device-01")
        raw = fake_cache.store.get(f"color-challenge:{challenge.challenge_id}")
        assert raw is not None
        data = json.loads(raw)
        expected_expires = challenge.created_at + CHALLENGE_TTL_SECONDS
        assert abs(data["expires_at"] - expected_expires) < 1.0
