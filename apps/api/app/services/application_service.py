"""Application service with AI agent integration."""

import sys
sys.path.insert(0, "/agents")

from typing import Dict, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.applications import Application, ApplicationStatus
from app.models.candidates import Candidate
from app.models.jobs import Job
from agents.decision.agent import DecisionAgent


class ApplicationService:
    """Service for application-related operations."""

    def __init__(self, session: AsyncSession):
        """Initialize application service.
        
        Args:
            session: Database session
        """
        self.session = session
        self.decision_agent = DecisionAgent()

    async def create_application(
        self,
        candidate_id: UUID,
        job_id: UUID,
        source: Optional[str] = None,
    ) -> Application:
        """Create application and calculate initial match score.
        
        Args:
            candidate_id: Candidate ID
            job_id: Job ID
            source: Application source
            
        Returns:
            Created application
        """
        # Verify candidate and job exist
        candidate = await self.session.get(Candidate, candidate_id)
        job = await self.session.get(Job, job_id)
        
        if not candidate:
            raise ValueError("Candidate not found")
        if not job:
            raise ValueError("Job not found")
        
        # Get match score from vector store
        from agents.rag.vector_store import VectorStore
        from app.config import settings
        
        vector_store = VectorStore(settings.database_url)
        
        try:
            matches = await vector_store.search_similar_candidates(job_id, top_k=100)
            
            # Find this candidate's score
            match_score = None
            for cid, score in matches:
                if cid == candidate_id:
                    match_score = score * 100
                    break
            
            if match_score is None:
                match_score = 50.0  # Default if not found
                
        finally:
            await vector_store.close()
        
        # Create application
        application = Application(
            candidate_id=candidate_id,
            job_id=job_id,
            source=source,
            status=ApplicationStatus.APPLIED,
            match_score=match_score,
        )
        
        self.session.add(application)
        await self.session.commit()
        await self.session.refresh(application)
        
        return application

    async def get_application(self, application_id: UUID) -> Optional[Application]:
        """Get application by ID.
        
        Args:
            application_id: Application ID
            
        Returns:
            Application or None
        """
        result = await self.session.execute(
            select(Application).where(Application.id == application_id)
        )
        return result.scalar_one_or_none()

    async def get_decision_recommendation(
        self,
        application_id: UUID
    ) -> Dict:
        """Get AI decision recommendation for application.
        
        Args:
            application_id: Application ID
            
        Returns:
            Decision recommendation
        """
        application = await self.get_application(application_id)
        if not application:
            raise ValueError("Application not found")
        
        # Get candidate and job
        candidate = await self.session.get(Candidate, application.candidate_id)
        job = await self.session.get(Job, application.job_id)
        
        # Use DecisionAgent
        decision_result = await self.decision_agent.execute({
            "candidate": {
                "id": str(candidate.id),
                "name": candidate.name,
                "profile_json": candidate.profile_json,
            },
            "job": {
                "id": str(job.id),
                "title": job.title,
                "spec_json": job.spec_json,
            },
            "match_score": application.match_score,
            "assessment_score": application.assessment_score,
            "interview_scores": application.interview_scores or {},
            "screening_notes": application.screening_notes or "",
        })
        
        if not decision_result.success:
            raise ValueError(f"Failed to get decision: {decision_result.error}")
        
        # Update application with recommendation
        decision_data = decision_result.output
        application.agent_recommendation = decision_data.get("recommendation")
        application.agent_confidence = decision_result.confidence
        application.agent_rationale = decision_data.get("rationale")
        
        await self.session.commit()
        
        return decision_data

