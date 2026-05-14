from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260502_0005"
down_revision = "20260501_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("persons", sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("persons", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_persons_is_deleted", "persons", ["is_deleted"], unique=False)

    op.add_column("admin_users", sa.Column("role", sa.String(length=32), server_default="admin", nullable=False))
    op.add_column("admin_users", sa.Column("lecturer_id", sa.UUID(), nullable=True))
    op.create_index("ix_admin_users_role", "admin_users", ["role"], unique=False)
    op.create_index("ix_admin_users_lecturer_id", "admin_users", ["lecturer_id"], unique=False)
    op.create_foreign_key("fk_admin_users_lecturer_id", "admin_users", "lecturers", ["lecturer_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.drop_constraint("fk_admin_users_lecturer_id", "admin_users", type_="foreignkey")
    op.drop_index("ix_admin_users_lecturer_id", table_name="admin_users")
    op.drop_index("ix_admin_users_role", table_name="admin_users")
    op.drop_column("admin_users", "lecturer_id")
    op.drop_column("admin_users", "role")

    op.drop_index("ix_persons_is_deleted", table_name="persons")
    op.drop_column("persons", "deleted_at")
    op.drop_column("persons", "is_deleted")
