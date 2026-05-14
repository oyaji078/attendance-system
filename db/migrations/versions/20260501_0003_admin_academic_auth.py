from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260501_0003"
down_revision = "20260420_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_admin_users_username", "admin_users", ["username"], unique=False)

    op.create_table(
        "lecturers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("lecturer_code", sa.String(length=64), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("department", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lecturer_code"),
    )
    op.create_index("ix_lecturers_lecturer_code", "lecturers", ["lecturer_code"], unique=False)

    op.create_table(
        "classes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("class_code", sa.String(length=64), nullable=False),
        sa.Column("class_name", sa.String(length=255), nullable=False),
        sa.Column("lecturer_id", sa.UUID(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["lecturer_id"], ["lecturers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("class_code"),
    )
    op.create_index("ix_classes_class_code", "classes", ["class_code"], unique=False)
    op.create_index("ix_classes_lecturer_id", "classes", ["lecturer_id"], unique=False)

    op.add_column("persons", sa.Column("class_id", sa.UUID(), nullable=True))
    op.create_index("ix_persons_class_id", "persons", ["class_id"], unique=False)
    op.create_foreign_key("fk_persons_class_id", "persons", "classes", ["class_id"], ["id"], ondelete="SET NULL")

    op.add_column("device_configs", sa.Column("candidate_margin_threshold", sa.Float(), server_default="0.05", nullable=False))

    op.add_column("attendance_sessions", sa.Column("class_id", sa.UUID(), nullable=True))
    op.add_column("attendance_sessions", sa.Column("lecturer_id", sa.UUID(), nullable=True))
    op.add_column("attendance_sessions", sa.Column("device_code", sa.String(length=64), nullable=True))
    op.create_index("ix_attendance_sessions_class_id", "attendance_sessions", ["class_id"], unique=False)
    op.create_index("ix_attendance_sessions_lecturer_id", "attendance_sessions", ["lecturer_id"], unique=False)
    op.create_foreign_key("fk_attendance_sessions_class_id", "attendance_sessions", "classes", ["class_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_attendance_sessions_lecturer_id", "attendance_sessions", "lecturers", ["lecturer_id"], ["id"], ondelete="SET NULL")

    op.add_column("attendance_logs", sa.Column("captured_image_uri", sa.Text(), nullable=True))
    op.add_column("attendance_logs", sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.create_index("ix_attendance_logs_is_deleted", "attendance_logs", ["is_deleted"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_attendance_logs_is_deleted", table_name="attendance_logs")
    op.drop_column("attendance_logs", "is_deleted")
    op.drop_column("attendance_logs", "captured_image_uri")

    op.drop_constraint("fk_attendance_sessions_lecturer_id", "attendance_sessions", type_="foreignkey")
    op.drop_constraint("fk_attendance_sessions_class_id", "attendance_sessions", type_="foreignkey")
    op.drop_index("ix_attendance_sessions_lecturer_id", table_name="attendance_sessions")
    op.drop_index("ix_attendance_sessions_class_id", table_name="attendance_sessions")
    op.drop_column("attendance_sessions", "device_code")
    op.drop_column("attendance_sessions", "lecturer_id")
    op.drop_column("attendance_sessions", "class_id")

    op.drop_column("device_configs", "candidate_margin_threshold")

    op.drop_constraint("fk_persons_class_id", "persons", type_="foreignkey")
    op.drop_index("ix_persons_class_id", table_name="persons")
    op.drop_column("persons", "class_id")

    op.drop_index("ix_classes_lecturer_id", table_name="classes")
    op.drop_index("ix_classes_class_code", table_name="classes")
    op.drop_table("classes")
    op.drop_index("ix_lecturers_lecturer_code", table_name="lecturers")
    op.drop_table("lecturers")
    op.drop_index("ix_admin_users_username", table_name="admin_users")
    op.drop_table("admin_users")
