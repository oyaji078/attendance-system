from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "20260516_0009"
down_revision = "20260515_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    # CREATE INDEX CONCURRENTLY cannot run inside a transaction block.
    # COMMIT ends Alembic's implicit transaction so the index builds without
    # holding an AccessExclusiveLock on face_templates.
    connection.execute(text("COMMIT"))

    # Drop the legacy index created by 0001_initial_schema (no CONCURRENTLY,
    # no hnsw parameters). Safe because IF EXISTS avoids errors if already gone.
    connection.execute(text("DROP INDEX CONCURRENTLY IF EXISTS face_templates_embedding_hnsw_idx"))

    # Build the production-ready HNSW index with cosine distance operator class
    # and tuned construction parameters.
    connection.execute(text("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS
            idx_face_templates_embedding_hnsw
        ON face_templates
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """))


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(text("COMMIT"))

    connection.execute(text("DROP INDEX CONCURRENTLY IF EXISTS idx_face_templates_embedding_hnsw"))

    # Restore the original index from 0001_initial_schema (no extra params).
    connection.execute(text("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS
            face_templates_embedding_hnsw_idx
        ON face_templates
        USING hnsw (embedding vector_cosine_ops)
    """))
