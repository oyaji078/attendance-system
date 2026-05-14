from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DeviceConfigWrite(BaseModel):
    device_name: str = Field(min_length=1, max_length=255)
    location_hint: str | None = Field(default=None, max_length=255)
    det_thresh: float = Field(default=0.60, ge=0.10, le=0.99)
    det_size: tuple[int, int] = Field(default=(320, 320))
    max_faces: int = Field(default=1, ge=1, le=4)
    min_face_width_px: int = Field(default=130, ge=32, le=2048)
    min_brightness: float = Field(default=75.0, ge=0.0, le=255.0)
    min_blur_score: float = Field(default=90.0, ge=0.0)
    similarity_threshold: float = Field(default=0.45, ge=0.0, le=1.0)
    candidate_margin_threshold: float = Field(default=0.05, ge=0.0, le=1.0)
    liveness_threshold: float = Field(default=0.70, ge=0.0, le=1.0)
    multi_frame_confirm: int = Field(default=2, ge=1, le=3)
    accepted_per_pose: int = Field(default=2, ge=1, le=10)
    cooldown_seconds: int = Field(default=30, ge=0, le=3600)
    is_enabled: bool = True

    @field_validator("det_size")
    @classmethod
    def validate_det_size(cls, value: tuple[int, int]) -> tuple[int, int]:
        if len(value) != 2 or value[0] <= 0 or value[1] <= 0:
            raise ValueError("det_size must contain exactly two positive integers")
        return value


class DeviceHeartbeatWrite(BaseModel):
    agent_version: str = Field(min_length=1, max_length=64)
    queue_depth: int = Field(ge=0, le=100000)
    captured_at: datetime


class DeviceHeartbeatRead(BaseModel):
    device_code: str
    agent_version: str
    queue_depth: int
    captured_at: datetime
    seen_at: datetime


class DeviceConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    device_code: str
    device_name: str
    location_hint: str | None
    det_thresh: float
    det_size: list[int]
    max_faces: int
    min_face_width_px: int
    min_brightness: float
    min_blur_score: float
    similarity_threshold: float
    candidate_margin_threshold: float
    liveness_threshold: float
    multi_frame_confirm: int
    accepted_per_pose: int
    cooldown_seconds: int
    is_enabled: bool
    updated_at: datetime
    heartbeat: DeviceHeartbeatRead | None = None
