from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from db.domain.attendance import RecognitionStatus, normalize_attendance_decision, normalize_attendance_reason, normalize_recognition_status
from db.schemas.common import DecisionType, FrameInput, PersonSummary
from db.schemas.attendance_sessions import ResolvedAttendanceSession


class RecognitionRequest(BaseModel):
    device_code: str = Field(min_length=1, max_length=64)
    frames: list[FrameInput] = Field(min_length=1, max_length=10)
    session_code: str | None = Field(default=None, max_length=64)
    challenge_id: str | None = Field(default=None, max_length=64)


class CandidateSummary(BaseModel):
    template_id: UUID
    person_id: UUID
    student_id: str
    full_name: str
    email: str | None = None
    class_id: UUID | None = None
    class_code: str | None = None
    class_name: str | None = None
    distance: float
    confidence: float


class QualityFrameSummary(BaseModel):
    index: int
    accepted: bool
    reason: str
    face_bbox: list[float] | None = None
    face_box_normalized: dict[str, float] | None = None
    face_center: dict[str, float] | None = None
    face_size_ratio: float | None = None
    face_width_px: int | None = None
    min_face_width_px: int | None = None
    face_count: int | None = None
    max_faces: int | None = None
    blur_score: float | None = None
    min_blur_score: float | None = None
    brightness_score: float | None = None
    min_brightness: float | None = None
    contrast_score: float | None = None
    min_contrast: float | None = None
    liveness_score: float | None = None
    liveness_threshold: float | None = None
    face_center_offset_x: float | None = None
    face_center_offset_y: float | None = None
    max_face_center_offset: float | None = None
    overexposed_ratio: float | None = None
    max_overexposed_ratio: float | None = None
    underexposed_ratio: float | None = None
    max_underexposed_ratio: float | None = None
    flags: dict[str, bool] = Field(default_factory=dict)


class QualitySummary(BaseModel):
    dominant_reason: str | None = None
    reason_counts: dict[str, int] = Field(default_factory=dict)
    reasons: dict[str, int] = Field(default_factory=dict)
    accepted_frames: int = 0
    rejected_frames: int = 0
    mean_liveness_score: float | None = None
    quality_mode: str | None = None
    frames: list[QualityFrameSummary] = Field(default_factory=list)


class RecognitionResponse(BaseModel):
    decision: DecisionType
    reason: str
    recognition_status: RecognitionStatus | None = None
    confirmed_frames: int
    device_code: str
    session_code: str | None
    person: PersonSummary | None = None
    confidence: float | None = None
    resolved_session: ResolvedAttendanceSession | None = None
    session_resolution: str | None = None
    top_candidates: list[CandidateSummary] = Field(default_factory=list)
    top1_distance: float | None = None
    top2_distance: float | None = None
    candidate_margin: float | None = None
    similarity_threshold: float | None = None
    confidence_threshold: float | None = None
    margin_threshold: float | None = None
    required_confirmed_frames: int | None = None
    cooldown_remaining_seconds: int | None = None
    captured_face_b64: str | None = None
    quality_summary: QualitySummary | None = None
    active_liveness_score: float | None = None
    active_liveness_passed: bool | None = None
    pending_attendance_token: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_decision_fields(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        original_decision = data.get("decision")
        reason = normalize_attendance_reason(data.get("reason"))
        normalized_decision = normalize_attendance_decision(original_decision, reason)
        if normalized_decision == "manual_approved":
            normalized_decision = "accepted"
        elif normalized_decision == "manual_rejected":
            normalized_decision = "rejected"
        data = dict(data)
        data["decision"] = normalized_decision
        data["reason"] = reason
        data["recognition_status"] = normalize_recognition_status(
            data.get("recognition_status"),
            decision=original_decision,
            reason=reason,
        )
        return data
