from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from db.domain.attendance import normalize_attendance_reason
from db.schemas.common import AttendanceDecision, AttendanceEventType


class AttendanceLogAdminRead(BaseModel):
    log_id: UUID
    no: int
    student_id: str | None
    full_name: str | None
    email: str | None
    class_code: str | None
    class_name: str | None
    session_code: str | None
    decision: AttendanceDecision
    reason: str
    confidence: float | None
    device_code: str
    event_type: AttendanceEventType
    captured_image_url: str | None
    created_at: datetime


class AttendanceMatrixColumn(BaseModel):
    session_id: UUID | None
    session_code: str | None
    session_name: str | None
    date: datetime | None
    label: str


class AttendanceMatrixRow(BaseModel):
    student_id: str
    full_name: str
    cells: list[bool]


class ClassAttendanceMatrixResponse(BaseModel):
    class_id: UUID
    class_code: str
    class_name: str
    columns: list[AttendanceMatrixColumn]
    rows: list[AttendanceMatrixRow]
    student_count: int


class AttendanceLogListResponse(BaseModel):
    items: list[AttendanceLogAdminRead]
    total: int = 0
    limit: int = 25
    offset: int = 0
    has_next: bool = False


class AttendanceLogUpdateRequest(BaseModel):
    decision: AttendanceDecision
    reason: str = Field(min_length=1)

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: object) -> str:
        return normalize_attendance_reason(value)


class DeviceConfigListResponse(BaseModel):
    items: list[object]
    total: int = 0
    limit: int = 25
    offset: int = 0
    has_next: bool = False
