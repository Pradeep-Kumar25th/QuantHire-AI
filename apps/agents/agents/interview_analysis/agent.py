"""Interview analysis agent for transcript analysis and scoring."""

from typing import Any, Dict, List

from pydantic import BaseModel, Field

from agents.base.agent import AgentConfig, BaseAgent
from agents.base.result import AgentResult


class InterviewInsight(BaseModel):
    """Interview analysis insight."""
    
    category: str  # technical, communication, problem_solving, cultural_fit
    observation: str
    impact: str  # positive, neutral, negative
    evidence: str


class InterviewAnalysisAgent(BaseAgent):
    """
    Agent for analyzing interview transcripts and recordings.
    
    Capabilities:
    - Transcript analysis
    - Sentiment analysis
    - Red flag detection
    - Strength identification
    - Communication assessment
    - Technical depth evaluation
    """
    
    def __init__(self):
        """Initialize interview analysis agent."""
        config = AgentConfig(
            name="InterviewAnalysisAgent",
            description="Analyzes interview transcripts and provides insights",
            temperature=0.3,
        )
        super().__init__(config)
    
    async def execute(self, input_data: Dict[str, Any]) -> AgentResult:
        """
        Analyze an interview.
        
        Args:
            input_data: Dictionary with:
                - transcript: str (interview transcript)
                - interview_type: str (technical, behavioral, cultural)
                - job_spec: Dict (for context)
                - interviewer_notes: str (optional)
            
        Returns:
            AgentResult with analysis and recommendations
        """
        transcript = input_data.get("transcript", "")
        interview_type = input_data.get("interview_type", "technical")
        job_spec = input_data.get("job_spec", {})
        
        if not transcript:
            return self._create_result(
                output={},
                success=False,
                error="Interview transcript is required",
            )
        
        try:
            # Analyze transcript
            analysis = await self._analyze_transcript(
                transcript=transcript,
                interview_type=interview_type,
                job_title=job_spec.get("title", ""),
                required_skills=job_spec.get("must_have_skills", []),
            )
            
            return self._create_result(
                output=analysis,
                confidence=analysis.get("confidence", 0.85),
                evidence=[
                    f"Interview type: {interview_type}",
                    f"Transcript length: {len(transcript)} characters",
                    f"Overall score: {analysis.get('overall_score', 0)}/100",
                ],
            )
        
        except Exception as e:
            return self._create_result(
                output={},
                success=False,
                error=f"Failed to analyze interview: {str(e)}",
            )
    
    async def _analyze_transcript(
        self,
        transcript: str,
        interview_type: str,
        job_title: str,
        required_skills: List[Dict],
    ) -> Dict:
        """Analyze interview transcript with LLM."""
        skills_list = [s.get("name", "") for s in required_skills]
        
        system_prompt = self.get_system_prompt() + f"""

You are analyzing a {interview_type} interview for: {job_title}

Required Skills: {', '.join(skills_list)}

Analyze the transcript for:
1. Technical competence (depth of knowledge)
2. Problem-solving ability
3. Communication skills
4. Cultural fit indicators
5. Red flags or concerns
6. Notable strengths

Provide:
- Overall score (0-100)
- Category scores
- Key insights with evidence
- Strengths and concerns
- Hiring recommendation"""
        
        user_prompt = f"""Analyze this interview transcript:

{transcript}

Return JSON with:
{{
  "overall_score": number,
  "category_scores": {{"technical": number, "communication": number, "problem_solving": number, "cultural_fit": number}},
  "insights": [{{"category": "string", "observation": "string", "impact": "positive|neutral|negative", "evidence": "string"}}],
  "strengths": ["string"],
  "concerns": ["string"],
  "red_flags": ["string"],
  "recommendation": "strong_hire|hire|maybe|no_hire",
  "confidence": number
}}"""
        
        analysis = await self.llm_client.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema={
                "overall_score": "number 0-100",
                "category_scores": {
                    "technical": "number 0-100",
                    "communication": "number 0-100",
                    "problem_solving": "number 0-100",
                    "cultural_fit": "number 0-100",
                },
                "insights": [
                    {
                        "category": "string",
                        "observation": "string",
                        "impact": "string",
                        "evidence": "string",
                    }
                ],
                "strengths": ["string"],
                "concerns": ["string"],
                "red_flags": ["string"],
                "recommendation": "string",
                "confidence": "number 0-1",
            },
        )
        
        return analysis












