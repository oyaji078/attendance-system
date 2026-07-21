from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from db.domain.attendance import normalize_attendance_decision, normalize_attendance_event_type, normalize_attendance_reason
from db.schemas.common import AttendanceDecision, AttendanceEventType, FrameInput, PersonSummary
from db.schemas.attendance_sessions import ResolvedAttendanceSession
from db.schemas.recognition import RecognitionResponse


class AttendanceCheckinRequest(BaseModel):
    session_code: str = Field(min_length=1, max_length=64)
    device_code: str = Field(min_length=1, max_length=64)
    frames: list[FrameInput] = Field(min_length=3, max_length=3)


class AttendancePreviewRequest(BaseModel):
    device_code: str = Field(min_length=1, max_length=64)
    frames: list[FrameInput] = Field(min_length=3, max_length=3)
    session_id: str | None = Field(default=None, max_length=64)


class AttendanceConfirmRequest(BaseModel):
    person_id: UUID
    session_code: str = Field(min_length=1, max_length=64)
    device_code: str = Field(min_length=1, max_length=64)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    captured_face_b64_or_uri: str | None = None
    recognition_token: str | None = None


class AttendanceStatusResponse(BaseModel):
    session_code: str
    session_name: str
    is_active: bool
    total_logs: int
    recognized: int
    cooldown: int
    unknown: int
    last_event_at: datetime | None


class AttendanceLogItem(BaseModel):
    id: UUID
    student_id: str | None
    full_name: str | None
    decision: AttendanceDecision
    reason: str
    confidence: float | None
    device_code: str
    event_type: AttendanceEventType
    created_at: datetime

    @field_validator("decision", mode="before")
    @classmethod
    def normalize_decision(cls, value: object) -> AttendanceDecision:
        return normalize_attendance_decision(value)

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: object) -> str:
        return normalize_attendance_reason(value)

    @field_validator("event_type", mode="before")
    @classmethod
    def normalize_event_type(cls, value: object) -> AttendanceEventType:
        return normalize_attendance_event_type(value)


class AttendanceLogsResponse(BaseModel):
    session_code: str
    items: list[AttendanceLogItem]


class AttendanceCheckinResponse(RecognitionResponse):
    pass


class AttendancePreviewResponse(RecognitionResponse):
    pass


class AttendanceRecordRead(BaseModel):
    log_id: UUID
    student_id: str
    full_name: str
    email: str | None = None
    class_id: UUID | None = None
    class_name: str | None = None
    session_code: str
    session_name: str
    lecturer_name: str | None = None
    decision: AttendanceDecision
    status: str
    confidence: float | None = None
    device_code: str
    created_at: datetime

    @field_validator("decision", mode="before")
    @classmethod
    def normalize_decision(cls, value: object) -> AttendanceDecision:
        return normalize_attendance_decision(value)


class AttendanceConfirmResponse(BaseModel):
    decision: AttendanceDecision
    reason: str
    device_code: str
    confidence: float | None = None
    cooldown_remaining_seconds: int | None = None
    person: PersonSummary | None = None
    resolved_session: ResolvedAttendanceSession | None = None
    attendance: AttendanceRecordRead | None = None

    @field_validator("decision", mode="before")
    @classmethod
    def normalize_decision(cls, value: object) -> AttendanceDecision:
        return normalize_attendance_decision(value)

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: object) -> str:
        return normalize_attendance_reason(value)
