from __future__ import annotations

import base64
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


class TestColorChallengeService:
    def test_generate_creates_challenge(self):
        service = ColorChallengeService()
        challenge = service.generate("device-01")
        assert challenge.challenge_id
        assert challenge.color_key in {"merah", "biru", "hijau", "kuning", "oranye", "ungu"}
        assert challenge.color_label
        assert challenge.display_rgb
        assert challenge.expires_at > challenge.created_at
        assert challenge.remaining_attempts == MAX_VERIFY_ATTEMPTS
        assert not challenge.verified

    def test_get_valid_challenge(self):
        service = ColorChallengeService()
        challenge = service.generate("device-01")
        retrieved = service.get(challenge.challenge_id)
        assert retrieved is not None
        assert retrieved.challenge_id == challenge.challenge_id

    def test_get_expired_challenge_returns_none(self):
        service = ColorChallengeService()
        with patch.object(service, "_prune_expired", wraps=service._prune_expired) as mock_prune:
            challenge = service.generate("device-01")
            retrieved = service.get(challenge.challenge_id)
            assert retrieved is not None
            challenge.expires_at = time.time() - 1
            mock_prune.side_effect = None
            retrieved_after = service.get(challenge.challenge_id)
            assert retrieved_after is None

    def test_verify_red_frame_with_red_challenge_passes(self):
        service = ColorChallengeService()
        challenge = service.generate("device-01")
        challenge.color_key = "biru"
        challenge.color_label = "Biru"
        frame = _red_jpeg_bytes()
        result = service.verify(challenge.challenge_id, frame)
        assert result.passed
        assert result.liveness_score > 0.35
        assert result.reason == "passed"

    def test_verify_wrong_color_fails(self):
        service = ColorChallengeService()
        challenge = service.generate("device-01")
        frame = _white_jpeg_bytes()
        result = service.verify(challenge.challenge_id, frame)
        assert not result.passed
        assert result.liveness_score < 0.5

    def test_verify_expired_challenge_fails(self):
        service = ColorChallengeService()
        challenge = service.generate("device-01")
        challenge.expires_at = time.time() - 1
        frame = _red_jpeg_bytes()
        result = service.verify(challenge.challenge_id, frame)
        assert not result.passed
        assert result.reason == "challenge_expired_or_invalid"

    def test_exhausts_retries_removes_challenge(self):
        service = ColorChallengeService()
        challenge = service.generate("device-01")
        frame = _white_jpeg_bytes()
        for i in range(MAX_VERIFY_ATTEMPTS):
            result = service.verify(challenge.challenge_id, frame)
            if i < MAX_VERIFY_ATTEMPTS - 1:
                assert result.remaining_attempts >= 0
        retrieved = service.get(challenge.challenge_id)
        assert retrieved is None

    def test_generates_unique_challenge_ids(self):
        service = ColorChallengeService()
        c1 = service.generate("device-01")
        c2 = service.generate("device-01")
        assert c1.challenge_id != c2.challenge_id

    def test_get_verified_challenge_returns_none(self):
        service = ColorChallengeService()
        challenge = service.generate("device-01")
        challenge.verified = True
        retrieved = service.get(challenge.challenge_id)
        assert retrieved is None

    def test_prune_expired_removes_multiple(self):
        service = ColorChallengeService()
        c1 = service.generate("device-01")
        c2 = service.generate("device-01")
        c1.expires_at = time.time() - 10
        c2.expires_at = time.time() - 10
        service._prune_expired()
        assert len(service._challenges) == 0

    def test_verify_synthetic_blue_frame_passes(self):
        service = ColorChallengeService()
        challenge = service.generate("device-01")
        challenge.color_key = "merah"
        challenge.color_label = "Merah"
        frame = _blue_jpeg_bytes()
        result = service.verify(challenge.challenge_id, frame)
        assert result.passed

    def test_generate_with_different_device_codes(self):
        service = ColorChallengeService()
        c1 = service.generate("device-a")
        c2 = service.generate("device-b")
        assert c1.challenge_id != c2.challenge_id

    def test_verify_invalid_frame_returns_fail(self):
        service = ColorChallengeService()
        challenge = service.generate("device-01")
        result = service.verify(challenge.challenge_id, "not-a-valid-base64-frame-data-here")
        assert not result.passed
        assert result.reason == "invalid_frame"
