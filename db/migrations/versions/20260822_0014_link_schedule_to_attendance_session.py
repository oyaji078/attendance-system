"""Link a jadwal to its face-recognition session.

"Sesi Absensi" and "Jadwal" both described the same thing — a class taught by a
teacher on a day at a time — so the UI now presents them as one menu. This FK is
what makes that a real merge instead of two lists on one page: creating a jadwal
can create (and own) the kiosk session, and the session's lifecycle is managed
from the jadwal row.

Existing ``attendance_sessions`` rows are untouched and keep working with the
kiosk exactly as before; they simply have no owning schedule yet.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "20260822_0014"
down_revision = "20260822_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "class_schedules",
        sa.Column("attendance_session_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_class_schedules_attendance_session",
        "class_schedules",
        "attendance_sessions",
        ["attendance_session_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # One session belongs to at most one jadwal, so the jadwal row is the single
    # place its lifecycle is managed. Partial index: many schedules may have none.
    op.create_index(
        "uq_class_schedules_attendance_session",
        "class_schedules",
        ["attendance_session_id"],
        unique=True,
        postgresql_where=sa.text("attendance_session_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_class_schedules_attendance_session", table_name="class_schedules")
    op.drop_constraint("fk_class_schedules_attendance_session", "class_schedules", type_="foreignkey")
    op.drop_column("class_schedules", "attendance_session_id")
