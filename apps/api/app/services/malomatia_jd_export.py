"""Export QuantHire enterprise JDs to official Malomatia Word templates."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from app.services.malomatia_template_fill import (
    MalomatiaTemplateNotFoundError,
    render_malomatia_docx_from_template,
)

TemplateType = Literal["leader", "non_leader"]

LEADER_YOE_THRESHOLD = 10

__all__ = [
    "LEADER_YOE_THRESHOLD",
    "MalomatiaTemplateNotFoundError",
    "TemplateRecommendation",
    "TemplateType",
    "build_download_filename",
    "build_malomatia_docx",
    "collect_yoe_source_text",
    "parse_yoe_details",
    "recommend_malomatia_template",
]


@dataclass
class YoeParseResult:
    minimum: int | None
    maximum: int | None
    has_plus: bool
    source_text: str


@dataclass
class TemplateRecommendation:
    template_type: TemplateType | None
    confidence: Literal["high", "ambiguous", "missing"]
    reason: str
    yoe_text: str
    yoe_minimum: int | None = None
    yoe_maximum: int | None = None


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def collect_yoe_source_text(jd: dict[str, Any]) -> str:
    parts: list[str] = []
    meta = jd.get("metadata")
    if isinstance(meta, dict):
        for key in ("years_of_experience",):
            if meta.get(key):
                parts.append(_safe_str(meta[key]))
        hr_inputs = meta.get("hr_inputs")
        if isinstance(hr_inputs, dict) and hr_inputs.get("years_of_experience"):
            parts.append(_safe_str(hr_inputs["years_of_experience"]))
        dialog_inputs = meta.get("dialog_inputs")
        if isinstance(dialog_inputs, dict) and dialog_inputs.get("years_of_experience"):
            parts.append(_safe_str(dialog_inputs["years_of_experience"]))

    qualifications = jd.get("required_qualifications")
    if isinstance(qualifications, dict) and qualifications.get("experience"):
        parts.append(_safe_str(qualifications["experience"]))

    return " ".join(p for p in parts if p)


def parse_yoe_details(text: str) -> YoeParseResult | None:
    cleaned = _safe_str(text)
    if not cleaned:
        return None

    numbers = [int(n) for n in re.findall(r"\d+", cleaned)]
    if not numbers:
        return None

    has_plus = bool(re.search(r"\d+\s*\+", cleaned, re.I))
    range_match = re.search(r"(\d+)\s*[-–—to]+\s*(\d+)", cleaned, re.I)
    if range_match:
        low = int(range_match.group(1))
        high = int(range_match.group(2))
        return YoeParseResult(minimum=low, maximum=high, has_plus=has_plus, source_text=cleaned)

    value = numbers[0]
    return YoeParseResult(
        minimum=value,
        maximum=value if not has_plus else None,
        has_plus=has_plus,
        source_text=cleaned,
    )


def recommend_malomatia_template(jd: dict[str, Any]) -> TemplateRecommendation:
    yoe_text = collect_yoe_source_text(jd)
    parsed = parse_yoe_details(yoe_text)
    if parsed is None:
        return TemplateRecommendation(
            template_type=None,
            confidence="missing",
            reason="Years of experience not found in the job description.",
            yoe_text=yoe_text,
        )

    minimum = parsed.minimum
    maximum = parsed.maximum if parsed.maximum is not None else parsed.minimum

    if parsed.has_plus and minimum is not None and minimum >= LEADER_YOE_THRESHOLD:
        return TemplateRecommendation(
            template_type="leader",
            confidence="high",
            reason=f"Detected {minimum}+ years of experience (Leader threshold is {LEADER_YOE_THRESHOLD}+).",
            yoe_text=yoe_text,
            yoe_minimum=minimum,
            yoe_maximum=maximum,
        )

    if minimum is not None and maximum is not None:
        if minimum >= LEADER_YOE_THRESHOLD:
            return TemplateRecommendation(
                template_type="leader",
                confidence="high",
                reason=f"Detected {minimum}–{maximum} years of experience.",
                yoe_text=yoe_text,
                yoe_minimum=minimum,
                yoe_maximum=maximum,
            )
        if maximum < LEADER_YOE_THRESHOLD:
            return TemplateRecommendation(
                template_type="non_leader",
                confidence="high",
                reason=f"Detected {minimum}–{maximum} years of experience (below {LEADER_YOE_THRESHOLD}).",
                yoe_text=yoe_text,
                yoe_minimum=minimum,
                yoe_maximum=maximum,
            )
        return TemplateRecommendation(
            template_type="leader",
            confidence="ambiguous",
            reason=(
                f"Experience range {minimum}–{maximum} crosses the {LEADER_YOE_THRESHOLD}-year Leader threshold. "
                "Please confirm the template."
            ),
            yoe_text=yoe_text,
            yoe_minimum=minimum,
            yoe_maximum=maximum,
        )

    if minimum is not None:
        if minimum >= LEADER_YOE_THRESHOLD:
            template: TemplateType = "leader"
            reason = f"Detected {minimum}+ years of experience."
        else:
            template = "non_leader"
            reason = f"Detected {minimum} years of experience (below {LEADER_YOE_THRESHOLD})."
        return TemplateRecommendation(
            template_type=template,
            confidence="high",
            reason=reason,
            yoe_text=yoe_text,
            yoe_minimum=minimum,
            yoe_maximum=maximum,
        )

    return TemplateRecommendation(
        template_type=None,
        confidence="missing",
        reason="Could not parse years of experience.",
        yoe_text=yoe_text,
    )


def build_malomatia_docx(jd: dict[str, Any], template_type: TemplateType) -> bytes:
    """Render JD by filling the official Malomatia .docx template (preserves layout)."""
    return render_malomatia_docx_from_template(jd, template_type)


def build_download_filename(jd: dict[str, Any], template_type: TemplateType) -> str:
    title = _safe_str(jd.get("job_title")) or "Job_Description"
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", title).strip("_") or "Job_Description"
    suffix = "Leader" if template_type == "leader" else "NonLeader"
    return f"{safe}_Malomatia_{suffix}.docx"
