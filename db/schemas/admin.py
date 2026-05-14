from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AdminActionResponse(BaseModel):
    status: str
    detail: str


class AdminMetricsResponse(BaseModel):
    total_persons: int
    active_persons: int
    total_students: int
    total_lecturers: int
    total_classes: int
    total_enrollments: int
    today_attendance_count: int
    unknown_failed_count: int
    total_templates: int
    total_samples: int
    total_logs: int
    recognized_last_24h: int


class AdminPersonResponse(BaseModel):
    person_id: UUID
    student_id: str
    full_name: str
    is_active: bool
    class_code: str | None = None
    class_name: str | None = None
    primary_template_id: UUID | None
    sample_count: int
    active_template_version: int | None
    last_seen_at: datetime | None
