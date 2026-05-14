from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260515_0008"
down_revision = "20260511_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE attendance_logs DROP CONSTRAINT IF EXISTS ck_attendance_logs_decision")
    op.execute("ALTER TABLE attendance_logs DROP CONSTRAINT IF EXISTS ck_attendance_logs_event_type")
    op.execute("ALTER TABLE attendance_sessions DROP CONSTRAINT IF EXISTS ck_attendance_sessions_session_kind")

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
            reason = COALESCE(NULLIF(trim(reason), ''), 'invalid_decision_' || lower(trim(COALESCE(decision, 'unknown'))))
        WHERE decision IS NULL
           OR lower(trim(decision)) NOT IN ('accepted', 'rejected', 'manual_approved', 'manual_rejected')
        """
    )
    op.execute(
        """
        UPDATE attendance_logs
        SET reason = 'cooldown'
        WHERE reason IN ('person_on_cooldown', 'cooldown_period')
        """
    )
    op.execute(
        """
        UPDATE attendance_logs
        SET event_type = 'recognition_attempt'
        WHERE event_type IS NULL
           OR lower(trim(event_type)) IN ('recognize', 'recognition', 'recognized', 'recognition_attempted')
           OR lower(trim(event_type)) NOT IN ('checkin', 'checkout', 'recognition_attempt')
        """
    )

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


def downgrade() -> None:
    op.execute("ALTER TABLE attendance_logs DROP CONSTRAINT IF EXISTS ck_attendance_logs_decision")
    op.execute("ALTER TABLE attendance_logs DROP CONSTRAINT IF EXISTS ck_attendance_logs_event_type")
    op.execute("ALTER TABLE attendance_sessions DROP CONSTRAINT IF EXISTS ck_attendance_sessions_session_kind")

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

