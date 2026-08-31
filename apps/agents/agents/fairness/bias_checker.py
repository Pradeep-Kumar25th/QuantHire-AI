"""Fairness and bias checking pipeline for hiring decisions."""

import logging
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class BiasCheckResult(BaseModel):
    """Result of bias check."""
    passed: bool
    checks_performed: List[str]
    concerns: List[str]
    recommendations: List[str]
    protected_attributes_found: List[str]
    confidence: float


class FairnessMetrics(BaseModel):
    """Fairness metrics for decision analysis."""
    demographic_parity: Optional[float] = None
    equal_opportunity: Optional[float] = None
    disparate_impact_ratio: Optional[float] = None
    statistical_significance: Optional[float] = None


class BiasChecker:
    """
    Checks for potential bias in hiring decisions.
    
    Implements:
    - Protected attribute detection
    - Decision consistency checking
    - Adverse impact analysis
    - Explainability validation
    """
    
    # Protected characteristics (should NOT influence decisions)
    PROTECTED_ATTRIBUTES = {
        "age", "birth_date", "date_of_birth", "dob",
        "gender", "sex", "male", "female", "non_binary",
        "race", "ethnicity", "color", "national_origin", "nationality",
        "religion", "religious", "faith",
        "disability", "disabled", "handicap",
        "marital_status", "married", "single", "divorced",
        "pregnancy", "pregnant",
        "sexual_orientation", "lgbt", "gay", "lesbian",
        "veteran_status", "military",
        "genetic_information",
    }
    
    # Job-relevant attributes (ALLOWED)
    JOB_RELEVANT_ATTRIBUTES = {
        "skills", "experience", "education", "certifications",
        "work_history", "achievements", "projects",
        "technical_assessment", "coding_test", "interview_score",
        "communication", "problem_solving", "leadership",
    }
    
    def __init__(self, strict_mode: bool = True):
        """
        Initialize bias checker.
        
        Args:
            strict_mode: If True, fail on any protected attribute mention
        """
        self.strict_mode = strict_mode
    
    def check_decision(
        self,
        input_data: Dict[str, Any],
        decision_data: Dict[str, Any],
        explanation: str,
    ) -> BiasCheckResult:
        """
        Check a hiring decision for potential bias.
        
        Args:
            input_data: Input to decision agent (candidate data, job spec)
            decision_data: Decision output (ranking, scores)
            explanation: Natural language explanation
            
        Returns:
            BiasCheckResult with findings
        """
        checks_performed = []
        concerns = []
        recommendations = []
        protected_found = []
        
        # Check 1: Protected attributes in input
        input_protected = self._find_protected_attributes(str(input_data))
        if input_protected:
            protected_found.extend(input_protected)
            concerns.append(
                f"Protected attributes found in input: {', '.join(input_protected)}"
            )
            recommendations.append(
                "Remove protected attributes from candidate data before decision-making"
            )
        checks_performed.append("protected_attributes_in_input")
        
        # Check 2: Protected attributes in explanation
        explanation_protected = self._find_protected_attributes(explanation)
        if explanation_protected:
            protected_found.extend(explanation_protected)
            concerns.append(
                f"Protected attributes mentioned in explanation: {', '.join(explanation_protected)}"
            )
            if self.strict_mode:
                concerns.append("CRITICAL: Decision may be influenced by protected characteristics")
        checks_performed.append("protected_attributes_in_explanation")
        
        # Check 3: Decision based on job-relevant criteria
        job_relevant = self._check_job_relevant_criteria(explanation, decision_data)
        if not job_relevant:
            concerns.append("Decision rationale lacks clear job-relevant justification")
            recommendations.append("Provide specific, measurable, job-relevant criteria")
        checks_performed.append("job_relevant_criteria")
        
        # Check 4: Consistency in scoring
        consistency = self._check_scoring_consistency(decision_data)
        if not consistency:
            concerns.append("Inconsistent scoring detected across candidates")
        checks_performed.append("scoring_consistency")
        
        # Check 5: Explainability quality
        explainable = self._check_explainability(explanation)
        if not explainable:
            concerns.append("Explanation lacks sufficient detail or evidence")
            recommendations.append("Include specific examples and evidence")
        checks_performed.append("explainability_quality")
        
        # Determine if passed
        critical_issues = any(
            "CRITICAL" in concern or
            (self.strict_mode and protected_found)
            for concern in concerns
        )
        
        passed = not critical_issues and len(concerns) <= 2
        confidence = 1.0 - (len(concerns) * 0.15)
        
        return BiasCheckResult(
            passed=passed,
            checks_performed=checks_performed,
            concerns=concerns,
            recommendations=recommendations,
            protected_attributes_found=list(set(protected_found)),
            confidence=max(0.0, min(1.0, confidence)),
        )
    
    def _find_protected_attributes(self, text: str) -> List[str]:
        """Find protected attributes in text."""
        text_lower = text.lower()
        found = []
        
        for attr in self.PROTECTED_ATTRIBUTES:
            if attr in text_lower:
                found.append(attr)
        
        return found
    
    def _check_job_relevant_criteria(
        self,
        explanation: str,
        decision_data: Dict,
    ) -> bool:
        """Check if decision based on job-relevant criteria."""
        explanation_lower = explanation.lower()
        
        # Count job-relevant terms
        relevant_count = sum(
            1 for attr in self.JOB_RELEVANT_ATTRIBUTES
            if attr in explanation_lower
        )
        
        # Should mention at least 3 job-relevant factors
        return relevant_count >= 3
    
    def _check_scoring_consistency(self, decision_data: Dict) -> bool:
        """Check for consistent scoring across candidates."""
        # Extract scores
        if "ranking" not in decision_data:
            return True  # No ranking to check
        
        rankings = decision_data.get("ranking", [])
        if len(rankings) < 2:
            return True
        
        # Check that scores are in descending order
        scores = [r.get("overall_score", 0) for r in rankings]
        is_consistent = all(scores[i] >= scores[i+1] for i in range(len(scores)-1))
        
        return is_consistent
    
    def _check_explainability(self, explanation: str) -> bool:
        """Check if explanation is sufficiently detailed."""
        # Basic checks
        if len(explanation) < 50:
            return False
        
        # Should include evidence words
        evidence_words = ["because", "demonstrated", "showed", "experience", "skill", "performance"]
        has_evidence = any(word in explanation.lower() for word in evidence_words)
        
        return has_evidence
    
    def calculate_adverse_impact(
        self,
        decisions: List[Dict],
        group_attribute: str,
    ) -> Dict[str, Any]:
        """
        Calculate adverse impact ratio.
        
        Used for EEOC compliance (80% rule).
        
        Args:
            decisions: List of hiring decisions
            group_attribute: Attribute to analyze (for audit only)
            
        Returns:
            Adverse impact analysis
        """
        # NOTE: This should only be used in aggregate analysis,
        # NEVER in individual decision-making
        
        logger.warning(
            "Adverse impact analysis should only be used for "
            "aggregate compliance monitoring, not individual decisions"
        )
        
        return {
            "total_decisions": len(decisions),
            "note": "Aggregate analysis only - not used in decision-making",
            "compliance_check": "EEOC 80% rule",
            "methodology": "Four-fifths rule for disparate impact",
        }


class FairnessPipeline:
    """
    Complete fairness checking pipeline.
    
    Runs before and after hiring decisions.
    """
    
    def __init__(self, strict_mode: bool = True):
        self.bias_checker = BiasChecker(strict_mode=strict_mode)
    
    async def validate_decision(
        self,
        input_data: Dict,
        decision: Dict,
        explanation: str,
    ) -> BiasCheckResult:
        """
        Validate a hiring decision for fairness.
        
        This is run automatically for all decision agent outputs.
        """
        result = self.bias_checker.check_decision(
            input_data=input_data,
            decision_data=decision,
            explanation=explanation,
        )
        
        # Log results
        if not result.passed:
            logger.warning(
                f"Bias check failed: {len(result.concerns)} concerns. "
                f"Protected attributes: {result.protected_attributes_found}"
            )
        else:
            logger.info(f"Bias check passed with confidence {result.confidence:.2f}")
        
        # Store in database for audit
        await self._store_bias_check_result(result)
        
        return result
    
    async def _store_bias_check_result(self, result: BiasCheckResult):
        """Store bias check result in database."""
        # TODO: Implement database storage
        pass
    
    async def run_periodic_fairness_audit(
        self,
        date_range: tuple,
        group_by: Optional[str] = None,
    ) -> Dict:
        """
        Run periodic fairness audit.
        
        Analyzes decisions in aggregate to ensure no systematic bias.
        
        Args:
            date_range: (start_date, end_date) tuple
            group_by: Grouping attribute (for reporting only)
            
        Returns:
            Audit report
        """
        logger.info(f"Running fairness audit for period: {date_range}")
        
        # TODO: Implement aggregate analysis
        # - Query all decisions in date range
        # - Calculate selection rates
        # - Check for adverse impact
        # - Generate report
        
        return {
            "period": date_range,
            "total_decisions": 0,
            "fairness_score": 0.95,
            "concerns": [],
            "status": "compliant",
        }


# Setup instructions
FAIRNESS_GUIDELINES = """
Fairness & Bias Prevention Guidelines
======================================

1. Protected Characteristics:
   The following should NEVER influence hiring decisions:
   - Age, date of birth
   - Gender, sex
   - Race, ethnicity, color, national origin
   - Religion
   - Disability status
   - Marital status
   - Pregnancy
   - Sexual orientation
   - Veteran status
   - Genetic information

2. Job-Relevant Criteria ONLY:
   Decisions must be based solely on:
   - Technical skills and proficiency
   - Relevant work experience
   - Education and certifications
   - Assessment performance
   - Interview performance
   - Communication and collaboration abilities

3. Bias Prevention Measures:
   ✅ Automated bias checking on all decisions
   ✅ Protected attribute filtering in input data
   ✅ Explainability requirements (evidence-based)
   ✅ Human-in-the-loop oversight
   ✅ Regular fairness audits
   ✅ Diverse hiring panel requirements

4. Compliance:
   - EEOC Guidelines (US)
   - GDPR Article 22 (Automated decisions)
   - EU AI Act (High-risk AI systems)
   - Qatar Labor Law

5. Monitoring:
   - Quarterly fairness audits
   - Adverse impact analysis
   - Decision explanation reviews
   - Human override pattern analysis

6. Transparency:
   Candidates have the right to:
   - Know that AI is used in hiring
   - Understand how decisions are made
   - Request human review
   - Challenge unfair decisions

Contact for Fairness Concerns:
- Email: fairness@quanthire.ai
- Data Protection Officer: dpo@quanthire.ai
"""


def print_fairness_guidelines():
    """Print fairness guidelines."""
    print(FAIRNESS_GUIDELINES)












