from __future__ import annotations

from datetime import datetime, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from db.domain.attendance import normalize_session_kind
from db.schemas.common import SessionKind

VALID_REPEAT_DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


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
    repeat_days: list[str] | None = None
    start_time: time | None = None
    end_time: time | None = None
    timezone: str = "Asia/Makassar"
    is_active: bool = True

    @field_validator("session_kind", mode="before")
    @classmethod
    def normalize_kind(cls, value: object) -> SessionKind:
        return normalize_session_kind(value)

    @field_validator("repeat_days", mode="before")
    @classmethod
    def normalize_repeat_days(cls, value: object) -> list[str] | None:
        if value is None:
            return None
        if isinstance(value, str):
            value = [d.strip().lower() for d in value.split(",") if d.strip()]
        normalized = [d.lower() for d in value if d.lower() in VALID_REPEAT_DAYS]
        return sorted(set(normalized)) or None

    @model_validator(mode="after")
    def validate_window(self) -> "AttendanceSessionWrite":
        if self.session_code is not None:
            self.session_code = self.session_code.strip() or None
        if self.starts_at is not None and self.ends_at is not None and self.ends_at < self.starts_at:
            raise ValueError("ends_at must be greater than or equal to starts_at")
        if self.start_time is not None and self.end_time is not None and self.end_time <= self.start_time:
            raise ValueError("end_time must be greater than start_time")
        recurring_fields = (self.repeat_days, self.start_time, self.end_time)
        any_recurring = any(field is not None for field in recurring_fields)
        if any_recurring:
            if not self.repeat_days:
                raise ValueError("repeat_days harus berisi minimal satu hari saat menggunakan jadwal berulang")
            if self.start_time is None:
                raise ValueError("start_time wajib diisi saat menggunakan jadwal berulang")
            if self.end_time is None:
                raise ValueError("end_time wajib diisi saat menggunakan jadwal berulang")
            if self.class_id is None:
                raise ValueError("class_id wajib diisi saat menggunakan jadwal berulang")
            if not self.timezone:
                self.timezone = "Asia/Makassar"
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
    repeat_days: list[str] | None = None
    start_time: time | None = None
    end_time: time | None = None
    timezone: str = "Asia/Makassar"
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
    repeat_days: list[str] | None = None
    start_time: time | None = None
    end_time: time | None = None
    timezone: str = "Asia/Makassar"


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
