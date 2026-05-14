from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class LecturerWrite(BaseModel):
    lecturer_code: str = Field(min_length=1, max_length=64)
    full_name: str = Field(min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    department: str | None = Field(default=None, max_length=255)
    is_active: bool = True


class LecturerRead(LecturerWrite):
    lecturer_id: UUID
    created_at: datetime
    updated_at: datetime


class LecturerListResponse(BaseModel):
    items: list[LecturerRead]
    total: int = 0
    limit: int = 25
    offset: int = 0
    has_next: bool = False


class ClassWrite(BaseModel):
    class_code: str = Field(min_length=1, max_length=64)
    class_name: str = Field(min_length=1, max_length=255)
    lecturer_id: UUID | None = None
    description: str | None = None
    is_active: bool = True


class ClassRead(ClassWrite):
    class_id: UUID
    lecturer_name: str | None = None
    total_students: int = 0
    created_at: datetime
    updated_at: datetime


class ClassListResponse(BaseModel):
    items: list[ClassRead]
    total: int = 0
    limit: int = 25
    offset: int = 0
    has_next: bool = False


class NextIdResponse(BaseModel):
    id: str
