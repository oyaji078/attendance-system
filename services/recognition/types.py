from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import numpy as np


@dataclass(slots=True)
class DetectedFace:
    bbox: tuple[float, float, float, float]
    det_score: float
    embedding: list[float]


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
    liveness_score: float
    face_width_px: int
    accepted: bool
    reason: str
    flags: dict[str, bool]


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

