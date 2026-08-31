"""Job specification generation agent."""

from typing import Any, Dict, List

from pydantic import BaseModel, Field

from agents.base.agent import AgentConfig, BaseAgent
from agents.base.result import AgentResult


class JobSpec(BaseModel):
    """Structured job specification."""

    title: str
    level: str  # Junior, Mid, Senior, Staff, Principal
    department: str
    skills: List[Dict[str, Any]] = Field(default_factory=list)
    # [{name, required: bool, level: str}]
    responsibilities: List[str] = Field(default_factory=list)
    screening_criteria: List[Dict[str, Any]] = Field(default_factory=list)
    # [{criterion, weight: float}]
    kpis: List[str] = Field(default_factory=list)
    compensation_range: Dict[str, Any] = Field(default_factory=dict)
    # {min, max, currency, equity_included: bool}
    confidence: float = Field(ge=0.0, le=1.0)


class SpecAgent(BaseAgent):
    """Agent for generating structured job specifications."""

    def __init__(self):
        """Initialize spec agent."""
        config = AgentConfig(
            name="SpecAgent",
            description="Generates structured job specifications from requirements",
            temperature=0.5,
        )
        super().__init__(config)

    def _get_spec_schema(self) -> Dict[str, Any]:
        """Get JSON schema for job spec.
        
        Returns:
            JSON schema
        """
        return {
            "title": "string",
            "level": "string (Junior|Mid|Senior|Staff|Principal)",
            "department": "string",
            "skills": [
                {
                    "name": "string",
                    "required": "boolean",
                    "level": "string (Beginner|Intermediate|Advanced|Expert)",
                }
            ],
            "responsibilities": ["string"],
            "screening_criteria": [
                {"criterion": "string", "weight": "number 0-1 (sum should be ~1.0)"}
            ],
            "kpis": ["string"],
            "compensation_range": {
                "min": "number",
                "max": "number",
                "currency": "string",
                "equity_included": "boolean",
            },
            "confidence": "number 0-1",
        }

    def _get_spec_prompt(self) -> str:
        """Get spec generation prompt.
        
        Returns:
            System prompt
        """
        return """You are an expert hiring manager and talent acquisition specialist. Your task is to generate comprehensive, structured job specifications.

GUIDELINES:
1. Infer appropriate level (Junior/Mid/Senior/Staff/Principal) based on requirements
2. Extract and normalize all skills (e.g., "React.js" not "react")
3. Mark skills as required vs. nice-to-have
4. Create specific, measurable responsibilities
5. Define weighted screening criteria (sum of weights should be ~1.0)
6. Suggest relevant KPIs for measuring success
7. Infer competitive compensation range based on level, location, and market data
8. Set confidence based on clarity of input

OUTPUT:
- Respond ONLY with valid JSON matching the schema
- Be thorough but realistic
- Use industry-standard terminology"""

    async def execute(self, input_data: Dict[str, Any]) -> AgentResult:
        """Generate job specification.
        
        Args:
            input_data: Dictionary with job requirements
                - description: str (free-form job description)
                - level: str (optional, can be inferred)
                - department: str (optional)
                - location: str (optional, for compensation)
            
        Returns:
            AgentResult with structured job spec
        """
        description = input_data.get("description", "")
        level = input_data.get("level")
        department = input_data.get("department")
        location = input_data.get("location", "US")

        if not description:
            return self._create_result(
                output={},
                success=False,
                error="Job description is required",
            )

        try:
            system_prompt = self.get_system_prompt() + "\n\n" + self._get_spec_prompt()
            schema = self._get_spec_schema()

            context = []
            if level:
                context.append(f"Level: {level}")
            if department:
                context.append(f"Department: {department}")
            if location:
                context.append(f"Location: {location}")

            user_prompt = f"""Generate a structured job specification for the following role:

{' | '.join(context) if context else ''}

JOB DESCRIPTION:
{description}

Respond with ONLY valid JSON matching the schema."""

            spec_data = await self.llm_client.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema=schema,
            )

            # Validate
            job_spec = JobSpec(**spec_data)

            # Build evidence
            evidence = [
                f"Generated spec for {job_spec.title} position",
                f"Identified {len(job_spec.skills)} skills",
                f"Created {len(job_spec.responsibilities)} responsibilities",
                f"Defined {len(job_spec.screening_criteria)} screening criteria",
            ]

            return self._create_result(
                output=job_spec.model_dump(),
                confidence=job_spec.confidence,
                evidence=evidence,
                metadata={
                    "total_skills": len(job_spec.skills),
                    "required_skills": sum(
                        1 for s in job_spec.skills if s.get("required", False)
                    ),
                },
            )

        except Exception as e:
            return self._create_result(
                output={},
                success=False,
                error=f"Failed to generate job spec: {str(e)}",
            )

