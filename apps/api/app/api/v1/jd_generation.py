"""
JD Generation API Endpoints
============================
API endpoints for AI-powered Job Description generation.
"""

import asyncio
import logging
import re
import threading
import uuid
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.auth_policy import require_user_when_basic_auth
from app.database import async_session_maker, get_session
from app.services import jd_generation_tasks

# Azure Non-Prod: JD generate auto-saves to Postgres + pgvector.
# Legacy local dev: optional Milvus save via /save endpoint.

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jd-generation", tags=["JD Generation"])

_jd_orchestrator: Any = None
_jd_orchestrator_lock = threading.Lock()


class JDGenerationRequest(BaseModel):
    """Request model for JD generation - Enterprise 15-section format."""
    
    job_title: str = Field(..., description="Job title")
    job_level: str = Field(..., description="Job level (e.g., Senior, Mid-level)")
    department: str = Field(..., description="Department name")
    years_of_experience: Optional[str] = Field(None, description="Years of experience from HR matrix")
    internal_title: Optional[str] = Field(None, description="Internal title from HR matrix")
    business_unit: Optional[str] = Field(None, description="Business unit (BU) from HR matrix")
    qualification: Optional[str] = Field(None, description="Qualification from HR matrix")
    skills: Optional[str] = Field(None, description="Skills from HR matrix")
    location: Optional[str] = Field(None, description="Job location (city)")
    remote_allowed: bool = Field(False, description="Whether remote work is allowed")
    user_requirements: Optional[str] = Field(None, description="Additional user requirements")
    user_edits: Optional[dict] = Field(None, description="User customizations to apply")
    job_id: Optional[str] = Field(
        None,
        description="Existing job ID — when set, auto-save updates that job instead of creating a duplicate",
    )
    # New fields for enterprise format
    company_name: Optional[str] = Field(None, description="Company name for About Company section")
    company_description: Optional[str] = Field(None, description="Optional company context/description")


class JDGenerationResponse(BaseModel):
    """Response model for JD generation - Enterprise 15-section format."""
    
    success: bool
    job_id: Optional[str] = None
    postgres_job_id: Optional[str] = None
    milvus_id: Optional[str] = None
    storage_backend: Optional[str] = None
    # Enterprise JD with all 15 sections
    job_description: Optional[dict] = Field(None, alias="jd", description="Generated enterprise job description with 15 sections")
    jd: Optional[dict] = Field(None, description="Generated enterprise job description (alias)")
    agent_thoughts: list[dict] = Field(default_factory=list, description="Agent thinking process")
    workflow_states: list[str] = Field(default_factory=list, description="Workflow states visited")
    errors: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    # Enterprise format indicator
    format_version: str = Field(default="enterprise-v1", description="JD format version")
    
    class Config:
        populate_by_name = True  # Allow both 'jd' and 'job_description'


class JDGenerationAsyncResponse(BaseModel):
    """Immediate response when starting async JD generation."""

    task_id: str
    status: str = "pending"
    message: str = (
        "JD generation started. Poll /jd-generation/generate-status/{task_id} "
        "until status is completed."
    )


class JDGenerationStatusResponse(BaseModel):
    """Poll response for async JD generation."""

    task_id: str
    status: str
    job_title: Optional[str] = None
    department: Optional[str] = None
    result: Optional[JDGenerationResponse] = None
    error: Optional[str] = None


def _clean_optional(value: Optional[str]) -> Optional[str]:
    """Return a stripped optional string."""
    if value is None:
        return None
    value = value.strip()
    return value or None


def _split_skills(value: Optional[str]) -> list[str]:
    """Split HR matrix skills entered as comma or newline separated text."""
    if not value:
        return []
    import re

    return [part.strip() for part in re.split(r"[\n,]+", value) if part.strip()]


def _is_grade_code(value: Optional[str]) -> bool:
    """Return True for HR grade/band codes such as A2, B3, or C1."""
    cleaned = _clean_optional(value)
    return bool(cleaned and re.fullmatch(r"[A-Z]{1,3}\d{1,3}", cleaned))


def _article_for(value: str) -> str:
    """Return a/an for short generated phrases."""
    cleaned = (value or "").strip().lower()
    return "an" if cleaned[:1] in {"a", "e", "i", "o", "u"} else "a"


def _unit_context(request: JDGenerationRequest) -> str:
    """Build natural placement text from Department/grade and BU inputs."""
    department = _clean_optional(request.department)
    business_unit = _clean_optional(request.business_unit)

    if _is_grade_code(department):
        if business_unit:
            return f"at grade/band {department} within {business_unit}"
        return f"at grade/band {department}"
    if department and business_unit:
        return f"in {department} within {business_unit}"
    if business_unit:
        return f"within {business_unit}"
    if department:
        return f"in {department}"
    return "within the assigned function"


def _work_area_label(request: JDGenerationRequest, fallback: str = "assigned work") -> str:
    """Return a business/work area without using grade codes as department names."""
    business_unit = _clean_optional(request.business_unit)
    department = _clean_optional(request.department)
    if business_unit:
        return business_unit
    if department and not _is_grade_code(department):
        return department
    return fallback


def _format_experience(value: str) -> str:
    """Keep HR-entered years exact while making the JD field readable."""
    if not value:
        return value

    if re.search(r"\b(year|years|yr|yrs)\b", value, flags=re.IGNORECASE):
        return value
    return f"{value} years of relevant experience"


def _normalized_years(value: Optional[str]) -> str:
    """Normalize a years range for reliable band checks."""
    cleaned = _clean_optional(value) or ""
    return re.sub(r"\s+", "", cleaned.lower())


def _years_bounds(value: Optional[str]) -> tuple[Optional[float], Optional[float]]:
    """Extract min/max years from strings like 1-3, 3+, or 12 - 15."""
    cleaned = _clean_optional(value)
    if not cleaned:
        return (None, None)

    numbers = [float(num) for num in re.findall(r"\d+(?:\.\d+)?", cleaned)]
    if not numbers:
        return (None, None)
    if len(numbers) == 1:
        return (numbers[0], numbers[0])
    return (numbers[0], numbers[1])


def _infer_job_level(request: JDGenerationRequest) -> str:
    """Infer a sensible level when the dialog level is blank/default-like."""
    title = " ".join(
        part for part in [request.job_title, request.internal_title] if part
    ).lower()
    years = _clean_optional(request.years_of_experience) or ""
    explicit = _clean_optional(request.job_level)
    explicit_lower = explicit.lower() if explicit else ""
    default_like_mid = explicit_lower in {"mid", "mid-level", "mid level", "midlevel", "middle"}

    if explicit and not default_like_mid:
        return explicit

    normalized_years = _normalized_years(years)
    min_years, max_years = _years_bounds(years)

    if "trainee" in title or "intern" in title or normalized_years.startswith("0-1"):
        return "Entry-level"
    if "principal" in title:
        return "Principal"
    if "architect" in title and "lead" in title:
        return "Architect / Delivery Lead"
    if "architect" in title:
        return "Architect"
    if "lead" in title:
        return "Lead"
    if "senior" in title:
        return "Senior"
    if "consultant" in title:
        return "Consultant"
    if "associate" in title or normalized_years.startswith("1-3"):
        return "Associate"
    if "junior" in title or normalized_years.startswith("2-4"):
        return "Junior"

    if min_years is not None and max_years is not None:
        if max_years <= 1:
            return "Entry-level"
        if min_years <= 1 and max_years <= 3:
            return "Associate"
        if min_years >= 12:
            return "Principal"
        if min_years >= 9:
            return "Senior"

    if explicit:
        return explicit
    return "Mid-level"


def _level_family(job_level: str, years: Optional[str] = None) -> str:
    """Convert varied HR titles/levels into a section-writing policy family."""
    level = (job_level or "").lower()
    normalized_years = _normalized_years(years)

    if any(token in level for token in ["trainee", "intern", "entry"]):
        return "early"
    if any(token in level for token in ["associate", "junior"]):
        return "early"
    if normalized_years.startswith(("0-1", "1-3", "2-4")):
        return "early"
    if any(token in level for token in ["principal", "architect", "lead"]):
        return "leadership"
    if "senior" in level:
        return "senior"
    if "consultant" in level:
        return "mid"
    return "mid"


def _level_forbidden_terms(job_level: str, years: Optional[str] = None) -> list[str]:
    """Terms that usually make a section too senior for the selected level."""
    family = _level_family(job_level, years)
    if family == "early":
        return [
            "architect",
            "architecture owner",
            "own the architecture",
            "lead a team",
            "lead teams",
            "manage a team",
            "manage teams",
            "mentor engineers",
            "strategic roadmap",
            "drive strategy",
            "governance",
            "principal",
            "director",
        ]
    if family == "mid":
        return [
            "director",
            "executive",
            "enterprise strategy",
            "own the architecture",
            "principal",
        ]
    return []


def _parse_location_input(value: Optional[str]) -> dict[str, str]:
    """Parse the dialog location without inventing unrelated values."""
    cleaned = _clean_optional(value)
    if not cleaned:
        return {}

    parts = [part.strip() for part in cleaned.split(",") if part.strip()]
    if len(parts) >= 2:
        return {"city": parts[0], "country": ", ".join(parts[1:])}
    return {"city": cleaned}


def _build_hr_context(request: JDGenerationRequest) -> Optional[str]:
    """Build prompt context from spreadsheet-style HR inputs."""
    rows = []
    fields = [
        ("JD Title", request.job_title),
        ("Seniority Level", _infer_job_level(request)),
        ("Department", request.department),
        ("Years of Exp", request.years_of_experience),
        ("Internal Title", request.internal_title),
        ("BU", request.business_unit),
        ("Qualification", request.qualification),
        ("Skills", request.skills),
        ("Location", request.location),
        ("Remote Work Allowed", str(request.remote_allowed)),
    ]
    for label, value in fields:
        cleaned = _clean_optional(value)
        if cleaned:
            rows.append(f"- {label}: {cleaned}")
    if not rows:
        return None
    guidance = [
        "HR matrix inputs to preserve in the generated JD:",
        *rows,
        "",
        "Use these values exactly as provided:",
        "- JD Title must remain the returned job_title unless blank, then use Internal Title.",
        "- Seniority Level must remain metadata.job_level.",
        "- Department must remain the JD department.",
        "- Years of Exp must drive required_qualifications.experience.",
        "- Internal Title must be preserved as internal_title and metadata.internal_title.",
        "- BU must be preserved as business_unit/division.",
        "- Qualification must drive required_qualifications.education.",
        "- Skills must be the source of truth for technical_skills and tools_technologies.",
        "- Location and Remote Work Allowed must drive location.city/country and location.work_model.",
        "",
        "Business-readiness rules:",
        "- Every narrative section must align with the exact Years of Exp and Seniority Level.",
        "- Do not add senior, lead, architecture, mentoring, management, or ownership language unless it matches the level and years.",
        "- Do not invent technologies, certifications, cloud platforms, or preferred qualifications outside the provided Skills, Qualification, BU, or Additional Requirements.",
        "- For early/associate roles, emphasize guided delivery, implementation, testing, documentation, learning, collaboration, and quality.",
        "- For senior/lead/principal roles, include leadership and architecture only when the provided level/title/years justify it.",
    ]
    return "\n".join(guidance)


def _missing_business_ready_inputs(request: JDGenerationRequest) -> list[str]:
    """Required HR inputs for a business-ready, non-invented JD."""
    missing: list[str] = []
    if not (_clean_optional(request.job_title) or _clean_optional(request.internal_title)):
        missing.append("JD Title or Internal Title")
    if not _clean_optional(request.department):
        missing.append("Department")
    if not _clean_optional(request.years_of_experience):
        missing.append("Years of Exp")
    if not _clean_optional(request.internal_title):
        missing.append("Internal Title")
    if not _clean_optional(request.qualification):
        missing.append("Qualification")
    if not _split_skills(request.skills):
        missing.append("Skills")
    return missing


def _merge_unique(primary: list[str], secondary: list[str]) -> list[str]:
    """Merge strings while preserving order."""
    seen: set[str] = set()
    output: list[str] = []
    for item in [*primary, *secondary]:
        cleaned = item.strip() if isinstance(item, str) else ""
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            output.append(cleaned)
    return output


def _success_metrics_need_enrichment(metrics: object, request: JDGenerationRequest) -> bool:
    """Return True when metrics are too generic for HR-ready use."""
    if not isinstance(metrics, list) or len(metrics) < 4:
        return True

    anchors = [
        request.job_title,
        request.department,
        request.internal_title,
        request.business_unit,
        request.skills,
    ]
    anchor_terms: set[str] = set()
    stop_words = {
        "and",
        "the",
        "for",
        "with",
        "from",
        "into",
        "ltd",
        "level",
        "senior",
        "consultant",
    }
    for anchor in anchors:
        for term in re.findall(r"[A-Za-z0-9+#.]+", anchor or ""):
            cleaned = term.lower().strip(".")
            if len(cleaned) > 2 and cleaned not in stop_words:
                anchor_terms.add(cleaned)

    generic_phrases = [
        "code quality and maintainability",
        "timely delivery",
        "stakeholder satisfaction",
        "innovation in",
        "project milestones",
    ]
    generic_count = 0
    anchored_count = 0
    level = _infer_job_level(request)
    forbidden_terms = _level_forbidden_terms(level, request.years_of_experience)
    for metric in metrics:
        text = str(metric).lower()
        if any(term in text for term in forbidden_terms):
            return True
        if any(phrase in text for phrase in generic_phrases):
            generic_count += 1
        if any(term in text for term in anchor_terms):
            anchored_count += 1

    return generic_count >= 2 or anchored_count < 2


def _build_role_specific_success_metrics(request: JDGenerationRequest) -> list[str]:
    """Create measurable, HR-ready metrics from exact HR matrix inputs."""
    work_area = _work_area_label(request, "assigned applications or services")
    priority_context = _priority_context(request)
    title = _clean_optional(request.internal_title) or _clean_optional(request.job_title) or "the role"
    level = _infer_job_level(request)
    family = _level_family(level, request.years_of_experience)
    years = _format_experience(_clean_optional(request.years_of_experience) or "") or "the required experience level"
    skills = _split_skills(request.skills)
    skill_text = ", ".join(skills[:4]) if skills else "the provided HR skills"
    service_management_role = _is_service_management_role(request)

    if family == "early":
        metrics = [
            f"Completion of assigned {work_area} tasks within agreed sprint, support, or project timelines aligned to {priority_context}.",
            f"Quality of deliverables built with {skill_text}, measured through review feedback, defect trends, and adherence to team standards.",
            f"Effective application of {years} through reliable implementation, testing, documentation, and timely issue resolution.",
            f"Accuracy of changes across assigned features, APIs, data updates, or support items, measured through rework levels and production readiness.",
            f"Growth in the required skill set for the {title} role, demonstrated through consistent use of {skill_text} and constructive response to review feedback.",
        ]
    elif family == "senior":
        if service_management_role:
            metrics = [
                f"SLA achievement and service stability for assigned applications or services aligned to {priority_context}.",
                f"Reduction in repeat incidents and production issues through effective use of {skill_text}, root cause analysis, and corrective action tracking.",
                f"Quality and timeliness of incident, problem, and change management execution, measured through backlog health, aging, and escalation trends.",
                f"Effectiveness of stakeholder communication and support handoffs for the {title} role, measured through service reviews and delivery feedback.",
                f"Improvement in runbooks, knowledge articles, release coordination, and operational readiness across supported services.",
            ]
            return metrics[:5]
        metrics = [
            f"Successful delivery of complex {work_area} work aligned to {priority_context}, with predictable timelines and low rework.",
            f"Technical quality of solutions using {skill_text}, measured through design review outcomes, defect reduction, and maintainability.",
            f"Effectiveness of technical guidance for the {title} role, measured through review quality, team enablement, and delivery consistency.",
            f"Reliability of services, integrations, and releases, measured through stable deployments, reduced incidents, and stronger support handoffs.",
            f"Practical adoption of {skill_text} in scalable implementation decisions, reusable patterns, and knowledge sharing.",
        ]
    elif family == "leadership":
        metrics = [
            f"Delivery leadership for assigned initiatives aligned to {priority_context}, measured through roadmap progress and stakeholder outcomes.",
            f"Architecture and solution quality using {skill_text}, measured through design governance, scalability, reliability, and delivery readiness.",
            f"Effectiveness of cross-functional direction for the {title} role, measured through decision quality, risk reduction, and team alignment.",
            f"Operational stability of platforms, services, or integrations, measured through release success, incident trends, and continuous improvement.",
            f"Capability building across {skill_text}, demonstrated through reusable practices, mentoring, and measurable delivery improvements.",
        ]
    else:
        metrics = [
            f"On-time delivery of {work_area} features, enhancements, and operational milestones aligned to {priority_context}.",
            f"Quality and maintainability of solutions built with {skill_text}, measured through review outcomes, defect trends, and release readiness.",
            f"Effective application of {years} through dependable analysis, implementation, troubleshooting, and stakeholder follow-through.",
            f"Reliability of application services and integrations, measured through reduced production issues, stable APIs, and clean support handoffs.",
            f"Practical adoption of required skills such as {skill_text} in delivered work, implementation decisions, and team collaboration.",
        ]

    return metrics[:5]


def _build_input_based_preferred_qualifications(request: JDGenerationRequest) -> list[str]:
    """Build preferred qualifications only from user-provided inputs."""
    skills = _split_skills(request.skills)
    qualification = _clean_optional(request.qualification)
    internal_title = _clean_optional(request.internal_title) or _clean_optional(request.job_title)
    business_unit = _clean_optional(request.business_unit)
    level = _infer_job_level(request)
    family = _level_family(level, request.years_of_experience)

    preferred: list[str] = []
    if skills:
        if family == "early":
            preferred.append(f"Hands-on exposure to {', '.join(skills[:4])}.")
        elif family == "leadership":
            preferred.append(f"Advanced experience applying {', '.join(skills[:4])} in architecture, delivery, or governance contexts.")
        else:
            preferred.append(f"Practical experience applying {', '.join(skills[:4])} in delivery or operational contexts.")
    if len(skills) > 4:
        preferred.append(f"Working familiarity with {', '.join(skills[4:])}.")
    if qualification:
        preferred.append(f"Qualification aligned with {qualification}.")
    if business_unit:
        preferred.append(f"Interest in contributing to {business_unit} initiatives.")
    if internal_title:
        if family == "early":
            preferred.append(f"Ability to grow in the {internal_title} role through structured delivery and continuous learning.")
        elif family == "leadership":
            preferred.append(f"Proven capability in {internal_title} responsibilities across solution direction, delivery governance, and stakeholder alignment.")
        else:
            preferred.append(f"Demonstrated experience in {internal_title} responsibilities with dependable delivery and stakeholder follow-through.")

    return preferred[:5]


def _skill_text(skills: list[str], max_items: int = 5) -> str:
    """Return a readable skill phrase without adding unprovided tools."""
    if not skills:
        return "the provided HR skills"
    return ", ".join(skills[:max_items])


def _is_service_management_role(request: JDGenerationRequest) -> bool:
    """Detect ITIL/application-support roles that need service-management wording."""
    text = " ".join(
        str(part or "")
        for part in [
            request.job_title,
            request.internal_title,
            request.department,
            request.business_unit,
            request.qualification,
            request.skills,
        ]
    ).lower()
    service_terms = [
        "itil",
        "incident management",
        "problem management",
        "change management",
        "application support",
        "service now",
        "servicenow",
        "sla management",
        "root cause analysis",
        "production support",
        "release coordination",
    ]
    return any(term in text for term in service_terms)


def _priority_context(request: JDGenerationRequest) -> str:
    """Return a business context without treating grade codes as business units."""
    business_unit = _clean_optional(request.business_unit)
    department = _clean_optional(request.department)
    if business_unit and department and not _is_grade_code(department):
        return f"{department} priorities within {business_unit}"
    if business_unit:
        return f"{business_unit} priorities"
    if department and _is_grade_code(department):
        return "business and delivery priorities"
    if department:
        return f"{department} priorities"
    return "business priorities"


def _initiative_context(request: JDGenerationRequest) -> str:
    """Return an initiative phrase that avoids awkward grade-code repetition."""
    business_unit = _clean_optional(request.business_unit)
    department = _clean_optional(request.department)
    if business_unit and department and not _is_grade_code(department):
        return f"{department} initiatives within {business_unit}"
    if business_unit:
        return f"{business_unit} initiatives"
    if department and _is_grade_code(department):
        return "assigned business and delivery initiatives"
    if department:
        return f"{department} initiatives"
    return "assigned business initiatives"


def _contains_forbidden_level_language(value: object, request: JDGenerationRequest) -> bool:
    """Detect seniority drift inside generated narrative sections."""
    level = _infer_job_level(request)
    terms = _level_forbidden_terms(level, request.years_of_experience)
    if not terms:
        return False

    if isinstance(value, list):
        text = " ".join(str(item) for item in value)
    else:
        text = str(value or "")
    lowered = text.lower()
    return any(term in lowered for term in terms)


def _build_level_appropriate_position_summary(request: JDGenerationRequest) -> str:
    """Build a concise, HR-ready summary that explicitly reflects inputs."""
    title = _clean_optional(request.internal_title) or _clean_optional(request.job_title) or "the role"
    qualification = _clean_optional(request.qualification)
    years = _format_experience(_clean_optional(request.years_of_experience) or "") or "the required experience level"
    level = _infer_job_level(request)
    family = _level_family(level, request.years_of_experience)
    skills = _split_skills(request.skills)
    skill_phrase = _skill_text(skills)
    service_management_role = _is_service_management_role(request)
    unit_context = _unit_context(request)
    article = _article_for(level)

    qualification_clause = f" and qualifications including {qualification}" if qualification else ""

    if family == "early":
        return (
            f"The {title} is {article} {level} role {unit_context} for candidates with "
            f"{years}{qualification_clause}. The role focuses on guided delivery, implementation, "
            f"testing, documentation, troubleshooting, and collaboration using {skill_phrase} to produce "
            "reliable, business-ready outcomes."
        )
    if family == "senior":
        if service_management_role:
            return (
                f"The {title} is {article} {level} role {unit_context} for professionals with "
                f"{years}{qualification_clause}. The role leads service delivery and application support "
                f"governance across incident, problem, and change management, with accountability for SLA "
                f"performance, root cause follow-through, and stakeholder coordination using {skill_phrase}."
            )
        return (
            f"The {title} is {article} {level} role {unit_context} for professionals with "
            f"{years}{qualification_clause}. The role is responsible for delivering high-quality solutions "
            f"with {skill_phrase}, improving engineering practices, and supporting predictable delivery for "
            "business stakeholders."
        )
    if family == "leadership":
        return (
            f"The {title} is {article} {level} role {unit_context} for professionals with "
            f"{years}{qualification_clause}. The role provides solution direction, delivery ownership, "
            f"technical governance, and stakeholder alignment across work involving {skill_phrase}."
        )
    return (
        f"The {title} is {article} {level} role {unit_context} for candidates with "
        f"{years}{qualification_clause}. The role focuses on dependable delivery, analysis, implementation, "
        f"quality, and operational follow-through using {skill_phrase}."
    )


def _build_level_appropriate_responsibilities(request: JDGenerationRequest) -> list[str]:
    """Create responsibilities that match the HR years, level, and skills."""
    title = _clean_optional(request.internal_title) or _clean_optional(request.job_title) or "the role"
    work_area = _work_area_label(request, "assigned applications or services")
    priority_context = _priority_context(request)
    initiative_context = _initiative_context(request)
    level = _infer_job_level(request)
    family = _level_family(level, request.years_of_experience)
    years = _format_experience(_clean_optional(request.years_of_experience) or "") or "the required experience level"
    skills = _split_skills(request.skills)
    skill_phrase = _skill_text(skills)
    primary_skill = skills[0] if skills else "the assigned technology stack"
    service_management_role = _is_service_management_role(request)

    if family == "early":
        return [
            f"Develop and maintain assigned {work_area} features or service components using {skill_phrase} under guidance from senior team members.",
            f"Implement, test, and document changes that match agreed requirements for {priority_context}.",
            f"Apply {years} to troubleshoot defects, analyze root causes, and support timely fixes within the assigned scope.",
            f"Use {primary_skill} and related required skills to build clean, readable, and maintainable deliverables.",
            "Participate in code reviews, sprint ceremonies, estimation discussions, and knowledge-sharing sessions with clear follow-through.",
            "Prepare clear technical notes, handover details, and status updates for completed development or support tasks.",
            "Collaborate with engineers, QA, analysts, and business stakeholders to clarify requirements and validate outcomes.",
            "Follow team standards for version control, testing, release readiness, and production support without taking unsupported ownership beyond the role level.",
        ]
    if family == "senior":
        if service_management_role:
            return [
                f"Lead senior-level application support and service management activities aligned to {priority_context}.",
                f"Oversee incident, problem, and change management processes using {skill_phrase} to improve service reliability and business continuity.",
                "Coordinate major incident response, root cause analysis, corrective actions, and stakeholder communications for assigned services.",
                "Monitor SLA performance, production support trends, release readiness, and operational risks to drive measurable service improvements.",
                "Guide support teams and less-experienced consultants through troubleshooting, documentation, escalation handling, and process discipline.",
                "Partner with application, operations, QA, and business stakeholders to prioritize fixes, service improvements, and release coordination.",
                "Strengthen knowledge articles, support handovers, runbooks, and service review practices for assigned applications or platforms.",
                f"Apply {years} to make sound operational decisions, manage risks, and support predictable service delivery outcomes.",
            ]
        return [
            f"Lead technical delivery of {work_area} features, services, or enhancements aligned to {priority_context}.",
            f"Design and implement maintainable solutions using {skill_phrase}, balancing performance, reliability, and delivery timelines.",
            f"Review code, solution approaches, and implementation plans to improve quality and reduce rework across the team.",
            f"Troubleshoot complex defects, integration issues, and production concerns related to {skill_phrase}.",
            "Mentor less-experienced engineers through practical reviews, pairing, documentation, and implementation guidance.",
            "Coordinate with product, QA, operations, and business stakeholders to translate requirements into delivery-ready technical work.",
            "Improve engineering practices, reusable patterns, automation, and release readiness for assigned applications or services.",
            f"Apply {years} to make sound technical decisions, manage risks, and support predictable delivery outcomes.",
        ]
    if family == "leadership":
        return [
            f"Own solution direction and delivery alignment for {initiative_context}, ensuring architecture decisions support business outcomes and stakeholder priorities.",
            f"Define scalable approaches using {skill_phrase}, ensuring architecture, integration, reliability, and maintainability expectations are met.",
            "Guide technical teams through design decisions, estimation, risk management, delivery planning, and implementation governance.",
            "Partner with business, delivery, operations, and engineering stakeholders to convert objectives into executable technology roadmaps.",
            "Review solution quality, dependency risks, and release readiness across services, platforms, or programs within scope.",
            "Establish reusable engineering practices, documentation standards, and governance checkpoints for consistent execution.",
            f"Mentor senior contributors and strengthen technical capability across {skill_phrase}.",
            f"Apply {years} to balance strategic direction, hands-on technical judgment, and measurable business outcomes.",
        ]
    return [
        f"Deliver {work_area} features, enhancements, or operational tasks aligned to {priority_context}.",
        f"Analyze requirements and implement maintainable solutions using {skill_phrase}.",
        f"Apply {years} to troubleshoot issues, resolve defects, and support stable application or service behavior.",
        "Coordinate with QA, operations, business users, and engineering stakeholders to validate requirements and outcomes.",
        "Prepare technical documentation, implementation notes, and handover details for delivered work.",
        "Participate in reviews, planning discussions, and release readiness activities with clear ownership of assigned tasks.",
        "Improve existing code, configurations, integrations, or support processes within the assigned scope.",
        "Track risks, dependencies, and progress updates so delivery stakeholders have accurate visibility.",
    ]


def _build_level_appropriate_soft_skills(request: JDGenerationRequest) -> list[str]:
    """Return soft skills that fit the seniority of the JD."""
    level = _infer_job_level(request)
    family = _level_family(level, request.years_of_experience)
    if family == "early":
        return [
            "Learning agility",
            "Attention to detail",
            "Clear written and verbal communication",
            "Accountability for assigned work",
            "Collaborative problem solving",
            "Openness to feedback",
        ]
    if family == "senior":
        return [
            "Technical judgment",
            "Mentoring and coaching",
            "Stakeholder communication",
            "Ownership of delivery outcomes",
            "Problem solving under ambiguity",
            "Continuous improvement mindset",
        ]
    if family == "leadership":
        return [
            "Strategic thinking",
            "Technical leadership",
            "Stakeholder management",
            "Decision making under complexity",
            "Coaching and capability building",
            "Delivery governance",
        ]
    return [
        "Analytical thinking",
        "Collaboration",
        "Clear communication",
        "Ownership of assigned outcomes",
        "Problem solving",
        "Adaptability",
    ]


def _build_business_ready_compensation_benefits(request: JDGenerationRequest) -> list[str]:
    """Keep benefits professional and aligned with the selected work model."""
    benefits = [
        "Competitive salary and performance-based rewards",
        "Health and wellness benefits",
        "Paid time off and leave benefits",
        "Professional development and learning opportunities",
    ]
    if request.remote_allowed:
        benefits.insert(3, "Remote work flexibility aligned with business and role requirements")
    return benefits


def _apply_level_appropriate_work_environment(jd: dict, request: JDGenerationRequest) -> None:
    """Keep reporting structure realistic for the level and avoid invented teams."""
    level = _infer_job_level(request)
    family = _level_family(level, request.years_of_experience)
    department = _clean_optional(request.department) or "department"
    business_unit = _clean_optional(request.business_unit)
    stakeholder_label = f"{business_unit} stakeholders" if business_unit else (
        f"{department} stakeholders"
        if not re.fullmatch(r"[A-Z]{1,3}\d{1,3}", department or "")
        else "Business stakeholders"
    )
    service_management_role = _is_service_management_role(request)

    report_map = {
        "early": "Senior Engineer or Team Lead",
        "mid": "Project Manager or Delivery Manager",
        "senior": "Engineering Manager or Technical Lead",
        "leadership": "Delivery Head or Senior Technology Leader",
    }
    if service_management_role:
        report_map = {
            "early": "Application Support Lead or Service Delivery Lead",
            "mid": "Service Delivery Manager or Application Support Manager",
            "senior": "Service Delivery Manager or Application Support Manager",
            "leadership": "Delivery Head or Senior Service Management Leader",
        }
    if family == "early":
        collaborators = ["Senior consultants", "QA team", "Business analysts", stakeholder_label]
    elif family == "leadership":
        collaborators = ["Delivery leadership", "Architecture teams", "Business stakeholders", "Engineering teams"]
    elif service_management_role:
        collaborators = ["Application support team", "Operations team", "QA team", stakeholder_label]
    else:
        collaborators = ["Engineering team", "QA team", "Operations team", stakeholder_label]

    jd["work_environment"] = {
        "reports_to": report_map[family],
        "team_size": None,
        "collaborates_with": collaborators,
        "collaboration_mode": "Cross-functional collaboration",
    }


def _align_level_sensitive_sections(jd: dict, request: JDGenerationRequest) -> list[str]:
    """Normalize narrative sections so they match exact HR inputs."""
    fixes: list[str] = []

    expected_summary = _build_level_appropriate_position_summary(request)
    if jd.get("position_summary") != expected_summary:
        jd["position_summary"] = expected_summary
        fixes.append("position_summary")

    base_responsibilities = _build_level_appropriate_responsibilities(request)
    existing_responsibilities = jd.get("responsibilities")
    aligned_responsibilities = base_responsibilities[:12]
    if existing_responsibilities != aligned_responsibilities:
        jd["responsibilities"] = aligned_responsibilities
        fixes.append("responsibilities")

    expected_metrics = _build_role_specific_success_metrics(request)
    if jd.get("success_metrics") != expected_metrics:
        jd["success_metrics"] = expected_metrics
        fixes.append("success_metrics")

    base_soft_skills = _build_level_appropriate_soft_skills(request)
    existing_soft_skills = jd.get("soft_skills")
    aligned_soft_skills = base_soft_skills[:7]
    if existing_soft_skills != aligned_soft_skills:
        jd["soft_skills"] = aligned_soft_skills
        fixes.append("soft_skills")

    before_work_environment = dict(jd.get("work_environment") or {}) if isinstance(jd.get("work_environment"), dict) else jd.get("work_environment")
    _apply_level_appropriate_work_environment(jd, request)
    if before_work_environment != jd.get("work_environment"):
        fixes.append("work_environment")

    return fixes


def _collect_dialog_inputs(
    request: JDGenerationRequest,
    effective_job_title: Optional[str] = None,
    clean_department: Optional[str] = None,
) -> dict:
    """Capture the exact dialog values used as source of truth."""
    return {
        "job_title": effective_job_title or _clean_optional(request.job_title),
        "job_level": _infer_job_level(request),
        "department": clean_department or _clean_optional(request.department),
        "years_of_experience": _clean_optional(request.years_of_experience),
        "internal_title": _clean_optional(request.internal_title),
        "business_unit": _clean_optional(request.business_unit),
        "qualification": _clean_optional(request.qualification),
        "skills": _split_skills(request.skills),
        "location": _clean_optional(request.location),
        "remote_allowed": request.remote_allowed,
        "user_requirements": _clean_optional(request.user_requirements),
    }


def _validate_dialog_conformance(jd: dict, request: JDGenerationRequest) -> list[str]:
    """Return any remaining mismatches after deterministic enforcement."""
    mismatches: list[str] = []
    expected_title = _clean_optional(request.job_title) or _clean_optional(request.internal_title)
    expected_department = _clean_optional(request.department)
    expected_years = _clean_optional(request.years_of_experience)
    expected_qualification = _clean_optional(request.qualification)
    expected_skills = _split_skills(request.skills)
    expected_level = _infer_job_level(request)

    required = jd.get("required_qualifications") if isinstance(jd, dict) else {}
    if not isinstance(required, dict):
        required = {}
    metadata = jd.get("metadata") if isinstance(jd, dict) else {}
    if not isinstance(metadata, dict):
        metadata = {}

    if expected_title and jd.get("job_title") != expected_title:
        mismatches.append("job_title")
    if expected_department and jd.get("department") != expected_department:
        mismatches.append("department")
    if expected_level and metadata.get("job_level") != expected_level:
        mismatches.append("job_level")
    if expected_years and required.get("experience") != _format_experience(expected_years):
        mismatches.append("years_of_experience")
    if expected_qualification and required.get("education") != expected_qualification:
        mismatches.append("qualification")
    if _clean_optional(request.internal_title) and jd.get("internal_title") != _clean_optional(request.internal_title):
        mismatches.append("internal_title")
    if _clean_optional(request.business_unit) and jd.get("business_unit") != _clean_optional(request.business_unit):
        mismatches.append("business_unit")
    if expected_skills:
        if required.get("technical_skills") != expected_skills:
            mismatches.append("technical_skills")
        if jd.get("tools_technologies") != expected_skills:
            mismatches.append("tools_technologies")

    location_input = _parse_location_input(request.location)
    location = jd.get("location")
    if location_input and isinstance(location, dict):
        for key, value in location_input.items():
            if location.get(key) != value:
                mismatches.append(f"location.{key}")
    if request.remote_allowed and isinstance(location, dict) and location.get("work_model") != "Remote":
        mismatches.append("location.work_model")

    if _contains_forbidden_level_language(
        [
            jd.get("position_summary", ""),
            *(jd.get("responsibilities") if isinstance(jd.get("responsibilities"), list) else []),
            *(jd.get("success_metrics") if isinstance(jd.get("success_metrics"), list) else []),
        ],
        request,
    ):
        mismatches.append("level_appropriate_sections")

    if expected_years:
        summary = str(jd.get("position_summary") or "")
        if expected_years not in summary and _format_experience(expected_years) not in summary:
            mismatches.append("position_summary.years_of_experience")

    if expected_skills:
        narrative_text = " ".join(
            [
                str(jd.get("position_summary") or ""),
                " ".join(
                    str(item)
                    for item in (
                        jd.get("responsibilities")
                        if isinstance(jd.get("responsibilities"), list)
                        else []
                    )
                ),
                " ".join(
                    str(item)
                    for item in (
                        jd.get("success_metrics")
                        if isinstance(jd.get("success_metrics"), list)
                        else []
                    )
                ),
            ]
        ).lower()
        anchored_skills = [
            skill
            for skill in expected_skills
            if skill.lower() in narrative_text
        ]
        if len(anchored_skills) < min(2, len(expected_skills)):
            mismatches.append("narrative_sections.skills")

    return mismatches


def _apply_hr_inputs_to_jd(jd: dict, request: JDGenerationRequest) -> dict:
    """Stamp exact dialog inputs onto the returned JD object."""
    if not isinstance(jd, dict):
        return jd

    effective_job_title = _clean_optional(request.job_title) or _clean_optional(request.internal_title)
    job_level = _infer_job_level(request)
    years = _clean_optional(request.years_of_experience)
    internal_title = _clean_optional(request.internal_title)
    business_unit = _clean_optional(request.business_unit)
    qualification = _clean_optional(request.qualification)
    skills = _split_skills(request.skills)
    department = _clean_optional(request.department)

    metadata = jd.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    if effective_job_title:
        jd["job_title"] = effective_job_title
    if job_level:
        metadata["job_level"] = job_level
    if department:
        jd["department"] = department

    metadata["hr_inputs"] = {
        "department": department,
        "years_of_experience": years,
        "internal_title": internal_title,
        "business_unit": business_unit,
        "qualification": qualification,
        "skills": skills or None,
    }
    metadata["department_display"] = {
        "label": "Grade/Band" if _is_grade_code(department) else "Department",
        "value": department,
        "business_unit": business_unit,
    }
    metadata["dialog_inputs"] = _collect_dialog_inputs(request, effective_job_title, department)

    if internal_title:
        metadata["internal_title"] = internal_title
        jd["internal_title"] = internal_title

    if business_unit:
        metadata["business_unit"] = business_unit
        jd["business_unit"] = business_unit
        jd["division"] = business_unit
    else:
        jd.pop("business_unit", None)
        jd["division"] = None

    jd["team"] = None

    if years or qualification or skills or "required_qualifications" in jd:
        required = jd.get("required_qualifications")
        if not isinstance(required, dict):
            required = {}
        if years:
            metadata["years_of_experience"] = years
            required["experience"] = _format_experience(years)
        if qualification:
            metadata["qualification"] = qualification
            required["education"] = qualification
        if skills:
            metadata["skills"] = skills
            required["technical_skills"] = skills
            jd["tools_technologies"] = skills
        else:
            metadata.pop("skills", None)
            required["technical_skills"] = []
            jd["tools_technologies"] = []

        jd["required_qualifications"] = required

    location_input = _parse_location_input(request.location)
    location = jd.get("location")
    if not isinstance(location, dict):
        location = {}
    if location_input or request.remote_allowed:
        location.update(location_input)
        if request.remote_allowed:
            location["work_model"] = "Remote"
        elif not location.get("work_model"):
            location["work_model"] = "Hybrid"
        location.setdefault("travel_required", False)
    else:
        location["city"] = "Location to be confirmed"
        location["country"] = ""
        location.setdefault("work_model", "Hybrid")
        location.setdefault("travel_required", False)
    jd["location"] = location

    jd["remote_allowed"] = request.remote_allowed

    if _success_metrics_need_enrichment(jd.get("success_metrics"), request):
        jd["success_metrics"] = _build_role_specific_success_metrics(request)

    preferred = _build_input_based_preferred_qualifications(request)
    if preferred:
        jd["preferred_qualifications"] = preferred

    level_section_fixes = _align_level_sensitive_sections(jd, request)
    expected_benefits = _build_business_ready_compensation_benefits(request)
    if jd.get("compensation_benefits") != expected_benefits:
        jd["compensation_benefits"] = expected_benefits
        level_section_fixes.append("compensation_benefits")

    jd["metadata"] = metadata
    mismatches = _validate_dialog_conformance(jd, request)
    metadata["input_conformance"] = {
        "source": "jd_generation_dialog",
        "enforced": True,
        "mismatches_after_enforcement": mismatches,
        "level_section_fixes": level_section_fixes,
        "enforced_fields": [
            "job_title",
            "job_level",
            "department",
            "years_of_experience",
            "internal_title",
            "business_unit",
            "qualification",
            "skills",
            "location",
            "remote_allowed",
            "position_summary",
            "responsibilities",
            "success_metrics",
            "soft_skills",
            "work_environment",
            "compensation_benefits",
        ],
    }

    jd["metadata"] = metadata
    return jd


def _ensure_agents_importable() -> None:
    """Ensure agents.jd_generation is importable (repo or container layout)."""
    import importlib.util
    import sys
    from pathlib import Path

    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent.parent.parent.parent
    agents_path = project_root / "apps" / "agents" / "agents"

    if not agents_path.exists():
        cwd = Path.cwd()
        if (cwd / "apps" / "agents" / "agents").exists():
            agents_path = cwd / "apps" / "agents" / "agents"
        elif (cwd.parent / "apps" / "agents" / "agents").exists():
            agents_path = cwd.parent / "apps" / "agents" / "agents"
        elif (current_file.parent.parent.parent.parent.parent / "apps" / "agents" / "agents").exists():
            agents_path = current_file.parent.parent.parent.parent.parent / "apps" / "agents" / "agents"

    if not agents_path.exists():
        api_dir = current_file.parent.parent.parent.parent
        if api_dir.name == "api" and (api_dir.parent / "agents" / "agents").exists():
            agents_path = api_dir.parent / "agents" / "agents"

    if agents_path.exists():
        if str(agents_path) not in sys.path:
            sys.path.insert(0, str(agents_path))
        agents_parent = agents_path.parent
        if agents_parent.exists() and str(agents_parent) not in sys.path:
            sys.path.insert(0, str(agents_parent))
        return

    if importlib.util.find_spec("agents.jd_generation") is None:
        error_msg = (
            f"Cannot find agents directory. Tried: {agents_path}, "
            f"Current file: {current_file}, Project root: {project_root}, CWD: {Path.cwd()}"
        )
        logger.error(error_msg)
        raise ImportError(error_msg)


def _llm_not_configured_detail(provider: str) -> str:
    if provider == "openai":
        return "OpenAI not configured. Set OPENAI_API_KEY and LLM_PROVIDER=openai."
    if provider == "azure_openai":
        return (
            "Azure OpenAI not configured. Set AZURE_OPENAI_ENDPOINT and "
            "AZURE_OPENAI_API_KEY (quanthire-aoai-secret on AKS)."
        )
    return (
        "Vertex AI not configured. Set GCP_PROJECT_ID and ADC, "
        "or use LLM_PROVIDER=openai with OPENAI_API_KEY."
    )


def _resolve_generation_inputs(
    request: JDGenerationRequest,
) -> tuple[str, str, str]:
    effective_job_title = _clean_optional(request.job_title) or _clean_optional(
        request.internal_title
    )
    clean_department = _clean_optional(request.department)
    effective_job_level = _infer_job_level(request)
    if not effective_job_title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="job_title or internal_title is required",
        )
    if not clean_department:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="department is required",
        )
    missing_inputs = _missing_business_ready_inputs(request)
    if missing_inputs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Cannot generate a business-ready JD because required HR matrix inputs are missing: "
                f"{', '.join(missing_inputs)}. Fill these fields to prevent invented skills, tools, "
                "qualifications, or role requirements."
            ),
        )
    return effective_job_title, clean_department, effective_job_level


def _get_jd_orchestrator():
    from agents.jd_generation.config import get_config
    from agents.jd_generation.exceptions import ConfigurationError
    from agents.jd_generation.orchestrator import JDGenerationOrchestrator

    _ensure_agents_importable()
    config = get_config()
    if not config.is_llm_configured:
        logger.error("LLM not configured (provider=%s)", config.llm_provider)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_llm_not_configured_detail(config.llm_provider),
        )

    global _jd_orchestrator
    try:
        with _jd_orchestrator_lock:
            if _jd_orchestrator is None:
                logger.info(
                    "Initializing JD Generation Orchestrator (provider=%s, model=%s)...",
                    config.llm_provider,
                    config.llm_model,
                )
                _jd_orchestrator = JDGenerationOrchestrator()
                logger.info("JD Generation Orchestrator initialized successfully")
            orchestrator = _jd_orchestrator
    except ConfigurationError as exc:
        logger.error("Configuration error: %s", exc.message, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Configuration error: {exc.message}",
        ) from exc
    except Exception as exc:
        logger.error("Failed to initialize orchestrator: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize JD generation system: {exc}",
        ) from exc
    return orchestrator


async def _execute_jd_generation_core(
    request: JDGenerationRequest,
    session: AsyncSession,
    current_user: Optional[dict],
    orchestrator: Any,
) -> dict:
    effective_job_title, clean_department, effective_job_level = _resolve_generation_inputs(
        request
    )

    logger.info(
        "Starting JD generation",
        extra={
            "job_title": effective_job_title,
            "job_level": effective_job_level,
            "department": clean_department,
        },
    )

    logger.info("Calling orchestrator.generate_job_description...")
    hr_context = _build_hr_context(request)
    combined_requirements = "\n\n".join(
        part for part in [request.user_requirements, hr_context] if part
    ) or None

    result = await asyncio.to_thread(
        orchestrator.generate_job_description,
        job_title=effective_job_title,
        job_level=effective_job_level,
        department=clean_department,
        location=request.location,
        remote_allowed=request.remote_allowed,
        user_requirements=combined_requirements,
        user_edits=request.user_edits,
        preserve_hr_inputs=True,
    )

    if "jd" in result and "job_description" not in result:
        result["job_description"] = result["jd"]
    elif "job_description" in result and "jd" not in result:
        result["jd"] = result["job_description"]

    jd_payload = result.get("jd") or result.get("job_description")
    if isinstance(jd_payload, dict):
        jd_payload = _apply_hr_inputs_to_jd(jd_payload, request)
        jd_payload["job_title"] = effective_job_title
        jd_payload["department"] = clean_department
        result["jd"] = jd_payload
        result["job_description"] = jd_payload

    result.setdefault("metadata", {})
    if isinstance(result["metadata"], dict):
        result["metadata"]["dialog_inputs"] = _collect_dialog_inputs(
            request,
            effective_job_title,
            clean_department,
        )
        result["metadata"]["hr_matrix_inputs"] = {
            "department": clean_department,
            "years_of_experience": _clean_optional(request.years_of_experience),
            "internal_title": _clean_optional(request.internal_title),
            "business_unit": _clean_optional(request.business_unit),
            "qualification": _clean_optional(request.qualification),
            "skills": _split_skills(request.skills),
        }
        if isinstance(result.get("jd"), dict):
            result["metadata"]["input_conformance"] = result["jd"].get(
                "metadata",
                {},
            ).get("input_conformance")

    if settings.use_pgvector_pipeline and isinstance(jd_payload, dict):
        try:
            from app.services.jd_pipeline_service import JDPipelineService

            job_id = request.job_id or str(uuid.uuid4())
            save_data = {
                **jd_payload,
                "id": job_id,
                "job_id": job_id,
                "job_title": effective_job_title,
                "department": clean_department,
            }
            created_by = None
            job_row_id = None
            if current_user and current_user.get("id"):
                try:
                    created_by = UUID(str(current_user["id"]))
                except (TypeError, ValueError):
                    created_by = None
            if request.job_id:
                try:
                    job_row_id = UUID(str(request.job_id))
                except (TypeError, ValueError):
                    job_row_id = None

            pipeline = JDPipelineService(session)
            save_result = await pipeline.store_jd(
                jd_data=save_data,
                created_by=created_by,
                job_row_id=job_row_id,
            )
            stored_id = save_result["job_id"]
            result["job_id"] = stored_id
            result["postgres_job_id"] = save_result.get("postgres_job_id") or stored_id
            result["milvus_id"] = stored_id
            result["vector_id"] = stored_id
            result["storage_backend"] = "pgvector"
            if isinstance(result.get("metadata"), dict):
                result["metadata"]["auto_saved"] = True
                result["metadata"]["storage_backend"] = "pgvector"
            logger.info("JD auto-saved to pgvector after generate: %s", stored_id)
        except Exception as save_exc:
            logger.warning(
                "JD generated but auto-save to pgvector failed: %s",
                save_exc,
                exc_info=True,
            )
            if isinstance(result.get("metadata"), dict):
                result["metadata"]["auto_save_error"] = str(save_exc)

    if result.get("agent_thoughts"):
        logger.info(
            "Agent thinking process",
            extra={"thought_count": len(result["agent_thoughts"])},
        )

    return result


def _raise_http_for_generation_error(exc: Exception) -> None:
    from agents.jd_generation.exceptions import ValidationError, WorkflowError

    if isinstance(exc, HTTPException):
        raise exc
    if isinstance(exc, ValidationError):
        logger.warning(
            "Validation error in JD generation",
            extra={"error": str(exc), "field": exc.details.get("field")},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {exc.message}",
        ) from exc
    if isinstance(exc, WorkflowError):
        logger.error(
            "Workflow error in JD generation",
            exc_info=True,
            extra={"error": str(exc), "state": exc.details.get("state")},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Workflow error: {exc.message}",
        ) from exc
    if isinstance(exc, AttributeError):
        error_msg = str(exc)
        if "MediaResolution" in error_msg or "GenerationConfig" in error_msg:
            logger.error(
                "LLM compatibility error in JD generation",
                exc_info=True,
                extra={"error": error_msg, "error_type": "compatibility"},
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    f"LLM compatibility error: {error_msg}. The system attempted to use "
                    "fallback LLM. Please check backend logs for details."
                ),
            ) from exc
    logger.error(
        "Unexpected error in JD generation",
        exc_info=True,
        extra={"error": str(exc), "error_type": type(exc).__name__},
    )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"JD generation failed: {exc}",
    ) from exc


async def _run_async_generation_task(
    task_id: str,
    request_payload: dict,
    current_user: Optional[dict],
) -> None:
    jd_generation_tasks.mark_running(task_id)
    try:
        orchestrator = _get_jd_orchestrator()
        request = JDGenerationRequest(**request_payload)
        async with async_session_maker() as session:
            result = await _execute_jd_generation_core(
                request,
                session,
                current_user,
                orchestrator,
            )
            await session.commit()
        jd_generation_tasks.mark_completed(
            task_id,
            jd_generation_tasks.serialize_result(result),
        )
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        jd_generation_tasks.mark_failed(task_id, detail)
    except Exception as exc:
        logger.error("Async JD generation failed for task %s", task_id, exc_info=True)
        jd_generation_tasks.mark_failed(task_id, str(exc))


@router.post(
    "/generate-async",
    response_model=JDGenerationAsyncResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_job_description_async(
    request: JDGenerationRequest,
    current_user: Optional[dict] = Depends(require_user_when_basic_auth),
):
    """
    Start JD generation and return immediately.

    Poll GET /jd-generation/generate-status/{task_id} until status is completed.
    """
    effective_job_title, clean_department, _ = _resolve_generation_inputs(request)
    task_id = str(uuid.uuid4())
    jd_generation_tasks.create_task(
        task_id,
        job_title=effective_job_title,
        department=clean_department,
    )
    user_snapshot = dict(current_user) if current_user else None
    asyncio.create_task(
        _run_async_generation_task(
            task_id,
            request.model_dump(),
            user_snapshot,
        )
    )
    return JDGenerationAsyncResponse(task_id=task_id)


@router.get(
    "/generate-status/{task_id}",
    response_model=JDGenerationStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def get_generation_status(task_id: str):
    """Poll async JD generation progress."""
    task = jd_generation_tasks.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generation task not found or expired",
        )
    payload = task.to_status_payload()
    result_payload = payload.get("result")
    parsed_result = None
    if result_payload:
        normalized = dict(result_payload)
        normalized.setdefault("success", True)
        parsed_result = JDGenerationResponse(**normalized)
    return JDGenerationStatusResponse(
        task_id=payload["task_id"],
        status=payload["status"],
        job_title=payload.get("job_title"),
        department=payload.get("department"),
        result=parsed_result,
        error=payload.get("error"),
    )


@router.post("/generate", response_model=JDGenerationResponse, status_code=status.HTTP_200_OK)
async def generate_job_description(
    request: JDGenerationRequest,
    current_user: Optional[dict] = Depends(require_user_when_basic_auth),
    session: AsyncSession = Depends(get_session),
):
    """Generate a job description synchronously (may take several minutes)."""
    try:
        orchestrator = _get_jd_orchestrator()
        result = await _execute_jd_generation_core(
            request,
            session,
            current_user,
            orchestrator,
        )
        return JDGenerationResponse(**result)
    except Exception as exc:
        _raise_http_for_generation_error(exc)


@router.get("/test", status_code=status.HTTP_200_OK)
async def test_endpoint():
    """
    Test endpoint to verify JD generation router is accessible.
    
    Returns:
        dict: Test response with Enterprise RAG status
    """
    # Check Enterprise RAG Service status
    rag_status = "unknown"
    rag_details = {}
    
    # ============================================================================
    # ENTERPRISE RAG REMOVED
    # ============================================================================
    # The Enterprise RAG Service has been removed to enforce single RAG pipeline.
    # All RAG queries must go through QueryRouter (apps/quantchat/core/query_router.py)
    # ============================================================================
    rag_status = "removed - use QueryRouter for RAG queries"
    rag_details = {
        "message": "Enterprise RAG Service removed",
        "canonical_pipeline": "apps.quantchat.core.query_router.QueryRouter",
        "access_via": "from apps.quantchat import get_query_router"
    }
    
    llm_info: dict = {}
    storage_info: dict = {}
    try:
        from agents.llm.chat_factory import llm_status
        from agents.deployment_env import (
            is_azure_nonprod,
            should_skip_local_vector_storage,
            vector_store_type,
        )

        llm_info = llm_status()
        storage_info = {
            "vector_store": vector_store_type() or "unknown",
            "skip_local_vector_storage": should_skip_local_vector_storage(),
            "azure_nonprod": is_azure_nonprod(),
        }
    except Exception as exc:
        llm_info = {"error": str(exc)}

    return {
        "status": "ok",
        "message": "JD Generation endpoint is accessible",
        "llm": llm_info,
        "storage": storage_info,
        "endpoints": {
            "generate": "/api/v1/jd-generation/generate",
            "generate_async": "/api/v1/jd-generation/generate-async",
            "generate_status": "/api/v1/jd-generation/generate-status/{task_id}",
            "save": "/api/v1/jd-generation/save",
            "test": "/api/v1/jd-generation/test"
        },
        "router": "registered",
        "database": {
            "type": "Enterprise RAG Architecture",
            "status": rag_status,
            "details": rag_details
        }
    }


@router.get("/thoughts/{job_id}", response_model=dict)
async def get_agent_thoughts(job_id: str):
    """
    Get agent thinking process for a job.
    
    Returns the complete thinking process visible to users.
    Note: Agent thoughts are stored in the workflow state and returned in the generation response.
    This endpoint is for future implementation to retrieve stored thoughts from Milvus.
    """
    return {
        "job_id": job_id,
        "agent_thoughts": [],
        "message": "Agent thoughts are included in the JD generation response. This endpoint will retrieve stored thoughts from Milvus in future versions."
    }


class JDSaveRequest(BaseModel):
    """Request model for saving/updating JD in Milvus."""
    
    job_id: Optional[str] = Field(None, description="Existing job ID (for updates)")
    job_title: str = Field(..., description="Job title")
    department: str = Field(..., description="Department name")
    job_description: dict = Field(..., description="Full job description object")


class JDSaveResponse(BaseModel):
    """Response model for JD save operation."""
    
    success: bool
    job_id: str
    milvus_id: Optional[str] = None
    storage_backend: Optional[str] = None
    message: str


class MalomatiaExportRequest(BaseModel):
    """Request model for Malomatia Word template export."""

    job_description: dict = Field(..., description="Enterprise JD payload to convert")
    template_type: str = Field(
        ...,
        description="Malomatia template variant: leader or non_leader",
    )

    @field_validator("template_type")
    @classmethod
    def validate_template_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"leader", "non_leader"}:
            raise ValueError("template_type must be 'leader' or 'non_leader'")
        return normalized


@router.post(
    "/export-malomatia",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "content": {
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {}
            }
        }
    },
)
async def export_malomatia_template(
    request: MalomatiaExportRequest,
    current_user: Optional[dict] = Depends(require_user_when_basic_auth),
):
    """Convert an enterprise JD into a Malomatia Word (.docx) template."""
    del current_user  # auth gate only

    if not isinstance(request.job_description, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="job_description must be an object",
        )

    try:
        from app.services.malomatia_jd_export import (
            MalomatiaTemplateNotFoundError,
            build_download_filename,
            build_malomatia_docx,
        )

        docx_bytes = build_malomatia_docx(
            request.job_description,
            request.template_type,  # type: ignore[arg-type]
        )
        filename = build_download_filename(
            request.job_description,
            request.template_type,  # type: ignore[arg-type]
        )
    except MalomatiaTemplateNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error("Malomatia JD export failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export Malomatia template: {exc}",
        ) from exc

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/save", response_model=JDSaveResponse, status_code=status.HTTP_200_OK)
async def save_job_description(
    request: JDSaveRequest,
    current_user: Optional[dict] = Depends(require_user_when_basic_auth),
    session: AsyncSession = Depends(get_session),
):
    """
    Save or update a Job Description in the vector store.
    
    Azure Non-Prod: Postgres + pgvector.
    Legacy local dev: Milvus via DocumentIngestion.
    """
    logger.info(f"💾 Save JD request received: job_title={request.job_title}, department={request.department}")
    logger.info(f"   Request data: job_id={request.job_id}, job_description type={type(request.job_description).__name__}, keys={list(request.job_description.keys()) if isinstance(request.job_description, dict) else 'N/A'}")
    
    # Validate request
    if not request.job_title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="job_title is required"
        )
    if not request.department:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="department is required"
        )
    if not request.job_description:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="job_description is required"
        )
    if not isinstance(request.job_description, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"job_description must be a dict, got {type(request.job_description).__name__}"
        )
    
    import uuid
    
    job_id = request.job_id or str(uuid.uuid4())
    jd_data = {
        "id": job_id,
        "job_title": request.job_title,
        "department": request.department,
    }
    if isinstance(request.job_description, dict):
        jd_data.update(request.job_description)
    else:
        jd_data["raw_jd"] = request.job_description
    jd_data["id"] = job_id
    jd_data["job_id"] = job_id

    if settings.use_pgvector_pipeline:
        try:
            from app.services.jd_pipeline_service import JDPipelineService

            created_by = None
            job_row_id = None
            if current_user and current_user.get("id"):
                try:
                    created_by = UUID(str(current_user["id"]))
                except (TypeError, ValueError):
                    created_by = None
            if request.job_id:
                try:
                    job_row_id = UUID(str(request.job_id))
                except (TypeError, ValueError):
                    job_row_id = None

            pipeline = JDPipelineService(session)
            result = await pipeline.store_jd(
                jd_data=jd_data,
                created_by=created_by,
                job_row_id=job_row_id,
            )
            stored_id = result["job_id"]
            return JDSaveResponse(
                success=True,
                job_id=stored_id,
                milvus_id=stored_id,
                storage_backend="pgvector",
                message=result["message"],
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("Failed to save JD to pgvector: %s", exc, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save job description: {exc}",
            ) from exc

    # Legacy Milvus path (local dev)
    try:
        from apps.quantchat.ingestion import get_document_ingestion
        
        ingestion_service = get_document_ingestion()
        
        if not ingestion_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="DocumentIngestion service not available"
            )
        
        if not ingestion_service.is_connected():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="DocumentIngestion service not connected to Milvus"
            )
        
        stored_id = ingestion_service.add_jd(jd_data)
        
        logger.info(f"✅ JD {stored_id} saved to Milvus successfully via DocumentIngestion")
        
        return JDSaveResponse(
            success=True,
            job_id=stored_id,
            milvus_id=stored_id,
            storage_backend="milvus",
            message=f"Job description saved to Milvus vector database (ID: {stored_id})"
        )
        
    except HTTPException as http_ex:
        # Re-raise HTTP exceptions as-is (already formatted)
        logger.warning(f"⚠️ HTTP Exception in save endpoint: {http_ex.detail}")
        raise
    except ValueError as val_err:
        # Validation errors
        error_msg = f"Validation error: {str(val_err)}"
        logger.error(f"❌ Validation error in save endpoint: {val_err}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    except Exception as e:
        error_msg = f"Failed to save job description: {str(e)}"
        logger.error(f"❌ Failed to save JD to Milvus: {e}", exc_info=True)
        import traceback
        logger.error(f"   Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )
