from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260502_0006"
down_revision = "20260502_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("attendance_sessions", sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("attendance_sessions", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_attendance_sessions_is_deleted", "attendance_sessions", ["is_deleted"], unique=False)

    op.add_column("face_samples", sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False))
    op.add_column("face_samples", sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("face_samples", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_face_samples_is_active", "face_samples", ["is_active"], unique=False)
    op.create_index("ix_face_samples_is_deleted", "face_samples", ["is_deleted"], unique=False)

    op.add_column("face_templates", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("face_templates", "deleted_at")

    op.drop_index("ix_face_samples_is_deleted", table_name="face_samples")
    op.drop_index("ix_face_samples_is_active", table_name="face_samples")
    op.drop_column("face_samples", "deleted_at")
    op.drop_column("face_samples", "is_deleted")
    op.drop_column("face_samples", "is_active")

    op.drop_index("ix_attendance_sessions_is_deleted", table_name="attendance_sessions")
    op.drop_column("attendance_sessions", "deleted_at")
    op.drop_column("attendance_sessions", "is_deleted")
