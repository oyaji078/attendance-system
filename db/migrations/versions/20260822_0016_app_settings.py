"""Small key/value store for console settings.

The redesigned console has a Pengaturan page holding a handful of values that
are neither per-device (that is ``device_configs``) nor per-user: the school
name in the header, and the academic year/semester the console preselects so
staff do not re-pick the same period on every page.

Key/value rather than a wide table: these are display preferences that come and
go, and a new one should not need a migration.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260822_0016"
down_revision = "20260822_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
