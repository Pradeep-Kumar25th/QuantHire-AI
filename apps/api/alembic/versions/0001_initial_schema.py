"""Initial QuantHire schema (Postgres + pgvector).

Creates all SQLModel tables registered in alembic/env.py.
Fresh Azure Non-Prod deploys should run: alembic upgrade head
"""

from alembic import op
from sqlalchemy import inspect
from sqlmodel import SQLModel

from app.models import (  # noqa: F401
    applications,
    assessments,
    audit_logs,
    candidates,
    document_chunks,
    interviews,
    jobs,
    offers,
    organizations,
    users,
)

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    bind = op.get_bind()
    SQLModel.metadata.create_all(bind=bind)

    inspector = inspect(bind)
    if inspector.has_table("document_chunks"):
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_document_chunks_vector_hnsw
            ON document_chunks USING hnsw (vector vector_cosine_ops)
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    SQLModel.metadata.drop_all(bind=bind)
