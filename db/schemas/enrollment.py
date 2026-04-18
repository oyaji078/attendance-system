from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from db.schemas.common import PoseName, QualitySnapshot


class EnrollmentStartRequest(BaseModel):
    student_id: str = Field(min_length=1, max_length=64)
    full_name: str = Field(min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    device_code: str = Field(min_length=1, max_length=64)


class EnrollmentStartResponse(BaseModel):
    enrollment_session_id: UUID
    person_id: UUID
    required_poses: list[PoseName]
    accepted_per_pose: int
    remaining_per_pose: dict[PoseName, int]


class EnrollmentFrameRequest(BaseModel):
    enrollment_session_id: UUID
    device_code: str = Field(min_length=1, max_length=64)
    pose: PoseName
    frame_b64: str = Field(min_length=32)


class EnrollmentFrameResponse(BaseModel):
    enrollment_session_id: UUID
    accepted: bool
    reason: str
    pose: PoseName
    pose_accepted_count: int
    total_accepted_count: int
    quality: QualitySnapshot


class EnrollmentFinishRequest(BaseModel):
    enrollment_session_id: UUID


class EnrollmentFinishResponse(BaseModel):
    enrollment_session_id: UUID
    person_id: UUID
    template_id: UUID
    total_samples: int
    activated: bool

