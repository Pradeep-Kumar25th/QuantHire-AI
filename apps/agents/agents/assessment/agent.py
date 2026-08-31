"""Assessment agent for automated grading."""

from typing import Any, Dict, List

from pydantic import BaseModel, Field

from agents.base.agent import AgentConfig, BaseAgent
from agents.base.result import AgentResult


class AssessmentScore(BaseModel):
    """Individual assessment component score."""
    
    component: str
    max_points: float
    points_awarded: float
    percentage: float
    feedback: str


class AssessmentAgent(BaseAgent):
    """
    Agent for automated assessment grading.
    
    Capabilities:
    - Grade coding assessments
    - Evaluate written responses
    - Score case studies
    - Provide detailed feedback
    """
    
    def __init__(self):
        """Initialize assessment agent."""
        config = AgentConfig(
            name="AssessmentAgent",
            description="Automatically grades assessments and provides feedback",
            temperature=0.2,  # Lower temperature for consistent grading
        )
        super().__init__(config)
    
    async def execute(self, input_data: Dict[str, Any]) -> AgentResult:
        """
        Grade an assessment.
        
        Args:
            input_data: Dictionary with:
                - assessment_type: str (coding, written, case_study)
                - rubric: Dict (scoring criteria)
                - submission: Dict (candidate's submission)
                - test_cases: List (for coding assessments)
            
        Returns:
            AgentResult with grades and feedback
        """
        assessment_type = input_data.get("assessment_type", "")
        rubric = input_data.get("rubric", {})
        submission = input_data.get("submission", {})
        
        if not assessment_type:
            return self._create_result(
                output={},
                success=False,
                error="Assessment type is required",
            )
        
        try:
            if assessment_type == "coding":
                result = await self._grade_coding_assessment(submission, rubric, input_data.get("test_cases", []))
            elif assessment_type == "written":
                result = await self._grade_written_assessment(submission, rubric)
            elif assessment_type == "case_study":
                result = await self._grade_case_study(submission, rubric)
            else:
                return self._create_result(
                    output={},
                    success=False,
                    error=f"Unsupported assessment type: {assessment_type}",
                )
            
            return self._create_result(
                output=result,
                confidence=result.get("grading_confidence", 0.85),
                evidence=[
                    f"Assessment type: {assessment_type}",
                    f"Overall score: {result.get('overall_score', 0)}/100",
                    f"Components graded: {len(result.get('component_scores', []))}",
                ],
            )
        
        except Exception as e:
            return self._create_result(
                output={},
                success=False,
                error=f"Failed to grade assessment: {str(e)}",
            )
    
    async def _grade_coding_assessment(
        self,
        submission: Dict,
        rubric: Dict,
        test_cases: List[Dict],
    ) -> Dict:
        """Grade coding assessment with test cases."""
        code = submission.get("code", "")
        language = submission.get("language", "python")
        
        component_scores = []
        
        # 1. Test case pass rate (40%)
        if test_cases:
            passed_tests = sum(1 for tc in test_cases if tc.get("passed", False))
            test_score = (passed_tests / len(test_cases)) * 40
            
            component_scores.append(AssessmentScore(
                component="Test Cases",
                max_points=40,
                points_awarded=test_score,
                percentage=(test_score / 40) * 100,
                feedback=f"Passed {passed_tests}/{len(test_cases)} test cases",
            ))
        
        # 2. Code quality (30%) - LLM evaluation
        quality_eval = await self._evaluate_code_quality(code, language, rubric)
        component_scores.append(AssessmentScore(
            component="Code Quality",
            max_points=30,
            points_awarded=quality_eval["score"],
            percentage=(quality_eval["score"] / 30) * 100,
            feedback=quality_eval["feedback"],
        ))
        
        # 3. Problem solving approach (30%) - LLM evaluation
        approach_eval = await self._evaluate_problem_solving(code, submission.get("problem_description", ""))
        component_scores.append(AssessmentScore(
            component="Problem Solving",
            max_points=30,
            points_awarded=approach_eval["score"],
            percentage=(approach_eval["score"] / 30) * 100,
            feedback=approach_eval["feedback"],
        ))
        
        # Calculate overall
        overall_score = sum(s.points_awarded for s in component_scores)
        
        return {
            "overall_score": overall_score,
            "component_scores": [s.dict() for s in component_scores],
            "grading_confidence": 0.9,
            "feedback_summary": self._generate_feedback_summary(component_scores),
        }
    
    async def _grade_written_assessment(
        self,
        submission: Dict,
        rubric: Dict,
    ) -> Dict:
        """Grade written assessment (essays, short answers)."""
        response = submission.get("response", "")
        
        # Use LLM to evaluate against rubric
        system_prompt = f"""You are grading a written assessment.

Rubric: {rubric}

Evaluate the response on:
1. Relevance to question
2. Depth of analysis
3. Clarity and structure
4. Evidence and examples
5. Professional communication

Provide scores and feedback."""
        
        user_prompt = f"""Grade this response:

{response}

Return JSON: {{"overall_score": number, "feedback": "string", "strengths": ["string"], "improvements": ["string"]}}"""
        
        evaluation = await self.llm_client.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema={
                "overall_score": "number 0-100",
                "feedback": "string",
                "strengths": ["string"],
                "improvements": ["string"],
            },
        )
        
        return {
            "overall_score": evaluation.get("overall_score", 0),
            "feedback": evaluation.get("feedback", ""),
            "strengths": evaluation.get("strengths", []),
            "improvements": evaluation.get("improvements", []),
            "grading_confidence": 0.80,
        }
    
    async def _grade_case_study(
        self,
        submission: Dict,
        rubric: Dict,
    ) -> Dict:
        """Grade case study assessment."""
        # Similar to written assessment but with specific case study criteria
        return await self._grade_written_assessment(submission, rubric)
    
    async def _evaluate_code_quality(
        self,
        code: str,
        language: str,
        rubric: Dict,
    ) -> Dict[str, Any]:
        """Evaluate code quality with LLM."""
        system_prompt = f"""Evaluate {language} code quality.

Criteria:
- Readability and style
- Proper use of language features
- Error handling
- Documentation
- Efficiency

Score out of 30."""
        
        user_prompt = f"""Evaluate this code:

```{language}
{code}
```

Return JSON: {{"score": number, "feedback": "string"}}"""
        
        try:
            evaluation = await self.llm_client.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema={"score": "number 0-30", "feedback": "string"},
            )
            
            return {
                "score": evaluation.get("score", 15),
                "feedback": evaluation.get("feedback", ""),
            }
        except Exception as e:
            logger.error(f"Failed to evaluate code quality: {e}")
            return {"score": 15, "feedback": "Could not evaluate"}
    
    async def _evaluate_problem_solving(
        self,
        code: str,
        problem_description: str,
    ) -> Dict[str, Any]:
        """Evaluate problem-solving approach."""
        system_prompt = """Evaluate the problem-solving approach in this code.

Consider:
- Understanding of requirements
- Algorithm choice
- Edge case handling
- Scalability considerations

Score out of 30."""
        
        user_prompt = f"""Problem: {problem_description}

Solution:
```
{code}
```

Return JSON: {{"score": number, "feedback": "string"}}"""
        
        try:
            evaluation = await self.llm_client.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema={"score": "number 0-30", "feedback": "string"},
            )
            
            return {
                "score": evaluation.get("score", 15),
                "feedback": evaluation.get("feedback", ""),
            }
        except Exception as e:
            logger.error(f"Failed to evaluate problem solving: {e}")
            return {"score": 15, "feedback": "Could not evaluate"}
    
    def _generate_feedback_summary(self, scores: List[AssessmentScore]) -> str:
        """Generate overall feedback summary."""
        strengths = [s.component for s in scores if s.percentage >= 80]
        improvements = [s.component for s in scores if s.percentage < 60]
        
        summary = "Assessment completed. "
        
        if strengths:
            summary += f"Strong performance in: {', '.join(strengths)}. "
        
        if improvements:
            summary += f"Areas for improvement: {', '.join(improvements)}."
        
        return summary












