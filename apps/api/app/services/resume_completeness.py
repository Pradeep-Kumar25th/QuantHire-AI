"""Enterprise resume completeness — section detection, gap analysis, raw coverage."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

# Common resume section headers (English + variants HR systems recognize)
SECTION_HEADER_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("summary", re.compile(r"^(?:professional\s+)?(?:summary|profile|objective|about\s+me)\s*:?\s*$", re.I | re.M)),
    ("experience", re.compile(r"^(?:work\s+)?(?:experience|employment|work\s+history|professional\s+experience|career\s+history)\s*:?\s*$", re.I | re.M)),
    ("education", re.compile(r"^(?:education|academic\s+background|qualifications?\s+\(academic\))\s*:?\s*$", re.I | re.M)),
    ("skills", re.compile(r"^(?:core\s+)?(?:skills|technical\s+skills|key\s+skills|core\s+competencies|competencies|expertise|technologies|tech\s+stack)\s*:?\s*$", re.I | re.M)),
    ("certificates", re.compile(r"^(?:certifications?|licenses?|credentials?|professional\s+certifications?)\s*:?\s*$", re.I | re.M)),
    ("projects", re.compile(r"^(?:selected\s+)?(?:projects?|portfolio|key\s+projects?|personal\s+projects?)\s*:?\s*$", re.I | re.M)),
    ("languages", re.compile(r"^(?:languages?|language\s+proficiency)\s*:?\s*$", re.I | re.M)),
    ("awards", re.compile(r"^(?:awards?|honors?|achievements?|recognition)\s*:?\s*$", re.I | re.M)),
    ("publications", re.compile(r"^(?:publications?|research|papers?)\s*:?\s*$", re.I | re.M)),
    ("volunteer", re.compile(r"^(?:volunteer(?:ing)?|community\s+service|social\s+work)\s*:?\s*$", re.I | re.M)),
    ("references", re.compile(r"^(?:references?|referees?)\s*:?\s*$", re.I | re.M)),
    ("military", re.compile(r"^(?:military\s+service|armed\s+forces|defence|defense)\s*:?\s*$", re.I | re.M)),
    ("training", re.compile(r"^(?:training|courses?|professional\s+development|workshops?)\s*:?\s*$", re.I | re.M)),
    ("internships", re.compile(r"^(?:internships?|internship\s+experience)\s*:?\s*$", re.I | re.M)),
    ("additional", re.compile(r"^(?:additional\s+information|personal\s+details|other\s+information|miscellaneous)\s*:?\s*$", re.I | re.M)),
    ("leadership", re.compile(r"^(?:leadership|awards?\s*&\s*leadership|honors?\s*&\s*awards?)\s*:?\s*$", re.I | re.M)),
]

GENERIC_SECTION_PATTERN = re.compile(
    r"^([A-Z][A-Za-z0-9 &/\-]{2,48})\s*:?\s*$",
    re.M,
)


def detect_section_headers(raw_text: str) -> List[str]:
    """Return section header lines detected in raw resume text."""
    if not raw_text:
        return []
    headers: List[str] = []
    seen: set[str] = set()
    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped or len(stripped) > 60:
            continue
        if not re.match(r"^[A-Za-z]", stripped):
            continue
        key = stripped.lower()
        if key in seen:
            continue
        for _, pattern in SECTION_HEADER_PATTERNS:
            if pattern.search(stripped):
                headers.append(stripped)
                seen.add(key)
                break
        else:
            if GENERIC_SECTION_PATTERN.match(stripped) and (
                stripped.isupper() or (stripped.istitle() and len(stripped.split()) <= 6)
            ):
                headers.append(stripped)
                seen.add(key)
    return headers


def _structured_char_count(parsed: Dict[str, Any]) -> int:
    """Rough count of characters captured in structured fields."""
    total = 0
    for key in (
        "summary",
        "name",
    ):
        val = parsed.get(key)
        if val:
            total += len(str(val))
    for key in (
        "experience",
        "education",
        "skills",
        "certificates",
        "projects",
        "languages",
        "awards",
        "publications",
        "volunteer",
        "internships",
        "trainings",
        "memberships",
        "military",
        "patents",
        "custom_sections",
    ):
        items = parsed.get(key) or []
        if isinstance(items, list):
            total += len(str(items))
        elif isinstance(items, dict):
            total += len(str(items))
    for section in parsed.get("custom_sections") or []:
        if isinstance(section, dict):
            total += len(str(section.get("content") or ""))
    return total


def compute_completeness(raw_text: str, parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Score how much of the raw resume is represented in structured extraction."""
    raw_len = len((raw_text or "").strip())
    structured_len = _structured_char_count(parsed)
    headers = detect_section_headers(raw_text)
    inventory = parsed.get("section_inventory") or []

    coverage_ratio = 0.0
    if raw_len > 0:
        # Structured JSON rarely equals raw length; use heuristic cap at 1.0
        coverage_ratio = min(1.0, structured_len / max(raw_len * 0.45, 1))

    mapped_headers = {h.lower() for h in inventory}
    unmapped_headers = [h for h in headers if h.lower() not in mapped_headers]

    gaps: List[str] = list(parsed.get("ambiguous_fields") or [])
    if not parsed.get("experience"):
        gaps.append("experience")
    if not parsed.get("skills") and "skills" not in [g.lower() for g in gaps]:
        if any("skill" in h.lower() for h in headers):
            gaps.append("skills")

    grade = "excellent"
    if coverage_ratio < 0.55 or len(unmapped_headers) > 2:
        grade = "needs_review"
    elif coverage_ratio < 0.75 or unmapped_headers:
        grade = "good"

    return {
        "raw_text_characters": raw_len,
        "structured_characters": structured_len,
        "coverage_ratio": round(coverage_ratio, 2),
        "completeness_grade": grade,
        "detected_headers": headers,
        "section_inventory": inventory,
        "unmapped_headers": unmapped_headers,
        "gaps_for_hr_review": gaps,
    }


def merge_custom_sections_from_headers(
    raw_text: str,
    parsed: Dict[str, Any],
) -> Dict[str, Any]:
    """Append verbatim section blocks for headers not fully structured."""
    if not raw_text:
        return parsed

    existing = list(parsed.get("custom_sections") or [])
    existing_titles = {
        str(s.get("title", "")).lower()
        for s in existing
        if isinstance(s, dict)
    }

    lines = raw_text.splitlines()
    section_starts: list[tuple[int, str]] = []
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        for _, pattern in SECTION_HEADER_PATTERNS:
            if pattern.match(stripped):
                section_starts.append((idx, stripped))
                break
        else:
            if GENERIC_SECTION_PATTERN.match(stripped) and (
                stripped.isupper() or (stripped.istitle() and len(stripped.split()) <= 5)
            ):
                section_starts.append((idx, stripped))

    for i, (start_idx, title) in enumerate(section_starts):
        title_key = title.lower()
        if title_key in existing_titles:
            continue
        end_idx = section_starts[i + 1][0] if i + 1 < len(section_starts) else len(lines)
        content = "\n".join(lines[start_idx + 1 : end_idx]).strip()
        if len(content) < 30:
            continue
        existing.append({"title": title, "content": content[:8000]})
        existing_titles.add(title_key)

    if existing:
        parsed["custom_sections"] = existing
    return parsed


def supplement_parsed_from_raw_text(raw_text: str, parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Backfill languages and HR screening fields often found in Additional Information blocks."""
    screening = parsed.get("screening") if isinstance(parsed.get("screening"), dict) else {}
    if not isinstance(parsed.get("screening"), dict):
        parsed["screening"] = screening

    lang_match = re.search(r"Languages?\s*:\s*([^\n|]+)", raw_text, re.I)
    if lang_match:
        existing = {
            str(item.get("language", "")).lower()
            for item in (parsed.get("languages") or [])
            if isinstance(item, dict)
        }
        for part in lang_match.group(1).split(","):
            name = part.strip().strip("|").strip()
            if name and name.lower() not in existing:
                parsed.setdefault("languages", []).append(
                    {"language": name, "proficiency": ""}
                )
                existing.add(name.lower())

    screening_patterns = (
        (r"Work Authorization\s*:\s*([^\n|]+)", "work_authorization"),
        (r"Availability\s*:\s*([^\n|]+)", "availability"),
        (r"Visa Status\s*:\s*([^\n|]+)", "visa_status"),
        (r"Notice Period\s*:\s*([^\n|]+)", "notice_period"),
    )
    for pattern, field in screening_patterns:
        match = re.search(pattern, raw_text, re.I)
        if match and not screening.get(field):
            screening[field] = match.group(1).strip().strip("|").strip()

    loc_match = re.search(r"Preferred Locations?\s*:\s*([^\n]+)", raw_text, re.I)
    if loc_match:
        existing_locs = {str(loc).lower() for loc in (parsed.get("locations") or [])}
        for loc in loc_match.group(1).split(","):
            cleaned = loc.strip().strip("|").strip()
            if cleaned and cleaned.lower() not in existing_locs:
                parsed.setdefault("locations", []).append(cleaned)
                existing_locs.add(cleaned.lower())

    parsed["screening"] = screening
    return parsed


def enrich_parsed_for_enterprise(raw_text: str, parsed: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Merge header-based sections and compute completeness metrics."""
    parsed = merge_custom_sections_from_headers(raw_text, parsed)
    parsed = supplement_parsed_from_raw_text(raw_text, parsed)
    completeness = compute_completeness(raw_text, parsed)
    parsed["completeness"] = completeness
    return parsed, completeness
