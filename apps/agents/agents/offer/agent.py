"""Offer generation and compensation recommendation agent."""

from typing import Any, Dict, Optional

from pydantic import BaseModel

from agents.base.agent import AgentConfig, BaseAgent
from agents.base.result import AgentResult


class CompensationPackage(BaseModel):
    """Compensation package model."""

    base_salary: int
    currency: str = "USD"
    bonus_percentage: Optional[float] = None
    equity_shares: Optional[int] = None
    equity_type: Optional[str] = None  # RSU, options, etc.
    benefits: list = []
    relocation_amount: Optional[int] = None
    start_date: Optional[str] = None
    rationale: str = ""


class OfferAgent(BaseAgent):
    """Agent for generating offer packages and compensation recommendations."""

    def __init__(self):
        """Initialize offer agent."""
        config = AgentConfig(
            name="OfferAgent",
            description="Generates compensation packages based on market data, candidate profile, and company bands",
            temperature=0.5,
        )
        super().__init__(config)

    def _get_market_data(self, job_level: str, location: str) -> Dict[str, Any]:
        """Get market compensation data (simulated).
        
        In production, this would query actual market data APIs.
        
        Args:
            job_level: Job level (Junior, Mid, Senior, Staff, Principal)
            location: Location
            
        Returns:
            Market data dictionary
        """
        # Simulated market data
        market_bands = {
            "Junior": {"min": 70000, "max": 90000, "median": 80000},
            "Mid": {"min": 90000, "max": 120000, "median": 105000},
            "Senior": {"min": 120000, "max": 160000, "median": 140000},
            "Staff": {"min": 160000, "max": 200000, "median": 180000},
            "Principal": {"min": 200000, "max": 250000, "median": 225000},
        }
        
        # Location multipliers (simulated)
        location_multipliers = {
            "San Francisco": 1.3,
            "New York": 1.25,
            "Seattle": 1.2,
            "Austin": 1.0,
            "Remote": 0.95,
        }
        
        base_band = market_bands.get(job_level, market_bands["Mid"])
        multiplier = location_multipliers.get(location, 1.0)
        
        return {
            "min": int(base_band["min"] * multiplier),
            "max": int(base_band["max"] * multiplier),
            "median": int(base_band["median"] * multiplier),
            "source": "simulated_market_data"
        }

    async def execute(self, input_data: Dict[str, Any]) -> AgentResult:
        """Generate offer package.
        
        Args:
            input_data: Dictionary with:
                - job_level: Job level
                - location: Job location
                - candidate_experience: Years of experience
                - candidate_current_comp: Current compensation (if known)
                - budget_max: Maximum budget
                - company_benefits: List of standard benefits
                
        Returns:
            AgentResult with compensation package
        """
        job_level = input_data.get("job_level", "Mid")
        location = input_data.get("location", "Remote")
        candidate_experience = input_data.get("candidate_experience", 3)
        candidate_current_comp = input_data.get("candidate_current_comp")
        budget_max = input_data.get("budget_max")
        company_benefits = input_data.get("company_benefits", [
            "Health Insurance",
            "401(k) Match",
            "PTO",
            "Remote Work",
        ])

        try:
            # Get market data
            market_data = self._get_market_data(job_level, location)
            
            # Calculate recommended salary
            # Start with market median
            recommended_salary = market_data["median"]
            
            # Adjust for experience (within level)
            experience_adjustment = 1.0
            if candidate_experience > 5:
                experience_adjustment = 1.1
            elif candidate_experience < 2:
                experience_adjustment = 0.9
            
            recommended_salary = int(recommended_salary * experience_adjustment)
            
            # Consider current compensation (aim for 10-20% increase)
            if candidate_current_comp:
                min_offer = int(candidate_current_comp * 1.1)
                if recommended_salary < min_offer:
                    recommended_salary = min_offer
            
            # Respect budget
            if budget_max and recommended_salary > budget_max:
                recommended_salary = budget_max
            
            # Ensure within market range
            recommended_salary = max(
                market_data["min"],
                min(market_data["max"], recommended_salary)
            )
            
            # Generate rationale using LLM
            context = f"""Generate a brief rationale for this compensation package:

Position: {job_level} level
Location: {location}
Market Range: ${market_data['min']:,} - ${market_data['max']:,}
Recommended: ${recommended_salary:,}
Candidate Experience: {candidate_experience} years
"""
            if candidate_current_comp:
                context += f"Current Compensation: ${candidate_current_comp:,}\n"
            
            llm_response = await self.llm_client.generate(
                system_prompt="You are a compensation specialist. Generate a 2-3 sentence rationale for the offer.",
                user_prompt=context
            )
            
            rationale = llm_response.content.strip()
            
            # Build package
            package = CompensationPackage(
                base_salary=recommended_salary,
                currency="USD",
                bonus_percentage=15.0 if job_level in ["Senior", "Staff", "Principal"] else 10.0,
                equity_shares=10000 if job_level in ["Staff", "Principal"] else None,
                equity_type="RSU" if job_level in ["Staff", "Principal"] else None,
                benefits=company_benefits,
                rationale=rationale,
            )
            
            return self._create_result(
                output=package.model_dump(),
                confidence=0.85,
                evidence=[
                    f"Market range: ${market_data['min']:,} - ${market_data['max']:,}",
                    f"Experience: {candidate_experience} years",
                    f"Level: {job_level}",
                    f"Location: {location}",
                ],
                metadata={
                    "market_data": market_data,
                    "adjustments": {
                        "experience": experience_adjustment,
                    }
                }
            )

        except Exception as e:
            return self._create_result(
                output={},
                success=False,
                error=f"Failed to generate offer: {str(e)}",
            )

