"""Academic schedule (jadwal + pertemuan) and manual H/S/I/A attendance.

Adds the missing academic layer on top of the existing face-recognition tables:

    Siswa -> Kelas
    Kelas + Guru + Mapel -> Jadwal (class_schedules)
    Jadwal -> Pertemuan (schedule_meetings)
    Pertemuan + Siswa -> Absensi (attendance_records)

Nothing is dropped or rewritten. ``persons`` and ``lecturers`` only gain
nullable columns, so every existing row and every existing query keeps working.

``attendance_logs`` (the face-recognition event log) is untouched and remains
the audit trail for kiosk scans; ``attendance_records`` is the separate,
teacher-facing H/S/I/A ledger, linked to the kiosk only through the optional
``schedule_meetings.attendance_session_id``.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "20260822_0013"
down_revision = "20260721_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- 1. Extra identity fields on existing master data (nullable = safe) ---
    op.add_column("persons", sa.Column("address", sa.Text(), nullable=True))
    op.add_column("lecturers", sa.Column("address", sa.Text(), nullable=True))
    op.add_column("lecturers", sa.Column("rank_grade", sa.String(64), nullable=True))

    # --- 2. Mata pelajaran ---
    op.create_table(
        "subjects",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("subject_code", sa.String(64), nullable=False),
        sa.Column("subject_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("subject_code", name="uq_subjects_subject_code"),
    )
    op.create_index("ix_subjects_subject_code", "subjects", ["subject_code"])

    # --- 3. Jadwal ---
    op.create_table(
        "class_schedules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("schedule_code", sa.String(64), nullable=False),
        sa.Column("class_id", UUID(as_uuid=True), sa.ForeignKey("classes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject_id", UUID(as_uuid=True), sa.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lecturer_id", UUID(as_uuid=True), sa.ForeignKey("lecturers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("academic_year", sa.String(16), nullable=False),
        sa.Column("semester", sa.String(16), nullable=False),
        sa.Column("day_of_week", sa.String(16), nullable=True),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("total_meetings", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("room", sa.String(64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("semester IN ('ganjil', 'genap')", name="ck_class_schedules_semester"),
        sa.CheckConstraint("total_meetings BETWEEN 1 AND 60", name="ck_class_schedules_total_meetings"),
        sa.CheckConstraint(
            "day_of_week IS NULL OR day_of_week IN "
            "('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')",
            name="ck_class_schedules_day_of_week",
        ),
        sa.UniqueConstraint("schedule_code", name="uq_class_schedules_schedule_code"),
        # One class studies one subject once per term: blocks duplicate jadwal.
        sa.UniqueConstraint(
            "class_id", "subject_id", "academic_year", "semester", name="uq_class_schedules_class_subject_term"
        ),
    )
    op.create_index("ix_class_schedules_schedule_code", "class_schedules", ["schedule_code"])
    op.create_index("ix_class_schedules_class_id", "class_schedules", ["class_id"])
    op.create_index("ix_class_schedules_subject_id", "class_schedules", ["subject_id"])
    op.create_index("ix_class_schedules_lecturer_id", "class_schedules", ["lecturer_id"])
    op.create_index("ix_class_schedules_academic_year", "class_schedules", ["academic_year"])
    op.create_index("ix_class_schedules_semester", "class_schedules", ["semester"])

    # --- 4. Pertemuan ---
    op.create_table(
        "schedule_meetings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("schedule_id", UUID(as_uuid=True), sa.ForeignKey("class_schedules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("meeting_number", sa.Integer(), nullable=False),
        sa.Column("meeting_date", sa.Date(), nullable=True),
        sa.Column("topic", sa.String(255), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="planned"),
        sa.Column(
            "attendance_session_id",
            UUID(as_uuid=True),
            sa.ForeignKey("attendance_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('planned', 'held', 'cancelled')", name="ck_schedule_meetings_status"),
        sa.CheckConstraint("meeting_number >= 1", name="ck_schedule_meetings_number"),
        sa.UniqueConstraint("schedule_id", "meeting_number", name="uq_schedule_meetings_schedule_number"),
    )
    op.create_index("ix_schedule_meetings_schedule_id", "schedule_meetings", ["schedule_id"])
    op.create_index("ix_schedule_meetings_status", "schedule_meetings", ["status"])
    op.create_index("ix_schedule_meetings_attendance_session_id", "schedule_meetings", ["attendance_session_id"])

    # --- 5. Absensi H/S/I/A ---
    op.create_table(
        "attendance_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("meeting_id", UUID(as_uuid=True), sa.ForeignKey("schedule_meetings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("person_id", UUID(as_uuid=True), sa.ForeignKey("persons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(1), nullable=False),
        sa.Column("note", sa.String(255), nullable=True),
        sa.Column("source", sa.String(16), nullable=False, server_default="manual"),
        sa.Column(
            "recorded_by_admin_id",
            UUID(as_uuid=True),
            sa.ForeignKey("admin_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('H', 'S', 'I', 'A')", name="ck_attendance_records_status"),
        sa.CheckConstraint("source IN ('manual', 'face')", name="ck_attendance_records_source"),
        # The anti-duplicate rule: one student has exactly one status per meeting.
        sa.UniqueConstraint("meeting_id", "person_id", name="uq_attendance_records_meeting_person"),
    )
    op.create_index("ix_attendance_records_meeting_id", "attendance_records", ["meeting_id"])
    op.create_index("ix_attendance_records_person_id", "attendance_records", ["person_id"])
    op.create_index("ix_attendance_records_status", "attendance_records", ["status"])


def downgrade() -> None:
    op.drop_table("attendance_records")
    op.drop_table("schedule_meetings")
    op.drop_table("class_schedules")
    op.drop_index("ix_subjects_subject_code", table_name="subjects")
    op.drop_table("subjects")
    op.drop_column("lecturers", "rank_grade")
    op.drop_column("lecturers", "address")
    op.drop_column("persons", "address")
