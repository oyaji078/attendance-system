from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260520_0010"
down_revision = "20260516_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("attendance_sessions", sa.Column("repeat_days", sa.JSON(), nullable=True, server_default="null"))
    op.add_column("attendance_sessions", sa.Column("start_time", sa.Time(), nullable=True))
    op.add_column("attendance_sessions", sa.Column("end_time", sa.Time(), nullable=True))
    op.add_column("attendance_sessions", sa.Column("timezone", sa.String(64), nullable=True, server_default="Asia/Makassar"))


def downgrade() -> None:
    op.drop_column("attendance_sessions", "timezone")
    op.drop_column("attendance_sessions", "end_time")
    op.drop_column("attendance_sessions", "start_time")
    op.drop_column("attendance_sessions", "repeat_days")
