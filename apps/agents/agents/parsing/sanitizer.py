"""Lenient normalization — accept any LLM resume shape before strict validation."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s\-().]{7,}\d)")


def _str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value)
    return str(value).strip()


def _float(value: Any, default: float = 0.75) -> float:
    try:
        if value is None:
            return default
        result = float(value)
        return max(0.0, min(1.0, result))
    except (TypeError, ValueError):
        return default


def _list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _normalize_string_list(items: Any) -> List[str]:
    result: List[str] = []
    for item in _list(items):
        if isinstance(item, dict):
            text = _str(item.get("title") or item.get("name") or item.get("text") or item)
            if text:
                result.append(text)
        elif item is not None:
            text = _str(item)
            if text:
                result.append(text)
    return result


def _normalize_bullets(value: Any) -> List[str]:
    bullets: List[str] = []
    for item in _list(value):
        if isinstance(item, dict):
            text = _str(item.get("text") or item.get("bullet") or item.get("description"))
        else:
            text = _str(item)
        if text:
            bullets.append(text)
    if not bullets and isinstance(value, str) and value.strip():
        bullets = [line.strip() for line in value.splitlines() if line.strip()]
    return bullets


def _normalize_experience_items(items: Any) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for raw in _list(items):
        if isinstance(raw, str) and raw.strip():
            normalized.append(
                {
                    "company": "",
                    "title": raw.strip(),
                    "start": "",
                    "end": "",
                    "bullets": [],
                    "location": "",
                    "technologies": [],
                }
            )
            continue
        if not isinstance(raw, dict):
            continue
        company = _str(
            raw.get("company")
            or raw.get("company_name")
            or raw.get("employer")
            or raw.get("organization")
            or raw.get("org")
        )
        title = _str(
            raw.get("title")
            or raw.get("role")
            or raw.get("position")
            or raw.get("job_title")
            or raw.get("designation")
        )
        start = _str(raw.get("start") or raw.get("start_date") or raw.get("from") or raw.get("date_from"))
        end = _str(raw.get("end") or raw.get("end_date") or raw.get("to") or raw.get("date_to"))
        if not company and not title:
            continue
        normalized.append(
            {
                "company": company,
                "title": title or company,
                "start": start,
                "end": end or "present",
                "bullets": _normalize_bullets(
                    raw.get("bullets")
                    or raw.get("responsibilities")
                    or raw.get("achievements")
                    or raw.get("description")
                    or raw.get("highlights")
                ),
                "location": _str(raw.get("location") or raw.get("city")),
                "technologies": _normalize_string_list(raw.get("technologies") or raw.get("tools")),
            }
        )
    return normalized


def _normalize_education_items(items: Any) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for raw in _list(items):
        if isinstance(raw, str) and raw.strip():
            normalized.append(
                {
                    "degree": raw.strip(),
                    "institution": "",
                    "year": "",
                    "field": "",
                    "location": "",
                    "gpa": "",
                    "honors": "",
                }
            )
            continue
        if not isinstance(raw, dict):
            continue
        degree = _str(raw.get("degree") or raw.get("qualification") or raw.get("program"))
        institution = _str(raw.get("institution") or raw.get("school") or raw.get("university") or raw.get("college"))
        if not degree and not institution:
            continue
        normalized.append(
            {
                "degree": degree,
                "institution": institution,
                "year": _str(raw.get("year") or raw.get("graduation_year") or raw.get("dates")),
                "field": _str(raw.get("field") or raw.get("major") or raw.get("specialization")),
                "location": _str(raw.get("location")),
                "gpa": _str(raw.get("gpa") or raw.get("grade") or raw.get("cgpa")),
                "honors": _str(raw.get("honors") or raw.get("distinction")),
            }
        )
    return normalized


def _normalize_skill_items(items: Any) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for raw in _list(items):
        if isinstance(raw, str) and raw.strip():
            for part in re.split(r"[,;|/•]", raw):
                name = part.strip()
                if name:
                    normalized.append(
                        {"name": name, "category": "technical", "confidence": 0.8, "proficiency": ""}
                    )
            continue
        if not isinstance(raw, dict):
            continue
        name = _str(raw.get("name") or raw.get("skill") or raw.get("technology") or raw.get("title"))
        if not name:
            continue
        category = _str(raw.get("category") or raw.get("type") or "technical").lower() or "technical"
        normalized.append(
            {
                "name": name,
                "category": category,
                "confidence": _float(raw.get("confidence"), 0.8),
                "proficiency": _str(raw.get("proficiency") or raw.get("level")),
            }
        )
    return normalized


def _normalize_certificate_items(items: Any) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for raw in _list(items):
        if isinstance(raw, str) and raw.strip():
            normalized.append(
                {"name": raw.strip(), "issuer": "", "date": "", "credential_id": ""}
            )
            continue
        if not isinstance(raw, dict):
            continue
        name = _str(raw.get("name") or raw.get("title") or raw.get("certification"))
        if not name:
            continue
        normalized.append(
            {
                "name": name,
                "issuer": _str(raw.get("issuer") or raw.get("provider") or raw.get("authority")),
                "date": _str(raw.get("date") or raw.get("year") or raw.get("issued")),
                "credential_id": _str(raw.get("credential_id") or raw.get("id") or raw.get("license")),
            }
        )
    return normalized


def _normalize_project_items(items: Any) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for raw in _list(items):
        if isinstance(raw, str) and raw.strip():
            normalized.append(
                {
                    "name": raw.strip()[:120],
                    "description": raw.strip(),
                    "technologies": [],
                    "url": "",
                    "dates": "",
                }
            )
            continue
        if not isinstance(raw, dict):
            continue
        name = _str(raw.get("name") or raw.get("title") or raw.get("project"))
        description = _str(raw.get("description") or raw.get("summary") or raw.get("details"))
        if not name and not description:
            continue
        normalized.append(
            {
                "name": name or description[:80],
                "description": description,
                "technologies": _normalize_string_list(raw.get("technologies") or raw.get("tools")),
                "url": _str(raw.get("url") or raw.get("link")),
                "dates": _str(raw.get("dates") or raw.get("duration")),
            }
        )
    return normalized


def _normalize_record_items(items: Any, fields: Dict[str, str]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for raw in _list(items):
        if isinstance(raw, str) and raw.strip():
            entry = {target: "" for target in fields.values()}
            entry[next(iter(fields.values()))] = raw.strip()
            normalized.append(entry)
            continue
        if not isinstance(raw, dict):
            continue
        entry = {target: _str(raw.get(source)) for source, target in fields.items()}
        if any(entry.values()):
            normalized.append(entry)
    return normalized


def _normalize_languages(items: Any) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for raw in _list(items):
        if isinstance(raw, dict):
            language = _str(raw.get("language") or raw.get("name") or raw.get("lang"))
            if language:
                normalized.append(
                    {"language": language, "proficiency": _str(raw.get("proficiency") or raw.get("level"))}
                )
        elif isinstance(raw, str) and raw.strip():
            normalized.append({"language": raw.strip(), "proficiency": ""})

    expanded: List[Dict[str, Any]] = []
    for lang in normalized:
        language = lang.get("language", "")
        proficiency = lang.get("proficiency", "")
        if "," in language and not proficiency:
            for part in language.split(","):
                part = part.strip()
                if part:
                    expanded.append({"language": part, "proficiency": ""})
        else:
            expanded.append(lang)
    return expanded


def _normalize_links(items: Any) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for raw in _list(items):
        if isinstance(raw, dict):
            url = _str(raw.get("url") or raw.get("link") or raw.get("href"))
            if url:
                link_type = _str(raw.get("type") or raw.get("platform") or "other").lower()
                if "linkedin" in url.lower():
                    link_type = "linkedin"
                elif "github" in url.lower():
                    link_type = "github"
                normalized.append({"type": link_type or "other", "url": url})
        elif isinstance(raw, str) and raw.strip():
            url = raw.strip()
            if not url.startswith("http"):
                url = f"https://{url.lstrip('/')}"
            normalized.append({"type": "other", "url": url})
    return normalized


def _normalize_custom_sections(items: Any) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for raw in _list(items):
        if isinstance(raw, dict):
            title = _str(raw.get("title") or raw.get("header") or raw.get("section"))
            content = _str(raw.get("content") or raw.get("body") or raw.get("text"))
            if title or content:
                normalized.append({"title": title or "Additional", "content": content})
        elif isinstance(raw, str) and raw.strip():
            normalized.append({"title": "Additional", "content": raw.strip()})
    return normalized


def _normalize_screening(value: Any) -> Dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    relocation = raw.get("relocation_willing")
    if isinstance(relocation, str):
        relocation = relocation.strip().lower() in {"true", "yes", "y", "1", "willing"}
    elif relocation is not None and not isinstance(relocation, bool):
        relocation = None
    return {
        "work_authorization": _str(raw.get("work_authorization")) or None,
        "visa_status": _str(raw.get("visa_status")) or None,
        "notice_period": _str(raw.get("notice_period")) or None,
        "availability": _str(raw.get("availability")) or None,
        "relocation_willing": relocation,
        "expected_salary": _str(raw.get("expected_salary") or raw.get("salary_expectation")) or None,
        "security_clearance": _str(raw.get("security_clearance")) or None,
        "career_level": _str(raw.get("career_level") or raw.get("seniority")) or None,
    }


def _extract_contacts_from_text(raw_text: str, parsed: Dict[str, Any]) -> None:
    if not raw_text:
        return
    emails = list(parsed.get("emails") or [])
    existing_emails = {e.lower() for e in emails}
    for match in EMAIL_RE.findall(raw_text):
        if match.lower() not in existing_emails:
            emails.append(match)
            existing_emails.add(match.lower())
    if emails:
        parsed["emails"] = emails

    if not parsed.get("phones"):
        phones: List[str] = []
        for match in PHONE_RE.findall(raw_text[:2000]):
            cleaned = re.sub(r"\s+", " ", match).strip()
            if len(re.sub(r"\D", "", cleaned)) >= 8:
                phones.append(cleaned)
        if phones:
            parsed["phones"] = phones[:3]


def sanitize_parsed_resume(parsed_data: Dict[str, Any], raw_text: Optional[str] = None) -> Dict[str, Any]:
    """Coerce heterogeneous LLM output into a validation-safe enterprise resume dict."""
    data = dict(parsed_data or {})

    if raw_text:
        _extract_contacts_from_text(raw_text, data)

    data["name"] = _str(data.get("name")) or None
    data["summary"] = _str(data.get("summary")) or None
    data["emails"] = _normalize_string_list(data.get("emails"))
    data["phones"] = _normalize_string_list(data.get("phones"))
    data["locations"] = _normalize_string_list(data.get("locations"))
    data["section_inventory"] = _normalize_string_list(data.get("section_inventory"))
    data["ambiguous_fields"] = _normalize_string_list(data.get("ambiguous_fields"))
    data["awards"] = _normalize_string_list(data.get("awards"))
    data["memberships"] = _normalize_string_list(data.get("memberships"))
    data["references"] = _normalize_string_list(data.get("references"))

    data["experience"] = _normalize_experience_items(data.get("experience"))
    data["internships"] = _normalize_experience_items(data.get("internships"))
    data["education"] = _normalize_education_items(data.get("education"))
    data["skills"] = _normalize_skill_items(data.get("skills"))
    data["certificates"] = _normalize_certificate_items(data.get("certificates"))
    data["projects"] = _normalize_project_items(data.get("projects"))
    data["languages"] = _normalize_languages(data.get("languages"))
    data["links"] = _normalize_links(data.get("links"))
    data["custom_sections"] = _normalize_custom_sections(data.get("custom_sections"))

    data["publications"] = _normalize_record_items(
        data.get("publications"),
        {"title": "title", "publisher": "publisher", "year": "year", "url": "url"},
    )
    data["volunteer"] = _normalize_record_items(
        data.get("volunteer"),
        {
            "organization": "organization",
            "role": "role",
            "dates": "dates",
            "description": "description",
        },
    )
    data["trainings"] = _normalize_record_items(
        data.get("trainings"),
        {"name": "name", "provider": "provider", "date": "date", "description": "description"},
    )
    data["military"] = _normalize_record_items(
        data.get("military"),
        {"branch": "branch", "rank": "rank", "dates": "dates", "description": "description"},
    )
    data["patents"] = _normalize_record_items(
        data.get("patents"),
        {"title": "title", "number": "number", "year": "year"},
    )

    data["screening"] = _normalize_screening(data.get("screening"))
    data["confidence"] = _float(data.get("confidence"), 0.75)
    return data
