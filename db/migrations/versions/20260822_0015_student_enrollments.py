"""Enrollment as a real relation: Siswa <-> Kelas, with status and history.

``persons.class_id`` alone could only answer "which class is this student in
now" — it could not say since when, or which class they were in last term. The
redesigned Siswa/Kelas pages need both, so enrollment becomes its own record.

``persons.class_id`` is kept and stays in sync with the active enrollment, so
every existing query (attendance sheets, recap, kiosk session matching) keeps
working untouched. This table is additive history on top of it.

Existing students are backfilled with one active enrollment from their current
class, so the new pages have data on day one.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "20260822_0015"
down_revision = "20260822_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "student_enrollments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("person_id", UUID(as_uuid=True), sa.ForeignKey("persons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("class_id", UUID(as_uuid=True), sa.ForeignKey("classes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("note", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="ck_student_enrollments_status"),
    )
    op.create_index("ix_student_enrollments_person_id", "student_enrollments", ["person_id"])
    op.create_index("ix_student_enrollments_class_id", "student_enrollments", ["class_id"])
    # A student sits in exactly one class at a time; past enrollments stay as
    # inactive rows, so the history is preserved without ambiguity.
    op.create_index(
        "uq_student_enrollments_one_active",
        "student_enrollments",
        ["person_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.execute(
        """
        INSERT INTO student_enrollments (id, person_id, class_id, status, start_date, created_at, updated_at)
        SELECT gen_random_uuid(), p.id, p.class_id, 'active', p.created_at::date, now(), now()
        FROM persons p
        WHERE p.class_id IS NOT NULL AND p.is_deleted = false
        """
    )


def downgrade() -> None:
    op.drop_index("uq_student_enrollments_one_active", table_name="student_enrollments")
    op.drop_index("ix_student_enrollments_class_id", table_name="student_enrollments")
    op.drop_index("ix_student_enrollments_person_id", table_name="student_enrollments")
    op.drop_table("student_enrollments")
