"""Service factory for dependency injection."""

from typing import Type, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.base import BaseService

ServiceType = TypeVar("ServiceType", bound=BaseService)


class ServiceFactory:
    """
    Factory for creating service instances with proper dependency injection.
    
    Benefits:
    - Centralized service creation
    - Consistent dependency injection
    - Easy mocking for testing
    - Type safety
    """
    
    def __init__(self, db: AsyncSession):
        """
        Initialize factory with database session.
        
        Args:
            db: Database session
        """
        self.db = db
    
    def create_job_service(self):
        """Create job service instance."""
        from app.models.jobs import Job
        from app.services.base import BaseService
        
        return BaseService(Job, self.db)
    
    def create_candidate_service(self):
        """Create candidate service instance."""
        from app.models.candidates import Candidate
        from app.services.base import BaseService
        
        return BaseService(Candidate, self.db)
    
    def create_application_service(self):
        """Create application service instance."""
        from app.models.applications import Application
        from app.services.base import BaseService
        
        return BaseService(Application, self.db)
    
    def create_assessment_service(self):
        """Create assessment service instance."""
        from app.models.assessments import Assessment
        from app.services.base import BaseService
        
        return BaseService(Assessment, self.db)
    
    def create_interview_service(self):
        """Create interview service instance."""
        from app.models.interviews import Interview
        from app.services.base import BaseService
        
        return BaseService(Interview, self.db)
    
    def create_offer_service(self):
        """Create offer service instance."""
        from app.models.offers import Offer
        from app.services.base import BaseService
        
        return BaseService(Offer, self.db)
    
    def create_user_service(self):
        """Create user service instance."""
        from app.models.users import User
        from app.services.base import BaseService
        
        return BaseService(User, self.db)


# FastAPI dependency
async def get_service_factory(db: AsyncSession) -> ServiceFactory:
    """
    Get service factory instance.
    
    Usage:
        @router.get("/jobs")
        async def list_jobs(factory: ServiceFactory = Depends(get_service_factory)):
            job_service = factory.create_job_service()
            jobs = await job_service.list()
            return jobs
    """
    return ServiceFactory(db)


class AgentFactory:
    """
    Factory for creating agent instances.
    
    Centralizes agent creation with proper configuration.
    """
    
    @staticmethod
    def create_parsing_agent():
        """Create ParsingAgent instance."""
        from agents.parsing.agent import ParsingAgent
        return ParsingAgent()
    
    @staticmethod
    def create_spec_agent():
        """Create SpecAgent instance."""
        from agents.spec.agent import SpecAgent
        return SpecAgent()
    
    @staticmethod
    def create_matching_agent():
        """Create MatchingAgent instance."""
        from agents.matching.agent import MatchingAgent
        return MatchingAgent()
    
    @staticmethod
    def create_decision_agent():
        """Create DecisionAgent instance."""
        from agents.decision.agent import DecisionAgent
        return DecisionAgent()
    
    @staticmethod
    def create_offer_agent():
        """Create OfferAgent instance."""
        from agents.offer.agent import OfferAgent
        return OfferAgent()
    
    @staticmethod
    def create_screening_agent():
        """Create ScreeningAgent instance."""
        from agents.screening.agent import ScreeningAgent
        return ScreeningAgent()
    
    @staticmethod
    def create_assessment_agent():
        """Create AssessmentAgent instance."""
        from agents.assessment.agent import AssessmentAgent
        return AssessmentAgent()
    
    @staticmethod
    def create_sourcing_agent():
        """Create SourcingAgent instance."""
        from agents.sourcing.agent import SourcingAgent
        return SourcingAgent()
    
    @staticmethod
    def create_interview_analysis_agent():
        """Create InterviewAnalysisAgent instance."""
        from agents.interview_analysis.agent import InterviewAnalysisAgent
        return InterviewAnalysisAgent()
    
    @staticmethod
    def create_scheduler_agent():
        """Create SchedulerAgent instance."""
        from agents.scheduler.agent import SchedulerAgent
        return SchedulerAgent()
    
    @staticmethod
    def create_engagement_agent():
        """Create EngagementAgent instance."""
        from agents.engagement.agent import EngagementAgent
        return EngagementAgent()
    
    @staticmethod
    def get_agent_by_name(agent_name: str):
        """
        Get agent instance by name.
        
        Args:
            agent_name: Name of agent
            
        Returns:
            Agent instance
            
        Raises:
            ValueError: If agent name is unknown
        """
        agent_map = {
            "ParsingAgent": AgentFactory.create_parsing_agent,
            "SpecAgent": AgentFactory.create_spec_agent,
            "MatchingAgent": AgentFactory.create_matching_agent,
            "DecisionAgent": AgentFactory.create_decision_agent,
            "OfferAgent": AgentFactory.create_offer_agent,
            "ScreeningAgent": AgentFactory.create_screening_agent,
            "AssessmentAgent": AgentFactory.create_assessment_agent,
            "SourcingAgent": AgentFactory.create_sourcing_agent,
            "InterviewAnalysisAgent": AgentFactory.create_interview_analysis_agent,
            "SchedulerAgent": AgentFactory.create_scheduler_agent,
            "EngagementAgent": AgentFactory.create_engagement_agent,
        }
        
        if agent_name not in agent_map:
            raise ValueError(f"Unknown agent: {agent_name}")
        
        return agent_map[agent_name]()












