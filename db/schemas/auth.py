from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=255)


class AdminUserRead(BaseModel):
    admin_id: UUID
    username: str
    email: str | None
    full_name: str
    role: str = "admin"
    lecturer_id: UUID | None = None
    lecturer_name: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None


class AdminUserCreateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    email: str | None = Field(default=None, max_length=255)
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=255)
    role: str = Field(default="admin", max_length=32)
    lecturer_id: UUID | None = None
    is_active: bool = True


class AdminUserUpdateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    email: str | None = Field(default=None, max_length=255)
    full_name: str = Field(min_length=1, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=255)
    role: str = Field(default="admin", max_length=32)
    lecturer_id: UUID | None = None
    is_active: bool = True


class AdminUserListResponse(BaseModel):
    items: list[AdminUserRead]
    total: int = 0
    limit: int = 25
    offset: int = 0
    has_next: bool = False


class AuthResponse(BaseModel):
    user: AdminUserRead
