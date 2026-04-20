from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260420_0002"
down_revision = "20260416_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "attendance_sessions",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.drop_constraint("uq_face_templates_person_active", "face_templates", type_="unique")
    op.create_unique_constraint("uq_face_templates_person_version", "face_templates", ["person_id", "version"])
    op.create_index(
        "ix_face_templates_one_active_per_person",
        "face_templates",
        ["person_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    op.drop_index("ix_face_templates_one_active_per_person", table_name="face_templates")
    op.drop_constraint("uq_face_templates_person_version", "face_templates", type_="unique")
    op.create_unique_constraint("uq_face_templates_person_active", "face_templates", ["person_id", "is_active"])
    op.drop_column("attendance_sessions", "updated_at")
