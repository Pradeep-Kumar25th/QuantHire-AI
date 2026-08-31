"""Retriever for RAG (Retrieval-Augmented Generation)."""

from typing import Any, Dict, List
from uuid import UUID

from agents.rag.embeddings import EmbeddingService
from agents.rag.vector_store import VectorStore


class Retriever:
    """Retriever for finding relevant context."""

    def __init__(self, vector_store: VectorStore, embedding_service: EmbeddingService):
        """Initialize retriever.
        
        Args:
            vector_store: Vector store instance
            embedding_service: Embedding service instance
        """
        self.vector_store = vector_store
        self.embedding_service = embedding_service

    async def retrieve_for_job(
        self,
        job_id: UUID,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """Retrieve top matching candidates for a job.
        
        Args:
            job_id: Job ID
            top_k: Number of candidates to retrieve
            
        Returns:
            List of candidate matches with scores
        """
        # Search vector store
        matches = await self.vector_store.search_similar_candidates(job_id, top_k)
        
        # Format results
        results = []
        for candidate_id, similarity in matches:
            results.append({
                "candidate_id": str(candidate_id),
                "similarity_score": similarity,
                "match_score": similarity * 100  # Convert to 0-100 scale
            })
        
        return results

    async def retrieve_for_candidate(
        self,
        candidate_id: UUID,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """Retrieve top matching jobs for a candidate.
        
        Args:
            candidate_id: Candidate ID
            top_k: Number of jobs to retrieve
            
        Returns:
            List of job matches with scores
        """
        # Search vector store
        matches = await self.vector_store.search_similar_jobs(candidate_id, top_k)
        
        # Format results
        results = []
        for job_id, similarity in matches:
            results.append({
                "job_id": str(job_id),
                "similarity_score": similarity,
                "match_score": similarity * 100  # Convert to 0-100 scale
            })
        
        return results

    async def generate_and_store_job_embedding(
        self,
        job_id: UUID,
        job_text: str
    ) -> None:
        """Generate and store embedding for a job.
        
        Args:
            job_id: Job ID
            job_text: Job description/specification text
        """
        # Generate embedding
        embedding = await self.embedding_service.generate_embedding(job_text)
        
        # Store in vector store
        await self.vector_store.store_job_embedding(job_id, embedding)

    async def generate_and_store_candidate_embedding(
        self,
        candidate_id: UUID,
        candidate_text: str
    ) -> None:
        """Generate and store embedding for a candidate.
        
        Args:
            candidate_id: Candidate ID
            candidate_text: Candidate profile/resume text
        """
        # Generate embedding
        embedding = await self.embedding_service.generate_embedding(candidate_text)
        
        # Store in vector store
        await self.vector_store.store_candidate_embedding(candidate_id, embedding)

