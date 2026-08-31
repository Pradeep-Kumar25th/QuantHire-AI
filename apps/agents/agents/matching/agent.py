"""Candidate matching agent using vector embeddings."""

from typing import Any, Dict, List

from pydantic import BaseModel, Field

from agents.base.agent import AgentConfig, BaseAgent
from agents.base.result import AgentResult


class CandidateMatch(BaseModel):
    """Candidate match result."""

    candidate_id: str
    score: float = Field(ge=0.0, le=100.0)
    rationale: str
    evidence: List[str]
    skill_matches: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)


class MatchingAgent(BaseAgent):
    """Agent for matching candidates to jobs using vector search and semantic analysis."""

    def __init__(self):
        """Initialize matching agent."""
        config = AgentConfig(
            name="MatchingAgent",
            description="Matches candidates to jobs using vector embeddings and skills analysis",
            temperature=0.4,
        )
        super().__init__(config)

    async def execute(self, input_data: Dict[str, Any]) -> AgentResult:
        """Match candidates to a job.
        
        Args:
            input_data: Dictionary with:
                - job_spec: Dict (structured job specification)
                - candidates: List[Dict] (candidate profiles)
                - top_k: int (optional, number of matches to return)
            
        Returns:
            AgentResult with ranked candidates
        """
        job_spec = input_data.get("job_spec", {})
        candidates = input_data.get("candidates", [])
        top_k = input_data.get("top_k", 10)

        if not job_spec:
            return self._create_result(
                output=[],
                success=False,
                error="Job specification is required",
            )

        if not candidates:
            return self._create_result(
                output=[],
                confidence=1.0,
                evidence=["No candidates available to match"],
            )

        try:
            # TODO: Implement actual vector search with embeddings
            # For now, use LLM for semantic matching

            job_title = job_spec.get("title", "")
            job_skills = job_spec.get("skills", [])
            job_level = job_spec.get("level", "")

            system_prompt = self.get_system_prompt() + f"""

You are matching candidates to this position:
Title: {job_title}
Level: {job_level}
Required Skills: {', '.join([s['name'] for s in job_skills if s.get('required', False)])}
Nice-to-have Skills: {', '.join([s['name'] for s in job_skills if not s.get('required', False)])}

For each candidate, you must:
1. Analyze skill overlap
2. Consider experience level match
3. Assess overall fit
4. Provide rationale with specific evidence
5. Assign a match score (0-100)

Be thorough and objective."""

            matches = []
            for candidate in candidates[:top_k]:  # Limit to top_k candidates
                candidate_name = candidate.get("name", "Unknown")
                candidate_skills = candidate.get("profile_json", {}).get("skills", [])
                candidate_experience = candidate.get("profile_json", {}).get("experience", [])

                user_prompt = f"""Rate this candidate's match for the position:

CANDIDATE: {candidate_name}
Skills: {', '.join([s.get('name', '') for s in candidate_skills])}
Experience: {len(candidate_experience)} positions

Provide:
1. Match score (0-100)
2. Rationale (2-3 sentences)
3. Matching skills (list)
4. Missing critical skills (list)

Format as JSON:
{{
  "score": number,
  "rationale": "string",
  "skill_matches": ["skill1", "skill2"],
  "missing_skills": ["skill1", "skill2"]
}}"""

                try:
                    match_data = await self.llm_client.generate_structured(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        schema={
                            "score": "number 0-100",
                            "rationale": "string",
                            "skill_matches": ["string"],
                            "missing_skills": ["string"],
                        },
                    )

                    matches.append({
                        "candidate_id": candidate.get("id", ""),
                        "candidate_name": candidate_name,
                        "score": match_data.get("score", 0),
                        "rationale": match_data.get("rationale", ""),
                        "evidence": [
                            f"{len(match_data.get('skill_matches', []))} matching skills",
                            f"{len(match_data.get('missing_skills', []))} missing critical skills",
                        ],
                        "skill_matches": match_data.get("skill_matches", []),
                        "missing_skills": match_data.get("missing_skills", []),
                    })

                except Exception as e:
                    # Skip candidate if matching fails
                    continue

            # Sort by score descending
            matches.sort(key=lambda x: x["score"], reverse=True)

            evidence = [
                f"Analyzed {len(candidates)} candidates",
                f"Found {len(matches)} valid matches",
                f"Top score: {matches[0]['score']:.1f}" if matches else "No matches",
            ]

            return self._create_result(
                output=matches[:top_k],
                confidence=0.85 if matches else 0.5,
                evidence=evidence,
                metadata={
                    "total_analyzed": len(candidates),
                    "total_matched": len(matches),
                    "job_title": job_title,
                },
            )

        except Exception as e:
            return self._create_result(
                output=[],
                success=False,
                error=f"Failed to match candidates: {str(e)}",
            )

