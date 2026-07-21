"""Drop invalid enrollment-session foreign keys.

``face_samples.enrollment_session_id`` and ``face_templates.built_from_session_id``
store the transient enrollment workflow UUID generated at enrollment start
(kept in Redis), not a reference to ``attendance_sessions``. The foreign keys
added in 20260511_0007 therefore reject every real enrollment insert with a
ForeignKeyViolationError, breaking enrollment entirely.

This migration removes both foreign keys and relaxes
``face_samples.enrollment_session_id`` to nullable so the schema matches the
ORM definition (``uuid.UUID | None``).
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260721_0011"
down_revision = "20260520_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("fk_face_samples_enrollment_session", "face_samples", type_="foreignkey")
    op.drop_constraint("fk_face_templates_built_from_session", "face_templates", type_="foreignkey")
    op.alter_column("face_samples", "enrollment_session_id", existing_type=sa.UUID(), nullable=True)


def downgrade() -> None:
    op.alter_column("face_samples", "enrollment_session_id", existing_type=sa.UUID(), nullable=False)
    op.create_foreign_key(
        "fk_face_samples_enrollment_session",
        "face_samples", "attendance_sessions",
        ["enrollment_session_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_face_templates_built_from_session",
        "face_templates", "attendance_sessions",
        ["built_from_session_id"], ["id"],
        ondelete="SET NULL",
    )
