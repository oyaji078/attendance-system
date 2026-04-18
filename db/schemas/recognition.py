from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from db.schemas.common import DecisionType, FrameInput, PersonSummary


class RecognitionRequest(BaseModel):
    device_code: str = Field(min_length=1, max_length=64)
    frames: list[FrameInput] = Field(min_length=3, max_length=3)
    session_code: str | None = Field(default=None, max_length=64)


class CandidateSummary(BaseModel):
    template_id: UUID
    person_id: UUID
    student_id: str
    full_name: str
    distance: float
    confidence: float


class RecognitionResponse(BaseModel):
    decision: DecisionType
    reason: str
    confirmed_frames: int
    device_code: str
    session_code: str | None
    person: PersonSummary | None = None
    confidence: float | None = None
    top_candidates: list[CandidateSummary] = Field(default_factory=list)

