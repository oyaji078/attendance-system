from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "20260416_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "persons",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.String(length=64), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("primary_template_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("student_id"),
    )
    op.create_index("ix_persons_student_id", "persons", ["student_id"], unique=False)

    op.create_table(
        "device_configs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("device_code", sa.String(length=64), nullable=False),
        sa.Column("device_name", sa.String(length=255), nullable=False),
        sa.Column("location_hint", sa.String(length=255), nullable=True),
        sa.Column("det_thresh", sa.Float(), nullable=False, server_default="0.60"),
        sa.Column("det_size_width", sa.Integer(), nullable=False, server_default="320"),
        sa.Column("det_size_height", sa.Integer(), nullable=False, server_default="320"),
        sa.Column("max_faces", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("min_face_width_px", sa.Integer(), nullable=False, server_default="160"),
        sa.Column("min_brightness", sa.Float(), nullable=False, server_default="75"),
        sa.Column("min_blur_score", sa.Float(), nullable=False, server_default="90"),
        sa.Column("similarity_threshold", sa.Float(), nullable=False, server_default="0.45"),
        sa.Column("liveness_threshold", sa.Float(), nullable=False, server_default="0.70"),
        sa.Column("multi_frame_confirm", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("accepted_per_pose", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("cooldown_seconds", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_code"),
    )
    op.create_index("ix_device_configs_device_code", "device_configs", ["device_code"], unique=False)

    op.create_table(
        "attendance_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("session_code", sa.String(length=64), nullable=False),
        sa.Column("session_name", sa.String(length=255), nullable=False),
        sa.Column("session_kind", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("cooldown_seconds", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_code"),
    )
    op.create_index("ix_attendance_sessions_session_code", "attendance_sessions", ["session_code"], unique=False)

    op.create_table(
        "face_samples",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("person_id", sa.UUID(), nullable=False),
        sa.Column("enrollment_session_id", sa.UUID(), nullable=False),
        sa.Column("pose", sa.String(length=32), nullable=False),
        sa.Column("embedding", Vector(512), nullable=False),
        sa.Column("image_uri", sa.Text(), nullable=True),
        sa.Column("source_device_code", sa.String(length=64), nullable=False),
        sa.Column("brightness_score", sa.Float(), nullable=False),
        sa.Column("blur_score", sa.Float(), nullable=False),
        sa.Column("liveness_score", sa.Float(), nullable=False),
        sa.Column("face_width_px", sa.Integer(), nullable=False),
        sa.Column("quality_flags", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_face_samples_enrollment_session_id", "face_samples", ["enrollment_session_id"], unique=False)
    op.create_index("ix_face_samples_pose", "face_samples", ["pose"], unique=False)

    op.create_table(
        "face_templates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("person_id", sa.UUID(), nullable=False),
        sa.Column("embedding", Vector(512), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("built_from_session_id", sa.UUID(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("person_id", "is_active", name="uq_face_templates_person_active"),
    )
    op.create_index("ix_face_templates_person_id", "face_templates", ["person_id"], unique=False)
    op.execute(
        """
        CREATE INDEX face_templates_embedding_hnsw_idx
        ON face_templates
        USING hnsw (embedding vector_cosine_ops)
        """
    )

    op.create_table(
        "attendance_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=True),
        sa.Column("person_id", sa.UUID(), nullable=True),
        sa.Column("matched_template_id", sa.UUID(), nullable=True),
        sa.Column("device_code", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("liveness_score", sa.Float(), nullable=True),
        sa.Column("frame_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["matched_template_id"], ["face_templates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["attendance_sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_attendance_logs_created_at", "attendance_logs", ["created_at"], unique=False)
    op.create_index("ix_attendance_logs_decision", "attendance_logs", ["decision"], unique=False)
    op.create_index("ix_attendance_logs_device_code", "attendance_logs", ["device_code"], unique=False)
    op.create_index("ix_attendance_logs_person_id", "attendance_logs", ["person_id"], unique=False)
    op.create_index("ix_attendance_logs_session_id", "attendance_logs", ["session_id"], unique=False)

    op.create_foreign_key(
        "fk_persons_primary_template_id",
        "persons",
        "face_templates",
        ["primary_template_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_persons_primary_template_id", "persons", type_="foreignkey")
    op.drop_table("attendance_logs")
    op.drop_index("face_templates_embedding_hnsw_idx", table_name="face_templates")
    op.drop_table("face_templates")
    op.drop_table("face_samples")
    op.drop_table("attendance_sessions")
    op.drop_table("device_configs")
    op.drop_table("persons")
