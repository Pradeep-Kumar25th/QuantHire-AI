"""Embedding generation tasks - COMPLETE IMPLEMENTATION."""

import os
import sys
sys.path.insert(0, "/agents")
sys.path.insert(0, "/api")

from uuid import UUID

from worker.celery_app import app
from agents.rag.embeddings import EmbeddingService
from agents.rag.vector_store import VectorStore


def get_vector_store():
    """Get vector store instance."""
    database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://quanthire:password@postgres:5432/quanthire")
    return VectorStore(database_url)


def get_embedding_service():
    """Get embedding service instance."""
    return EmbeddingService()


@app.task(bind=True, max_retries=3)
def generate_candidate_embedding(self, candidate_id: str, profile_text: str):
    """Generate embedding for candidate profile.
    
    Args:
        candidate_id: Candidate ID
        profile_text: Candidate profile text
        
    Returns:
        dict: Embedding data
    """
    try:
        import asyncio
        
        vector_store = get_vector_store()
        embedding_service = get_embedding_service()
        
        # Generate embedding
        loop = asyncio.get_event_loop()
        embedding = loop.run_until_complete(
            embedding_service.generate_embedding(profile_text)
        )
        
        # Store in vector store
        loop.run_until_complete(
            vector_store.store_candidate_embedding(UUID(candidate_id), embedding)
        )
        
        # Cleanup
        loop.run_until_complete(vector_store.close())
        
        return {
            "candidate_id": candidate_id,
            "status": "completed",
            "vector_dimension": len(embedding),
            "model": embedding_service.model
        }
    
    except Exception as e:
        raise self.retry(exc=e, countdown=2 ** self.request.retries)


@app.task(bind=True, max_retries=3)
def generate_job_embedding(self, job_id: str, job_text: str):
    """Generate embedding for job specification.
    
    Args:
        job_id: Job ID
        job_text: Job specification text
        
    Returns:
        dict: Embedding data
    """
    try:
        import asyncio
        
        vector_store = get_vector_store()
        embedding_service = get_embedding_service()
        
        # Generate embedding
        loop = asyncio.get_event_loop()
        embedding = loop.run_until_complete(
            embedding_service.generate_embedding(job_text)
        )
        
        # Store in vector store
        loop.run_until_complete(
            vector_store.store_job_embedding(UUID(job_id), embedding)
        )
        
        # Cleanup
        loop.run_until_complete(vector_store.close())
        
        return {
            "job_id": job_id,
            "status": "completed",
            "vector_dimension": len(embedding),
            "model": embedding_service.model
        }
    
    except Exception as e:
        raise self.retry(exc=e, countdown=2 ** self.request.retries)


@app.task
def batch_generate_embeddings(items: list, item_type: str = "candidate"):
    """Batch generate embeddings for multiple items.
    
    Args:
        items: List of dicts with 'id' and 'text' keys
        item_type: 'candidate' or 'job'
        
    Returns:
        dict: Summary of results
    """
    from celery import group
    
    if item_type == "candidate":
        task_func = generate_candidate_embedding
    else:
        task_func = generate_job_embedding
    
    # Create group of tasks
    job = group(
        task_func.s(item["id"], item["text"])
        for item in items
    )
    
    result = job.apply_async()
    
    return {
        "job_id": result.id,
        "total": len(items),
        "type": item_type,
        "status": "processing"
    }
