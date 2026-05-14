from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

import numpy as np


@dataclass(slots=True)
class DetectedFace:
    bbox: tuple[float, float, float, float]
    det_score: float
    embedding: list[float]
    keypoints: list[tuple[float, float]]
    pose_yaw: float
    pose_pitch: float
    pose_roll: float
    center_offset_x: float
    center_offset_y: float
    relative_area: float


@dataclass(slots=True)
class FrameAnalysis:
    frame: np.ndarray
    faces: list[DetectedFace]


@dataclass(slots=True)
class LivenessResult:
    score: float
    mode: str
    implemented: bool
    details: dict[str, float]


@dataclass(slots=True)
class QualityResult:
    brightness_score: float
    blur_score: float
    contrast_score: float
    overexposed_ratio: float
    underexposed_ratio: float
    liveness_score: float
    face_width_px: int
    face_center_offset_x: float
    face_center_offset_y: float
    pose_yaw: float
    pose_pitch: float
    pose_roll: float
    pose_valid: bool
    accepted: bool
    reason: str
    ui_hint: str
    flags: dict[str, bool]
    face_bbox: list[float] | None = None
    face_box_normalized: dict[str, float] | None = None
    face_center: dict[str, float] | None = None
    face_size_ratio: float | None = None
    face_count: int = 0
    max_faces: int | None = None
    min_face_width_px: int | None = None
    min_brightness: float | None = None
    min_blur_score: float | None = None
    liveness_threshold: float | None = None
    min_contrast: float | None = None
    max_overexposed_ratio: float | None = None
    max_underexposed_ratio: float | None = None
    max_face_center_offset: float | None = None
    quality_mode: str | None = None


@dataclass(slots=True)
class RecognitionFrameDecision:
    accepted: bool
    reason: str
    matched_person_id: UUID | None
    matched_template_id: UUID | None
    student_id: str | None
    full_name: str | None
    distance: float | None
    confidence: float | None
    quality: QualityResult


@dataclass(slots=True)
class EnrollmentState:
    enrollment_session_id: UUID
    person_id: UUID
    student_id: str
    full_name: str
    device_code: str
    accepted_counts: dict[str, int]
    started_at: datetime
    rejected_counts: dict[str, int] = field(default_factory=dict)
