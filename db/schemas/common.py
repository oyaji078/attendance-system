from __future__ import annotations

import base64
import binascii
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


PoseName = Literal["front", "left_20", "right_20", "up_or_down"]
DecisionType = Literal["recognized", "unknown", "rejected", "cooldown", "session_inactive"]
REQUIRED_POSES: tuple[PoseName, ...] = ("front", "left_20", "right_20", "up_or_down")


class FrameInput(BaseModel):
    frame_b64: str = Field(min_length=32)
    pose_hint: PoseName | None = None
    captured_at: datetime | None = None

    @field_validator("frame_b64")
    @classmethod
    def validate_frame_b64(cls, value: str) -> str:
        payload = value.split(",", maxsplit=1)[-1]
        try:
            decoded = base64.b64decode(payload, validate=True)
        except binascii.Error as exc:
            raise ValueError("frame_b64 must be valid base64") from exc
        if not decoded:
            raise ValueError("frame_b64 must not decode to empty bytes")
        return value


class PersonSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    person_id: UUID
    student_id: str
    full_name: str
    template_id: UUID | None = None


class QualitySnapshot(BaseModel):
    brightness_score: float
    blur_score: float
    liveness_score: float
    face_width_px: int
    accepted: bool
    reason: str
    flags: dict[str, bool]

