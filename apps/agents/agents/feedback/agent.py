"""
FeedbackAgent - Monitors hiring outcomes and optimizes AI models through continuous learning.

This agent collects recruiter feedback, analyzes hiring outcomes, identifies model drift,
and provides recommendations for model retraining and prompt optimization.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from agents.base.agent import AgentConfig, BaseAgent
from agents.base.result import AgentResult


class FeedbackData(BaseModel):
    """Structured feedback data."""

    job_id: str
    candidate_id: str
    application_id: str
    recruiter_id: str
    
    # Outcome data
    hire_decision: str  # hired, rejected, withdrawn
    hire_date: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    
    # AI performance feedback
    ai_match_score: float = Field(..., ge=0.0, le=1.0)
    ai_match_accurate: bool
    ai_ranking_position: int
    actual_recruiter_rating: float = Field(..., ge=0.0, le=10.0)
    
    # Quality metrics
    time_to_hire_days: Optional[int] = None
    interview_stages_completed: int = 0
    recruiter_satisfaction: float = Field(default=5.0, ge=1.0, le=10.0)
    candidate_quality_rating: float = Field(default=5.0, ge=1.0, le=10.0)
    
    # Detailed feedback
    what_worked_well: Optional[str] = None
    areas_for_improvement: Optional[str] = None
    ai_missed_factors: Optional[List[str]] = None
    
    # Performance tracking
    source_channel: Optional[str] = None
    job_category: str
    seniority_level: str
    
    feedback_timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FeedbackAnalysis(BaseModel):
    """Analysis results from feedback data."""

    total_feedback_count: int
    time_period_days: int
    
    # Accuracy metrics
    overall_accuracy: float
    false_positive_rate: float  # AI recommended but rejected
    false_negative_rate: float  # AI rejected but would have been good
    
    # Performance trends
    average_time_to_hire: float
    recruiter_satisfaction_avg: float
    candidate_quality_avg: float
    
    # Model drift indicators
    drift_detected: bool
    drift_severity: str  # none, low, medium, high
    drift_reasons: List[str]
    
    # Recommendations
    retraining_recommended: bool
    retraining_priority: str  # low, medium, high, critical
    recommended_actions: List[str]
    
    # Bias analysis
    bias_detected: bool
    bias_categories: List[str]
    fairness_score: float = Field(ge=0.0, le=1.0)
    
    # Improvement opportunities
    prompt_optimization_suggestions: List[str]
    feature_importance_changes: Dict[str, float]
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class FeedbackAgent(BaseAgent):
    """
    Agent for collecting and analyzing hiring feedback to continuously improve AI models.
    
    This agent:
    - Analyzes recruiter feedback on AI recommendations
    - Detects model drift and performance degradation
    - Identifies bias and fairness issues
    - Recommends model retraining and prompt optimization
    - Tracks hiring outcome metrics
    """

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
    ):
        """Initialize the FeedbackAgent."""
        if config is None:
            config = AgentConfig(
                name="FeedbackAgent",
                description="Analyzes hiring feedback to optimize AI models through continuous learning",
                temperature=0.3,  # Lower temperature for analytical tasks
                max_tokens=4096,
                timeout=45,
            )
        super().__init__(config)

    async def execute(self, input_data: Dict[str, Any]) -> AgentResult:
        """
        Analyze feedback data and generate insights.
        
        Args:
            input_data: Dictionary containing:
                - feedback_records: List[FeedbackData] or single FeedbackData
                - analysis_period_days: Optional[int] = 30
                - min_samples_for_drift: Optional[int] = 20
                - drift_threshold: Optional[float] = 0.15
        
        Returns:
            AgentResult with FeedbackAnalysis
        """
        try:
            # Parse input
            if "feedback_records" in input_data:
                feedback_list = input_data["feedback_records"]
                if isinstance(feedback_list, dict):
                    feedback_list = [FeedbackData(**feedback_list)]
                elif isinstance(feedback_list, list):
                    feedback_list = [
                        FeedbackData(**f) if isinstance(f, dict) else f
                        for f in feedback_list
                    ]
            else:
                raise ValueError("Missing 'feedback_records' in input_data")

            analysis_period_days = input_data.get("analysis_period_days", 30)
            min_samples = input_data.get("min_samples_for_drift", 20)
            drift_threshold = input_data.get("drift_threshold", 0.15)

            # Filter feedback by time period
            cutoff_date = datetime.utcnow() - timedelta(days=analysis_period_days)
            recent_feedback = [
                f for f in feedback_list
                if f.feedback_timestamp >= cutoff_date
            ]

            if len(recent_feedback) < 5:
                return self._create_result(
                    output={
                        "message": "Insufficient feedback data for analysis",
                        "feedback_count": len(recent_feedback),
                    },
                    success=True,
                    confidence=0.5,
                    explanation="Need at least 5 feedback records for meaningful analysis",
                )

            # Perform analysis
            analysis = await self._analyze_feedback(
                feedback_records=recent_feedback,
                min_samples=min_samples,
                drift_threshold=drift_threshold,
            )

            # Use LLM for advanced insights
            llm_insights = await self._get_llm_insights(
                feedback_records=recent_feedback,
                analysis=analysis,
            )

            # Merge LLM insights into analysis
            final_analysis = self._merge_insights(analysis, llm_insights)

            return self._create_result(
                output=final_analysis.model_dump(),
                success=True,
                confidence=0.9 if len(recent_feedback) >= min_samples else 0.7,
                explanation=f"Analyzed {len(recent_feedback)} feedback records over {analysis_period_days} days",
                evidence=[
                    f"Overall AI accuracy: {analysis.overall_accuracy:.2%}",
                    f"Recruiter satisfaction: {analysis.recruiter_satisfaction_avg:.1f}/10",
                    f"Drift detected: {analysis.drift_detected}",
                    f"Retraining recommended: {analysis.retraining_recommended}",
                ],
            )

        except Exception as e:
            self.logger.error(f"Error in FeedbackAgent execution: {e}", exc_info=True)
            return self._create_result(
                output={},
                success=False,
                error=str(e),
                confidence=0.0,
            )

    async def _analyze_feedback(
        self,
        feedback_records: List[FeedbackData],
        min_samples: int,
        drift_threshold: float,
    ) -> FeedbackAnalysis:
        """Perform statistical analysis on feedback data."""
        total_count = len(feedback_records)

        # Calculate accuracy metrics
        accurate_predictions = sum(1 for f in feedback_records if f.ai_match_accurate)
        overall_accuracy = accurate_predictions / total_count if total_count > 0 else 0.0

        hired_candidates = [f for f in feedback_records if f.hire_decision == "hired"]
        rejected_candidates = [f for f in feedback_records if f.hire_decision == "rejected"]

        # False positives: AI scored high but rejected
        false_positives = sum(
            1 for f in rejected_candidates
            if f.ai_match_score >= 0.7
        )
        false_positive_rate = false_positives / len(rejected_candidates) if rejected_candidates else 0.0

        # False negatives: AI scored low but hired
        false_negatives = sum(
            1 for f in hired_candidates
            if f.ai_match_score < 0.5
        )
        false_negative_rate = false_negatives / len(hired_candidates) if hired_candidates else 0.0

        # Performance metrics
        avg_time_to_hire = (
            sum(f.time_to_hire_days for f in hired_candidates if f.time_to_hire_days)
            / len([f for f in hired_candidates if f.time_to_hire_days])
            if any(f.time_to_hire_days for f in hired_candidates)
            else 0.0
        )

        recruiter_satisfaction_avg = (
            sum(f.recruiter_satisfaction for f in feedback_records) / total_count
            if total_count > 0 else 5.0
        )

        candidate_quality_avg = (
            sum(f.candidate_quality_rating for f in feedback_records) / total_count
            if total_count > 0 else 5.0
        )

        # Detect drift
        drift_detected = False
        drift_severity = "none"
        drift_reasons = []

        if total_count >= min_samples:
            if overall_accuracy < 0.70:
                drift_detected = True
                drift_reasons.append(f"Accuracy dropped to {overall_accuracy:.2%}")
            
            if false_positive_rate > drift_threshold:
                drift_detected = True
                drift_reasons.append(f"High false positive rate: {false_positive_rate:.2%}")
            
            if recruiter_satisfaction_avg < 6.0:
                drift_detected = True
                drift_reasons.append(f"Low recruiter satisfaction: {recruiter_satisfaction_avg:.1f}/10")

            # Determine severity
            if len(drift_reasons) >= 3 or overall_accuracy < 0.60:
                drift_severity = "high"
            elif len(drift_reasons) == 2 or overall_accuracy < 0.70:
                drift_severity = "medium"
            elif len(drift_reasons) == 1:
                drift_severity = "low"

        # Retraining recommendations
        retraining_recommended = drift_detected and total_count >= min_samples
        retraining_priority = "low"
        
        if drift_severity == "high":
            retraining_priority = "critical"
        elif drift_severity == "medium":
            retraining_priority = "high"
        elif drift_severity == "low":
            retraining_priority = "medium"

        recommended_actions = []
        if retraining_recommended:
            recommended_actions.append("Schedule model retraining with updated feedback data")
        if false_positive_rate > 0.2:
            recommended_actions.append("Adjust ranking threshold to reduce false positives")
        if recruiter_satisfaction_avg < 7.0:
            recommended_actions.append("Review and optimize prompt templates")
        if avg_time_to_hire > 45:
            recommended_actions.append("Optimize interview scheduling workflow")

        # Bias detection (simplified - would use fairness module in production)
        bias_detected = False
        bias_categories = []
        fairness_score = 0.85  # Placeholder

        return FeedbackAnalysis(
            total_feedback_count=total_count,
            time_period_days=30,
            overall_accuracy=overall_accuracy,
            false_positive_rate=false_positive_rate,
            false_negative_rate=false_negative_rate,
            average_time_to_hire=avg_time_to_hire,
            recruiter_satisfaction_avg=recruiter_satisfaction_avg,
            candidate_quality_avg=candidate_quality_avg,
            drift_detected=drift_detected,
            drift_severity=drift_severity,
            drift_reasons=drift_reasons,
            retraining_recommended=retraining_recommended,
            retraining_priority=retraining_priority,
            recommended_actions=recommended_actions,
            bias_detected=bias_detected,
            bias_categories=bias_categories,
            fairness_score=fairness_score,
            prompt_optimization_suggestions=[],
            feature_importance_changes={},
        )

    async def _get_llm_insights(
        self,
        feedback_records: List[FeedbackData],
        analysis: FeedbackAnalysis,
    ) -> Dict[str, Any]:
        """Use LLM to generate qualitative insights from feedback."""
        # Prepare feedback summary for LLM
        feedback_summary = self._summarize_feedback(feedback_records)
        
        prompt = f"""You are an AI hiring system analyst. Analyze the following hiring feedback data and provide actionable insights.

QUANTITATIVE ANALYSIS:
- Total Feedback: {analysis.total_feedback_count} records
- Overall Accuracy: {analysis.overall_accuracy:.2%}
- False Positive Rate: {analysis.false_positive_rate:.2%}
- Recruiter Satisfaction: {analysis.recruiter_satisfaction_avg:.1f}/10
- Drift Detected: {analysis.drift_detected} ({analysis.drift_severity})

QUALITATIVE FEEDBACK THEMES:
{feedback_summary}

TASK: Provide:
1. Top 3 prompt optimization suggestions
2. Key factors the AI is missing (if any)
3. Specific improvements for the ranking algorithm
4. Any concerning patterns or biases

Format as JSON:
{{
    "prompt_optimizations": ["suggestion1", "suggestion2", "suggestion3"],
    "missed_factors": ["factor1", "factor2"],
    "algorithm_improvements": ["improvement1", "improvement2"],
    "concerning_patterns": ["pattern1", "pattern2"]
}}
"""

        try:
            response = await self.llm_client.generate(
                messages=[
                    {"role": "system", "content": self.get_system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
                max_tokens=1500,
            )
            
            # Parse JSON response
            import json
            insights = json.loads(response.content)
            return insights

        except Exception as e:
            self.logger.warning(f"LLM insights generation failed: {e}")
            return {
                "prompt_optimizations": [],
                "missed_factors": [],
                "algorithm_improvements": [],
                "concerning_patterns": [],
            }

    def _summarize_feedback(self, feedback_records: List[FeedbackData]) -> str:
        """Create a text summary of qualitative feedback."""
        positive_feedback = []
        negative_feedback = []
        
        for f in feedback_records:
            if f.what_worked_well:
                positive_feedback.append(f.what_worked_well)
            if f.areas_for_improvement:
                negative_feedback.append(f.areas_for_improvement)
        
        summary = ""
        if positive_feedback:
            summary += "WHAT WORKED WELL:\n" + "\n".join(f"- {fb}" for fb in positive_feedback[:5])
        if negative_feedback:
            summary += "\n\nAREAS FOR IMPROVEMENT:\n" + "\n".join(f"- {fb}" for fb in negative_feedback[:5])
        
        return summary or "No qualitative feedback provided."

    def _merge_insights(
        self,
        analysis: FeedbackAnalysis,
        llm_insights: Dict[str, Any],
    ) -> FeedbackAnalysis:
        """Merge LLM insights into the analysis."""
        analysis.prompt_optimization_suggestions = llm_insights.get("prompt_optimizations", [])
        
        # Add LLM insights to recommended actions
        for improvement in llm_insights.get("algorithm_improvements", []):
            if improvement not in analysis.recommended_actions:
                analysis.recommended_actions.append(improvement)
        
        # Check for concerning patterns
        concerning_patterns = llm_insights.get("concerning_patterns", [])
        if concerning_patterns:
            analysis.bias_detected = True
            analysis.bias_categories = concerning_patterns
        
        return analysis

    def get_system_prompt(self) -> str:
        """Return the system prompt for the feedback agent."""
        return """You are an expert AI system analyst specializing in hiring AI performance optimization.

Your responsibilities:
1. Analyze recruiter feedback on AI hiring recommendations
2. Identify patterns in AI successes and failures
3. Detect model drift and performance degradation
4. Provide actionable recommendations for model improvement
5. Ensure fairness and prevent bias in AI decisions

Guidelines:
- Be data-driven and objective in your analysis
- Provide specific, actionable recommendations
- Consider both quantitative metrics and qualitative feedback
- Prioritize fairness and ethical AI practices
- Focus on continuous improvement

Always provide insights in structured JSON format for easy integration."""












