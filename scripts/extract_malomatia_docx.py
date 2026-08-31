"""Extract and compare Malomatia JD docx templates via word/document.xml.

Usage (Command Prompt):
    python scripts/extract_malomatia_docx.py

Writes: tests/fixtures/malomatia_docx_extract.json
"""
from __future__ import annotations

import json
import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = REPO_ROOT / "tests" / "fixtures" / "malomatia_docx_extract.json"

FILES = {
    "data_center_manager": Path(
        r"c:\Users\prakumar\Downloads\Data Center Manager JD (1).docx"
    ),
    "leader_template": Path(
        r"c:\Users\prakumar\Downloads\JD Template_Leader position (1).docx"
    ),
    "non_leader_template": Path(
        r"c:\Users\prakumar\Downloads\JD Template_Non-Leader position (2).docx"
    ),
}

SECTION_RE = re.compile(
    r"^(\d+(?:\.\d+)*)[\.\)]\s+(.+)$|^(Section\s+\d+[:\.]?\s*.+)$",
    re.I,
)
YOE_RE = re.compile(
    r"(\d+\+?\s*(?:years?|yrs?\.?)(?:\s+of\s+)?(?:relevant\s+)?(?:experience|exp\.?)"
    r"|\d+\s*[-–—to]+\s*\d+\s*(?:years?|yrs?)"
    r"(?:minimum|min\.?|at least)\s+\d+\s*(?:years?|yrs?)"
    r"|(?:years?|yrs?)\s*(?:of\s+)?(?:experience|exp\.?).*?\d+)",
    re.I,
)
PLACEHOLDER_RE = re.compile(
    r"\[[^\]]+\]|\{[^}]+\}|<[^>]+>|_{3,}|\.{3,}|"
    r"\b(TBD|INSERT|PLACEHOLDER|XXX+|e\.g\.|example|sample text|to be confirmed|"
    r"enter job title|enter department|add here)\b",
    re.I,
)


@dataclass
class Paragraph:
    index: int
    text: str
    style: str | None = None
    is_bullet: bool = False
    is_numbered_section: bool = False
    section_number: str | None = None
    section_title: str | None = None
    has_placeholder: bool = False
    yoe_mentions: list[str] = field(default_factory=list)


@dataclass
class DocAnalysis:
    file_key: str
    file_name: str
    exists: bool
    paragraphs: list[Paragraph] = field(default_factory=list)
    section_headings: list[dict[str, str]] = field(default_factory=list)
    yoe_all: list[str] = field(default_factory=list)
    placeholders: list[str] = field(default_factory=list)
    filled_samples: list[str] = field(default_factory=list)
    error: str | None = None


def _paragraph_style(p: ET.Element) -> str | None:
    p_pr = p.find("w:pPr", NS)
    if p_pr is None:
        return None
    p_style = p_pr.find("w:pStyle", NS)
    if p_style is None:
        return None
    return p_style.get(f"{{{W_NS}}}val")


def _is_bullet(p: ET.Element, text: str) -> bool:
    p_pr = p.find("w:pPr", NS)
    if p_pr is not None and p_pr.find("w:numPr", NS) is not None:
        return True
    return bool(re.match(r"^[\u2022\u2023\u25E6\u2043\-\*•·]\s+", text)) or bool(
        re.match(r"^[a-z]\)\s+", text, re.I)
    )


def _parse_section(text: str) -> tuple[str | None, str | None]:
    m = SECTION_RE.match(text.strip())
    if not m:
        return None, None
    if m.group(1):
        return m.group(1), m.group(2).strip()
    return None, m.group(3).strip()


def extract_docx(path: Path) -> list[Paragraph]:
    with zipfile.ZipFile(path, "r") as zf:
        xml = zf.read("word/document.xml")
    root = ET.fromstring(xml)

    out: list[Paragraph] = []
    idx = 0
    for p in root.iter(f"{{{W_NS}}}p"):
        parts: list[str] = []
        for node in p.iter(f"{{{W_NS}}}t"):
            if node.text:
                parts.append(node.text)
            if node.tail:
                parts.append(node.tail)
        text = "".join(parts).strip()
        if not text:
            continue
        idx += 1
        sec_num, sec_title = _parse_section(text)
        yoe = YOE_RE.findall(text)
        out.append(
            Paragraph(
                index=idx,
                text=text,
                style=_paragraph_style(p),
                is_bullet=_is_bullet(p, text),
                is_numbered_section=sec_num is not None or sec_title is not None,
                section_number=sec_num,
                section_title=sec_title,
                has_placeholder=bool(PLACEHOLDER_RE.search(text)),
                yoe_mentions=yoe,
            )
        )
    return out


def analyze_file(file_key: str, path: Path) -> DocAnalysis:
    if not path.is_file():
        return DocAnalysis(
            file_key=file_key,
            file_name=path.name,
            exists=False,
            error=f"File not found: {path}",
        )

    try:
        paragraphs = extract_docx(path)
    except Exception as exc:  # noqa: BLE001
        return DocAnalysis(
            file_key=file_key,
            file_name=path.name,
            exists=True,
            error=str(exc),
        )

    section_headings: list[dict[str, str]] = []
    yoe_all: list[str] = []
    placeholders: list[str] = []
    filled: list[str] = []

    for p in paragraphs:
        yoe_all.extend(p.yoe_mentions)
        if p.has_placeholder:
            placeholders.append(p.text)
        elif len(p.text) > 25 and not p.is_numbered_section and not p.is_bullet:
            filled.append(p.text)

        if p.is_numbered_section:
            section_headings.append(
                {
                    "number": p.section_number or "",
                    "title": p.section_title or p.text,
                    "raw": p.text,
                }
            )

    return DocAnalysis(
        file_key=file_key,
        file_name=path.name,
        exists=True,
        paragraphs=paragraphs,
        section_headings=section_headings,
        yoe_all=list(dict.fromkeys(yoe_all)),
        placeholders=placeholders,
        filled_samples=filled[:20],
    )


def compare_templates(
    leader: DocAnalysis, non_leader: DocAnalysis
) -> dict[str, Any]:
    leader_texts = {p.text for p in leader.paragraphs}
    non_leader_texts = {p.text for p in non_leader.paragraphs}

    leader_sections = [h["raw"] for h in leader.section_headings]
    non_leader_sections = [h["raw"] for h in non_leader.section_headings]

    return {
        "leader_only_sections": [
            s for s in leader_sections if s not in non_leader_sections
        ],
        "non_leader_only_sections": [
            s for s in non_leader_sections if s not in leader_sections
        ],
        "shared_sections": [
            s for s in leader_sections if s in non_leader_sections
        ],
        "leader_only_paragraphs_count": len(leader_texts - non_leader_texts),
        "non_leader_only_paragraphs_count": len(non_leader_texts - leader_texts),
        "leader_only_paragraph_samples": sorted(leader_texts - non_leader_texts)[:30],
        "non_leader_only_paragraph_samples": sorted(non_leader_texts - leader_texts)[
            :30
        ],
    }


def map_dcm_to_template(
    dcm: DocAnalysis, template: DocAnalysis
) -> list[dict[str, str]]:
    mapping: list[dict[str, str]] = []
    dcm_sections = {h["number"]: h for h in dcm.section_headings if h["number"]}
    tmpl_sections = {h["number"]: h for h in template.section_headings if h["number"]}

    for num in sorted(set(dcm_sections) | set(tmpl_sections), key=lambda x: int(x.split(".")[0])):
        dcm_h = dcm_sections.get(num)
        tmpl_h = tmpl_sections.get(num)
        mapping.append(
            {
                "section_number": num,
                "template_heading": tmpl_h["raw"] if tmpl_h else "(missing in template)",
                "dcm_heading": dcm_h["raw"] if dcm_h else "(missing in DCM JD)",
                "match": "yes"
                if dcm_h and tmpl_h and dcm_h["title"] == tmpl_h["title"]
                else "partial"
                if dcm_h and tmpl_h
                else "missing",
            }
        )
    return mapping


def main() -> None:
    results = {key: analyze_file(key, path) for key, path in FILES.items()}

    leader = results["leader_template"]
    non_leader = results["non_leader_template"]
    dcm = results["data_center_manager"]

    payload = {
        "files": {
            key: {
                **{k: v for k, v in asdict(doc).items() if k != "paragraphs"},
                "paragraphs": [asdict(p) for p in doc.paragraphs],
            }
            for key, doc in results.items()
        },
        "comparison": compare_templates(leader, non_leader)
        if leader.paragraphs and non_leader.paragraphs
        else {},
        "dcm_to_leader_mapping": map_dcm_to_template(dcm, leader)
        if dcm.paragraphs and leader.paragraphs
        else [],
        "dcm_to_non_leader_mapping": map_dcm_to_template(dcm, non_leader)
        if dcm.paragraphs and non_leader.paragraphs
        else [],
    }

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Wrote {OUTPUT_JSON}")
    for key, doc in results.items():
        print(f"\n{'=' * 80}\n{key.upper()} — {doc.file_name}\n{'=' * 80}")
        if doc.error:
            print(f"ERROR: {doc.error}")
            continue
        for p in doc.paragraphs:
            style = f" [{p.style}]" if p.style else ""
            print(f"{p.index:3d}{style}: {p.text}")
        print(f"\nSections ({len(doc.section_headings)}):")
        for h in doc.section_headings:
            print(f"  • {h['raw']}")
        print(f"YOE: {doc.yoe_all or '(none)'}")
        print(f"Placeholders ({len(doc.placeholders)}):")
        for ph in doc.placeholders:
            print(f"  • {ph}")


if __name__ == "__main__":
    main()
