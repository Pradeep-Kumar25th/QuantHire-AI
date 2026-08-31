"""Convert ParsingAgent output to resume_parsing / QuantChat chunk format."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


def _parse_year_month(value: Any) -> Optional[tuple[int, int]]:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text or text in {"present", "current", "now", "ongoing"}:
        now = datetime.utcnow()
        return now.year, now.month
    match = re.search(r"(\d{4})(?:[-/](\d{1,2}))?", text)
    if not match:
        year_only = re.search(r"(\d{4})", text)
        if year_only:
            return int(year_only.group(1)), 1
        return None
    year = int(match.group(1))
    month = int(match.group(2) or 1)
    return year, max(1, min(12, month))


def _estimate_total_years(experience_items: List[Any]) -> float:
    months = 0
    for item in experience_items:
        if not isinstance(item, dict):
            continue
        start = _parse_year_month(item.get("start"))
        end = _parse_year_month(item.get("end")) or _parse_year_month("present")
        if not start or not end:
            continue
        start_index = start[0] * 12 + start[1]
        end_index = end[0] * 12 + end[1]
        if end_index >= start_index:
            months += end_index - start_index
    if months <= 0 and experience_items:
        return float(len(experience_items))
    return round(months / 12.0, 1)


def _skill_names(skills: List[Any]) -> List[str]:
    names: List[str] = []
    for item in skills or []:
        if isinstance(item, dict):
            name = item.get("name")
            if name:
                names.append(str(name))
        elif isinstance(item, str) and item.strip():
            names.append(item.strip())
    return names


def _categorize_skills(skills: List[Any]) -> Tuple[List[str], List[str], List[str]]:
    technical: List[str] = []
    soft: List[str] = []
    tools: List[str] = []
    seen: set[str] = set()

    def _add(bucket: List[str], name: str) -> None:
        key = name.lower()
        if key not in seen:
            seen.add(key)
            bucket.append(name)

    for item in skills or []:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            category = str(item.get("category") or "technical").lower()
            if category in {"soft", "soft_skill", "interpersonal", "methodology"}:
                _add(soft, name)
            elif category in {"tool", "tools", "platform", "framework"}:
                _add(tools, name)
            elif category in {"language", "spoken_language"}:
                _add(soft, name)
            else:
                _add(technical, name)
        elif isinstance(item, str) and item.strip():
            _add(technical, item.strip())
    return technical, soft, tools


def _experience_positions(items: List[Any]) -> List[Dict[str, Any]]:
    positions = []
    for exp in items or []:
        if not isinstance(exp, dict):
            continue
        bullets = exp.get("bullets") or []
        techs = exp.get("technologies") or []
        desc_parts = list(bullets)
        if techs:
            desc_parts.append("Technologies: " + ", ".join(str(t) for t in techs))
        positions.append(
            {
                "company": exp.get("company", ""),
                "title": exp.get("title", ""),
                "start_date": exp.get("start", ""),
                "end_date": exp.get("end", ""),
                "duration": (
                    f"{exp.get('start', '')} - {exp.get('end', '')}".strip(" -")
                    if exp.get("start") or exp.get("end")
                    else ""
                ),
                "description": "\n".join(str(p) for p in desc_parts if p),
                "location": exp.get("location", ""),
            }
        )
    return positions


def _format_languages(languages: List[Any]) -> List[str]:
    formatted = []
    for lang in languages or []:
        if isinstance(lang, dict):
            name = lang.get("language") or lang.get("name") or ""
            prof = lang.get("proficiency") or ""
            if name:
                formatted.append(f"{name} ({prof})".strip(" ()") if prof else str(name))
        elif isinstance(lang, str) and lang.strip():
            formatted.append(lang.strip())
    return formatted


def _build_screening_report(parsed: Dict[str, Any], total_years: float) -> Dict[str, Any]:
    screening = parsed.get("screening") or {}
    if not isinstance(screening, dict):
        screening = {}

    missing: List[str] = []
    for field in parsed.get("ambiguous_fields") or []:
        if field and field not in missing:
            missing.append(str(field))

    completeness = parsed.get("completeness") if isinstance(parsed.get("completeness"), dict) else {}

    sections_found = {
        "contact": bool(parsed.get("name") or parsed.get("emails")),
        "summary": bool(parsed.get("summary")),
        "experience": bool(parsed.get("experience")),
        "internships": bool(parsed.get("internships")),
        "education": bool(parsed.get("education")),
        "skills": bool(parsed.get("skills")),
        "certificates": bool(parsed.get("certificates")),
        "projects": bool(parsed.get("projects")),
        "publications": bool(parsed.get("publications")),
        "languages": bool(parsed.get("languages")),
        "awards": bool(parsed.get("awards")),
        "volunteer": bool(parsed.get("volunteer")),
        "trainings": bool(parsed.get("trainings")),
        "memberships": bool(parsed.get("memberships")),
        "military": bool(parsed.get("military")),
        "patents": bool(parsed.get("patents")),
        "references": bool(parsed.get("references")),
        "custom_sections": bool(parsed.get("custom_sections")),
        "links": bool(parsed.get("links")),
    }

    return {
        "confidence": float(parsed.get("confidence") or 0.0),
        "total_years_experience": total_years,
        "experience_entries": len(parsed.get("experience") or []),
        "internship_entries": len(parsed.get("internships") or []),
        "education_entries": len(parsed.get("education") or []),
        "skills_count": len(parsed.get("skills") or []),
        "certificates_count": len(parsed.get("certificates") or []),
        "projects_count": len(parsed.get("projects") or []),
        "publications_count": len(parsed.get("publications") or []),
        "custom_sections_count": len(parsed.get("custom_sections") or []),
        "section_inventory": parsed.get("section_inventory") or [],
        "sections_found": sections_found,
        "completeness_grade": completeness.get("completeness_grade", "good"),
        "coverage_ratio": completeness.get("coverage_ratio"),
        "detected_headers": completeness.get("detected_headers") or [],
        "unmapped_headers": completeness.get("unmapped_headers") or [],
        "gaps_for_hr_review": completeness.get("gaps_for_hr_review") or missing,
        "missing_or_ambiguous_fields": missing,
        "work_authorization": screening.get("work_authorization"),
        "visa_status": screening.get("visa_status"),
        "notice_period": screening.get("notice_period"),
        "availability": screening.get("availability"),
        "relocation_willing": screening.get("relocation_willing"),
        "expected_salary": screening.get("expected_salary"),
        "security_clearance": screening.get("security_clearance"),
        "career_level": screening.get("career_level"),
    }


def parsing_agent_to_resume_format(
    parsed: Dict[str, Any],
    *,
    resume_id: str,
    resume_text: str,
    parsing_method: str = "ENTERPRISE_PARSING_AGENT",
) -> Dict[str, Any]:
    """Map enterprise ParsingAgent JSON to nested structure for chunking and HR UI."""
    all_experience = list(parsed.get("experience") or []) + list(parsed.get("internships") or [])
    positions = _experience_positions(parsed.get("experience") or [])
    positions.extend(_experience_positions(parsed.get("internships") or []))

    education_items = parsed.get("education") or []
    degrees, universities = [], []
    for edu in education_items:
        if not isinstance(edu, dict):
            continue
        degree = edu.get("degree") or edu.get("field") or ""
        institution = edu.get("institution") or ""
        year = edu.get("year")
        honors = edu.get("honors") or edu.get("gpa")
        if degree:
            label = f"{degree} ({year})" if year else str(degree)
            if honors:
                label = f"{label}, {honors}"
            degrees.append(label)
        if institution:
            universities.append(str(institution))

    technical_skills, soft_skills, tools = _categorize_skills(parsed.get("skills") or [])
    if not technical_skills:
        technical_skills = _skill_names(parsed.get("skills") or [])

    total_years = _estimate_total_years(all_experience)
    certs = []
    for cert in parsed.get("certificates") or []:
        if isinstance(cert, dict) and cert.get("name"):
            issuer = cert.get("issuer") or ""
            certs.append(f"{cert['name']} ({issuer})".strip(" ()"))

    emails = parsed.get("emails") or []
    phones = parsed.get("phones") or []
    locations = parsed.get("locations") or []
    summary = (parsed.get("summary") or "").strip()
    screening = parsed.get("screening") if isinstance(parsed.get("screening"), dict) else {}

    personal: Dict[str, Any] = {
        "name": parsed.get("name") or "Unknown",
        "email": emails[0] if emails else "",
        "phone": phones[0] if phones else "",
        "location": locations[0] if locations else "",
    }
    for link in parsed.get("links") or []:
        if not isinstance(link, dict):
            continue
        link_type = str(link.get("type") or "").lower()
        url = link.get("url") or ""
        if "linkedin" in link_type:
            personal["linkedin"] = url
        elif "github" in link_type:
            personal["github"] = url
        elif url:
            personal.setdefault("portfolio", url)

    return {
        "id": resume_id,
        "summary": summary,
        "raw_text": resume_text,
        "content": resume_text,
        "upload_date": datetime.utcnow().isoformat(),
        "parsing_method": parsing_method,
        "match_percentage": int(float(parsed.get("confidence", 0.0)) * 100),
        "active_applications": 0,
        "security_status": "verified",
        "personal_info": personal,
        "skills": {
            "technical_skills": technical_skills,
            "soft_skills": soft_skills,
            "tools": tools,
            "certifications": certs,
        },
        "experience": {
            "total_years": total_years,
            "current_role": positions[0].get("title") if positions else "",
            "positions": positions,
        },
        "education": {
            "degrees": degrees,
            "universities": universities,
        },
        "certifications": certs,
        "projects": parsed.get("projects") or [],
        "publications": parsed.get("publications") or [],
        "awards": parsed.get("awards") or [],
        "volunteer": parsed.get("volunteer") or [],
        "trainings": parsed.get("trainings") or [],
        "memberships": parsed.get("memberships") or [],
        "military": parsed.get("military") or [],
        "patents": parsed.get("patents") or [],
        "references": parsed.get("references") or [],
        "custom_sections": parsed.get("custom_sections") or [],
        "section_inventory": parsed.get("section_inventory") or [],
        "languages": _format_languages(parsed.get("languages") or []),
        "links": parsed.get("links") or [],
        "screening": screening,
        "completeness": parsed.get("completeness") or {},
        "screening_report": _build_screening_report(parsed, total_years),
    }
