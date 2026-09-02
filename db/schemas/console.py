"""Schemas for the redesigned admin console.

Read models are shaped for the screens that render them (dashboard cards,
monitoring rows, the two recap tables), so the frontend never has to reshape or
recompute anything a page displays.
"""

from __future__ import annotations

from datetime import date as date_type, datetime, time
from typing import Literal, TypeAlias
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

EnrollmentStatus: TypeAlias = Literal["active", "inactive"]
AttendanceSource: TypeAlias = Literal["face", "manual"]


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #


class DashboardMetric(BaseModel):
    key: str
    label: str
    value: int
    hint: str | None = None


class DashboardActivity(BaseModel):
    at: datetime
    student_name: str | None = None
    student_id: str | None = None
    class_code: str | None = None
    subject_name: str | None = None
    status: str
    source: AttendanceSource
    # Face-match score behind the row, 0..1; None for manual entry.
    match_score: float | None = None


class DashboardAccuracy(BaseModel):
    """How sure the camera was about the attendance it recorded.

    ``date`` is the teaching day the figures cover: today when the camera has
    been used today, otherwise the most recent day it was. A console that is not
    scanning right now should still be able to see how recognition is doing.

    Reported as fractions (0..1) like the score itself, so the page decides how
    to present them. ``threshold`` travels with the numbers so the card can name
    the line it counted ``weak`` against instead of repeating it.
    """

    date: date_type | None = None
    scored: int = 0
    average: float | None = None
    lowest: float | None = None
    weak: int = 0
    threshold: float = 0.55


class DashboardResponse(BaseModel):
    metrics: list[DashboardMetric]
    today_present: int = 0
    today_absent: int = 0
    today_total: int = 0
    accuracy: DashboardAccuracy = Field(default_factory=DashboardAccuracy)
    activity: list[DashboardActivity] = Field(default_factory=list)
    generated_at: datetime


# --------------------------------------------------------------------------- #
# Monitoring absensi
# --------------------------------------------------------------------------- #


class AttendanceEventRow(BaseModel):
    no: int
    record_id: UUID | None = None
    date: date_type | None = None
    class_code: str | None = None
    class_name: str | None = None
    subject_name: str | None = None
    subject_code: str | None = None
    meeting_number: int | None = None
    start_time: time | None = None
    end_time: time | None = None
    student_id: str | None = None
    student_name: str | None = None
    person_id: UUID | None = None
    status: str
    recorded_at: datetime | None = None
    source: AttendanceSource
    # Face-match score of the scan behind the row, 0..1. None for manual entry,
    # and for face rows filed before the score was carried across.
    match_score: float | None = None


class AttendanceEventListResponse(BaseModel):
    items: list[AttendanceEventRow]
    total: int = 0
    limit: int = 100
    offset: int = 0
    has_next: bool = False


class FaceSyncResponse(BaseModel):
    days: int = 0
    recorded: int = 0
    scored: int = 0
    skipped_days: int = 0
    detail: str = ""


# --------------------------------------------------------------------------- #
# Rekap per kelas (summary across subjects)
# --------------------------------------------------------------------------- #


class ClassRecapSubject(BaseModel):
    schedule_id: UUID
    subject_id: UUID
    subject_code: str | None = None
    subject_name: str
    lecturer_name: str | None = None
    held_meetings: int = 0
    total_meetings: int = 0


class ClassRecapRow(BaseModel):
    no: int
    person_id: UUID
    student_id: str
    full_name: str
    # Aligned with ``subjects`` by index; ``None`` = that subject has no held
    # meeting yet, which is different from 0%.
    percents: list[float | None]
    average_percent: float | None = None


class ClassRecapResponse(BaseModel):
    class_id: UUID
    class_code: str
    class_name: str
    academic_year: str | None = None
    semester: str | None = None
    subjects: list[ClassRecapSubject]
    rows: list[ClassRecapRow]
    student_count: int = 0
    average_percent: float | None = None


# --------------------------------------------------------------------------- #
# Enrollment (siswa <-> kelas)
# --------------------------------------------------------------------------- #


class EnrollmentWrite(BaseModel):
    class_id: UUID
    status: EnrollmentStatus = "active"
    start_date: date_type | None = None
    note: str | None = Field(default=None, max_length=255)

    @field_validator("note")
    @classmethod
    def strip_note(cls, value: str | None) -> str | None:
        return (value or "").strip() or None


class EnrollmentRead(BaseModel):
    enrollment_id: UUID
    person_id: UUID
    class_id: UUID
    class_code: str | None = None
    class_name: str | None = None
    status: EnrollmentStatus
    start_date: date_type | None = None
    end_date: date_type | None = None
    note: str | None = None
    created_at: datetime
    updated_at: datetime


class EnrollmentListResponse(BaseModel):
    items: list[EnrollmentRead]
    total: int = 0


# --------------------------------------------------------------------------- #
# Detail siswa
# --------------------------------------------------------------------------- #


class StudentSubjectSummary(BaseModel):
    subject_id: UUID
    subject_code: str | None = None
    subject_name: str
    hadir: int = 0
    izin: int = 0
    sakit: int = 0
    alpha: int = 0
    held_meetings: int = 0
    attendance_percent: float = 0.0


class StudentDetailResponse(BaseModel):
    person_id: UUID
    student_id: str
    full_name: str
    email: str | None = None
    address: str | None = None
    class_id: UUID | None = None
    class_code: str | None = None
    class_name: str | None = None
    is_active: bool
    has_face_profile: bool = False
    sample_count: int = 0
    last_seen_at: datetime | None = None
    enrollments: list[EnrollmentRead] = Field(default_factory=list)
    subjects: list[StudentSubjectSummary] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Detail kelas
# --------------------------------------------------------------------------- #


class ClassStudentRow(BaseModel):
    no: int
    person_id: UUID
    student_id: str
    full_name: str
    is_active: bool
    has_face_profile: bool = False
    enrollment_status: EnrollmentStatus | None = None
    start_date: date_type | None = None


class ClassDetailResponse(BaseModel):
    class_id: UUID
    class_code: str
    class_name: str
    lecturer_id: UUID | None = None
    lecturer_name: str | None = None
    description: str | None = None
    is_active: bool
    student_count: int = 0
    schedule_count: int = 0
    students: list[ClassStudentRow] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Pengaturan
# --------------------------------------------------------------------------- #


# A logo is stored inline as a data URI rather than as a file: it is one small
# image, it has to reach both the PDF and the Excel export, and keeping it in
# the settings row means no upload directory to secure or back up separately.
MAX_LOGO_CHARS: int = 400_000  # ~300 KB of base64
ALLOWED_LOGO_PREFIXES: tuple[str, ...] = (
    "data:image/png;base64,",
    "data:image/jpeg;base64,",
    "data:image/jpg;base64,",
)


class SettingsPayload(BaseModel):
    school_name: str | None = Field(default=None, max_length=120)
    default_academic_year: str | None = Field(default=None, max_length=16)
    default_semester: str | None = Field(default=None, max_length=16)
    # Base64 data URI, or "" to clear it.
    school_logo: str | None = None

    @field_validator("school_name", "default_academic_year", "default_semester")
    @classmethod
    def strip_value(cls, value: str | None) -> str | None:
        return (value or "").strip() or None

    @field_validator("school_logo")
    @classmethod
    def validate_logo(cls, value: str | None) -> str | None:
        cleaned = (value or "").strip()
        if not cleaned:
            return None
        if not cleaned.startswith(ALLOWED_LOGO_PREFIXES):
            raise ValueError("Logo harus berupa gambar PNG atau JPEG.")
        if len(cleaned) > MAX_LOGO_CHARS:
            raise ValueError("Ukuran logo terlalu besar (maksimal sekitar 300 KB).")
        # Reject anything that is not actually decodable, so a malformed value
        # cannot reach the PDF writer and break every export.
        import base64
        import binascii

        payload = cleaned.split(",", 1)[1]
        try:
            base64.b64decode(payload, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("Data logo tidak valid.") from exc
        return cleaned


class SettingsResponse(SettingsPayload):
    updated_at: datetime | None = None
