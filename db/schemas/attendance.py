from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from db.schemas.common import FrameInput
from db.schemas.recognition import RecognitionResponse


class AttendanceCheckinRequest(BaseModel):
    session_code: str = Field(min_length=1, max_length=64)
    device_code: str = Field(min_length=1, max_length=64)
    frames: list[FrameInput] = Field(min_length=3, max_length=3)


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
    decision: str
    reason: str
    confidence: float | None
    device_code: str
    event_type: str
    created_at: datetime


class AttendanceLogsResponse(BaseModel):
    session_code: str
    items: list[AttendanceLogItem]


class AttendanceCheckinResponse(RecognitionResponse):
    pass

