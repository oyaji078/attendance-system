from __future__ import annotations

from pydantic import BaseModel, Field

from db.schemas.common import MAX_FRAME_B64_LENGTH


class ChallengeRequest(BaseModel):
    device_code: str = Field(min_length=1, max_length=64)


class ChallengeResponse(BaseModel):
    challenge_id: str
    color_key: str
    color_label: str
    display_rgb: tuple[int, int, int]
    expires_at_seconds: int


class ChallengeVerifyRequest(BaseModel):
    challenge_id: str = Field(min_length=1, max_length=64)
    device_code: str = Field(min_length=1, max_length=64)
    frame_b64: str = Field(min_length=32, max_length=MAX_FRAME_B64_LENGTH)


class ChallengeVerifyResponse(BaseModel):
    challenge_id: str
    passed: bool
    liveness_score: float
    reason: str
    remaining_attempts: int
    color_present_ratio: float
