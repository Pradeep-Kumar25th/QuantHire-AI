"""Add document_chunks table for pgvector RAG (Phase 4)."""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision = "add_document_chunks_pgvector"
down_revision = "migrate_embeddings_to_bge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("document_chunks"):
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("document_id", sa.String(length=128), nullable=False),
        sa.Column("document_type", sa.String(length=32), nullable=False),
        sa.Column("entity_name", sa.String(length=255), nullable=False, server_default="Unknown"),
        sa.Column("section_type", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("full_content", sa.Text(), nullable=True),
        sa.Column("candidate_id", sa.Uuid(), sa.ForeignKey("candidates.id"), nullable=True),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("vector", Vector(768), nullable=True),
        sa.Column(
            "embedding_model",
            sa.String(length=100),
            nullable=False,
            server_default="BAAI/bge-base-en-v1.5",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("ix_document_chunks_document_type", "document_chunks", ["document_type"])
    op.create_index("ix_document_chunks_entity_name", "document_chunks", ["entity_name"])
    op.create_index("ix_document_chunks_candidate_id", "document_chunks", ["candidate_id"])
    op.create_index("ix_document_chunks_job_id", "document_chunks", ["job_id"])
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_document_chunks_vector_hnsw
        ON document_chunks USING hnsw (vector vector_cosine_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_vector_hnsw")
    op.drop_index("ix_document_chunks_job_id", table_name="document_chunks")
    op.drop_index("ix_document_chunks_candidate_id", table_name="document_chunks")
    op.drop_index("ix_document_chunks_entity_name", table_name="document_chunks")
    op.drop_index("ix_document_chunks_document_type", table_name="document_chunks")
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_table("document_chunks")
