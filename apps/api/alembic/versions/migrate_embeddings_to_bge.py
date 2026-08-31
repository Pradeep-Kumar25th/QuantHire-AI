"""Migrate embeddings from OpenAI (1536d) to BGE (768d)

Revision ID: migrate_embeddings_to_bge
Revises: 0001_initial_schema
Create Date: 2026-01-24

Safe for Azure Non-Prod: skips destructive DELETE when tables are already vector(768).
"""
from alembic import op
import sqlalchemy as sa


revision = "migrate_embeddings_to_bge"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def _pg_vector_type(bind, table_name: str, column_name: str = "vector") -> str | None:
    row = bind.execute(
        sa.text(
            """
            SELECT format_type(a.atttypid, a.atttypmod)
            FROM pg_attribute a
            JOIN pg_class c ON a.attrelid = c.oid
            JOIN pg_namespace n ON c.relnamespace = n.oid
            WHERE c.relname = :table_name
              AND a.attname = :column_name
              AND NOT a.attisdropped
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    ).scalar()
    return row


def upgrade():
    """
    Migrate 1536-dim embeddings to 768-dim BGE.

    Fresh installs and databases already on vector(768) are no-ops (no data deleted).
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("candidate_embeddings"):
        return

    candidate_vector_type = _pg_vector_type(bind, "candidate_embeddings")
    job_vector_type = _pg_vector_type(bind, "job_embeddings")

    if candidate_vector_type == "vector(768)" and job_vector_type == "vector(768)":
        return

    if candidate_vector_type != "vector(1536)" or job_vector_type != "vector(1536)":
        raise RuntimeError(
            "Unexpected embedding vector dimensions: "
            f"candidate_embeddings={candidate_vector_type}, "
            f"job_embeddings={job_vector_type}. "
            "Manual migration required."
        )

    op.execute("DELETE FROM candidate_embeddings")
    op.execute("DELETE FROM job_embeddings")
    op.execute("ALTER TABLE candidate_embeddings ALTER COLUMN vector TYPE vector(768)")
    op.execute("ALTER TABLE job_embeddings ALTER COLUMN vector TYPE vector(768)")
    op.execute(
        "UPDATE candidate_embeddings SET model = 'BAAI/bge-base-en-v1.5' "
        "WHERE model = 'text-embedding-3-large'"
    )
    op.execute(
        "UPDATE job_embeddings SET model = 'BAAI/bge-base-en-v1.5' "
        "WHERE model = 'text-embedding-3-large'"
    )


def downgrade():
    """Rollback to OpenAI embeddings — only when currently vector(768)."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("candidate_embeddings"):
        return

    candidate_vector_type = _pg_vector_type(bind, "candidate_embeddings")
    if candidate_vector_type != "vector(768)":
        return

    op.execute("DELETE FROM candidate_embeddings")
    op.execute("DELETE FROM job_embeddings")
    op.execute("ALTER TABLE candidate_embeddings ALTER COLUMN vector TYPE vector(1536)")
    op.execute("ALTER TABLE job_embeddings ALTER COLUMN vector TYPE vector(1536)")
    op.execute(
        "UPDATE candidate_embeddings SET model = 'text-embedding-3-large' "
        "WHERE model = 'BAAI/bge-base-en-v1.5'"
    )
    op.execute(
        "UPDATE job_embeddings SET model = 'text-embedding-3-large' "
        "WHERE model = 'BAAI/bge-base-en-v1.5'"
    )
