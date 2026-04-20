from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class AttendanceSessionWrite(BaseModel):
    session_code: str = Field(min_length=1, max_length=64)
    session_name: str = Field(min_length=1, max_length=255)
    session_kind: str = Field(min_length=1, max_length=32)
    cooldown_seconds: int = Field(default=30, ge=0, le=3600)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def validate_window(self) -> "AttendanceSessionWrite":
        if self.starts_at is not None and self.ends_at is not None and self.ends_at < self.starts_at:
            raise ValueError("ends_at must be greater than or equal to starts_at")
        return self


class AttendanceSessionCreateRequest(AttendanceSessionWrite):
    pass


class AttendanceSessionUpdateRequest(AttendanceSessionWrite):
    pass


class AttendanceSessionRead(BaseModel):
    session_id: UUID
    session_code: str
    session_name: str
    session_kind: str
    is_active: bool
    cooldown_seconds: int
    starts_at: datetime | None
    ends_at: datetime | None
    total_logs: int
    recognized: int
    cooldown: int
    unknown: int
    last_event_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AttendanceSessionListResponse(BaseModel):
    items: list[AttendanceSessionRead]
