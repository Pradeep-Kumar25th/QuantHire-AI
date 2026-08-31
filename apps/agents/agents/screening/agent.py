"""Screening agent for automated pre-screening."""

from typing import Any, Dict, List

from pydantic import BaseModel, Field

from agents.base.agent import AgentConfig, BaseAgent
from agents.base.result import AgentResult


class ScreeningResult(BaseModel):
    """Individual screening result."""
    
    question_id: str
    question: str
    answer: str
    score: float = Field(ge=0.0, le=100.0)
    rationale: str
    meets_requirement: bool


class ScreeningAgent(BaseAgent):
    """
    Agent for automated candidate pre-screening.
    
    Evaluates candidate responses to screening questions and
    determines if they meet minimum requirements.
    """
    
    def __init__(self):
        """Initialize screening agent."""
        config = AgentConfig(
            name="ScreeningAgent",
            description="Evaluates screening question responses and determines candidate fit",
            temperature=0.3,
        )
        super().__init__(config)
    
    async def execute(self, input_data: Dict[str, Any]) -> AgentResult:
        """
        Screen a candidate based on their responses.
        
        Args:
            input_data: Dictionary with:
                - screening_questions: List[Dict] (questions with ideal answers)
                - candidate_responses: Dict (question_id -> response)
                - job_spec: Dict (for context)
                - passing_threshold: float (default 70.0)
            
        Returns:
            AgentResult with screening evaluation
        """
        screening_questions = input_data.get("screening_questions", [])
        candidate_responses = input_data.get("candidate_responses", {})
        job_spec = input_data.get("job_spec", {})
        passing_threshold = input_data.get("passing_threshold", 70.0)
        
        if not screening_questions:
            return self._create_result(
                output=[],
                success=False,
                error="Screening questions are required",
            )
        
        if not candidate_responses:
            return self._create_result(
                output=[],
                success=False,
                error="Candidate responses are required",
            )
        
        try:
            results = []
            total_score = 0.0
            
            for question in screening_questions:
                question_id = question.get("id", "")
                question_text = question.get("question", "")
                question_type = question.get("type", "short_text")
                ideal_answer = question.get("ideal_answer", "")
                required = question.get("required", False)
                
                candidate_answer = candidate_responses.get(question_id, "")
                
                # Skip if not answered and not required
                if not candidate_answer and not required:
                    continue
                
                # Evaluate answer
                evaluation = await self._evaluate_answer(
                    question=question_text,
                    candidate_answer=candidate_answer,
                    ideal_answer=ideal_answer,
                    question_type=question_type,
                    job_context=job_spec.get("title", ""),
                )
                
                results.append(ScreeningResult(
                    question_id=question_id,
                    question=question_text,
                    answer=candidate_answer,
                    score=evaluation["score"],
                    rationale=evaluation["rationale"],
                    meets_requirement=evaluation["score"] >= 60.0,
                ))
                
                total_score += evaluation["score"]
            
            # Calculate overall score
            overall_score = total_score / len(results) if results else 0.0
            passed = overall_score >= passing_threshold
            
            # Check if all required questions met
            all_required_met = all(
                r.meets_requirement for r in results
                if any(q.get("id") == r.question_id and q.get("required")
                       for q in screening_questions)
            )
            
            recommendation = "proceed" if (passed and all_required_met) else "reject"
            
            evidence = [
                f"Answered {len(results)} screening questions",
                f"Overall score: {overall_score:.1f}/100",
                f"Passing threshold: {passing_threshold}",
                f"Recommendation: {recommendation}",
            ]
            
            return self._create_result(
                output={
                    "screening_results": [r.dict() for r in results],
                    "overall_score": overall_score,
                    "passed": passed,
                    "recommendation": recommendation,
                    "all_required_met": all_required_met,
                },
                confidence=0.85,
                evidence=evidence,
                metadata={
                    "total_questions": len(screening_questions),
                    "answered_questions": len(results),
                    "passing_threshold": passing_threshold,
                },
            )
        
        except Exception as e:
            return self._create_result(
                output=[],
                success=False,
                error=f"Failed to screen candidate: {str(e)}",
            )
    
    async def _evaluate_answer(
        self,
        question: str,
        candidate_answer: str,
        ideal_answer: str,
        question_type: str,
        job_context: str,
    ) -> Dict[str, Any]:
        """
        Evaluate a single screening answer.
        
        Returns score (0-100) and rationale.
        """
        # Handle different question types
        if question_type == "yes_no":
            # Simple yes/no comparison
            score = 100.0 if candidate_answer.lower() == ideal_answer.lower() else 0.0
            rationale = f"Answer matches requirement: {candidate_answer == ideal_answer}"
        
        elif question_type == "numeric":
            # Numeric comparison
            try:
                candidate_val = float(candidate_answer)
                ideal_val = float(ideal_answer)
                
                if candidate_val >= ideal_val:
                    score = 100.0
                    rationale = f"Exceeds requirement ({candidate_val} >= {ideal_val})"
                else:
                    score = (candidate_val / ideal_val) * 100
                    rationale = f"Below requirement ({candidate_val} < {ideal_val})"
            except ValueError:
                score = 0.0
                rationale = "Invalid numeric answer"
        
        else:
            # Use LLM for text evaluation
            system_prompt = self.get_system_prompt() + f"""

You are evaluating a screening question response for: {job_context}

Question: {question}
Ideal Answer Guideline: {ideal_answer}
Candidate Answer: {candidate_answer}

Evaluate the answer on:
1. Completeness
2. Relevance to question
3. Alignment with ideal answer
4. Clarity

Provide a score (0-100) and brief rationale."""
            
            user_prompt = f"""Evaluate this response:

Question: {question}
Candidate Answer: {candidate_answer}

Return JSON: {{"score": number, "rationale": "string"}}"""
            
            try:
                evaluation = await self.llm_client.generate_structured(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    schema={"score": "number 0-100", "rationale": "string"},
                )
                
                score = evaluation.get("score", 50.0)
                rationale = evaluation.get("rationale", "Evaluated by AI")
            
            except Exception as e:
                logger.error(f"Failed to evaluate answer: {e}")
                score = 50.0
                rationale = "Could not evaluate"
        
        return {
            "score": score,
            "rationale": rationale,
        }








