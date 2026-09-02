"""Schemas for jadwal, pertemuan, and manual H/S/I/A attendance.

Kept separate from ``db.schemas.academic`` (lecturers/classes master data) and
from ``db.schemas.attendance`` (the face-recognition kiosk contract), so none of
the existing request/response shapes shift under the older modules.
"""

from __future__ import annotations

from datetime import date as date_type, datetime, time
from typing import Literal, TypeAlias
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

AttendanceStatus: TypeAlias = Literal["H", "S", "I", "A"]
MeetingStatus: TypeAlias = Literal["planned", "held", "cancelled"]
Semester: TypeAlias = Literal["ganjil", "genap"]
DayOfWeek: TypeAlias = Literal["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

ATTENDANCE_STATUSES: tuple[str, ...] = ("H", "S", "I", "A")
ATTENDANCE_STATUS_LABELS: dict[str, str] = {"H": "Hadir", "S": "Sakit", "I": "Izin", "A": "Alpha"}
VALID_DAYS: tuple[str, ...] = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")

# Guard rail for the bulk save: a class roster far larger than any real one is a
# malformed or hostile payload, not a school.
MAX_ATTENDANCE_ENTRIES: int = 500


def normalize_status(value: object) -> str:
    """Accept 'h', 'Hadir', 'ALPHA', ... and return the canonical letter."""
    token = str(value or "").strip().upper()
    if not token:
        raise ValueError("status absensi wajib diisi")
    if token in ATTENDANCE_STATUSES:
        return token
    aliases = {"HADIR": "H", "SAKIT": "S", "IZIN": "I", "ALPHA": "A", "ALPA": "A", "ABSEN": "A"}
    if token in aliases:
        return aliases[token]
    raise ValueError("status absensi harus salah satu dari H, S, I, A")


# --------------------------------------------------------------------------- #
# Mata pelajaran
# --------------------------------------------------------------------------- #


class SubjectWrite(BaseModel):
    # Optional: auto-generated server-side (MAPEL-NNNN) when left blank.
    subject_code: str | None = Field(default=None, max_length=64)
    subject_name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    is_active: bool = True

    @field_validator("subject_code")
    @classmethod
    def strip_code(cls, value: str | None) -> str | None:
        return (value or "").strip() or None


class SubjectRead(BaseModel):
    subject_id: UUID
    subject_code: str
    subject_name: str
    description: str | None = None
    is_active: bool
    schedule_count: int = 0
    created_at: datetime
    updated_at: datetime


class SubjectListResponse(BaseModel):
    items: list[SubjectRead]
    total: int = 0
    limit: int = 100
    offset: int = 0
    has_next: bool = False


# --------------------------------------------------------------------------- #
# Jadwal
# --------------------------------------------------------------------------- #


class ClassScheduleWrite(BaseModel):
    # Optional: auto-generated server-side (JDW-NNNN) when left blank.
    schedule_code: str | None = Field(default=None, max_length=64)
    class_id: UUID
    subject_id: UUID
    lecturer_id: UUID | None = None
    academic_year: str = Field(min_length=4, max_length=16)
    semester: Semester = "ganjil"
    day_of_week: DayOfWeek | None = None
    start_time: time | None = None
    end_time: time | None = None
    total_meetings: int = Field(default=12, ge=1, le=60)
    room: str | None = Field(default=None, max_length=64)
    is_active: bool = True
    # Create/refresh the kiosk session for this jadwal so Mode Absensi can use
    # it. Off means the jadwal is for manual H/S/I/A only.
    with_kiosk_session: bool = False
    device_code: str | None = Field(default=None, max_length=64)

    @field_validator("schedule_code", "room", "device_code")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        return (value or "").strip() or None

    @field_validator("semester", mode="before")
    @classmethod
    def normalize_semester(cls, value: object) -> str:
        token = str(value or "ganjil").strip().lower()
        if token in ("1", "gasal", "ganjil"):
            return "ganjil"
        if token in ("2", "genap"):
            return "genap"
        return token

    @field_validator("day_of_week", mode="before")
    @classmethod
    def normalize_day(cls, value: object) -> str | None:
        token = str(value or "").strip().lower()
        if not token:
            return None
        indonesian = {
            "senin": "monday",
            "selasa": "tuesday",
            "rabu": "wednesday",
            "kamis": "thursday",
            "jumat": "friday",
            "jum'at": "friday",
            "sabtu": "saturday",
            "minggu": "sunday",
        }
        return indonesian.get(token, token)

    @field_validator("academic_year", mode="before")
    @classmethod
    def normalize_academic_year(cls, value: object) -> str:
        return str(value or "").strip()

    @model_validator(mode="after")
    def validate_time_window(self) -> "ClassScheduleWrite":
        if self.start_time is not None and self.end_time is not None and self.end_time <= self.start_time:
            raise ValueError("Jam selesai harus lebih besar dari jam mulai")
        return self


class ClassScheduleRead(BaseModel):
    schedule_id: UUID
    schedule_code: str
    class_id: UUID
    class_code: str | None = None
    class_name: str | None = None
    subject_id: UUID
    subject_code: str | None = None
    subject_name: str | None = None
    lecturer_id: UUID | None = None
    lecturer_name: str | None = None
    academic_year: str
    semester: str
    day_of_week: str | None = None
    start_time: time | None = None
    end_time: time | None = None
    total_meetings: int
    room: str | None = None
    is_active: bool
    attendance_session_id: UUID | None = None
    session_code: str | None = None
    session_name: str | None = None
    session_is_active: bool | None = None
    student_count: int = 0
    meeting_count: int = 0
    held_meeting_count: int = 0
    created_at: datetime
    updated_at: datetime


class ClassScheduleListResponse(BaseModel):
    items: list[ClassScheduleRead]
    total: int = 0


class ScheduleDeleteResponse(BaseModel):
    status: str = "deleted"
    meetings_deleted: int = 0
    records_deleted: int = 0
    detail: str = "Jadwal dihapus."


class KioskSessionRequest(BaseModel):
    device_code: str | None = Field(default=None, max_length=64)

    @field_validator("device_code")
    @classmethod
    def strip_device_code(cls, value: str | None) -> str | None:
        return (value or "").strip() or None


# --------------------------------------------------------------------------- #
# Pertemuan
# --------------------------------------------------------------------------- #


class MeetingWrite(BaseModel):
    meeting_date: date_type | None = None
    topic: str | None = Field(default=None, max_length=255)
    status: MeetingStatus = "planned"
    attendance_session_id: UUID | None = None
    notes: str | None = None

    @field_validator("topic", "notes")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        return (value or "").strip() or None


class MeetingGenerateRequest(BaseModel):
    """Create meetings 1..``total_meetings`` for a schedule.

    ``total_meetings`` overrides the schedule value when given, so a term can be
    extended without editing the schedule first. Existing meetings are kept.
    """

    total_meetings: int | None = Field(default=None, ge=1, le=60)


class MeetingRead(BaseModel):
    meeting_id: UUID
    schedule_id: UUID
    meeting_number: int
    meeting_date: date_type | None = None
    topic: str | None = None
    status: MeetingStatus
    attendance_session_id: UUID | None = None
    notes: str | None = None
    recorded_count: int = 0
    present_count: int = 0
    created_at: datetime
    updated_at: datetime


class MeetingListResponse(BaseModel):
    schedule: ClassScheduleRead
    items: list[MeetingRead]
    total: int = 0


# --------------------------------------------------------------------------- #
# Input absensi
# --------------------------------------------------------------------------- #


class AttendanceSheetStudent(BaseModel):
    no: int
    person_id: UUID
    student_id: str
    full_name: str
    address: str | None = None
    status: AttendanceStatus | None = None
    note: str | None = None
    source: str | None = None
    updated_at: datetime | None = None


class AttendanceSheetResponse(BaseModel):
    schedule: ClassScheduleRead
    meeting: MeetingRead
    students: list[AttendanceSheetStudent]
    student_count: int = 0
    status_labels: dict[str, str] = Field(default_factory=lambda: dict(ATTENDANCE_STATUS_LABELS))


class AttendanceEntry(BaseModel):
    person_id: UUID
    status: AttendanceStatus
    note: str | None = Field(default=None, max_length=255)

    @field_validator("status", mode="before")
    @classmethod
    def coerce_status(cls, value: object) -> str:
        return normalize_status(value)

    @field_validator("note")
    @classmethod
    def strip_note(cls, value: str | None) -> str | None:
        return (value or "").strip() or None


class AttendanceSaveRequest(BaseModel):
    entries: list[AttendanceEntry] = Field(min_length=1, max_length=MAX_ATTENDANCE_ENTRIES)
    # Saving a sheet normally means the meeting actually happened. Callers can
    # opt out when correcting a cancelled meeting after the fact.
    mark_meeting_held: bool = True

    @model_validator(mode="after")
    def reject_duplicate_person(self) -> "AttendanceSaveRequest":
        seen: set[UUID] = set()
        for entry in self.entries:
            if entry.person_id in seen:
                raise ValueError("Setiap siswa hanya boleh memiliki satu status per pertemuan")
            seen.add(entry.person_id)
        return self


class AttendanceSaveResponse(BaseModel):
    meeting_id: UUID
    created: int = 0
    updated: int = 0
    skipped: int = 0
    detail: str = "Absensi tersimpan."


class AttendancePrefillResponse(BaseModel):
    meeting_id: UUID
    matched: int = 0
    students: list[AttendanceSheetStudent] = Field(default_factory=list)
    detail: str = ""


# --------------------------------------------------------------------------- #
# Rekap
# --------------------------------------------------------------------------- #


class RecapMeetingColumn(BaseModel):
    meeting_id: UUID
    meeting_number: int
    meeting_date: date_type | None = None
    status: MeetingStatus
    label: str


class RecapRow(BaseModel):
    no: int
    person_id: UUID
    student_id: str
    full_name: str
    # One entry per column, aligned by index. ``None`` = no record taken.
    cells: list[AttendanceStatus | None]
    hadir: int = 0
    sakit: int = 0
    izin: int = 0
    alpha: int = 0
    held_meetings: int = 0
    attendance_percent: float = 0.0


class RecapResponse(BaseModel):
    schedule: ClassScheduleRead
    columns: list[RecapMeetingColumn]
    rows: list[RecapRow]
    student_count: int = 0
    total_meetings: int = 0
    held_meetings: int = 0
    average_percent: float = 0.0


class RecapFilterOptions(BaseModel):
    academic_years: list[str] = Field(default_factory=list)
    semesters: list[str] = Field(default_factory=list)
