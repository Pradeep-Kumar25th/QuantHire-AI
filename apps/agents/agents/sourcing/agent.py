"""Sourcing agent for candidate discovery and recruitment."""

from typing import Any, Dict, List

from pydantic import BaseModel, Field

from agents.base.agent import AgentConfig, BaseAgent
from agents.base.result import AgentResult


class CandidateSource(BaseModel):
    """Candidate source information."""
    
    source_type: str  # linkedin, github, referral, job_board, internal
    source_id: str
    source_url: str
    confidence: float = Field(ge=0.0, le=1.0)


class SourcingAgent(BaseAgent):
    """
    Agent for sourcing candidates from multiple channels.
    
    Capabilities:
    - Search internal candidate database
    - Query LinkedIn (via connector)
    - Search GitHub profiles (via connector)
    - Process employee referrals
    - Aggregate from job boards
    """
    
    def __init__(self):
        """Initialize sourcing agent."""
        config = AgentConfig(
            name="SourcingAgent",
            description="Sources candidates from multiple channels based on job requirements",
            temperature=0.4,
        )
        super().__init__(config)
    
    async def execute(self, input_data: Dict[str, Any]) -> AgentResult:
        """
        Source candidates for a job.
        
        Args:
            input_data: Dictionary with:
                - job_spec: Dict (structured job specification)
                - channels: List[str] (sourcing channels to use)
                - limit: int (max candidates to return)
                - search_external: bool (search external sources)
            
        Returns:
            AgentResult with sourced candidates
        """
        job_spec = input_data.get("job_spec", {})
        channels = input_data.get("channels", ["internal", "linkedin", "github"])
        limit = input_data.get("limit", 50)
        search_external = input_data.get("search_external", False)
        
        if not job_spec:
            return self._create_result(
                output=[],
                success=False,
                error="Job specification is required",
            )
        
        try:
            sourced_candidates = []
            
            # Extract job requirements for search
            job_title = job_spec.get("title", "")
            required_skills = [
                s.get("name", "") for s in job_spec.get("must_have_skills", [])
            ]
            location = job_spec.get("location", "")
            
            # Channel 1: Internal database
            if "internal" in channels:
                internal_candidates = await self._search_internal_database(
                    skills=required_skills,
                    location=location,
                    limit=limit // 2
                )
                sourced_candidates.extend(internal_candidates)
            
            # Channel 2: LinkedIn (if external search enabled)
            if "linkedin" in channels and search_external:
                linkedin_candidates = await self._search_linkedin(
                    skills=required_skills,
                    location=location,
                    limit=20
                )
                sourced_candidates.extend(linkedin_candidates)
            
            # Channel 3: GitHub (for technical roles)
            if "github" in channels and search_external:
                github_candidates = await self._search_github(
                    skills=required_skills,
                    limit=15
                )
                sourced_candidates.extend(github_candidates)
            
            # Deduplicate and rank
            unique_candidates = self._deduplicate_candidates(sourced_candidates)
            ranked_candidates = unique_candidates[:limit]
            
            evidence = [
                f"Searched {len(channels)} channels",
                f"Found {len(sourced_candidates)} total candidates",
                f"Returned {len(ranked_candidates)} unique candidates",
            ]
            
            return self._create_result(
                output=ranked_candidates,
                confidence=0.80,
                evidence=evidence,
                metadata={
                    "channels_searched": channels,
                    "total_found": len(sourced_candidates),
                    "unique_candidates": len(unique_candidates),
                },
            )
        
        except Exception as e:
            return self._create_result(
                output=[],
                success=False,
                error=f"Failed to source candidates: {str(e)}",
            )
    
    async def _search_internal_database(
        self,
        skills: List[str],
        location: str,
        limit: int,
    ) -> List[Dict]:
        """Search internal candidate database."""
        # TODO: Implement actual database search with vector similarity
        
        return [
            {
                "candidate_id": f"internal_{i}",
                "name": f"Internal Candidate {i}",
                "source": CandidateSource(
                    source_type="internal",
                    source_id=f"internal_{i}",
                    source_url=f"https://app.quanthire.ai/candidates/internal_{i}",
                    confidence=0.9,
                ).dict(),
                "skills": skills[:3],
                "match_score": 0.85,
            }
            for i in range(min(5, limit))
        ]
    
    async def _search_linkedin(
        self,
        skills: List[str],
        location: str,
        limit: int,
    ) -> List[Dict]:
        """Search LinkedIn via connector."""
        # TODO: Use LinkedIn connector
        from app.integrations.linkedin import LinkedInConnector
        
        connector = LinkedInConnector()
        if not connector.enabled:
            logger.info("LinkedIn connector not configured, skipping")
            return []
        
        query = " ".join(skills)
        results = await connector.search_candidates(
            keywords=skills,
            location=location,
            limit=limit,
        )
        
        return [
            {
                "candidate_id": r.get("linkedin_id"),
                "name": r.get("name"),
                "source": CandidateSource(
                    source_type="linkedin",
                    source_id=r.get("linkedin_id"),
                    source_url=r.get("profile_url"),
                    confidence=0.7,
                ).dict(),
                "skills": skills,
                "match_score": 0.75,
            }
            for r in results
        ]
    
    async def _search_github(
        self,
        skills: List[str],
        limit: int,
    ) -> List[Dict]:
        """Search GitHub via connector."""
        # TODO: Use GitHub connector
        from app.integrations.github import GitHubConnector
        
        connector = GitHubConnector()
        if not connector.enabled:
            logger.info("GitHub connector not configured, skipping")
            return []
        
        query = " ".join(skills)
        results = await connector.search_users(
            query=query,
            limit=limit,
        )
        
        return [
            {
                "candidate_id": r.get("github_id"),
                "name": r.get("name"),
                "source": CandidateSource(
                    source_type="github",
                    source_id=r.get("username"),
                    source_url=r.get("profile_url"),
                    confidence=0.65,
                ).dict(),
                "skills": skills,
                "match_score": 0.70,
            }
            for r in results
        ]
    
    def _deduplicate_candidates(self, candidates: List[Dict]) -> List[Dict]:
        """Remove duplicate candidates based on email or name."""
        seen = set()
        unique = []
        
        for candidate in candidates:
            # Create identifier
            identifier = candidate.get("name", "").lower()
            
            if identifier and identifier not in seen:
                seen.add(identifier)
                unique.append(candidate)
        
        return unique












