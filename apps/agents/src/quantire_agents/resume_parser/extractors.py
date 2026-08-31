"""
Local extraction utilities for the QuantHire resume parsing agent.

These helpers provide deterministic, offline extraction so that the
autonomous agent always has a reliable baseline before invoking tools,
LLMs, or RAG enrichment.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from quantire_agents.config.constants import (
    RegexPattern,
    TECHNICAL_SKILLS,
    SOFT_SKILLS_KEYWORDS,
    TOOLS_KEYWORDS,
)
from quantire_agents.config.logging_config import AgentLogger


logger = AgentLogger.get_logger(__name__)


@dataclass(frozen=True)
class _ExtractionDefaults:
    personal_info: Dict[str, str] = None  # type: ignore[assignment]
    skills: Dict[str, List[str]] = None  # type: ignore[assignment]
    experience: Dict[str, Any] = None  # type: ignore[assignment]
    education: Dict[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "personal_info",
            {
                "name": "Unknown",
                "email": "",
                "phone": "",
                "location": "",
                "linkedin": "",
                "github": "",
                "website": "",
            },
        )
        object.__setattr__(
            self,
            "skills",
            {
                "technical_skills": [],
                "soft_skills": [],
                "tools": [],
                "certifications": [],
            },
        )
        object.__setattr__(
            self,
            "experience",
            {
                "total_years": 0,
                "positions": [],
                "companies": [],
                "current_role": "",
                "highlights": [],
            },
        )
        object.__setattr__(
            self,
            "education",
            {
                "degrees": [],
                "institutions": [],
                "graduation_years": [],
                "gpa": "",
            },
        )


DEFAULTS = _ExtractionDefaults()


class LocalExtractor:
    """Deterministic regex and keyword based extraction helpers."""

    @staticmethod
    def extract_personal_info(text: str) -> Dict[str, str]:
        """Extract the candidate's basic contact details."""
        try:
            lines: List[str] = [line.strip() for line in text.splitlines() if line.strip()]
            
            # Smart name extraction: look for name patterns, not just first line
            name = DEFAULTS.personal_info["name"]
            
            # Comprehensive name extraction strategies (in order of reliability)
            
            # Strategy 1: Look for explicit "Name:" label pattern (most reliable)
            name_label_patterns = [
                re.compile(r'^name\s*:?\s*(.+)$', re.IGNORECASE),
                re.compile(r'^full\s+name\s*:?\s*(.+)$', re.IGNORECASE),
                re.compile(r'^candidate\s+name\s*:?\s*(.+)$', re.IGNORECASE),
            ]
            for pattern in name_label_patterns:
                for line in lines[:15]:
                    match = pattern.match(line)
                    if match:
                        candidate_name = match.group(1).strip()
                        # Clean up common prefixes/suffixes
                        candidate_name = re.sub(r'^(mr|mrs|ms|dr)\.?\s+', '', candidate_name, flags=re.IGNORECASE).strip()
                        # Validate it looks like a name (1-5 words, mostly capitalized)
                        words = candidate_name.split()
                        if 1 <= len(words) <= 5:
                            # Check if most words start with capital
                            capitalized_count = sum(1 for w in words if w and w[0].isupper())
                            if capitalized_count >= len(words) * 0.7:  # At least 70% capitalized
                                name = candidate_name
                                break
                if name != DEFAULTS.personal_info["name"]:
                    break
            
            # Strategy 2: Look for name-like patterns in first few lines
            # A name typically: 1-5 words, mostly capitalized, no special chars except hyphens/apostrophes
            if name == DEFAULTS.personal_info["name"]:
                # More flexible name pattern
                name_pattern = re.compile(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,4}(?:[\s\-][A-Z][a-z]+)?$')
                
                # Common section headers to skip (expanded list)
                header_keywords = [
                    'ui', 'ux', 'summary', 'professional summary', 'executive summary', 'objective', 
                    'profile', 'experience', 'work experience', 'employment', 'education', 
                    'academic', 'skills', 'technical skills', 'core competencies', 'contact', 
                    'contact information', 'phone', 'email', 'projects', 'certifications', 
                    'certificate', 'awards', 'publications', 'references', 'resume', 'cv',
                    'curriculum vitae', 'portfolio', 'linkedin', 'github'
                ]
                
                # Check first 15 lines for a name pattern
                for i, line in enumerate(lines[:15]):
                    line_lower = line.lower().strip()
                    
                    # Skip common section headers
                    if any(keyword in line_lower for keyword in header_keywords):
                        continue
                    
                    # Skip lines that are too short or too long
                    if len(line) < 2 or len(line) > 60:
                        continue
                    
                    # Skip lines with email/phone patterns (those are contact info, not names)
                    if '@' in line or re.search(r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}', line):
                        continue
                    
                    # Skip lines with "–" or "-" that look like filenames or job titles
                    if ('–' in line or ' - ' in line) and ('resume' in line_lower or 'cv' in line_lower):
                        continue
                    
                    # Skip lines that look like job titles (common patterns)
                    if re.search(r'\b(engineer|developer|scientist|manager|director|analyst|designer|architect)\b', line_lower):
                        # But allow if it's clearly a name (e.g., "John Engineer" - rare but possible)
                        if not name_pattern.match(line):
                            continue
                    
                    # Check if line matches name pattern
                    if name_pattern.match(line):
                        name = line
                        break
            
            # Strategy 3: If no pattern match, use first substantial non-header line
            if name == DEFAULTS.personal_info["name"]:
                header_keywords = [
                    'ui', 'ux', 'summary', 'professional summary', 'executive summary', 'objective', 
                    'profile', 'experience', 'education', 'skills', 'contact', 'phone', 'email',
                    'projects', 'certifications', 'resume', 'cv', 'linkedin', 'github'
                ]
                for line in lines[:8]:
                    line_lower = line.lower().strip()
                    # Skip section headers, emails, phones, and filename patterns
                    if (not any(keyword in line_lower for keyword in header_keywords) and
                        len(line) >= 2 and len(line) <= 60 and
                        '@' not in line and 
                        not re.search(r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}', line) and
                        '–' not in line and 
                        (' - ' not in line or 'resume' not in line_lower) and
                        not re.search(r'^https?://', line, re.IGNORECASE)):
                        # Prefer lines that look like names (have capital letters)
                        if any(c.isupper() for c in line):
                            name = line
                            break

            email = LocalExtractor._safe_search(RegexPattern.EMAIL, text)
            phone = LocalExtractor._safe_search(RegexPattern.PHONE, text)
            location = LocalExtractor._safe_search(RegexPattern.LOCATION, text)
            linkedin = LocalExtractor._safe_search(RegexPattern.LINKEDIN, text, flags=re.IGNORECASE)
            github = LocalExtractor._safe_search(RegexPattern.GITHUB, text, flags=re.IGNORECASE)

            website_match = re.search(r"(https?://[^\s]+)", text, flags=re.IGNORECASE)
            website = website_match.group(1) if website_match else ""

            # Clean up name: Remove dashes between single characters (PDF extraction artifact)
            # Pattern: "-K-A-R-A-N-" -> "KARAN"
            if name and '-' in name:
                # Check if it's the dash-between-chars pattern
                name_parts = name.split()
                cleaned_parts = []
                for part in name_parts:
                    # If part looks like "-K-A-R-A-N-", clean it
                    if part.startswith('-') and part.endswith('-') and len(part) > 2:
                        # Remove leading and trailing dashes, then remove dashes between single chars
                        cleaned = part.strip('-')
                        # If pattern is like "K-A-R-A-N", join without dashes
                        if '-' in cleaned and all(len(c) == 1 for c in cleaned.split('-')):
                            cleaned = cleaned.replace('-', '')
                        cleaned_parts.append(cleaned)
                    else:
                        cleaned_parts.append(part)
                name = ' '.join(cleaned_parts)
            
            return {
                "name": name,
                "email": email,
                "phone": phone,
                "location": location,
                "linkedin": linkedin,
                "github": github,
                "website": website,
            }
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error extracting personal info: %s", exc, exc_info=True)
            return DEFAULTS.personal_info.copy()

    @staticmethod
    def extract_skills(text: str) -> Dict[str, List[str]]:
        """Collect technical skills, soft skills, tools, and certifications."""
        try:
            lower_text = text.lower()
            technical = LocalExtractor._match_keywords(TECHNICAL_SKILLS, lower_text)
            soft_skills = LocalExtractor._match_keywords(SOFT_SKILLS_KEYWORDS, lower_text)
            tools = LocalExtractor._match_keywords(TOOLS_KEYWORDS, lower_text)

            certifications = LocalExtractor._find_all(RegexPattern.CERTIFICATION, text, flags=re.IGNORECASE)
            
            # Extract skills from various formats in Skills section
            # Handle multiple section name variations
            skills_section_patterns = [
                re.compile(r'(?:technical\s+)?skills?\s*:?\s*(.*?)(?=experience|work|education|projects|certifications|awards|references|$)', re.IGNORECASE | re.DOTALL),
                re.compile(r'core\s+competencies?\s*:?\s*(.*?)(?=experience|work|education|projects|certifications|$)', re.IGNORECASE | re.DOTALL),
                re.compile(r'technologies?\s*:?\s*(.*?)(?=experience|work|education|projects|certifications|$)', re.IGNORECASE | re.DOTALL),
            ]
            
            extracted_skills_set = set()  # Track extracted skills to avoid duplicates
            
            for pattern in skills_section_patterns:
                skills_match = pattern.search(text)
                if skills_match:
                    skills_section = skills_match.group(1)
                    
                    # Extract items with bullet points, dashes, or numbers
                    # More precise pattern: bullet/dash/number followed by skill name
                    bullet_items = re.findall(r'[•\-\*\d+\.]\s*([A-Z][^\n•\-\*\d]+?)(?=\n|$|[•\-\*\d])', skills_section)
                    
                    # Also handle comma-separated lists (but only in skills section)
                    comma_items = re.findall(r'\b([A-Z][A-Za-z\s&]{2,30}?)\b(?=,|$)', skills_section)
                    
                    # Combine both extraction methods
                    all_items = bullet_items + comma_items
                    
                    for item in all_items:
                        skill = item.strip()
                        
                        # Skip invalid entries
                        if not skill or len(skill) < 2:
                            continue
                        
                        # Skip if it's a common word or phrase (not a skill)
                        common_words = ['skills', 'skill', 'ed in', 'in designing', 'and', 'the', 'a', 'an', 
                                       'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
                                       'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might']
                        if skill.lower() in common_words or any(word in skill.lower() for word in ['ed in', 'ing ', ' the ', ' a ', ' an ']):
                            continue
                        
                        # Skip if it looks like a sentence fragment (contains common verbs/articles)
                        if re.search(r'\b(ed|ing|the|a|an|is|are|was|were|be|been|being|have|has|had|do|does|did)\b', skill.lower()):
                            # But allow if it's a known technical term
                            if not any(tech.lower() in skill.lower() for tech in TECHNICAL_SKILLS):
                                continue
                        
                        # Clean up common prefixes/suffixes
                        skill = re.sub(r'^(proficient\s+in|experienced\s+with|knowledge\s+of|expertise\s+in|skilled\s+in)\s+', '', skill, flags=re.IGNORECASE).strip()
                        skill = re.sub(r'\s+(years?|yrs?)$', '', skill, flags=re.IGNORECASE).strip()
                        skill = re.sub(r'^(and|or|&)\s+', '', skill, flags=re.IGNORECASE).strip()
                        skill = re.sub(r'\s+(and|or|&)$', '', skill, flags=re.IGNORECASE).strip()
                        
                        # Final validation: skill should be 2-50 chars, mostly letters/spaces/hyphens
                        if (2 <= len(skill) <= 50 and 
                            re.match(r'^[A-Za-z][A-Za-z\s\-&]+$', skill) and
                            skill.lower() not in extracted_skills_set):
                            technical.append(skill)
                            extracted_skills_set.add(skill.lower())
            
            # Extract certifications from Certifications section (various formats)
            cert_section_patterns = [
                re.compile(r'certifications?\s*:?\s*(.*?)(?=projects|education|experience|skills|awards|references|$)', re.IGNORECASE | re.DOTALL),
                re.compile(r'professional\s+certifications?\s*:?\s*(.*?)(?=projects|education|experience|skills|$)', re.IGNORECASE | re.DOTALL),
                re.compile(r'licenses?\s*:?\s*(.*?)(?=projects|education|experience|skills|$)', re.IGNORECASE | re.DOTALL),
            ]
            
            for pattern in cert_section_patterns:
                cert_match = pattern.search(text)
                if cert_match:
                    cert_section = cert_match.group(1)
                    cert_items = re.findall(r'[•\-\*\d+\.]\s*([^\n•\-\*]+)', cert_section, re.IGNORECASE)
                    for item in cert_items:
                        cert = item.strip()
                        if cert and len(cert) > 2 and cert.lower() not in [c.lower() for c in certifications]:
                            certifications.append(cert)
            
            # Also extract skills mentioned in job descriptions and projects (but be careful)
            # Only extract if they're mentioned as standalone terms, not as part of sentences
            experience_section = re.search(r'(?:experience|work\s+history|employment)\s*:?\s*(.*?)(?=education|skills|certifications|projects|$)', text, re.IGNORECASE | re.DOTALL)
            if experience_section:
                exp_text = experience_section.group(1)
                # Look for technical skills mentioned as standalone terms or in lists
                for tech_skill in TECHNICAL_SKILLS:
                    # Check if skill appears as a standalone word (not part of another word)
                    pattern = r'\b' + re.escape(tech_skill) + r'\b'
                    if re.search(pattern, exp_text, re.IGNORECASE):
                        if tech_skill.lower() not in extracted_skills_set:
                            technical.append(tech_skill)
                            extracted_skills_set.add(tech_skill.lower())

            return {
                "technical_skills": technical,
                "soft_skills": soft_skills,
                "tools": tools,
                "certifications": certifications,
            }
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error extracting skills: %s", exc, exc_info=True)
            return DEFAULTS.skills.copy()

    @staticmethod
    def extract_experience(text: str) -> Dict[str, Any]:
        """Extract high-level experience data."""
        try:
            total_years = 0
            
            # Strategy 1: Look for explicit years of experience patterns
            years_match = re.search(RegexPattern.YEARS_EXPERIENCE, text, flags=re.IGNORECASE)
            if years_match:
                try:
                    total_years = int(years_match.group(1))
                except ValueError:
                    total_years = DEFAULTS.experience["total_years"]
            
            # Strategy 2: If no explicit years found, try to calculate from job dates
            if total_years == 0:
                # Look for date patterns in experience section
                experience_section = re.search(r'(?:(?:professional\s+)?experience|work\s+history|employment)\s*:?\s*(.*?)(?=education|skills|certifications|projects|ai\s+projects|$)', text, re.IGNORECASE | re.DOTALL)
                if experience_section:
                    exp_text = experience_section.group(1)
                    
                    # Month abbreviations mapping
                    month_map = {
                        'jan': 1, 'january': 1, 'feb': 2, 'february': 2, 'mar': 3, 'march': 3,
                        'apr': 4, 'april': 4, 'may': 5, 'jun': 6, 'june': 6,
                        'jul': 7, 'july': 7, 'aug': 8, 'august': 8, 'sep': 9, 'september': 9,
                        'oct': 10, 'october': 10, 'nov': 11, 'november': 11, 'dec': 12, 'december': 12
                    }
                    
                    # Find date ranges with various formats:
                    # "Jan 2022 – Present", "2022 - 2024", "Jan 2022 - Present", etc.
                    date_patterns = [
                        # Format: "Month YYYY – Present" or "Month YYYY - Present"
                        r'(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|september|oct|october|nov|november|dec|december)\s+((?:19|20)\d{2})\s*[–\-]\s*(present|current|now)',
                        # Format: "Month YYYY – Month YYYY"
                        r'(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|september|oct|october|nov|november|dec|december)\s+((?:19|20)\d{2})\s*[–\-]\s*(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|september|oct|october|nov|november|dec|december)\s+((?:19|20)\d{2})',
                        # Format: "YYYY – Present" or "YYYY - Present"
                        r'\b((?:19|20)\d{2})\s*[–\-]\s*(present|current|now)\b',
                        # Format: "YYYY – YYYY" or "YYYY - YYYY"
                        r'\b((?:19|20)\d{2})\s*[–\-]\s*((?:19|20)\d{2})\b',
                    ]
                    
                    from datetime import datetime
                    current_year = datetime.now().year
                    current_month = datetime.now().month
                    found_years = []
                    
                    for pattern in date_patterns:
                        matches = re.finditer(pattern, exp_text, re.IGNORECASE)
                        for match in matches:
                            groups = match.groups()
                            
                            if len(groups) == 2:
                                # Format: "YYYY – Present" or "YYYY - YYYY"
                                start_year = int(groups[0])
                                end_str = groups[1].lower()
                                
                                if end_str in ['present', 'current', 'now']:
                                    # Calculate to current date
                                    found_years.append(start_year)
                                    # Estimate end year as current year
                                    end_year = current_year
                                else:
                                    # Two years provided
                                    end_year = int(end_str)
                                    found_years.extend([start_year, end_year])
                                    
                            elif len(groups) == 3:
                                # Format: "Month YYYY – Present"
                                month_str = groups[0].lower()
                                start_year = int(groups[1])
                                end_str = groups[2].lower()
                                
                                if end_str in ['present', 'current', 'now']:
                                    found_years.append(start_year)
                                    # Calculate to current date (more accurate)
                                    if month_str in month_map:
                                        start_month = month_map[month_str]
                                        # If start month hasn't passed this year, use last year
                                        if start_month > current_month:
                                            end_year = current_year - 1
                                        else:
                                            end_year = current_year
                                    else:
                                        end_year = current_year
                                        
                            elif len(groups) == 4:
                                # Format: "Month YYYY – Month YYYY"
                                start_month_str = groups[0].lower()
                                start_year = int(groups[1])
                                end_month_str = groups[2].lower()
                                end_year = int(groups[3])
                                
                                found_years.extend([start_year, end_year])
                    
                    # Also find standalone years (YYYY format)
                    standalone_years = re.findall(r'\b((?:19|20)\d{2})\b', exp_text)
                    found_years.extend([int(y) for y in standalone_years])
                    
                    if found_years:
                        years_int = sorted(set(found_years))
                        if len(years_int) >= 2:
                            # Calculate difference between earliest and latest year
                            years_range = max(years_int) - min(years_int)
                            # If "present" is mentioned, use current year
                            if re.search(r'\b(present|current|now)\b', exp_text, re.IGNORECASE):
                                if max(years_int) < current_year:
                                    years_range = current_year - min(years_int)
                            total_years = max(1, years_range)  # At least 1 year if dates found
                        elif len(years_int) == 1:
                            # Only one year found - if it's in the past, estimate experience
                            if years_int[0] < current_year:
                                # Estimate based on how old the year is
                                years_range = current_year - years_int[0]
                                if years_range > 0:
                                    total_years = max(1, min(years_range, 30))  # Cap at 30 years
                    
                    # Also check for phrases like "X+ years", "over X years", etc.
                    if total_years == 0:
                        years_phrases = re.findall(r'(?:over|more\s+than|at\s+least|minimum\s+of|about|approximately)\s+(\d+)\s+years?', exp_text, re.IGNORECASE)
                        if years_phrases:
                            total_years = max([int(y) for y in years_phrases])
            
            # Strategy 3: If still 0, check if experience section mentions "led", "built", "designed" (suggests experience)
            if total_years == 0:
                experience_section = re.search(r'(?:(?:professional\s+)?experience|work\s+history|employment)\s*:?\s*(.*?)(?=education|skills|certifications|projects|ai\s+projects|$)', text, re.IGNORECASE | re.DOTALL)
                if experience_section:
                    exp_text = experience_section.group(1).lower()
                    # If it mentions multiple projects/roles, estimate at least 2-3 years
                    if any(word in exp_text for word in ['led', 'built', 'designed', 'architected', 'managed', 'developed']):
                        # Count mentions of projects/roles
                        project_indicators = ['project', 'system', 'infrastructure', 'migration', 'architecture']
                        count = sum(1 for indicator in project_indicators if indicator in exp_text)
                        if count >= 2:
                            total_years = 2  # Minimum estimate for multiple projects
            
            # Strategy 4: If still 0, search entire text for date patterns (fallback)
            if total_years == 0:
                # Search entire text for "Jan 2022 – Present" or similar patterns
                from datetime import datetime
                current_year = datetime.now().year
                
                # Look for "Month YYYY – Present" pattern anywhere in text
                present_pattern = r'(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|september|oct|october|nov|november|dec|december)\s+((?:19|20)\d{2})\s*[–\-]\s*(present|current|now)'
                present_matches = re.finditer(present_pattern, text, re.IGNORECASE)
                for match in present_matches:
                    start_year = int(match.group(2))
                    years_range = current_year - start_year
                    if years_range > 0:
                        total_years = max(1, years_range)
                        break
                
                # If still 0, look for any year patterns and estimate
                if total_years == 0:
                    all_years = re.findall(r'\b((?:19|20)\d{2})\b', text)
                    if all_years:
                        years_int = sorted([int(y) for y in set(all_years)])
                        # Filter out graduation years (usually in education section)
                        # Keep only years that might be work experience (recent years)
                        recent_years = [y for y in years_int if y >= 2000 and y <= current_year]
                        if recent_years:
                            earliest = min(recent_years)
                            if earliest < current_year:
                                total_years = max(1, current_year - earliest)

            positions, companies = LocalExtractor._extract_roles_and_companies(text)
            current_role = positions[0] if positions else ""

            highlights = LocalExtractor._extract_highlights(text)

            return {
                "total_years": total_years,
                "positions": positions,
                "companies": companies,
                "current_role": current_role,
                "highlights": highlights,
            }
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error extracting experience: %s", exc, exc_info=True)
            return DEFAULTS.experience.copy()

    @staticmethod
    def extract_education(text: str) -> Dict[str, Any]:
        """Extract education history from the resume text."""
        try:
            degrees: List[str] = []
            institutions: List[str] = []
            graduation_years: List[str] = []

            degree_patterns = [
                r"(Bachelor(?:'s)?\s+of\s+[A-Za-z&\s]+)",
                r"(Master(?:'s)?\s+of\s+[A-Za-z&\s]+)",
                r"(MBA)",
                r"(Ph\.?D\.?)",
                r"(B\.Sc\.|M\.Sc\.|B\.Eng\.|M\.Eng\.)",
            ]

            for pattern in degree_patterns:
                degrees.extend(LocalExtractor._find_all(pattern, text, flags=re.IGNORECASE))

            institution_pattern = r"([A-Z][A-Za-z&\s]+ (University|College|Institute|School))"
            institutions = LocalExtractor._find_all(institution_pattern, text)
            institutions = [match.strip() for match in institutions]

            graduation_years = LocalExtractor._find_all(r"(?:20|19)\d{2}", text)

            gpa_match = re.search(RegexPattern.GPA, text, flags=re.IGNORECASE)
            gpa = gpa_match.group(1) if gpa_match else ""

            return {
                "degrees": LocalExtractor._dedupe_preserve_order(degrees),
                "institutions": LocalExtractor._dedupe_preserve_order(institutions),
                "graduation_years": LocalExtractor._dedupe_preserve_order(graduation_years),
                "gpa": gpa,
            }
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error extracting education: %s", exc, exc_info=True)
            return DEFAULTS.education.copy()

    @staticmethod
    def extract_all(text: str) -> Dict[str, Any]:
        """Convenience helper to run all local extractions at once."""
        return {
            "personal_info": LocalExtractor.extract_personal_info(text),
            "skills": LocalExtractor.extract_skills(text),
            "experience": LocalExtractor.extract_experience(text),
            "education": LocalExtractor.extract_education(text),
        }

    # --------------------------------------------------------------------- #
    # Helper utilities
    # --------------------------------------------------------------------- #

    @staticmethod
    def _safe_search(pattern: str, text: str, flags: int = 0) -> str:
        match = re.search(pattern, text, flags)
        if not match:
            return ""
        # Prefer the first non-empty capturing group if available
        if match.groups():
            for group in match.groups():
                if group:
                    return group.strip()
        return match.group().strip()

    @staticmethod
    def _match_keywords(keywords: Sequence[str], lower_text: str) -> List[str]:
        found: List[str] = []
        for keyword in keywords:
            if keyword.lower() in lower_text:
                found.append(keyword)
        return LocalExtractor._dedupe_preserve_order(found)

    @staticmethod
    def _find_all(pattern: str, text: str, flags: int = 0) -> List[str]:
        matches = re.findall(pattern, text, flags)
        if not matches:
            return []
        flat_matches: List[str] = []
        for match in matches:
            if isinstance(match, str):
                flat_matches.append(match.strip())
            else:
                flat_matches.append(" ".join(str(part).strip() for part in match if part))
        return LocalExtractor._dedupe_preserve_order(flat_matches)

    @staticmethod
    def _extract_roles_and_companies(text: str) -> Tuple[List[str], List[str]]:
        positions: List[str] = []
        companies: List[str] = []

        role_keywords = [
            "engineer",
            "developer",
            "scientist",
            "manager",
            "consultant",
            "analyst",
            "architect",
            "lead",
            "specialist",
            "director",
        ]

        company_keywords = [
            "inc",
            "llc",
            "corp",
            "corporation",
            "company",
            "technologies",
            "solutions",
            "labs",
            "systems",
        ]

        for line in text.splitlines():
            clean = line.strip()
            if not clean:
                continue

            lower_line = clean.lower()
            if any(keyword in lower_line for keyword in role_keywords):
                positions.append(clean)

            if any(keyword in lower_line for keyword in company_keywords):
                companies.append(clean)

        return (
            LocalExtractor._dedupe_preserve_order(positions),
            LocalExtractor._dedupe_preserve_order(companies),
        )

    @staticmethod
    def _extract_highlights(text: str) -> List[str]:
        bullet_regex = r"^\s*[-•·]\s*(.+)$"
        highlights = LocalExtractor._find_all(bullet_regex, text, flags=re.MULTILINE)
        return highlights[:10]  # keep list manageable

    @staticmethod
    def _dedupe_preserve_order(items: Iterable[str]) -> List[str]:
        seen = set()
        ordered: List[str] = []
        for item in items:
            stripped = item.strip()
            if not stripped:
                continue
            key = stripped.lower()
            if key in seen:
                continue
            seen.add(key)
            ordered.append(stripped)
        return ordered


__all__ = ["LocalExtractor"]


