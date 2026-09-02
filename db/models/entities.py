from __future__ import annotations

import uuid
from datetime import date, datetime, time

from sqlalchemy import JSON, Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, Time, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import Base
from db.models.vector import VECTOR_DIMENSION, AsyncpgVector


class Person(Base):
    __tablename__ = "persons"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    class_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="SET NULL"), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", index=True)
    primary_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("face_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    samples: Mapped[list["FaceSample"]] = relationship(back_populates="person", foreign_keys="FaceSample.person_id")
    templates: Mapped[list["FaceTemplate"]] = relationship(back_populates="person", foreign_keys="FaceTemplate.person_id")
    primary_template: Mapped["FaceTemplate | None"] = relationship(foreign_keys=[primary_template_id], uselist=False, post_update=True)
    class_group: Mapped["ClassGroup | None"] = relationship(back_populates="students")


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    full_name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(32), default="admin", server_default="admin", index=True)
    lecturer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("lecturers.id", ondelete="SET NULL"), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Lecturer(Base):
    __tablename__ = "lecturers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lecturer_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    # "Golongan" on the Indonesian civil-service scale (e.g. "III/b"). Free text:
    # private schools use their own grading letters.
    rank_grade: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    classes: Mapped[list["ClassGroup"]] = relationship(back_populates="lecturer")
    sessions: Mapped[list["AttendanceSession"]] = relationship(back_populates="lecturer")
    schedules: Mapped[list["ClassSchedule"]] = relationship(back_populates="lecturer")


class ClassGroup(Base):
    __tablename__ = "classes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    class_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    class_name: Mapped[str] = mapped_column(String(255))
    lecturer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("lecturers.id", ondelete="SET NULL"), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    lecturer: Mapped["Lecturer | None"] = relationship(back_populates="classes")
    students: Mapped[list["Person"]] = relationship(back_populates="class_group")
    sessions: Mapped[list["AttendanceSession"]] = relationship(back_populates="class_group")
    schedules: Mapped[list["ClassSchedule"]] = relationship(back_populates="class_group")


class DeviceConfig(Base):
    __tablename__ = "device_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    device_name: Mapped[str] = mapped_column(String(255))
    location_hint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    det_thresh: Mapped[float] = mapped_column(Float, default=0.60, server_default="0.60")
    det_size_width: Mapped[int] = mapped_column(Integer, default=320, server_default="320")
    det_size_height: Mapped[int] = mapped_column(Integer, default=320, server_default="320")
    max_faces: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    min_face_width_px: Mapped[int] = mapped_column(Integer, default=130, server_default="130")
    min_brightness: Mapped[float] = mapped_column(Float, default=75.0, server_default="75")
    min_blur_score: Mapped[float] = mapped_column(Float, default=90.0, server_default="90")
    similarity_threshold: Mapped[float] = mapped_column(Float, default=0.45, server_default="0.45")
    candidate_margin_threshold: Mapped[float] = mapped_column(Float, default=0.05, server_default="0.05")
    liveness_threshold: Mapped[float] = mapped_column(Float, default=0.70, server_default="0.70")
    multi_frame_confirm: Mapped[int] = mapped_column(Integer, default=2, server_default="2")
    accepted_per_pose: Mapped[int] = mapped_column(Integer, default=2, server_default="2")
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=30, server_default="30")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AttendanceSession(Base):
    __tablename__ = "attendance_sessions"
    __table_args__ = (
        CheckConstraint("session_kind IN ('lecture', 'lab', 'exam', 'other')", name="ck_attendance_sessions_session_kind"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    session_name: Mapped[str] = mapped_column(String(255))
    session_kind: Mapped[str] = mapped_column(String(32))
    class_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="SET NULL"), nullable=True, index=True)
    lecturer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("lecturers.id", ondelete="SET NULL"), nullable=True, index=True)
    device_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", index=True)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=30, server_default="30")
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    repeat_days: Mapped[list[str] | None] = mapped_column(JSON, nullable=True, default=None)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True, server_default="Asia/Makassar")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    logs: Mapped[list["AttendanceLog"]] = relationship(back_populates="session")
    class_group: Mapped["ClassGroup | None"] = relationship(back_populates="sessions")
    lecturer: Mapped["Lecturer | None"] = relationship(back_populates="sessions")


class FaceSample(Base):
    __tablename__ = "face_samples"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    person_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"))
    # Transient enrollment workflow id (generated per enrollment run, kept in
    # Redis) — intentionally NOT a foreign key to attendance_sessions.
    enrollment_session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    pose: Mapped[str] = mapped_column(String(32), index=True)
    embedding: Mapped[list[float]] = mapped_column(AsyncpgVector(VECTOR_DIMENSION), nullable=False)
    image_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_device_code: Mapped[str] = mapped_column(String(64))
    brightness_score: Mapped[float] = mapped_column(Float)
    blur_score: Mapped[float] = mapped_column(Float)
    liveness_score: Mapped[float] = mapped_column(Float)
    face_width_px: Mapped[int] = mapped_column(Integer)
    quality_flags: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", index=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    person: Mapped["Person"] = relationship(back_populates="samples", foreign_keys=[person_id])


class FaceTemplate(Base):
    __tablename__ = "face_templates"
    __table_args__ = (
        UniqueConstraint("person_id", "version", name="uq_face_templates_person_version"),
        Index(
            "ix_face_templates_one_active_per_person",
            "person_id",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    person_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), index=True)
    embedding: Mapped[list[float]] = mapped_column(AsyncpgVector(VECTOR_DIMENSION), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    sample_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    built_from_session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    person: Mapped["Person"] = relationship(back_populates="templates", foreign_keys=[person_id])


class AttendanceLog(Base):
    __tablename__ = "attendance_logs"
    __table_args__ = (
        CheckConstraint("decision IN ('accepted', 'rejected', 'manual_approved', 'manual_rejected')", name="ck_attendance_logs_decision"),
        CheckConstraint("event_type IN ('checkin', 'checkout', 'recognition_attempt')", name="ck_attendance_logs_event_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("attendance_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    person_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("persons.id", ondelete="SET NULL"), nullable=True, index=True)
    matched_template_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("face_templates.id", ondelete="SET NULL"), nullable=True)
    device_code: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(32))
    decision: Mapped[str] = mapped_column(String(32), index=True)
    reason: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    liveness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    captured_image_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    frame_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    payload_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    session: Mapped["AttendanceSession | None"] = relationship(back_populates="logs")



class StudentEnrollment(Base):
    """Siswa <-> Kelas with a status and a start date.

    ``Person.class_id`` remains the fast path every existing query uses and is
    kept in sync with the one ``active`` row here; this table adds the history
    (which class before, since when) that the redesigned pages show.
    """

    __tablename__ = "student_enrollments"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'inactive')", name="ck_student_enrollments_status"),
        Index(
            "uq_student_enrollments_one_active",
            "person_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    person_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), index=True)
    class_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="active", server_default="active")
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Subject(Base):
    """Mata pelajaran. Kept separate from ``ClassGroup`` so one class can be
    taught several subjects, each by its own lecturer, without duplicating the
    class or its student roster."""

    __tablename__ = "subjects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    subject_name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    schedules: Mapped[list["ClassSchedule"]] = relationship(back_populates="subject")


class ClassSchedule(Base):
    """Jadwal: one class + subject + lecturer for one academic term.

    ``total_meetings`` is stored per schedule rather than hardcoded to 12, so a
    short term or an extended one is a data change, not a code change.
    """

    __tablename__ = "class_schedules"
    __table_args__ = (
        CheckConstraint("semester IN ('ganjil', 'genap')", name="ck_class_schedules_semester"),
        CheckConstraint("total_meetings BETWEEN 1 AND 60", name="ck_class_schedules_total_meetings"),
        CheckConstraint(
            "day_of_week IS NULL OR day_of_week IN "
            "('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')",
            name="ck_class_schedules_day_of_week",
        ),
        UniqueConstraint(
            "class_id",
            "subject_id",
            "academic_year",
            "semester",
            name="uq_class_schedules_class_subject_term",
        ),
        Index(
            "uq_class_schedules_attendance_session",
            "attendance_session_id",
            unique=True,
            postgresql_where=text("attendance_session_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schedule_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    class_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), index=True)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), index=True)
    lecturer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("lecturers.id", ondelete="SET NULL"), nullable=True, index=True)
    academic_year: Mapped[str] = mapped_column(String(16), index=True)
    semester: Mapped[str] = mapped_column(String(16), index=True)
    day_of_week: Mapped[str | None] = mapped_column(String(16), nullable=True)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    total_meetings: Mapped[int] = mapped_column(Integer, default=12, server_default="12")
    room: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # The kiosk session this jadwal owns. "Sesi Absensi" and "Jadwal" describe
    # the same class hour, so the jadwal row manages both.
    attendance_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attendance_sessions.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    class_group: Mapped["ClassGroup"] = relationship(back_populates="schedules")
    subject: Mapped["Subject"] = relationship(back_populates="schedules")
    lecturer: Mapped["Lecturer | None"] = relationship(back_populates="schedules")
    meetings: Mapped[list["ScheduleMeeting"]] = relationship(back_populates="schedule", cascade="all, delete-orphan")


class ScheduleMeeting(Base):
    """Pertemuan ke-N of a schedule.

    ``status`` decides the attendance denominator: only ``held`` meetings count
    toward "pertemuan yang sudah dilaksanakan", so a term that is half over does
    not report every student as half absent.
    """

    __tablename__ = "schedule_meetings"
    __table_args__ = (
        CheckConstraint("status IN ('planned', 'held', 'cancelled')", name="ck_schedule_meetings_status"),
        CheckConstraint("meeting_number >= 1", name="ck_schedule_meetings_number"),
        UniqueConstraint("schedule_id", "meeting_number", name="uq_schedule_meetings_schedule_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schedule_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("class_schedules.id", ondelete="CASCADE"), index=True)
    meeting_number: Mapped[int] = mapped_column(Integer)
    meeting_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    topic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="planned", server_default="planned", index=True)
    # Optional bridge to the face-recognition kiosk: when set, meeting attendance
    # can be prefilled from accepted attendance_logs of that session.
    attendance_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attendance_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    schedule: Mapped["ClassSchedule"] = relationship(back_populates="meetings")
    records: Mapped[list["AttendanceRecord"]] = relationship(back_populates="meeting", cascade="all, delete-orphan")


class AttendanceRecord(Base):
    """One student's H/S/I/A for one meeting.

    The unique constraint is the whole point: re-saving Pertemuan 1 updates the
    same rows instead of appending, and Pertemuan 2 can never overwrite them.
    """

    __tablename__ = "attendance_records"
    __table_args__ = (
        CheckConstraint("status IN ('H', 'S', 'I', 'A')", name="ck_attendance_records_status"),
        CheckConstraint("source IN ('manual', 'face')", name="ck_attendance_records_source"),
        UniqueConstraint("meeting_id", "person_id", name="uq_attendance_records_meeting_person"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("schedule_meetings.id", ondelete="CASCADE"), index=True)
    person_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(1), index=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(16), default="manual", server_default="manual")
    # How well the face matched when the camera recorded this row: a copy of
    # ``attendance_logs.confidence`` (0..1) taken at the moment of the scan, so
    # the figure the console shows stays the one the decision was made on even
    # after the template is re-enrolled. NULL for anything entered by hand.
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    recorded_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    meeting: Mapped["ScheduleMeeting"] = relationship(back_populates="records")


class AppSetting(Base):
    """Console-level key/value preferences (school name, default period)."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
