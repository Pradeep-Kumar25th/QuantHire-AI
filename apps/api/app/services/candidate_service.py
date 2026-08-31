"""Candidate service with AI agent integration."""

import sys
sys.path.insert(0, "/agents")

from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candidates import Candidate
from agents.parsing.agent import ParsingAgent


class CandidateService:
    """Service for candidate-related operations."""

    def __init__(self, session: AsyncSession):
        """Initialize candidate service.
        
        Args:
            session: Database session
        """
        self.session = session
        self.parsing_agent = ParsingAgent()

    async def create_candidate_from_resume(
        self,
        resume_text: str,
        source: str = "upload"
    ) -> Dict:
        """Create candidate from resume using AI parsing.
        
        Args:
            resume_text: Resume text
            source: Source of resume
            
        Returns:
            Dictionary with candidate info and parsing status
        """
        # Parse resume using ParsingAgent
        parse_result = await self.parsing_agent.execute({
            "resume_text": resume_text
        })
        
        if not parse_result.success:
            raise ValueError(f"Failed to parse resume: {parse_result.error}")
        
        parsed_data = parse_result.output
        
        # Create candidate
        candidate = Candidate(
            name=parsed_data.get("name", "Unknown"),
            email=parsed_data.get("emails", [""])[0] if parsed_data.get("emails") else "",
            phone=parsed_data.get("phones", [""])[0] if parsed_data.get("phones") else None,
            location=parsed_data.get("locations", [""])[0] if parsed_data.get("locations") else None,
            raw_resume_text=resume_text,
            profile_json=parsed_data,
            parsing_confidence=parsed_data.get("confidence", 0.0),
            missing_fields=parsed_data.get("ambiguous_fields", []),
            source=source,
        )
        
        self.session.add(candidate)
        await self.session.flush()
        
        # Queue embedding generation (Celery worker — optional in API-only deploys)
        profile_text = f"{candidate.name} {' '.join([s.get('name', '') for s in parsed_data.get('skills', [])])} {resume_text[:1000]}"
        try:
            from worker.tasks.embeddings import generate_candidate_embedding

            generate_candidate_embedding.delay(str(candidate.id), profile_text)
        except ModuleNotFoundError:
            pass
        
        await self.session.commit()
        await self.session.refresh(candidate)
        
        return {
            "candidate_id": str(candidate.id),
            "parsing_status": "completed",
            "confidence": candidate.parsing_confidence,
            "missing_fields": candidate.missing_fields,
            "profile": candidate.profile_json,
        }

    async def get_candidate(self, candidate_id: UUID) -> Optional[Candidate]:
        """Get candidate by ID.
        
        Args:
            candidate_id: Candidate ID
            
        Returns:
            Candidate or None
        """
        result = await self.session.execute(
            select(Candidate).where(Candidate.id == candidate_id)
        )
        return result.scalar_one_or_none()

    async def list_candidates(
        self,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[Candidate]:
        """List candidates with filtering.
        
        Args:
            is_active: Filter by active status
            skip: Offset
            limit: Limit
            
        Returns:
            List of candidates
        """
        query = select(Candidate)
        
        if is_active is not None:
            query = query.where(Candidate.is_active == is_active)
        
        query = query.offset(skip).limit(limit).order_by(Candidate.created_at.desc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def match_jobs(
        self,
        candidate_id: UUID,
        top_k: int = 10
    ) -> List[Dict]:
        """Find best matching jobs for a candidate.
        
        Args:
            candidate_id: Candidate ID
            top_k: Number of jobs to return
            
        Returns:
            List of job matches with scores
        """
        from agents.rag.vector_store import VectorStore
        from app.config import settings
        
        vector_store = VectorStore(settings.database_url)
        
        try:
            matches = await vector_store.search_similar_jobs(candidate_id, top_k)
            
            # Format results
            results = []
            for job_id, similarity in matches:
                # Get job details
                from app.models.jobs import Job
                result = await self.session.execute(
                    select(Job).where(Job.id == job_id)
                )
                job = result.scalar_one_or_none()
                
                if job:
                    results.append({
                        "job_id": str(job.id),
                        "title": job.title,
                        "department": job.department,
                        "match_score": similarity * 100,
                        "level": job.level,
                        "location": job.location,
                    })
            
            return results
            
        finally:
            await vector_store.close()

