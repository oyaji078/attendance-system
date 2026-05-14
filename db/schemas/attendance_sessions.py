from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from db.domain.attendance import normalize_session_kind
from db.schemas.common import SessionKind


class AttendanceSessionWrite(BaseModel):
    session_code: str | None = Field(default=None, max_length=64)
    session_name: str = Field(min_length=1, max_length=255)
    session_kind: SessionKind = "other"
    class_id: UUID | None = None
    lecturer_id: UUID | None = None
    device_code: str | None = Field(default=None, max_length=64)
    cooldown_seconds: int = Field(default=30, ge=0, le=3600)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool = True

    @field_validator("session_kind", mode="before")
    @classmethod
    def normalize_kind(cls, value: object) -> SessionKind:
        return normalize_session_kind(value)

    @model_validator(mode="after")
    def validate_window(self) -> "AttendanceSessionWrite":
        if self.session_code is not None:
            self.session_code = self.session_code.strip() or None
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
    session_kind: SessionKind
    class_id: UUID | None = None
    class_code: str | None = None
    class_name: str | None = None
    lecturer_id: UUID | None = None
    lecturer_name: str | None = None
    device_code: str | None = None
    is_active: bool
    is_deleted: bool = False
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
    deleted_at: datetime | None = None


class AttendanceSessionPublicRead(BaseModel):
    session_id: UUID
    session_code: str
    session_name: str
    session_kind: SessionKind
    class_id: UUID | None = None
    class_code: str | None = None
    class_name: str | None = None
    lecturer_name: str | None = None
    is_active: bool
    starts_at: datetime | None
    ends_at: datetime | None


class ResolvedAttendanceSession(BaseModel):
    session_id: UUID
    session_code: str
    session_name: str
    class_id: UUID | None = None
    class_name: str | None = None
    lecturer_id: UUID | None = None
    lecturer_name: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None


class AttendanceSessionListResponse(BaseModel):
    items: list[AttendanceSessionRead]
    total: int = 0
    limit: int = 25
    offset: int = 0
    has_next: bool = False


class AttendanceSessionNextCodeResponse(BaseModel):
    session_code: str
