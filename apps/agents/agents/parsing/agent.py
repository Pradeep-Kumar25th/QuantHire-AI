"""Resume parsing agent — enterprise HR screening extraction for any resume layout."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError

from agents.base.agent import AgentConfig, BaseAgent
from agents.base.result import AgentResult
from agents.parsing.sanitizer import sanitize_parsed_resume

import logging

logger = logging.getLogger(__name__)


class ScreeningMetadata(BaseModel):
    """HR screening signals extracted when present in the resume."""

    work_authorization: Optional[str] = None
    visa_status: Optional[str] = None
    notice_period: Optional[str] = None
    availability: Optional[str] = None
    relocation_willing: Optional[bool] = None
    expected_salary: Optional[str] = None
    security_clearance: Optional[str] = None
    career_level: Optional[str] = None


class CustomSection(BaseModel):
    """Catch-all for resume sections with non-standard titles."""

    title: str = ""
    content: str = ""


class ParsedResume(BaseModel):
    """Enterprise structured resume — all standard and custom sections."""

    name: Optional[str] = None
    emails: List[str] = Field(default_factory=list)
    phones: List[str] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)
    summary: Optional[str] = None
    section_inventory: List[str] = Field(default_factory=list)
    education: List[Dict[str, Any]] = Field(default_factory=list)
    experience: List[Dict[str, Any]] = Field(default_factory=list)
    internships: List[Dict[str, Any]] = Field(default_factory=list)
    skills: List[Dict[str, Any]] = Field(default_factory=list)
    certificates: List[Dict[str, Any]] = Field(default_factory=list)
    links: List[Dict[str, Any]] = Field(default_factory=list)
    languages: List[Dict[str, Any]] = Field(default_factory=list)
    projects: List[Dict[str, Any]] = Field(default_factory=list)
    publications: List[Dict[str, Any]] = Field(default_factory=list)
    awards: List[str] = Field(default_factory=list)
    volunteer: List[Dict[str, Any]] = Field(default_factory=list)
    trainings: List[Dict[str, Any]] = Field(default_factory=list)
    memberships: List[str] = Field(default_factory=list)
    military: List[Dict[str, Any]] = Field(default_factory=list)
    patents: List[Dict[str, Any]] = Field(default_factory=list)
    references: List[str] = Field(default_factory=list)
    custom_sections: List[CustomSection] = Field(default_factory=list)
    screening: ScreeningMetadata = Field(default_factory=ScreeningMetadata)
    confidence: float = Field(default=0.75, ge=0.0, le=1.0)
    ambiguous_fields: List[str] = Field(default_factory=list)


class ParsingAgent(BaseAgent):
    """Enterprise resume screener — exhaustive extraction for HR workflows.

    Handles any layout: single/multi-column, tables, timelines, creative designs,
    scanned OCR, DOCX, PDF, long CVs (10+ pages), English and mixed-language headers.
    """

    def __init__(self):
        config = AgentConfig(
            name="ParsingAgent",
            description="Enterprise resume screener — exhaustive structured extraction",
            temperature=0.15,
            max_tokens=16384,
            timeout=240,
        )
        super().__init__(config)

    def _get_parsing_schema(self) -> Dict[str, Any]:
        return {
            "name": "string or null",
            "emails": ["string"],
            "phones": ["string"],
            "locations": ["string"],
            "summary": "string or null — full professional summary/objective/profile verbatim",
            "section_inventory": [
                "list EVERY section header/title found in the resume, in document order"
            ],
            "education": [
                {
                    "degree": "string",
                    "institution": "string",
                    "year": "string or number",
                    "field": "string or null",
                    "location": "string or null",
                    "gpa": "string or null",
                    "honors": "string or null",
                }
            ],
            "experience": [
                {
                    "company": "string",
                    "title": "string",
                    "start": "YYYY-MM or string",
                    "end": "YYYY-MM or 'present'",
                    "bullets": ["every achievement/responsibility bullet verbatim"],
                    "location": "string or null",
                    "technologies": ["tools/languages used in this role, if mentioned"],
                }
            ],
            "internships": [
                {
                    "company": "string",
                    "title": "string",
                    "start": "YYYY-MM",
                    "end": "YYYY-MM or 'present'",
                    "bullets": ["string"],
                }
            ],
            "skills": [
                {
                    "name": "string",
                    "category": "technical|soft|tool|domain|language|methodology",
                    "confidence": "number 0-1",
                    "proficiency": "string or null",
                }
            ],
            "certificates": [
                {
                    "name": "string",
                    "issuer": "string or null",
                    "date": "string or null",
                    "credential_id": "string or null",
                }
            ],
            "links": [{"type": "linkedin|github|portfolio|website|other", "url": "string"}],
            "languages": [{"language": "string", "proficiency": "string or null"}],
            "projects": [
                {
                    "name": "string",
                    "description": "string",
                    "technologies": ["string"],
                    "url": "string or null",
                    "dates": "string or null",
                }
            ],
            "publications": [
                {"title": "string", "publisher": "string", "year": "string", "url": "string or null"}
            ],
            "awards": ["string"],
            "volunteer": [
                {"organization": "string", "role": "string", "dates": "string", "description": "string"}
            ],
            "trainings": [
                {"name": "string", "provider": "string", "date": "string", "description": "string"}
            ],
            "memberships": ["professional association or society memberships"],
            "military": [
                {"branch": "string", "rank": "string", "dates": "string", "description": "string"}
            ],
            "patents": [{"title": "string", "number": "string", "year": "string"}],
            "references": ["reference lines if provided, or 'Available upon request'"],
            "custom_sections": [
                {
                    "title": "exact section header from resume",
                    "content": "full verbatim text under that section",
                }
            ],
            "screening": {
                "work_authorization": "string or null",
                "visa_status": "string or null",
                "notice_period": "string or null",
                "availability": "string or null",
                "relocation_willing": "boolean or null",
                "expected_salary": "string or null — only if explicitly stated",
                "security_clearance": "string or null",
                "career_level": "entry|junior|mid|senior|lead|executive or null",
            },
            "confidence": "number 0-1",
            "ambiguous_fields": ["fields needing HR clarification"],
        }

    def _get_parsing_prompt(self) -> str:
        return """You are an enterprise ATS-grade resume screener used by HR teams worldwide.
Your job is to extract EVERY piece of information from ANY resume — nothing may be omitted.

RESUME FORMATS YOU MUST HANDLE (all equally):
- Single column, double column, sidebar, infographic, timeline, table/grid layouts
- Chronological, functional, hybrid, academic CV, executive summary formats
- 1-page to 20+ page CVs; creative/designer resumes; government/military formats
- PDF text layer, scanned OCR text, Word exports, plain text, image-based resumes
- Section headers in ANY language or creative wording (map to standard fields + custom_sections)
- Tables (skills matrices, competency grids, two-column experience blocks) — extract every cell/row
- Inline sections (e.g. "Languages: English, Hindi" in footer) — parse into structured fields

MANDATORY EXTRACTION RULES:
1. Read the ENTIRE document top to bottom — never stop after page 1
2. For multi-column layouts: read column-by-column, then merge in logical reading order
3. List ALL section headers in section_inventory using exact wording from the resume
4. Extract EVERY job/role: full-time, part-time, contract, freelance, consulting, internship
5. Capture EVERY bullet under each role — preserve metrics, tools, and action verbs verbatim
6. Extract skills from dedicated skills sections AND from job descriptions/project text
7. Capture certifications, licenses, trainings, courses, workshops, bootcamps
8. Capture projects, publications, patents, awards, honors, volunteer, military, memberships
9. ANY section that does not map cleanly → custom_sections with exact title + full verbatim content
10. Do NOT invent information — only extract what is present in the document
11. Do NOT over-summarize — HR needs complete data for screening and compliance
12. Normalize dates to YYYY-MM when possible; use "present" for current roles
13. For comma-separated lists (skills, languages, tools) — expand into individual items
14. Redact only SSN/passport numbers; keep all professional contact and career data

JSON OUTPUT RULES (critical for production):
- Use empty string "" instead of null for ALL string fields
- Use empty arrays [] for missing list sections
- Never omit required top-level keys

SECTION HEADER MAPPING (examples — not exhaustive):
- Work History / Employment / Professional Experience / Career → experience
- Internship / Trainee → internships
- Education / Academic Background / Qualifications → education
- Skills / Core Competencies / Tech Stack / Expertise → skills
- Certifications / Licenses / Credentials → certificates
- Projects / Portfolio / Key Projects / Selected Projects → projects
- Publications / Research / Papers → publications
- Awards / Honors / Achievements / Leadership → awards (or custom_sections if mixed)
- Volunteer / Community Service → volunteer
- Languages / Language Proficiency → languages
- References / Referees → references
- Training / Courses / Professional Development → trainings
- Memberships / Affiliations / Professional Bodies → memberships
- Military Service / Armed Forces → military
- Patents → patents
- Additional Information / Personal Details / Other → screening + custom_sections
- ANY unknown header → custom_sections (verbatim)

OUTPUT: Valid JSON only. Lower confidence only when name or experience is genuinely missing."""

    @classmethod
    def _normalize_parsed_data(
        cls, parsed_data: Dict[str, Any], raw_text: Optional[str] = None
    ) -> Dict[str, Any]:
        return sanitize_parsed_resume(parsed_data, raw_text=raw_text)

    @classmethod
    def _validate_parsed_resume(cls, parsed_data: Dict[str, Any]) -> ParsedResume:
        try:
            return ParsedResume(**parsed_data)
        except ValidationError as exc:
            logger.warning(
                "ParsedResume validation retry after sanitizer: %s", exc.errors()[:3]
            )
            # Last-resort: drop custom sections that still fail, keep core candidate data
            fallback = dict(parsed_data)
            fallback["custom_sections"] = []
            return ParsedResume(**fallback)

    async def execute(self, input_data: Dict[str, Any]) -> AgentResult:
        resume_text = input_data.get("resume_text", "")

        if not resume_text or not resume_text.strip():
            return self._create_result(
                output={},
                success=False,
                error="Empty resume text provided",
            )

        text = resume_text.strip()
        max_chars = 90000
        truncated = False
        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n[document truncated for model context]"
            truncated = True

        try:
            system_prompt = self.get_system_prompt() + "\n\n" + self._get_parsing_prompt()
            schema = self._get_parsing_schema()

            user_prompt = f"""Perform enterprise HR screening extraction on this resume.
The candidate may use ANY layout, language mix, or section naming — extract everything.

RESUME TEXT:
{text}

Respond with ONLY valid JSON matching the schema.
Use "" for empty strings, [] for empty lists — never use null for string fields."""

            parsed_data = await self.llm_client.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema=schema,
            )

            parsed_data = self._normalize_parsed_data(parsed_data, raw_text=text)
            parsed_resume = self._validate_parsed_resume(parsed_data)

            missing = list(parsed_resume.ambiguous_fields)
            for field, condition in (
                ("name", not parsed_resume.name),
                ("email", not parsed_resume.emails),
                ("experience", not parsed_resume.experience and not parsed_resume.internships),
            ):
                if condition and field not in missing:
                    missing.append(field)

            evidence = []
            if parsed_resume.name:
                evidence.append(f"Name: {parsed_resume.name}")
            if parsed_resume.section_inventory:
                evidence.append(
                    f"Sections inventoried: {len(parsed_resume.section_inventory)}"
                )
            exp_count = len(parsed_resume.experience) + len(parsed_resume.internships)
            if exp_count:
                evidence.append(f"Roles captured: {exp_count}")
            if parsed_resume.skills:
                evidence.append(f"Skills captured: {len(parsed_resume.skills)}")
            if parsed_resume.custom_sections:
                evidence.append(
                    f"Custom sections: {len(parsed_resume.custom_sections)}"
                )

            output = parsed_resume.model_dump()
            output["ambiguous_fields"] = missing

            return self._create_result(
                output=output,
                confidence=parsed_resume.confidence,
                evidence=evidence,
                metadata={
                    "missing_fields": missing,
                    "total_skills": len(parsed_resume.skills),
                    "total_experience": len(parsed_resume.experience),
                    "total_internships": len(parsed_resume.internships),
                    "total_education": len(parsed_resume.education),
                    "total_projects": len(parsed_resume.projects),
                    "total_publications": len(parsed_resume.publications),
                    "total_custom_sections": len(parsed_resume.custom_sections),
                    "section_inventory_count": len(parsed_resume.section_inventory),
                    "parser": "enterprise_parsing_agent",
                    "truncated_input": truncated,
                },
            )

        except Exception as e:
            logger.error("Resume parsing failed: %s", e, exc_info=True)
            return self._create_result(
                output={},
                success=False,
                error=f"Failed to parse resume: {str(e)}",
            )

    async def parse(self, resume_text: str) -> ParsedResume:
        result = await self.execute({"resume_text": resume_text})
        if not result.success:
            raise ValueError(result.error)
        return ParsedResume(**result.output)
