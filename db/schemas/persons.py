from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PersonCreateRequest(BaseModel):
    student_id: str = Field(min_length=1, max_length=64)
    full_name: str = Field(min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    is_active: bool = False


class PersonUpdateRequest(BaseModel):
    student_id: str = Field(min_length=1, max_length=64)
    full_name: str = Field(min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=255)


class PersonRead(BaseModel):
    person_id: UUID
    student_id: str
    full_name: str
    email: str | None
    is_active: bool
    primary_template_id: UUID | None
    sample_count: int
    active_template_version: int | None
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PersonListResponse(BaseModel):
    items: list[PersonRead]
