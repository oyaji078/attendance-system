from __future__ import annotations

import base64
import logging
import time
import uuid
from dataclasses import dataclass

import cv2
import numpy as np

CHALLENGE_TTL_SECONDS: int = 45
MAX_VERIFY_ATTEMPTS: int = 3

COLOR_DEFINITIONS: dict[str, tuple[np.ndarray, np.ndarray, str]] = {
    "merah": (
        np.array([0, 50, 50], dtype=np.uint8),
        np.array([10, 255, 255], dtype=np.uint8),
        "Merah",
    ),
    "biru": (
        np.array([100, 50, 50], dtype=np.uint8),
        np.array([130, 255, 255], dtype=np.uint8),
        "Biru",
    ),
    "hijau": (
        np.array([40, 50, 50], dtype=np.uint8),
        np.array([80, 255, 255], dtype=np.uint8),
        "Hijau",
    ),
    "kuning": (
        np.array([20, 50, 50], dtype=np.uint8),
        np.array([35, 255, 255], dtype=np.uint8),
        "Kuning",
    ),
    "oranye": (
        np.array([5, 50, 50], dtype=np.uint8),
        np.array([18, 255, 255], dtype=np.uint8),
        "Oranye",
    ),
    "ungu": (
        np.array([130, 50, 50], dtype=np.uint8),
        np.array([160, 255, 255], dtype=np.uint8),
        "Ungu",
    ),
}

DISPLAY_COLORS: dict[str, tuple[int, int, int]] = {
    "merah": (220, 50, 50),
    "biru": (50, 100, 220),
    "hijau": (50, 180, 50),
    "kuning": (220, 200, 50),
    "oranye": (220, 140, 50),
    "ungu": (160, 60, 200),
}

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ColorChallenge:
    challenge_id: str
    color_key: str
    color_label: str
    display_rgb: tuple[int, int, int]
    created_at: float
    expires_at: float
    remaining_attempts: int = MAX_VERIFY_ATTEMPTS
    verified: bool = False


@dataclass(slots=True)
class ChallengeResult:
    passed: bool
    liveness_score: float
    reason: str
    remaining_attempts: int
    color_present_ratio: float


def decode_frame_b64(frame_b64: str) -> np.ndarray:
    raw = cv2.imdecode(np.frombuffer(base64.b64decode(frame_b64), dtype=np.uint8), cv2.IMREAD_COLOR)
    if raw is None:
        raise ValueError("invalid frame data")
    return raw


def _challenge_to_dict(challenge: ColorChallenge) -> dict:
    return {
        "challenge_id": challenge.challenge_id,
        "color_key": challenge.color_key,
        "color_label": challenge.color_label,
        "display_rgb": list(challenge.display_rgb),
        "created_at": challenge.created_at,
        "expires_at": challenge.expires_at,
        "remaining_attempts": challenge.remaining_attempts,
        "verified": challenge.verified,
    }


def _dict_to_challenge(data: dict) -> ColorChallenge:
    display = data["display_rgb"]
    if isinstance(display, list):
        display = tuple(display)
    return ColorChallenge(
        challenge_id=data["challenge_id"],
        color_key=data["color_key"],
        color_label=data["color_label"],
        display_rgb=display,
        created_at=float(data["created_at"]),
        expires_at=float(data["expires_at"]),
        remaining_attempts=int(data.get("remaining_attempts", MAX_VERIFY_ATTEMPTS)),
        verified=bool(data.get("verified", False)),
    )


class ColorChallengeService:
    def __init__(self, cache: object | None = None) -> None:
        self._cache = cache
        self._challenges: dict[str, ColorChallenge] = {}

    def _prune_expired(self) -> None:
        now = time.time()
        expired = [cid for cid, c in self._challenges.items() if c.expires_at < now]
        for cid in expired:
            del self._challenges[cid]

    async def generate(self, device_code: str) -> ColorChallenge:
        color_keys = list(COLOR_DEFINITIONS.keys())
        color_key = color_keys[uuid.uuid4().int % len(color_keys)]
        now = time.time()
        challenge = ColorChallenge(
            challenge_id=str(uuid.uuid4()),
            color_key=color_key,
            color_label=COLOR_DEFINITIONS[color_key][2],
            display_rgb=DISPLAY_COLORS[color_key],
            created_at=now,
            expires_at=now + CHALLENGE_TTL_SECONDS,
        )
        if self._cache is not None:
            try:
                await self._cache.set_color_challenge(challenge.challenge_id, _challenge_to_dict(challenge), CHALLENGE_TTL_SECONDS)
            except Exception:
                logger.warning("Failed to store color challenge in Redis, falling back to in-memory: %s", challenge.challenge_id)
                self._prune_expired()
                self._challenges[challenge.challenge_id] = challenge
        else:
            self._prune_expired()
            self._challenges[challenge.challenge_id] = challenge
        return challenge

    async def get(self, challenge_id: str) -> ColorChallenge | None:
        if self._cache is not None:
            try:
                data = await self._cache.get_color_challenge(challenge_id)
                if data is None:
                    return None
                challenge = _dict_to_challenge(data)
                if challenge.expires_at < time.time():
                    await self._cache.delete_color_challenge(challenge_id)
                    return None
                if challenge.verified:
                    return None
                return challenge
            except Exception:
                logger.warning("Redis unavailable for color challenge lookup, falling back to in-memory: %s", challenge_id)
        self._prune_expired()
        challenge = self._challenges.get(challenge_id)
        if challenge is None:
            return None
        if challenge.expires_at < time.time():
            del self._challenges[challenge_id]
            return None
        if challenge.verified:
            return None
        return challenge

    async def verify(self, challenge_id: str, frame_b64: str, *, min_color_ratio: float = 0.04) -> ChallengeResult:
        challenge = await self.get(challenge_id)
        if challenge is None:
            return ChallengeResult(passed=False, liveness_score=0.0, reason="challenge_expired_or_invalid", remaining_attempts=0, color_present_ratio=0.0)
        challenge.remaining_attempts -= 1
        if challenge.remaining_attempts <= 0:
            if self._cache is not None:
                try:
                    await self._cache.delete_color_challenge(challenge_id)
                except Exception:
                    pass
            self._challenges.pop(challenge_id, None)
        try:
            frame = decode_frame_b64(frame_b64)
        except ValueError:
            return ChallengeResult(passed=False, liveness_score=0.0, reason="invalid_frame", remaining_attempts=challenge.remaining_attempts, color_present_ratio=0.0)
        lower, upper, _ = COLOR_DEFINITIONS[challenge.color_key]
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, lower, upper)
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        color_pixels = int(cv2.countNonZero(mask))
        total_pixels = frame.shape[0] * frame.shape[1]
        color_ratio = color_pixels / max(total_pixels, 1)
        brightness = float(np.mean(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))) / 255.0
        blur = float(cv2.Laplacian(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())
        blur_normalized = min(1.0, blur / 150.0)
        brightness_normalized = 1.0 - min(abs(brightness - 0.5) / 0.5, 1.0)
        passive_score = round((0.55 * blur_normalized) + (0.45 * brightness_normalized), 4)
        color_score = min(1.0, color_ratio / min_color_ratio)
        liveness_score = round(0.4 * passive_score + 0.6 * color_score, 4)
        passed = color_ratio >= min_color_ratio and liveness_score >= 0.35
        if passed:
            challenge.verified = True
            if self._cache is not None:
                try:
                    await self._cache.delete_color_challenge(challenge_id)
                except Exception:
                    pass
            else:
                self._challenges.pop(challenge_id, None)
        else:
            if self._cache is not None and challenge.remaining_attempts > 0:
                try:
                    await self._cache.set_color_challenge(challenge_id, _challenge_to_dict(challenge), CHALLENGE_TTL_SECONDS)
                except Exception:
                    pass
            elif challenge.remaining_attempts > 0:
                self._challenges[challenge_id] = challenge
        return ChallengeResult(
            passed=passed,
            liveness_score=liveness_score,
            reason="passed" if passed else f"color_ratio_{color_ratio:.3f}_below_{min_color_ratio:.2f}",
            remaining_attempts=challenge.remaining_attempts,
            color_present_ratio=round(color_ratio, 4),
        )
