"""Document chunk model for pgvector RAG (replaces Milvus on Azure Non-Prod)."""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Column, Index, Text
from sqlmodel import Field, SQLModel


class DocumentChunk(SQLModel, table=True):
    """Semantic document chunk with embedding for QuantChat / job matching RAG."""

    __tablename__ = "document_chunks"
    __table_args__ = (
        Index("ix_document_chunks_document_id", "document_id"),
        Index("ix_document_chunks_document_type", "document_type"),
        Index("ix_document_chunks_entity_name", "entity_name"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    document_id: str = Field(max_length=128)
    document_type: str = Field(max_length=32)  # resume | job_description
    entity_name: str = Field(default="Unknown", max_length=255)
    section_type: str = Field(default="", max_length=128)
    chunk_text: str = Field(sa_column=Column(Text, nullable=False))
    full_content: Optional[str] = Field(default=None, sa_column=Column(Text))
    candidate_id: Optional[UUID] = Field(default=None, foreign_key="candidates.id", index=True)
    job_id: Optional[UUID] = Field(default=None, foreign_key="jobs.id", index=True)
    vector: Optional[list] = Field(
        default=None,
        sa_column=Column(Vector(768)),
    )
    embedding_model: str = Field(default="BAAI/bge-base-en-v1.5", max_length=100)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    def __repr__(self) -> str:
        return (
            f"<DocumentChunk {self.document_type}:{self.document_id} "
            f"section={self.section_type}>"
        )
