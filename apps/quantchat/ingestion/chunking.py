"""
Document Chunking
=================

Semantic section-based chunking for resumes and JDs.
With smart truncation, quality validation, and optional overlap.
"""

import re
from typing import List, Dict, Any
from ..config.logging_config import setup_logger
from ..config.settings import RESUME_CHUNK_SIZE, JD_CHUNK_SIZE

logger = setup_logger("chunking")

# Minimum chunk content length to be considered valid (filter out low-quality chunks)
MIN_CHUNK_LENGTH = 50

# Overlap size for chunk boundaries (helps with semantic continuity)
CHUNK_OVERLAP_SIZE = 100


def _smart_truncate(text: str, max_length: int, overlap: bool = False) -> str:
    """Truncate text at sentence/paragraph boundary instead of mid-word.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        overlap: If True, include overlap content for next chunk
    
    Returns:
        Truncated text at clean boundary
    """
    if not text or len(text) <= max_length:
        return text
    
    # Find the last sentence boundary before max_length
    # Look for period, newline, or bullet point as natural boundaries
    truncated = text[:max_length]
    
    # Find last sentence end (. ! ? followed by space or newline)
    sentence_end = -1
    for pattern in ['. ', '.\n', '! ', '!\n', '? ', '?\n', '\n\n', '\n• ', '\n- ']:
        pos = truncated.rfind(pattern)
        if pos > sentence_end and pos > max_length * 0.7:  # At least 70% of content
            sentence_end = pos + len(pattern) - 1
    
    if sentence_end > 0:
        return text[:sentence_end + 1].strip()
    
    # Fallback: truncate at last space to avoid word breaks
    last_space = truncated.rfind(' ')
    if last_space > max_length * 0.8:  # At least 80% of content
        return text[:last_space].strip()
    
    # Final fallback: hard truncate
    return truncated.strip()


def _validate_chunk_quality(content: str, section: str) -> bool:
    """Validate that a chunk has sufficient content quality.
    
    Args:
        content: Chunk content
        section: Section name
    
    Returns:
        True if chunk meets quality threshold
    """
    if not content:
        return False
    
    # Remove the section header/prefix to check actual content
    lines = content.split('\n')
    content_lines = [l for l in lines if l.strip() and not l.strip().endswith(':')]
    
    actual_content = ' '.join(content_lines)
    
    # Check minimum length
    if len(actual_content) < MIN_CHUNK_LENGTH:
        logger.debug(f"Chunk '{section}' rejected: content too short ({len(actual_content)} chars)")
        return False
    
    return True

def _clean_pdf_artifacts(text: str) -> str:
    """Comprehensive cleaning of PDF extraction artifacts.
    
    Handles ALL known PDF artifact patterns:
    - "-Aditya- -Rao-" -> "Aditya Rao" (hyphens around words)
    - "-6- -years -o-f" -> "6 years of" (hyphens around chars/words)
    - "-U-X -Designer" -> "UX Designer" (partial hyphens)
    
    Preserves legitimate hyphens in words like "Mary-Jane", "year-over-year"
    """
    if not text:
        return ""
    
    cleaned = text
    
    # PASS 1: Remove hyphens wrapped completely around words/numbers: "-Word-" -> "Word"
    cleaned = re.sub(r'(?<![A-Za-z0-9])-([A-Za-z0-9]+)-(?![A-Za-z0-9])', r'\1', cleaned)
    
    # PASS 2: Remove leading hyphens at word boundaries: " -Word" -> " Word"
    cleaned = re.sub(r'(?<=\s)-([A-Za-z0-9])', r'\1', cleaned)
    cleaned = re.sub(r'^-([A-Za-z0-9])', r'\1', cleaned, flags=re.MULTILINE)
    
    # PASS 3: Remove trailing hyphens at word boundaries: "Word- " -> "Word "
    cleaned = re.sub(r'([A-Za-z0-9])-(?=\s|$|[,.\.)])', r'\1', cleaned)
    
    # PASS 4: Handle "-o-f" pattern (single chars with leading/trailing hyphens)
    cleaned = re.sub(r'(?<=\s)-([a-zA-Z0-9])-(?=\s)', r'\1', cleaned)
    
    # PASS 5: Clean up isolated hyphens
    cleaned = re.sub(r'\s+-\s+', ' ', cleaned)
    
    # PASS 6: Handle dashes between SINGLE characters only: "-U-X" -> "UX"
    def clean_dash_chars(match):
        word = match.group(0).strip('-')
        parts = word.split('-')
        if all(len(p.strip()) == 1 for p in parts if p.strip()):
            return ''.join(p for p in parts if p.strip())
        return match.group(0)
    cleaned = re.sub(r'-?([A-Za-z0-9]+)(?:-([A-Za-z0-9]+))+(-)?', clean_dash_chars, cleaned)
    
    # PASS 7: Remove trailing commas with hyphens: "word,- " -> "word, "
    cleaned = re.sub(r',-\s+', ', ', cleaned)
    
    # PASS 8: Clean remaining hyphens around punctuation
    cleaned = re.sub(r'-+([,.\)\(])', r'\1', cleaned)
    cleaned = re.sub(r'([,.\)\(])-+', r'\1', cleaned)
    
    # PASS 9: Clean patterns like "(2021-Present)" from "(2021---Present-)"
    cleaned = re.sub(r'\(-*(\d+)-*-+(\w+)-*\)', r'(\1-\2)', cleaned)
    
    # PASS 10: Clean multiple spaces
    cleaned = re.sub(r'\s{2,}', ' ', cleaned)
    
    # PASS 11: Clean multiple hyphens: "---" -> "-"
    cleaned = re.sub(r'-{2,}', '-', cleaned)
    
    return cleaned.strip()


def _clean_entity_name(name: str) -> str:
    """Clean hyphenated name artifacts from PDF extraction.
    
    Converts "-Aditya- -Rao-" to "Aditya Rao"
    Preserves legitimate hyphenated names like "Mary-Jane"
    """
    if not name or name == "Unknown":
        return "Unknown"
    
    # Use the comprehensive cleaner first
    cleaned = _clean_pdf_artifacts(name)
    
    # Handle "-K-A-R-A-N-" patterns (single chars with dashes)
    def clean_dash_chars(match):
        word = match.group(0).strip('-')
        parts = word.split('-')
        if all(len(p.strip()) == 1 for p in parts if p.strip()):
            return ''.join(p for p in parts if p.strip())
        return match.group(0)
    cleaned = re.sub(r'\b(-?[A-Za-z0-9](?:-[A-Za-z0-9]){2,}-?)\b', clean_dash_chars, cleaned)
    
    # Clean up extra spaces
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    return cleaned if cleaned else "Unknown"

class ResumeChunker:
    """Chunks resumes into semantic sections for optimal RAG retrieval."""
    
    def chunk_resume(self, parsed_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Chunk resume into semantic sections.
        
        Creates separate chunks for each major section to enable:
        - Section-specific queries (e.g., "What are Karan's skills?")
        - Full document retrieval (all chunks have same entity_id)
        - Semantic search (each chunk is independently searchable)
        
        Args:
            parsed_data: Parsed resume data
        
        Returns:
            List of chunks with metadata
        """
        chunks = []
        resume_id = parsed_data.get('id', 'unknown')
        raw_candidate_name = parsed_data.get('personal_info', {}).get('name', 'Unknown')
        # CRITICAL: Clean hyphenated name artifacts before storing in Milvus
        candidate_name = _clean_entity_name(raw_candidate_name)
        raw_text = parsed_data.get('raw_text', '')
        
        # Helper to add entity context to chunks for better RAG retrieval
        # When user asks "What are John's skills?", the chunk contains "John" for matching
        def add_context_prefix(content: str, section: str) -> str:
            if candidate_name and candidate_name != "Unknown":
                return f"[{candidate_name}'s {section}]\n{content}"
            return content
        
        # Helper to create validated chunk with smart truncation
        def create_chunk(content: str, section: str, section_label: str) -> dict:
            """Create a chunk with smart truncation and validation."""
            prefixed = add_context_prefix(content, section_label)
            truncated = _smart_truncate(prefixed, RESUME_CHUNK_SIZE)
            return {
                'entity_id': resume_id,
                'entity_name': candidate_name,
                'doc_type': 'resume',
                'section': section,
                'content': truncated,
            }
        
        # Chunk 1: Personal Info (Contact + Summary)
        personal_chunk = self._create_personal_chunk(parsed_data)
        if personal_chunk and _validate_chunk_quality(personal_chunk, 'Personal Info'):
            chunks.append(create_chunk(personal_chunk, 'Personal Info', "Contact Info"))
        
        # Chunk 2: Professional Summary (separate for better retrieval)
        summary_chunk = self._create_summary_chunk(parsed_data)
        if summary_chunk and _validate_chunk_quality(summary_chunk, 'Summary'):
            chunks.append(create_chunk(summary_chunk, 'Summary', "Professional Summary"))
        
        # Chunk 3: Skills (Technical, Tools, Soft Skills)
        skills_chunk = self._create_skills_chunk(parsed_data)
        if skills_chunk and _validate_chunk_quality(skills_chunk, 'Skills'):
            chunks.append(create_chunk(skills_chunk, 'Skills', "Skills"))
        
        # Chunk 4: Experience (Consolidated or per-position)
        experience_chunks = self._create_experience_chunks(parsed_data)
        if experience_chunks:
            # Add context to experience chunks with smart truncation
            for chunk in experience_chunks:
                prefixed = add_context_prefix(chunk['content'], "Work Experience")
                chunk['content'] = _smart_truncate(prefixed, RESUME_CHUNK_SIZE)
            chunks.extend(experience_chunks)
        else:
            # Fallback: Try to extract from raw_text if positions list is empty
            exp_from_text = self._extract_experience_from_text(raw_text, resume_id, candidate_name)
            if exp_from_text:
                prefixed = add_context_prefix(exp_from_text['content'], "Work Experience")
                exp_from_text['content'] = _smart_truncate(prefixed, RESUME_CHUNK_SIZE)
                chunks.append(exp_from_text)
        
        # Chunk 5: Education
        education_chunk = self._create_education_chunk(parsed_data)
        if education_chunk and _validate_chunk_quality(education_chunk, 'Education'):
            chunks.append(create_chunk(education_chunk, 'Education', "Education"))
        
        # Chunk 6: Projects
        projects_chunk = self._create_projects_chunk(parsed_data)
        if projects_chunk and _validate_chunk_quality(projects_chunk, 'Projects'):
            chunks.append(create_chunk(projects_chunk, 'Projects', "Projects"))
        
        # Chunk 7: Certifications (separate for better searchability)
        certifications_chunk = self._create_certifications_chunk(parsed_data)
        if certifications_chunk and _validate_chunk_quality(certifications_chunk, 'Certifications'):
            chunks.append(create_chunk(certifications_chunk, 'Certifications', "Certifications"))
        
        # Chunk 8: Languages (spoken languages for international roles)
        languages_chunk = self._create_languages_chunk(parsed_data)
        if languages_chunk and _validate_chunk_quality(languages_chunk, 'Languages'):
            chunks.append(create_chunk(languages_chunk, 'Languages', "Languages"))

        # Chunk 9+: Enterprise sections (awards, publications, volunteer, etc.)
        for section_name, chunk_content in self._create_enterprise_section_chunks(parsed_data):
            if chunk_content and _validate_chunk_quality(chunk_content, section_name):
                chunks.append(create_chunk(chunk_content, section_name, section_name))

        # Chunk N: Verbatim raw text coverage (guarantees nothing is lost for RAG/matching)
        chunks.extend(
            self._create_raw_coverage_chunks(raw_text, resume_id, candidate_name)
        )
        
        # Ensure at least one chunk exists (fallback to raw text)
        if not chunks and raw_text:
            chunks.append({
                'entity_id': resume_id,
                'entity_name': candidate_name,
                'doc_type': 'resume',
                'section': 'Full Resume',
                'content': _smart_truncate(_clean_pdf_artifacts(raw_text), RESUME_CHUNK_SIZE),
            })
        
        logger.info(f"Created {len(chunks)} resume chunks for {candidate_name}")
        return chunks
    
    def _create_personal_chunk(self, parsed_data: Dict[str, Any]) -> str:
        """Create personal info chunk (contact details only, no summary)."""
        parts = []
        personal = parsed_data.get('personal_info', {})
        
        if personal.get('name'):
            parts.append(f"Name: {personal['name']}")
        if personal.get('email'):
            parts.append(f"Email: {personal['email']}")
        if personal.get('phone'):
            parts.append(f"Phone: {personal['phone']}")
        if personal.get('location'):
            parts.append(f"Location: {personal['location']}")
        if personal.get('linkedin'):
            parts.append(f"LinkedIn: {personal['linkedin']}")
        if personal.get('github'):
            parts.append(f"GitHub: {personal['github']}")
        
        return "\n".join(parts)
    
    def _create_summary_chunk(self, parsed_data: Dict[str, Any]) -> str:
        """Create professional summary chunk (separate for better retrieval)."""
        summary = parsed_data.get('summary', '')
        if summary:
            return f"Professional Summary:\n{summary}"
        return ""
    
    def _create_skills_chunk(self, parsed_data: Dict[str, Any]) -> str:
        """Create skills chunk (technical, tools, soft skills - NO certifications)."""
        parts = []
        skills = parsed_data.get('skills', {})
        
        # Handle multiple possible key names for technical skills
        technical = (
            skills.get('technical_skills', []) or 
            skills.get('technical', []) or
            skills.get('all_skills', [])  # Fallback to all_skills
        )
        if technical:
            parts.append("Technical Skills:")
            if isinstance(technical, list):
                parts.append(", ".join(str(s) for s in technical))
            else:
                parts.append(str(technical))
        
        tools = skills.get('tools', []) or skills.get('frameworks', [])
        if tools:
            parts.append("\nTools & Frameworks:")
            if isinstance(tools, list):
                parts.append(", ".join(str(t) for t in tools))
            else:
                parts.append(str(tools))
        
        soft = skills.get('soft_skills', []) or skills.get('soft', [])
        if soft:
            parts.append("\nSoft Skills:")
            if isinstance(soft, list):
                parts.append(", ".join(str(s) for s in soft))
            else:
                parts.append(str(soft))
        
        # DO NOT include certifications here - they get their own chunk
        
        return "\n".join(parts)
    
    def _create_certifications_chunk(self, parsed_data: Dict[str, Any]) -> str:
        """Create certifications chunk (separate for searchability)."""
        parts = []
        
        # Check multiple possible locations for certifications
        skills = parsed_data.get('skills', {})
        certs = skills.get('certifications', [])
        
        # Also check root level
        root_certs = parsed_data.get('certifications', [])
        if root_certs:
            certs = list(set(certs + root_certs))
        
        if certs:
            parts.append("Certifications:")
            for cert in certs:
                parts.append(f"• {cert}")
        
        return "\n".join(parts)
    
    def _create_languages_chunk(self, parsed_data: Dict[str, Any]) -> str:
        """Create languages chunk (spoken languages for international/multilingual roles)."""
        parts = []
        languages = parsed_data.get('languages', [])
        if languages and isinstance(languages, list):
            parts.append("Languages:")
            for lang in languages:
                if isinstance(lang, dict):
                    name = lang.get('language') or lang.get('name') or ''
                    prof = lang.get('proficiency') or ''
                    if name:
                        parts.append(f"• {name} ({prof})" if prof else f"• {name}")
                elif lang:
                    parts.append(f"• {lang}")
        return "\n".join(parts)
    
    def _create_enterprise_section_chunks(self, parsed_data: Dict[str, Any]) -> List[tuple[str, str]]:
        """Build chunks for extended enterprise resume sections."""
        sections: List[tuple[str, str]] = []

        awards = parsed_data.get('awards') or []
        if awards:
            lines = ["Awards & Honors:"] + [f"• {a}" for a in awards if a]
            sections.append(("Awards", "\n".join(lines)))

        publications = parsed_data.get('publications') or []
        if publications:
            lines = ["Publications:"]
            for pub in publications:
                if isinstance(pub, dict):
                    title = pub.get('title') or pub.get('name') or ''
                    publisher = pub.get('publisher') or pub.get('publication') or ''
                    year = pub.get('year') or ''
                    if title:
                        lines.append(f"• {title} ({publisher}, {year})".rstrip(", )"))
                elif pub:
                    lines.append(f"• {pub}")
            sections.append(("Publications", "\n".join(lines)))

        volunteer = parsed_data.get('volunteer') or []
        if volunteer:
            lines = ["Volunteer Experience:"]
            for item in volunteer:
                if isinstance(item, dict):
                    org = item.get('organization') or item.get('company') or ''
                    role = item.get('role') or item.get('title') or ''
                    desc = item.get('description') or ''
                    lines.append(f"• {role} at {org}: {desc}".strip(" :"))
            sections.append(("Volunteer", "\n".join(lines)))

        trainings = parsed_data.get('trainings') or []
        if trainings:
            lines = ["Training & Courses:"]
            for item in trainings:
                if isinstance(item, dict):
                    lines.append(f"• {item.get('name', '')} ({item.get('provider', '')})")
                elif item:
                    lines.append(f"• {item}")
            sections.append(("Training", "\n".join(lines)))

        memberships = parsed_data.get('memberships') or []
        if memberships:
            lines = ["Professional Memberships:"] + [f"• {m}" for m in memberships if m]
            sections.append(("Memberships", "\n".join(lines)))

        military = parsed_data.get('military') or []
        if military:
            lines = ["Military Service:"]
            for item in military:
                if isinstance(item, dict):
                    lines.append(
                        f"• {item.get('rank', '')} — {item.get('branch', '')} ({item.get('dates', '')})"
                    )
            sections.append(("Military", "\n".join(lines)))

        patents = parsed_data.get('patents') or []
        if patents:
            lines = ["Patents:"]
            for item in patents:
                if isinstance(item, dict):
                    lines.append(f"• {item.get('title', '')} ({item.get('number', '')})")
            sections.append(("Patents", "\n".join(lines)))

        references = parsed_data.get('references') or []
        if references:
            lines = ["References:"] + [f"• {r}" for r in references if r]
            sections.append(("References", "\n".join(lines)))

        screening = parsed_data.get('screening') or {}
        if isinstance(screening, dict) and any(v for v in screening.values() if v):
            lines = ["HR Screening Notes:"]
            for key, val in screening.items():
                if val:
                    label = str(key).replace('_', ' ').title()
                    lines.append(f"• {label}: {val}")
            sections.append(("Screening", "\n".join(lines)))

        for custom in parsed_data.get('custom_sections') or []:
            if isinstance(custom, dict) and custom.get('content'):
                title = custom.get('title') or 'Additional Section'
                sections.append((str(title)[:128], f"{title}:\n{custom['content']}"))

        return sections

    def _create_raw_coverage_chunks(
        self, raw_text: str, resume_id: str, candidate_name: str
    ) -> List[Dict[str, Any]]:
        """Overlapping verbatim chunks so long/unusual sections remain searchable."""
        if not raw_text or len(raw_text.strip()) < 400:
            return []

        cleaned = _clean_pdf_artifacts(raw_text)
        chunk_size = max(RESUME_CHUNK_SIZE - 250, 800)
        overlap = CHUNK_OVERLAP_SIZE
        chunks: List[Dict[str, Any]] = []
        start = 0
        part = 0

        while start < len(cleaned):
            end = min(start + chunk_size, len(cleaned))
            piece = cleaned[start:end].strip()
            if len(piece) >= MIN_CHUNK_LENGTH:
                part += 1
                label = f"Full Resume (Part {part})"
                prefixed = (
                    f"[{candidate_name}'s {label}]\n{piece}"
                    if candidate_name and candidate_name != "Unknown"
                    else piece
                )
                chunks.append({
                    'entity_id': resume_id,
                    'entity_name': candidate_name,
                    'doc_type': 'resume',
                    'section': label,
                    'content': prefixed,
                })
            if end >= len(cleaned):
                break
            start = max(start + 1, end - overlap)

        return chunks
    
    def _create_experience_chunks(self, parsed_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create experience chunks - one consolidated chunk with all positions for better RAG."""
        chunks = []
        experience = parsed_data.get('experience', {})
        positions = experience.get('positions', [])
        companies = experience.get('companies', [])
        current_role = experience.get('current_role', '')
        total_years = experience.get('total_years', 0)
        resume_id = parsed_data.get('id', 'unknown')
        candidate_name = _clean_entity_name(parsed_data.get('personal_info', {}).get('name', 'Unknown'))
        
        # Build consolidated experience content
        exp_parts = []
        
        # Add summary info
        if total_years:
            exp_parts.append(f"Total Experience: {total_years} years")
        if current_role:
            exp_parts.append(f"Current Role: {current_role}")
        
        if positions and isinstance(positions, list) and len(positions) > 0:
            exp_parts.append("\nWork History:")
            
            # Check if positions are dicts (structured) or strings
            if isinstance(positions[0], dict):
                for idx, pos in enumerate(positions):
                    title = pos.get('title', 'N/A')
                    company = pos.get('company', 'N/A')
                    duration = pos.get('duration', '')
                    if not duration:
                        start = pos.get('start_date') or pos.get('start') or ''
                        end = pos.get('end_date') or pos.get('end') or ''
                        if start or end:
                            duration = f"{start} - {end}".strip(" -")
                    description = pos.get('description', '')
                    
                    entry = f"\n• {title}"
                    if company and company != 'N/A':
                        entry += f" at {company}"
                    if duration:
                        entry += f" ({duration})"
                    exp_parts.append(entry)
                    
                    if description:
                        exp_parts.append(f"  {description}")
            else:
                # Positions are strings (job titles)
                for i, pos in enumerate(positions):
                    company = companies[i] if i < len(companies) else ""
                    if company:
                        exp_parts.append(f"• {pos} at {company}")
                    else:
                        exp_parts.append(f"• {pos}")
        
        # Create single consolidated chunk
        if exp_parts:
            chunks.append({
                'entity_id': resume_id,
                'entity_name': candidate_name,
                'doc_type': 'resume',
                'section': 'Experience',
                'content': "\n".join(exp_parts)[:RESUME_CHUNK_SIZE],
            })
        
        return chunks
    
    def _extract_experience_from_text(self, raw_text: str, resume_id: str, candidate_name: str) -> Dict[str, Any]:
        """Extract experience section from raw text as fallback."""
        if not raw_text:
            return None
        
        # Try to find experience section in raw text
        exp_match = re.search(
            r'(?:PROFESSIONAL\s+)?EXPERIENCE\s*\n(.*?)(?=\n(?:AI\s+)?PROJECTS?|\nEDUCATION|\nCERTIFICATIONS?|\nSKILLS|\Z)',
            raw_text, re.IGNORECASE | re.DOTALL
        )
        
        if exp_match:
            exp_content = _clean_pdf_artifacts(exp_match.group(1).strip())
            if exp_content and len(exp_content) > 20:
                return {
                    'entity_id': resume_id,
                    'entity_name': candidate_name,
                    'doc_type': 'resume',
                    'section': 'Experience',
                    'content': f"Professional Experience:\n{exp_content}"[:RESUME_CHUNK_SIZE],
                }
        
        return None
    
    def _create_education_chunk(self, parsed_data: Dict[str, Any]) -> str:
        """Create education chunk with degrees and institutions."""
        parts = []
        education = parsed_data.get('education', {})
        
        degrees = education.get('degrees', [])
        institutions = education.get('universities', []) or education.get('institutions', [])
        graduation_years = education.get('graduation_years', [])
        gpa = education.get('gpa', '')
        
        parts.append("Education:")
        
        # Handle different list lengths gracefully
        max_items = max(len(degrees), len(institutions))
        for i in range(max_items):
            degree = degrees[i] if i < len(degrees) else ""
            institution = institutions[i] if i < len(institutions) else ""
            year = graduation_years[i] if i < len(graduation_years) else ""
            
            if degree and institution:
                entry = f"• {degree} - {institution}"
            elif degree:
                entry = f"• {degree}"
            elif institution:
                entry = f"• {institution}"
            else:
                continue
            
            if year:
                entry += f" ({year})"
            parts.append(entry)
        
        if gpa:
            parts.append(f"\nGPA: {gpa}")
        
        return "\n".join(parts) if len(parts) > 1 else ""
    
    def _create_projects_chunk(self, parsed_data: Dict[str, Any]) -> str:
        """Create projects chunk."""
        projects = parsed_data.get('projects', [])
        if projects and isinstance(projects, list):
            parts = ["Projects:"]
            for p in projects:
                if isinstance(p, dict):
                    name = p.get('name') or 'Project'
                    desc = p.get('description') or ''
                    techs = p.get('technologies') or []
                    line = f"• {name}"
                    if desc:
                        line += f": {desc}"
                    if techs:
                        line += f" [Tech: {', '.join(str(t) for t in techs)}]"
                    parts.append(line)
                else:
                    parts.append(f"• {p}")
            return "\n".join(parts)
        return ""

# Maps enterprise preview section IDs (HITL UI) to chunk labels and data accessors.
_JD_ENTERPRISE_SECTIONS: list[tuple[str, str, str]] = [
    ("job_title", "Job Title", "job_title"),
    ("department_team", "Department", "department"),
    ("location_work_model", "Location", "location"),
    ("about_company", "About Company", "about_company"),
    ("position_summary", "Position Summary", "position_summary"),
    ("responsibilities", "Responsibilities", "responsibilities"),
    ("required_qualifications", "Required Qualifications", "required_qualifications"),
    ("preferred_qualifications", "Preferred Qualifications", "preferred_qualifications"),
    ("soft_skills", "Soft Skills", "soft_skills"),
    ("tools_technologies", "Tools & Technologies", "tools_technologies"),
    ("success_metrics", "Success Metrics", "success_metrics"),
    ("work_environment", "Work Environment", "work_environment"),
    ("compensation_benefits", "Compensation & Benefits", "compensation_benefits"),
    ("equal_opportunity_statement", "Equal Opportunity", "equal_opportunity_statement"),
    ("application_instructions", "Application Instructions", "application_instructions"),
]


CUSTOM_JD_SECTION_PREFIX = "Custom: "


def _is_hr_grade_code(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Z]{1,3}\d{1,3}", (value or "").strip()))


def format_jd_department_team(jd_data: Dict[str, Any]) -> str:
    """Format department, team, division, and BU for indexing and display."""
    department = str(jd_data.get("department") or "").strip()
    team = str(jd_data.get("team") or "").strip()
    division = str(jd_data.get("division") or "").strip()
    business_unit = str(jd_data.get("business_unit") or "").strip()
    metadata = jd_data.get("metadata") or {}
    if isinstance(metadata, dict) and not business_unit:
        business_unit = str(metadata.get("business_unit") or "").strip()

    if _is_hr_grade_code(department):
        parts = [f"Grade/Band: {department}"]
        if business_unit or division:
            parts.append(f"Business Unit: {business_unit or division}")
        return "\n".join(parts)

    parts = [part for part in (department, team, division or business_unit) if part]
    return " / ".join(parts)


def format_jd_job_title_block(jd_data: Dict[str, Any]) -> str:
    """Include title, level, and internal title in the indexed job title chunk."""
    title = str(jd_data.get("job_title") or jd_data.get("title") or "").strip()
    metadata = jd_data.get("metadata") or {}
    level = ""
    internal_title = ""
    if isinstance(metadata, dict):
        level = str(metadata.get("job_level") or "").strip()
        internal_title = str(metadata.get("internal_title") or "").strip()

    lines = [title] if title else []
    if level and level.lower() not in title.lower():
        lines.append(f"Level: {level}")
    if internal_title and internal_title != title:
        lines.append(f"Internal Title: {internal_title}")
    return "\n".join(lines)


def _validate_jd_chunk_quality(content: str, section: str) -> bool:
    """JD sections may be shorter than resume chunks but must contain real text."""
    if not content:
        return False

    lines = content.split("\n")
    content_lines = [line for line in lines if line.strip() and not line.strip().endswith(":")]
    actual_content = " ".join(content_lines).strip()
    min_length = 8 if section in {"Job Title", "Department", "Location"} else 20
    if len(actual_content) < min_length:
        logger.debug(
            "JD chunk '%s' rejected: content too short (%s chars)",
            section,
            len(actual_content),
        )
        return False
    return True


def jd_removed_section_ids(jd_data: Dict[str, Any]) -> set[str]:
    """Return section IDs removed via human-in-the-loop customization."""
    metadata = jd_data.get("metadata") or {}
    if not isinstance(metadata, dict):
        return set()
    return {str(section_id) for section_id in (metadata.get("removed_sections") or []) if section_id}


class JDChunker:
    """Chunks job descriptions into semantic sections."""
    
    def chunk_jd(self, jd_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Chunk JD into semantic sections.
        
        Args:
            jd_data: JD data
        
        Returns:
            List of chunks with metadata
        """
        chunks = []
        jd_id = jd_data.get('id', 'unknown')
        jd_title = jd_data.get('job_title', 'Unknown')
        removed = jd_removed_section_ids(jd_data)
        
        # Helper to add entity context for better matching
        def add_jd_context(content: str, section: str) -> str:
            if jd_title and jd_title != "Unknown":
                return f"[{jd_title} - {section}]\n{content}"
            return content
        
        for section_id, section_name, field_name in _JD_ENTERPRISE_SECTIONS:
            if section_id in removed:
                continue
            if section_id == "job_title":
                section_data = format_jd_job_title_block(jd_data)
            elif section_id == "department_team":
                section_data = format_jd_department_team(jd_data)
            else:
                section_data = jd_data.get(field_name)
            if section_data:
                content = self._format_section(section_data)
                if content and _validate_jd_chunk_quality(content, section_name):
                    prefixed = add_jd_context(content, section_name)
                    chunks.append({
                        'entity_id': jd_id,
                        'entity_name': jd_title,
                        'doc_type': 'jd',
                        'section': section_name,
                        'content': _smart_truncate(prefixed, JD_CHUNK_SIZE),
                    })

        for custom in jd_data.get("custom_sections") or []:
            if not isinstance(custom, dict):
                continue
            title = str(custom.get("title") or "Custom Section").strip()
            content_body = str(custom.get("content") or "").strip()
            if not title and not content_body:
                continue
            section_label = title[:128] or "Custom Section"
            content = f"{section_label}:\n{content_body}" if content_body else section_label
            if _validate_jd_chunk_quality(content, section_label):
                prefixed = add_jd_context(content, section_label)
                chunks.append({
                    'entity_id': jd_id,
                    'entity_name': jd_title,
                    'doc_type': 'jd',
                    'section': f"{CUSTOM_JD_SECTION_PREFIX}{section_label}",
                    'content': _smart_truncate(prefixed, JD_CHUNK_SIZE),
                })
        
        logger.info(
            "Created %s JD chunks for %s (removed_sections=%s, custom_sections=%s)",
            len(chunks),
            jd_title,
            sorted(removed),
            len(jd_data.get("custom_sections") or []),
        )
        return chunks
    
    def _format_section(self, data: Any, indent: int = 0) -> str:
        """
        Format section data as human-readable text.
        Properly handles nested dicts, lists, and special structures.
        
        Args:
            data: Section data (can be str, list, dict, or nested)
            indent: Indentation level for nested items
            
        Returns:
            Formatted string representation
        """
        indent_str = "  " * indent
        
        if data is None:
            return ""
        
        if isinstance(data, str):
            return data
        
        if isinstance(data, list):
            formatted_items = []
            for item in data:
                if isinstance(item, dict):
                    # Nested dict in list - format recursively
                    formatted_items.append(f"{indent_str}• {self._format_section(item, indent + 1)}")
                else:
                    formatted_items.append(f"{indent_str}• {item}")
            return "\n".join(formatted_items)
        
        if isinstance(data, dict):
            parts = []
            for key, value in data.items():
                # Format key nicely (snake_case to Title Case)
                nice_key = str(key).replace('_', ' ').title()
                
                if isinstance(value, list):
                    if all(isinstance(v, str) for v in value):
                        # Simple string list - join with commas
                        value_str = ", ".join(value)
                        parts.append(f"{indent_str}**{nice_key}:** {value_str}")
                    else:
                        # Complex list - format recursively
                        list_str = self._format_section(value, indent + 1)
                        parts.append(f"{indent_str}**{nice_key}:**\n{list_str}")
                elif isinstance(value, dict):
                    # Nested dict - format recursively
                    nested_str = self._format_section(value, indent + 1)
                    parts.append(f"{indent_str}**{nice_key}:**\n{nested_str}")
                elif value is not None:
                    parts.append(f"{indent_str}**{nice_key}:** {value}")
            return "\n".join(parts)
        
        # Fallback for other types
        return str(data)
