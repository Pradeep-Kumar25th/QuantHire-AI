"""Vector store implementation using pgvector."""

import os
from functools import lru_cache
from typing import List, Optional, Tuple
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import bindparam, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


def _embedding_dimensions() -> int:
    try:
        return int(os.getenv("EMBEDDING_DIMENSION", "768"))
    except ValueError:
        return 768


def _vector_param(name: str):
    """Bind a Python float list to a pgvector column in raw SQL."""
    return bindparam(name, type_=Vector(_embedding_dimensions()))


def _embedding_model_label() -> str:
    from agents.rag.unified_embeddings import embedding_model_label

    return embedding_model_label()


@lru_cache(maxsize=1)
def get_vector_store(database_url: str) -> "VectorStore":
    """Return a process-wide VectorStore singleton (one engine/pool)."""
    return VectorStore(database_url)


class VectorStore:
    """Vector store using PostgreSQL with pgvector extension."""

    def __init__(self, database_url: str):
        """Initialize vector store.
        
        Args:
            database_url: Async PostgreSQL connection string
        """
        # asyncpg rejects the libpq ``sslmode`` query param (Azure URLs use
        # ``?sslmode=require``) — translate it to the asyncpg ``ssl`` arg.
        url = make_url(database_url)
        if url.drivername in ("postgres", "postgresql"):
            url = url.set(drivername="postgresql+asyncpg")
        query = dict(url.query)
        sslmode = query.pop("sslmode", None)
        url = url.set(query=query)
        connect_args = {}
        if sslmode in ("require", "verify-ca", "verify-full"):
            connect_args["ssl"] = True
        elif sslmode == "disable":
            connect_args["ssl"] = False

        self.engine = create_async_engine(url, echo=False, connect_args=connect_args)
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def store_job_embedding(
        self,
        job_id: UUID,
        embedding: List[float],
        model: Optional[str] = None,
    ) -> None:
        """Store job embedding in vector store.
        
        Args:
            job_id: Job ID
            embedding: Embedding vector
            model: Model used for embedding
        """
        model_name = model or _embedding_model_label()
        async with self.async_session() as session:
            # Check if embedding already exists
            result = await session.execute(
                text("SELECT id FROM job_embeddings WHERE job_id = :job_id"),
                {"job_id": str(job_id)}
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                # Update
                stmt = text("""
                        UPDATE job_embeddings 
                        SET vector = :vector, model = :model, updated_at = NOW()
                        WHERE job_id = :job_id
                    """).bindparams(_vector_param("vector"))
                await session.execute(
                    stmt,
                    {
                        "job_id": str(job_id),
                        "vector": embedding,
                        "model": model_name,
                    }
                )
            else:
                # Insert
                stmt = text("""
                        INSERT INTO job_embeddings (id, job_id, vector, model, created_at, updated_at)
                        VALUES (gen_random_uuid(), :job_id, :vector, :model, NOW(), NOW())
                    """).bindparams(_vector_param("vector"))
                await session.execute(
                    stmt,
                    {
                        "job_id": str(job_id),
                        "vector": embedding,
                        "model": model_name,
                    }
                )
            
            await session.commit()

    async def store_candidate_embedding(
        self,
        candidate_id: UUID,
        embedding: List[float],
        model: Optional[str] = None,
    ) -> None:
        """Store candidate embedding in vector store.
        
        Args:
            candidate_id: Candidate ID
            embedding: Embedding vector
            model: Model used for embedding
        """
        model_name = model or _embedding_model_label()
        async with self.async_session() as session:
            # Check if embedding already exists
            result = await session.execute(
                text("SELECT id FROM candidate_embeddings WHERE candidate_id = :candidate_id"),
                {"candidate_id": str(candidate_id)}
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                # Update
                stmt = text("""
                        UPDATE candidate_embeddings 
                        SET vector = :vector, model = :model, updated_at = NOW()
                        WHERE candidate_id = :candidate_id
                    """).bindparams(_vector_param("vector"))
                await session.execute(
                    stmt,
                    {
                        "candidate_id": str(candidate_id),
                        "vector": embedding,
                        "model": model_name,
                    }
                )
            else:
                # Insert
                stmt = text("""
                        INSERT INTO candidate_embeddings 
                        (id, candidate_id, vector, model, created_at, updated_at)
                        VALUES (gen_random_uuid(), :candidate_id, :vector, :model, NOW(), NOW())
                    """).bindparams(_vector_param("vector"))
                await session.execute(
                    stmt,
                    {
                        "candidate_id": str(candidate_id),
                        "vector": embedding,
                        "model": model_name,
                    }
                )
            
            await session.commit()

    async def search_similar_candidates(
        self,
        job_id: UUID,
        top_k: int = 10
    ) -> List[Tuple[UUID, float]]:
        """Find candidates most similar to a job.
        
        Args:
            job_id: Job ID to match against
            top_k: Number of results to return
            
        Returns:
            List of (candidate_id, similarity_score) tuples
        """
        async with self.async_session() as session:
            # Get job embedding
            result = await session.execute(
                text("SELECT vector FROM job_embeddings WHERE job_id = :job_id"),
                {"job_id": str(job_id)}
            )
            job_embedding = result.scalar_one_or_none()
            
            if not job_embedding:
                return []
            
            # Find similar candidates using cosine similarity
            stmt = text("""
                    SELECT 
                        candidate_id,
                        1 - (vector <=> :job_vector) as similarity
                    FROM candidate_embeddings
                    WHERE vector IS NOT NULL
                    ORDER BY vector <=> :job_vector
                    LIMIT :limit
                """).bindparams(_vector_param("job_vector"))
            result = await session.execute(
                stmt,
                {
                    "job_vector": job_embedding,
                    "limit": top_k
                }
            )
            
            rows = result.fetchall()
            return [(UUID(row[0]), float(row[1])) for row in rows]

    async def search_similar_jobs(
        self,
        candidate_id: UUID,
        top_k: int = 10
    ) -> List[Tuple[UUID, float]]:
        """Find jobs most similar to a candidate.
        
        Args:
            candidate_id: Candidate ID to match against
            top_k: Number of results to return
            
        Returns:
            List of (job_id, similarity_score) tuples
        """
        async with self.async_session() as session:
            # Get candidate embedding
            result = await session.execute(
                text("SELECT vector FROM candidate_embeddings WHERE candidate_id = :candidate_id"),
                {"candidate_id": str(candidate_id)}
            )
            candidate_embedding = result.scalar_one_or_none()
            
            if not candidate_embedding:
                return []
            
            # Find similar jobs
            stmt = text("""
                    SELECT 
                        job_id,
                        1 - (vector <=> :candidate_vector) as similarity
                    FROM job_embeddings
                    WHERE vector IS NOT NULL
                    ORDER BY vector <=> :candidate_vector
                    LIMIT :limit
                """).bindparams(_vector_param("candidate_vector"))
            result = await session.execute(
                stmt,
                {
                    "candidate_vector": candidate_embedding,
                    "limit": top_k
                }
            )
            
            rows = result.fetchall()
            return [(UUID(row[0]), float(row[1])) for row in rows]

    async def close(self) -> None:
        """Close database connections."""
        await self.engine.dispose()

