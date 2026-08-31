"""
Precision Malomatia .docx template filler supporting both Leader and Non-Leader layouts.
"""

from __future__ import annotations

import copy
import io
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Literal

from docx import Document
from docx.document import Document as DocumentType
from docx.shared import Pt, RGBColor
from docx.table import Table
from docx.text.paragraph import Paragraph

TemplateType = Literal["leader", "non_leader"]

TEMPLATE_FILENAMES: dict[TemplateType, str] = {
    "leader": "leader_template.docx",
    "non_leader": "non_leader_template.docx",
}

TEMPLATE_ASSETS_DIR = Path(__file__).resolve().parent.parent / "templates" / "malomatia"

DOWNLOADS_FALLBACK: dict[TemplateType, tuple[str, ...]] = {
    "leader": (
        r"C:\Users\prakumar\Downloads\JD Template_Leader position (1).docx",
        r"C:\Users\prakumar\Downloads\JD Templates\JD Template_Leader position (1).docx",
    ),
    "non_leader": (
        r"C:\Users\prakumar\Downloads\JD Template_Non-Leader position (2).docx",
        r"C:\Users\prakumar\Downloads\JD Templates\JD Template_Non-Leader position (2).docx",
    ),
}

DEFAULT_LANGUAGE = "English, Arabic (preferred)"
DEFAULT_EXTERNAL = ["Client", "Vendors and Suppliers", "Consultants"]

DEFAULT_CORE_SKILLS_LEADER = [
    "Strong leadership and people management skills.",
    "Excellent problem-solving and decision-making abilities.",
    "Knowledge of ITIL and operational best practices.",
    "Experience with enterprise monitoring and infrastructure tools.",
    "Strong communication and stakeholder management skills.",
]

DEFAULT_CORE_SKILLS_NON_LEADER = [
    "Proficiency in modern development, automation, and infrastructure tooling.",
    "Excellent problem-solving and analytical abilities.",
    "Strong collaboration and cross-functional teamwork skills.",
    "Experience with agile workflows, CI/CD, and quality standards.",
    "Clear technical communication and documentation skills.",
]

STRATEGIC_KEYWORDS = (
    "strateg",
    "long-term",
    "long term",
    "policy",
    "policies",
    "standard",
    "capacity planning",
    "budget",
    "forecast",
    "optimization",
    "initiative",
    "improvement",
    "organizational",
    "develop and maintain",
    "demand forecasting",
    "expansion",
    "align with",
    "architecture",
    "roadmap",
)

PEOPLE_KEYWORDS = (
    "coach",
    "mentor",
    "staff",
    "shift team",
    "culture",
    "engagement",
    "career",
    "development",
    "people management",
    "lead, coach",
    "manage data center staff",
    "employee",
    "team members",
)


class MalomatiaTemplateNotFoundError(FileNotFoundError):
    """Raised when official Malomatia template files are missing."""


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_label(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", _safe_str(text)).lower()
    cleaned = cleaned.replace("–", "-").replace("—", "-")
    return cleaned


def _listify(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_safe_str(item) for item in value if _safe_str(item)]
    text = _safe_str(value)
    if not text:
        return []
    if "\n" in text:
        return [line.strip().lstrip("•-* \t") for line in text.splitlines() if line.strip()]
    if "•" in text:
        return [part.strip(" •\t") for part in text.split("•") if part.strip()]
    return [text]


def resolve_template_path(template_type: TemplateType) -> Path:
    bundled = TEMPLATE_ASSETS_DIR / TEMPLATE_FILENAMES[template_type]
    if bundled.is_file():
        return bundled
    for candidate in DOWNLOADS_FALLBACK.get(template_type, ()):
        path = Path(candidate)
        if path.is_file():
            return path
    raise MalomatiaTemplateNotFoundError(
        f"Official Malomatia Word template not found at {bundled}."
    )


def _hierarchy_fields(jd: dict[str, Any]) -> dict[str, str]:
    meta = jd.get("metadata") if isinstance(jd.get("metadata"), dict) else {}
    return {
        "strategic_business_unit": _safe_str(
            jd.get("business_unit") or meta.get("business_unit") or "Cloud, Infrastructure & Security Services (CISS)"
        ),
        "business_unit": _safe_str(
            jd.get("department") or meta.get("department") or "Cloud & Infrastructure Services (CIS)"
        ),
        "practice_unit": _safe_str(
            jd.get("team") or meta.get("team") or "Cloud & Infrastructure Managed Services"
        ),
        "delivery_unit": _safe_str(
            jd.get("division") or meta.get("division") or "Managed Infrastructure Services"
        ),
        "reporting_to": _safe_str(
            (jd.get("work_environment") or {}).get("reports_to") or "Delivery Leader – Managed Infrastructure Services"
        ),
    }


def _default_internal_interfaces(jd: dict[str, Any], hierarchy: dict[str, str]) -> list[str]:
    interfaces: list[str] = []
    reports_to = hierarchy.get("reporting_to")
    if reports_to:
        interfaces.append(reports_to)

    work_env = jd.get("work_environment") if isinstance(jd.get("work_environment"), dict) else {}
    for item in _listify(work_env.get("collaborates_with")):
        if item not in interfaces:
            interfaces.append(item)

    defaults = [
        "Other Delivery Leaders",
        "Members from functional teams such as HR, Finance, IT etc.",
        "All other malomatia Personnel (as and when required)",
    ]
    for item in defaults:
        if item not in interfaces:
            interfaces.append(item)
    return interfaces


def _experience_lines(jd: dict[str, Any], template_type: TemplateType) -> list[str]:
    qualifications = jd.get("required_qualifications")
    lines: list[str] = []
    
    if isinstance(qualifications, dict):
        experience = _safe_str(qualifications.get("experience"))
        if experience:
            lines.extend(_listify(experience))

    meta = jd.get("metadata") if isinstance(jd.get("metadata"), dict) else {}
    yoe = _safe_str(meta.get("years_of_experience"))
    if not lines and yoe:
        lines.append(f"{yoe} years of relevant experience in the domain.")

    if not lines:
        if template_type == "leader":
            lines = [
                "7–12 years of experience in IT infrastructure or operations.",
                "Minimum 3–5 years in a managerial or supervisory role.",
                "Strong knowledge of enterprise systems, high availability, and architecture standards.",
            ]
        else:
            lines = [
                "3–7 years of relevant hands-on professional experience.",
                "Demonstrated track record delivering technical solutions in agile teams.",
            ]
    return lines


def _education_text(jd: dict[str, Any]) -> str:
    qualifications = jd.get("required_qualifications")
    education = ""
    if isinstance(qualifications, dict):
        education = _safe_str(qualifications.get("education"))

    is_only_certs = bool(education and not re.search(r"degree|bachelor|master|bsc|msc|b\.e|b\.tech|diploma", education, re.I))
    if not education or is_only_certs:
        base_degree = "Bachelor’s degree in Computer Science, IT, Engineering, or related field."
        if is_only_certs:
            return f"{base_degree}\nCertifications: {education}"
        return base_degree

    preferred = [
        _safe_str(item)
        for item in _listify(jd.get("preferred_qualifications"))
        if re.search(r"degree|diploma|certification|master|bachelor|mba", _safe_str(item), re.I)
    ]
    if preferred:
        return f"{education}\nPreferred: {preferred[0]}"
    return education


def _job_specific_skills(jd: dict[str, Any], template_type: TemplateType) -> list[str]:
    qualifications = jd.get("required_qualifications")
    skills: list[str] = []
    
    if isinstance(qualifications, dict):
        tech = _listify(qualifications.get("technical_skills"))
        for item in tech:
            if len(item) > 15 and item not in skills:
                skills.append(item)
    
    if not skills:
        skills = DEFAULT_CORE_SKILLS_LEADER if template_type == "leader" else DEFAULT_CORE_SKILLS_NON_LEADER
    
    return skills[:6]


def _technical_competencies(jd: dict[str, Any]) -> list[str]:
    items = _listify(jd.get("tools_technologies"))
    qualifications = jd.get("required_qualifications")
    if isinstance(qualifications, dict):
        tech_skills = _listify(qualifications.get("technical_skills"))
        for s in tech_skills:
            if len(s) <= 40 and s not in items:
                items.append(s)
    
    deduped: list[str] = []
    for item in items:
        cleaned = item.strip("•- ")
        if cleaned and cleaned not in deduped:
            deduped.append(cleaned)
            
    if not deduped:
        deduped = [
            "Data Center Infrastructure Management",
            "Power & Cooling Systems",
            "Network & Connectivity",
            "Cloud & Hybrid Infrastructure",
            "Security & Compliance",
            "IT Operations & Service Management",
            "Monitoring & DCIM Tools",
            "Vendor & Asset Management",
            "Disaster Recovery & Business Continuity",
            "Virtualization & Systems Knowledge",
        ]
    return deduped[:10]


def _behavioral_competencies(jd: dict[str, Any]) -> list[str]:
    items = _listify(jd.get("soft_skills"))
    deduped: list[str] = []
    for item in items:
        cleaned = item.strip("•- ")
        if cleaned and cleaned not in deduped:
            deduped.append(cleaned)
            
    if not deduped:
        deduped = [
            "Leadership & Team Management",
            "Strategic Thinking",
            "Problem-Solving & Decision-Making",
            "Communication Skills",
            "Time Management & Prioritization",
            "Adaptability & Crisis Management",
            "Collaboration & Stakeholder Management",
            "Attention to Detail",
            "Accountability & Ownership",
        ]
    return deduped[:10]


def _split_responsibilities(
    responsibilities: list[str], template_type: TemplateType
) -> dict[str, list[str]]:
    cleaned = [_safe_str(item) for item in responsibilities if _safe_str(item)]
    if template_type == "non_leader":
        return {"operational": cleaned, "strategic": [], "people": []}

    strategic: list[str] = []
    operational: list[str] = []
    people: list[str] = []

    for item in cleaned:
        lowered = item.lower()
        if any(keyword in lowered for keyword in PEOPLE_KEYWORDS):
            people.append(item)
        elif any(keyword in lowered for keyword in STRATEGIC_KEYWORDS):
            strategic.append(item)
        else:
            operational.append(item)

    if not strategic and cleaned:
        strategic = cleaned[: max(1, len(cleaned) // 4)]
        operational = [item for item in cleaned if item not in strategic and item not in people]

    if not people:
        people = [
            "Foster a collaborative team culture aligned with malomatia values.",
            "Support career planning, coaching, and development for direct reports.",
            "Promote employee engagement, recognition, and continuous improvement.",
        ]

    if not operational and cleaned:
        operational = [item for item in cleaned if item not in strategic and item not in people]

    return {"strategic": strategic, "operational": operational, "people": people}


def _clear_cell(cell) -> None:
    for paragraph in list(cell.paragraphs):
        element = paragraph._element
        element.getparent().remove(element)


def _style_template_paragraph(cell) -> Paragraph | None:
    for paragraph in cell.paragraphs:
        if _safe_str(paragraph.text):
            return paragraph
    return cell.paragraphs[0] if cell.paragraphs else None


def _apply_run_font(run, *, bold: bool = False, size_pt: float = 8.0, color_rgb: RGBColor | None = None) -> None:
    run.font.name = "Georgia"
    run.font.size = Pt(size_pt)
    run.bold = bold
    run.font.color.rgb = color_rgb or RGBColor(0x00, 0x00, 0x00)


def _write_plain_cell(cell, text: str, *, bold: bool = False, size_pt: float = 8.0) -> None:
    template = _style_template_paragraph(cell)
    _clear_cell(cell)
    paragraph = cell.add_paragraph()
    if template is not None and template._p.pPr is not None:
        paragraph._p.insert(0, copy.deepcopy(template._p.pPr))
    run = paragraph.add_run(text or "—")
    _apply_run_font(run, bold=bold, size_pt=size_pt)


def _write_list_cell(cell, items: list[str], *, numbered: bool = False, bullet_prefix: str = "• ") -> None:
    template = _style_template_paragraph(cell)
    _clear_cell(cell)
    if not items:
        paragraph = cell.add_paragraph()
        if template is not None and template._p.pPr is not None:
            paragraph._p.insert(0, copy.deepcopy(template._p.pPr))
        run = paragraph.add_run("—")
        _apply_run_font(run)
        return

    for index, item in enumerate(items, start=1):
        paragraph = cell.add_paragraph()
        if template is not None and template._p.pPr is not None:
            paragraph._p.insert(0, copy.deepcopy(template._p.pPr))
        prefix = f"{index}. " if numbered else bullet_prefix
        run = paragraph.add_run(f"{prefix}{item}")
        _apply_run_font(run)


def _replace_paragraph_text(paragraph: Paragraph, replacements: dict[str, str]) -> None:
    text = paragraph.text
    updated = text
    for old, new in replacements.items():
        if old in updated:
            updated = updated.replace(old, new)
    if updated != text:
        if paragraph.runs:
            paragraph.runs[0].text = updated
            for run in paragraph.runs[1:]:
                run.text = ""
        else:
            paragraph.add_run(updated)


def _replace_document_tokens(doc: DocumentType, replacements: dict[str, str]) -> None:
    for section in doc.sections:
        for p in section.header.paragraphs:
            _replace_paragraph_text(p, replacements)
        for p in section.footer.paragraphs:
            _replace_paragraph_text(p, replacements)
    for p in doc.paragraphs:
        _replace_paragraph_text(p, replacements)


def build_template_context(jd: dict[str, Any], template_type: TemplateType) -> dict[str, Any]:
    hierarchy = _hierarchy_fields(jd)
    job_title = _safe_str(jd.get("job_title")) or "Position Title"
    split = _split_responsibilities(_listify(jd.get("responsibilities")), template_type)
    ref_id = f"JD_{re.sub(r'[^A-Za-z0-9]+', '_', hierarchy['strategic_business_unit'])}_{re.sub(r'[^A-Za-z0-9]+', '_', hierarchy['business_unit'])}_{re.sub(r'[^A-Za-z0-9]+', '_', job_title)}"[:100]
    
    return {
        "job_title": job_title,
        "hierarchy": hierarchy,
        "ref_id": ref_id,
        "header_date": datetime.now().strftime("%B %Y"),
        "position_summary": _safe_str(jd.get("position_summary")) or "—",
        "education": _education_text(jd),
        "experience": _experience_lines(jd, template_type),
        "skills": _job_specific_skills(jd, template_type),
        "technical": _technical_competencies(jd),
        "behavioral": _behavioral_competencies(jd),
        "external": DEFAULT_EXTERNAL,
        "internal": _default_internal_interfaces(jd, hierarchy),
        "split": split,
        "template_type": template_type,
    }


def fill_malomatia_template(doc: DocumentType, jd: dict[str, Any], template_type: TemplateType) -> None:
    ctx = build_template_context(jd, template_type)
    hierarchy = ctx["hierarchy"]
    split = ctx["split"]

    # 1. Replace header tokens if present in header/body
    _replace_document_tokens(
        doc,
        {
            "JD_UNIT/SBU_FUNCTION NAME_POSITION TTLE": ctx["ref_id"],
            "JD_UNIT/SBU_FUNCTION NAME_POSITION TITLE": ctx["ref_id"],
            "JD_Unit/SBU Name_Function Name_Position Title": ctx["ref_id"],
            "Monthxx Yearxx": ctx["header_date"],
            "Version:1": "Version:1",
        },
    )

    if not doc.tables:
        return

    table = doc.tables[0]
    rows = table.rows

    # Row 0: Job Description: {job_title}
    if len(rows) > 0:
        _clear_cell(rows[0].cells[0])
        p_title = rows[0].cells[0].add_paragraph()
        r_prefix = p_title.add_run("Job Description:     ")
        _apply_run_font(r_prefix, bold=True, size_pt=10.0)
        r_title = p_title.add_run(ctx["job_title"])
        _apply_run_font(r_title, bold=True, size_pt=10.0)

    # Hierarchy mapping (Rows 2 to 6/7)
    hierarchy_map = {
        "job title": ctx["job_title"],
        "strategic business unit": hierarchy["strategic_business_unit"],
        "unit/strategic business unit": hierarchy["strategic_business_unit"],
        "business unit": hierarchy["business_unit"],
        "function/business unit": hierarchy["business_unit"],
        "practice unit": hierarchy["practice_unit"],
        "sub function/practice unit": hierarchy["practice_unit"],
        "delivery unit": hierarchy["delivery_unit"],
        "reporting to": hierarchy["reporting_to"],
    }

    for row in rows:
        label = _normalize_label(row.cells[0].text) if row.cells else ""
        for key, val in hierarchy_map.items():
            if label == key and len(row.cells) > 1:
                _write_plain_cell(row.cells[1], val)

    # Role Summary (Row below 'role summary')
    for idx, row in enumerate(rows):
        if _normalize_label(row.cells[0].text) == "role summary" and idx + 1 < len(rows):
            _write_plain_cell(rows[idx + 1].cells[0], ctx["position_summary"])
            break

    # External & Internal Interfaces (Row below interfaces banner)
    for idx, row in enumerate(rows):
        labels = [_normalize_label(c.text) for c in row.cells]
        if "external interfaces" in labels and "internal interfaces" in labels and idx + 1 < len(rows):
            target_row = rows[idx + 1]
            _write_list_cell(target_row.cells[0], ctx["external"])
            int_cell = target_row.cells[2] if len(target_row.cells) > 2 else target_row.cells[1]
            _write_list_cell(int_cell, ctx["internal"])
            break

    # Job Specifications
    specs_map = {
        "desired educational background": lambda c: _write_plain_cell(c, ctx["education"]),
        "language requirement": lambda c: _write_plain_cell(c, DEFAULT_LANGUAGE),
        "desired experience": lambda c: _write_list_cell(c, ctx["experience"]),
        "job specific skills": lambda c: _write_list_cell(c, ctx["skills"]),
    }
    for row in rows:
        label = _normalize_label(row.cells[0].text) if row.cells else ""
        for key, handler in specs_map.items():
            if label == key and len(row.cells) > 1:
                handler(row.cells[1])

    # Competencies (Technical & Behavioral)
    for row in rows:
        label = _normalize_label(row.cells[0].text) if row.cells else ""
        if label == "competencies" and len(row.cells) >= 3:
            # Technical (cells[1])
            _clear_cell(row.cells[1])
            p_tech_hdr = row.cells[1].add_paragraph()
            r_tech = p_tech_hdr.add_run("Technical")
            _apply_run_font(r_tech, bold=True, size_pt=8.0)
            for item in ctx["technical"]:
                p_item = row.cells[1].add_paragraph()
                r_item = p_item.add_run(f"• {item}")
                _apply_run_font(r_item, size_pt=8.0)

            # Behavioral (cells[3] or cells[2])
            beh_cell = row.cells[3] if len(row.cells) > 3 else row.cells[2]
            _clear_cell(beh_cell)
            p_beh_hdr = beh_cell.add_paragraph()
            r_beh = p_beh_hdr.add_run("Behavioral")
            _apply_run_font(r_beh, bold=True, size_pt=8.0)
            for item in ctx["behavioral"]:
                p_item = beh_cell.add_paragraph()
                r_item = p_item.add_run(f"• {item}")
                _apply_run_font(r_item, size_pt=8.0)
            break

    # Roles & Responsibilities Section
    if template_type == "leader":
        # Check if template has distinct Strategic / Operational / People Management sub-headers
        has_subheaders = False
        for idx, row in enumerate(rows):
            label = _normalize_label(row.cells[0].text) if row.cells else ""
            if label == "strategic" and idx + 1 < len(rows):
                has_subheaders = True
                _write_list_cell(rows[idx + 1].cells[0], split["strategic"] or ["Define and execute strategic priorities aligned with business goals."], numbered=True)
            elif label == "operational" and idx + 1 < len(rows):
                _write_list_cell(rows[idx + 1].cells[0], split["operational"] or ["Oversee operational execution, SLAs, and service delivery excellence."], numbered=True)
            elif label == "people management" and idx + 1 < len(rows):
                pm_cell = rows[idx + 1].cells[0]
                _clear_cell(pm_cell)
                
                # Culture
                p1 = pm_cell.add_paragraph()
                r1 = p1.add_run("Culture")
                _apply_run_font(r1, bold=True, size_pt=8.0)
                for item in (split["people"][:1] or ["Champion malomatia culture and values within the team."]):
                    p = pm_cell.add_paragraph()
                    r = p.add_run(f"1. {item}")
                    _apply_run_font(r, size_pt=8.0)
                
                # Career Planning & Development
                p2 = pm_cell.add_paragraph()
                r2 = p2.add_run("Career Planning & Development")
                _apply_run_font(r2, bold=True, size_pt=8.0)
                for item in (split["people"][1:2] or ["Coach and develop team members to meet performance and career goals."]):
                    p = pm_cell.add_paragraph()
                    r = p.add_run(f"1. {item}")
                    _apply_run_font(r, size_pt=8.0)
                    
                # Employee Engagement
                p3 = pm_cell.add_paragraph()
                r3 = p3.add_run("Employee Engagement")
                _apply_run_font(r3, bold=True, size_pt=8.0)
                for item in (split["people"][2:3] or ["Drive employee engagement, recognition, and continuous improvement."]):
                    p = pm_cell.add_paragraph()
                    r = p.add_run(f"1. {item}")
                    _apply_run_font(r, size_pt=8.0)
                    
        # If Leader template has single Roles & Responsibilities row (like the completed Data Center Manager reference)
        if not has_subheaders:
            for idx, row in enumerate(rows):
                label = _normalize_label(row.cells[0].text) if row.cells else ""
                if label == "roles & responsibilities" and idx + 1 < len(rows):
                    leader_resp = split["strategic"] + split["operational"]
                    _write_list_cell(rows[idx + 1].cells[0], leader_resp or ["Execute strategic leadership and operational management."], numbered=True)
                    break
    else:
        # Non-Leader: Operational duties list ending with "Other duties as assigned."
        for idx, row in enumerate(rows):
            label = _normalize_label(row.cells[0].text) if row.cells else ""
            if label in ("operational", "roles & responsibilities") and idx + 1 < len(rows):
                numbered = list(split["operational"] or ["Perform assigned operational duties for the role."])
                if "Other duties as assigned." not in numbered:
                    numbered.append("Other duties as assigned.")
                _write_list_cell(rows[idx + 1].cells[0], numbered, numbered=True)
                break


def render_malomatia_docx_from_template(jd: dict[str, Any], template_type: TemplateType) -> bytes:
    template_path = resolve_template_path(template_type)
    doc = Document(str(template_path))
    fill_malomatia_template(doc, jd, template_type)
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
