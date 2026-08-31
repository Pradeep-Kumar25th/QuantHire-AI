"""Job service with AI agent integration."""

import sys
import os
import logging

# Add agents path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
agents_path = os.path.join(project_root, "agents", "agents")
if os.path.exists(agents_path) and agents_path not in sys.path:
    sys.path.insert(0, agents_path)

from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.jobs import Job, JobStatus

logger = logging.getLogger(__name__)


class JobService:
    """Service for job-related operations."""

    def __init__(self, session: AsyncSession):
        """Initialize job service.
        
        Args:
            session: Database session
        """
        self.session = session
        # SpecAgent is optional - only use if available
        try:
            from agents.spec.agent import SpecAgent
            self.spec_agent = SpecAgent()
        except ImportError:
            logger.warning("SpecAgent not available - will skip spec generation")
            self.spec_agent = None

    async def create_job_with_ai(
        self,
        title: str,
        description: str,
        level: Optional[str] = None,
        department: Optional[str] = None,
        location: Optional[str] = None,
        remote_allowed: bool = False,
        created_by: UUID = None,
    ) -> Job:
        """Create job with AI-powered spec generation.
        
        Args:
            title: Job title
            description: Job description
            level: Job level (optional)
            department: Department (optional)
            location: Location (optional)
            created_by: User ID who created the job
            
        Returns:
            Created job with generated spec
        """
        # Use SpecAgent to generate structured spec if available
        spec_data = {}
        if self.spec_agent:
            try:
                spec_result = await self.spec_agent.execute({
                    "description": description,
                    "level": level,
                    "department": department,
                    "location": location,
                })
                
                if spec_result.success:
                    spec_data = spec_result.output
            except Exception as e:
                logger.warning(f"Spec generation failed, continuing without spec: {e}")
        
        # Parse description if it's a JSON string
        try:
            if isinstance(description, str) and description.strip().startswith('{'):
                import json
                parsed_desc = json.loads(description)
                # Extract structured data from parsed description
                if isinstance(parsed_desc, dict):
                    spec_data.update(parsed_desc.get("sections", {}))
        except Exception:
            pass  # Use description as-is if parsing fails
        
        # Create job
        job = Job(
            title=title or spec_data.get("title", ""),
            level=level or spec_data.get("level", ""),
            department=department or spec_data.get("department", ""),
            location=location,
            remote_allowed=remote_allowed,
            description=description,
            spec_json=spec_data,
            status=JobStatus.DRAFT,
            created_by=created_by,
        )
        
        self.session.add(job)
        await self.session.flush()
        
        # ============================================================================
        # ENTERPRISE RAG REMOVED - Job storage now DB-only
        # ============================================================================
        # The Enterprise RAG Service has been removed to enforce single RAG pipeline.
        # Job data is stored in PostgreSQL only. For RAG queries, use QueryRouter.
        # 
        # TODO: Implement dedicated job/JD storage service if needed (separate from RAG).
        # ============================================================================
        logger.info(f"Job {job.id} created (DB storage only - Enterprise RAG removed)")
        
        await self.session.commit()
        await self.session.refresh(job)
        
        return job

    async def get_job(self, job_id: UUID) -> Optional[Job]:
        """Get job by ID.
        
        Args:
            job_id: Job ID
            
        Returns:
            Job or None
        """
        result = await self.session.execute(
            select(Job).where(Job.id == job_id)
        )
        return result.scalar_one_or_none()

    async def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        department: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[Job]:
        """List jobs with filtering.
        
        Args:
            status: Filter by status
            department: Filter by department
            skip: Offset
            limit: Limit
            
        Returns:
            List of jobs
        """
        query = select(Job)
        
        if status:
            query = query.where(Job.status == status)
        if department:
            query = query.where(Job.department == department)
        
        query = query.offset(skip).limit(limit).order_by(Job.created_at.desc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def publish_job(self, job_id: UUID) -> Job:
        """Publish a job (change status to OPEN).
        
        Args:
            job_id: Job ID
            
        Returns:
            Updated job
        """
        job = await self.get_job(job_id)
        if not job:
            raise ValueError("Job not found")
        
        job.status = JobStatus.OPEN
        await self.session.commit()
        await self.session.refresh(job)
        
        return job

    async def match_candidates(
        self,
        job_id: UUID,
        top_k: int = 10
    ) -> List[Dict]:
        """Find best matching candidates for a job.
        
        Args:
            job_id: Job ID
            top_k: Number of candidates to return
            
        Returns:
            List of candidate matches with scores
        """
        # This will use the vector store
        from agents.rag.vector_store import get_vector_store
        from app.config import settings
        
        vector_store = get_vector_store(settings.database_url)

        try:
            matches = await vector_store.search_similar_candidates(job_id, top_k)

            if not matches:
                return []

            from app.models.candidates import Candidate

            candidate_ids = [candidate_id for candidate_id, _ in matches]
            result = await self.session.execute(
                select(Candidate).where(Candidate.id.in_(candidate_ids))
            )
            candidates_by_id = {candidate.id: candidate for candidate in result.scalars().all()}

            results = []
            for candidate_id, similarity in matches:
                candidate = candidates_by_id.get(candidate_id)
                if candidate:
                    results.append(
                        {
                            "candidate_id": str(candidate.id),
                            "name": candidate.name,
                            "email": candidate.email,
                            "match_score": similarity * 100,
                            "skills": candidate.profile_json.get("skills", []),
                            "experience": len(candidate.profile_json.get("experience", [])),
                        }
                    )

            return results

        finally:
            pass

