"""Decision agent for hiring recommendations."""

from typing import Any, Dict, List

from pydantic import BaseModel, Field

from agents.base.agent import AgentConfig, BaseAgent
from agents.base.result import AgentResult


class HiringDecision(BaseModel):
    """Hiring decision recommendation."""

    recommendation: str  # "hire", "reject", "review"
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    strengths: List[str] = Field(default_factory=list)
    concerns: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    suggested_next_steps: List[str] = Field(default_factory=list)


class DecisionAgent(BaseAgent):
    """Agent for making hiring recommendations based on multiple signals."""

    def __init__(self):
        """Initialize decision agent."""
        config = AgentConfig(
            name="DecisionAgent",
            description="Makes data-driven hiring recommendations with explainability",
            temperature=0.3,  # Lower temperature for consistent decisions
        )
        super().__init__(config)

    def _get_decision_schema(self) -> Dict[str, Any]:
        """Get decision schema.
        
        Returns:
            JSON schema for decision
        """
        return {
            "recommendation": "string (hire|reject|review)",
            "confidence": "number 0-1",
            "rationale": "string (2-3 sentences explaining decision)",
            "strengths": ["string (candidate's strengths)"],
            "concerns": ["string (areas of concern)"],
            "evidence": ["string (specific data points supporting decision)"],
            "suggested_next_steps": ["string (recommended actions)"],
        }

    async def execute(self, input_data: Dict[str, Any]) -> AgentResult:
        """Make hiring decision.
        
        Args:
            input_data: Dictionary with:
                - candidate: Dict (candidate profile)
                - job: Dict (job specification)
                - match_score: float (from MatchingAgent)
                - assessment_score: float (optional)
                - interview_scores: List[Dict] (optional)
                - screening_notes: str (optional)
            
        Returns:
            AgentResult with decision recommendation
        """
        candidate = input_data.get("candidate", {})
        job = input_data.get("job", {})
        match_score = input_data.get("match_score")
        assessment_score = input_data.get("assessment_score")
        interview_scores = input_data.get("interview_scores", [])
        screening_notes = input_data.get("screening_notes", "")

        if not candidate or not job:
            return self._create_result(
                output={},
                success=False,
                error="Candidate and job information required",
            )

        try:
            # Compile signals
            signals = []
            if match_score is not None:
                signals.append(f"Match Score: {match_score:.1f}/100")
            if assessment_score is not None:
                signals.append(f"Assessment Score: {assessment_score:.1f}/100")
            if interview_scores:
                avg_interview = sum(s.get("score", 0) for s in interview_scores) / len(
                    interview_scores
                )
                signals.append(f"Average Interview Score: {avg_interview:.1f}/100")

            system_prompt = self.get_system_prompt() + """

You are making a hiring decision. Your recommendation must be:
- DATA-DRIVEN: Based on objective signals and evidence
- EXPLAINABLE: Clear rationale with specific examples
- FAIR: Avoiding bias and focusing on qualifications
- ACTIONABLE: Include next steps regardless of recommendation

DECISION GUIDELINES:
- "hire": Strong fit across multiple signals (typically 75+ overall)
- "reject": Clear gaps or concerns (typically <60 overall)
- "review": Mixed signals, needs human judgment (60-75 range)

Always include confidence score and be transparent about limitations."""

            candidate_name = candidate.get("name", "Unknown")
            job_title = job.get("title", "Unknown Position")

            user_prompt = f"""Make a hiring decision for this application:

CANDIDATE: {candidate_name}
POSITION: {job_title}

SIGNALS:
{chr(10).join('- ' + s for s in signals)}

SCREENING NOTES:
{screening_notes if screening_notes else 'None provided'}

CANDIDATE BACKGROUND:
- Experience: {len(candidate.get('profile_json', {}).get('experience', []))} positions
- Skills: {len(candidate.get('profile_json', {}).get('skills', []))} listed
- Education: {len(candidate.get('profile_json', {}).get('education', []))} degrees

Provide your decision as JSON matching the schema."""

            decision_data = await self.llm_client.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema=self._get_decision_schema(),
            )

            # Validate
            decision = HiringDecision(**decision_data)

            # Compile evidence
            all_evidence = signals + decision.evidence

            return self._create_result(
                output=decision.model_dump(),
                confidence=decision.confidence,
                evidence=all_evidence,
                metadata={
                    "candidate_id": candidate.get("id"),
                    "job_id": job.get("id"),
                    "match_score": match_score,
                    "assessment_score": assessment_score,
                    "interview_count": len(interview_scores),
                },
            )

        except Exception as e:
            return self._create_result(
                output={},
                success=False,
                error=f"Failed to make decision: {str(e)}",
            )

