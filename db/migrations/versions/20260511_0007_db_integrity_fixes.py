from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260511_0007"
down_revision = "20260502_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Foreign Keys ---
    op.create_foreign_key(
        "fk_face_samples_enrollment_session",
        "face_samples", "attendance_sessions",
        ["enrollment_session_id"], ["id"],
        ondelete="SET NULL",
        source_schema=None,
    )
    op.create_foreign_key(
        "fk_face_templates_built_from_session",
        "face_templates", "attendance_sessions",
        ["built_from_session_id"], ["id"],
        ondelete="SET NULL",
        source_schema=None,
    )

    # --- Composite Indexes ---
    op.create_index(
        "ix_attendance_logs_session_created",
        "attendance_logs",
        ["session_id", sa.text("created_at DESC")],
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ix_attendance_logs_person_created",
        "attendance_logs",
        ["person_id", sa.text("created_at DESC")],
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ix_attendance_logs_device_created",
        "attendance_logs",
        ["device_code", sa.text("created_at DESC")],
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ix_attendance_logs_decision_created",
        "attendance_logs",
        ["decision", sa.text("created_at DESC")],
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ix_attendance_sessions_time_window",
        "attendance_sessions",
        ["starts_at", "ends_at"],
        postgresql_where=sa.text("is_deleted = false AND is_active = true"),
    )
    op.create_index(
        "ix_attendance_sessions_class_time",
        "attendance_sessions",
        ["class_id", "starts_at", "ends_at"],
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ix_attendance_sessions_lecturer_time",
        "attendance_sessions",
        ["lecturer_id", "starts_at", "ends_at"],
        postgresql_where=sa.text("is_deleted = false"),
    )

    # --- Legacy enum backfill before CHECK constraints ---
    op.execute("UPDATE attendance_sessions SET session_kind = 'lecture' WHERE lower(trim(session_kind)) = 'class'")
    op.execute(
        """
        UPDATE attendance_sessions
        SET session_kind = 'other'
        WHERE session_kind IS NULL
           OR lower(trim(session_kind)) NOT IN ('lecture', 'lab', 'exam', 'other')
        """
    )
    op.execute(
        """
        UPDATE attendance_logs
        SET decision = 'accepted',
            reason = COALESCE(NULLIF(trim(reason), ''), 'multi_frame_confirm_passed')
        WHERE lower(trim(decision)) = 'recognized'
        """
    )
    op.execute(
        """
        UPDATE attendance_logs
        SET decision = 'rejected',
            reason = 'cooldown'
        WHERE lower(trim(decision)) = 'cooldown'
        """
    )
    op.execute(
        """
        UPDATE attendance_logs
        SET decision = 'rejected',
            reason = COALESCE(NULLIF(trim(reason), ''), lower(trim(decision)))
        WHERE lower(trim(decision)) IN ('unknown', 'session_inactive', 'no_matching_session', 'multiple_matching_sessions')
        """
    )
    op.execute(
        """
        UPDATE attendance_logs
        SET decision = 'rejected',
            reason = COALESCE(NULLIF(trim(reason), ''), 'invalid_decision_' || lower(trim(decision)))
        WHERE decision IS NULL
           OR lower(trim(decision)) NOT IN ('accepted', 'rejected', 'manual_approved', 'manual_rejected')
        """
    )
    op.execute(
        """
        UPDATE attendance_logs
        SET event_type = 'recognition_attempt'
        WHERE lower(trim(event_type)) IN ('recognize', 'recognition', 'recognized', 'recognition_attempted')
           OR event_type IS NULL
           OR lower(trim(event_type)) NOT IN ('checkin', 'checkout', 'recognition_attempt')
        """
    )

    # --- Check Constraints ---
    op.create_check_constraint(
        "ck_attendance_logs_decision",
        "attendance_logs",
        sa.text("decision IN ('accepted', 'rejected', 'manual_approved', 'manual_rejected')"),
    )
    op.create_check_constraint(
        "ck_attendance_logs_event_type",
        "attendance_logs",
        sa.text("event_type IN ('checkin', 'checkout', 'recognition_attempt')"),
    )
    op.create_check_constraint(
        "ck_attendance_sessions_session_kind",
        "attendance_sessions",
        sa.text("session_kind IN ('lecture', 'lab', 'exam', 'other')"),
    )
    op.create_check_constraint(
        "ck_face_samples_pose",
        "face_samples",
        sa.text("pose IN ('front', 'left_20', 'right_20', 'up_or_down')"),
    )
    op.create_check_constraint(
        "ck_admin_users_role",
        "admin_users",
        sa.text("role IN ('admin', 'operator', 'lecturer')"),
    )


def downgrade() -> None:
    op.drop_constraint("ck_admin_users_role", "admin_users")
    op.drop_constraint("ck_face_samples_pose", "face_samples")
    op.drop_constraint("ck_attendance_sessions_session_kind", "attendance_sessions")
    op.drop_constraint("ck_attendance_logs_event_type", "attendance_logs")
    op.drop_constraint("ck_attendance_logs_decision", "attendance_logs")

    op.drop_index("ix_attendance_sessions_lecturer_time", table_name="attendance_sessions")
    op.drop_index("ix_attendance_sessions_class_time", table_name="attendance_sessions")
    op.drop_index("ix_attendance_sessions_time_window", table_name="attendance_sessions")
    op.drop_index("ix_attendance_logs_decision_created", table_name="attendance_logs")
    op.drop_index("ix_attendance_logs_device_created", table_name="attendance_logs")
    op.drop_index("ix_attendance_logs_person_created", table_name="attendance_logs")
    op.drop_index("ix_attendance_logs_session_created", table_name="attendance_logs")

    op.drop_constraint("fk_face_templates_built_from_session", "face_templates")
    op.drop_constraint("fk_face_samples_enrollment_session", "face_samples")
