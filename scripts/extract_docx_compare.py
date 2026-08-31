"""Extract and compare JD docx files via word/document.xml."""
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}


def extract_docx(path: str) -> list[dict]:
    path = Path(path)
    with zipfile.ZipFile(path, "r") as z:
        xml = z.read("word/document.xml")
    root = ET.fromstring(xml)

    paragraphs = []
    for p in root.iter(f"{{{W_NS}}}p"):
        texts = []
        for t in p.iter(f"{{{W_NS}}}t"):
            if t.text:
                texts.append(t.text)
            if t.tail:
                texts.append(t.tail)
        text = "".join(texts).strip()
        if not text:
            continue

        style = None
        p_pr = p.find("w:pPr", NS)
        if p_pr is not None:
            p_style = p_pr.find("w:pStyle", NS)
            if p_style is not None:
                style = p_style.get(f"{{{W_NS}}}val")

        paragraphs.append({"text": text, "style": style})
    return paragraphs


def is_numbered_section(text: str) -> bool:
    return bool(re.match(r"^\d+(\.\d+)*[\.\)]?\s+", text))


def is_placeholder(text: str) -> bool:
    patterns = [
        r"\[.*?\]",
        r"\{.*?\}",
        r"<.*?>",
        r"XXX+",
        r"TBD",
        r"INSERT",
        r"PLACEHOLDER",
        r"e\.g\.",
        r"example",
        r"\.\.\.",
        r"___+",
    ]
    lower = text.lower()
    return any(re.search(p, text, re.I) for p in patterns) or "xxx" in lower


def find_yoe(text: str) -> list[str]:
    patterns = [
        r"\d+\+?\s*(?:years?|yrs?\.?)\s*(?:of\s+)?(?:experience|exp\.?)",
        r"(?:minimum|min\.?|at least)\s+\d+\s*(?:years?|yrs?)",
        r"\d+\s*-\s*\d+\s*(?:years?|yrs?)",
        r"(?:years?|yrs?)\s*(?:of\s+)?(?:experience|exp\.?).*?\d+",
    ]
    hits = []
    for p in patterns:
        hits.extend(re.findall(p, text, re.I))
    return hits


def analyze(paragraphs: list[dict]) -> dict:
    sections = []
    bullets = []
    placeholders = []
    filled = []
    yoe_all = []

    for p in paragraphs:
        text = p["text"]
        yoe = find_yoe(text)
        yoe_all.extend(yoe)

        if is_numbered_section(text) or (p["style"] and "Heading" in (p["style"] or "")):
            sections.append(text)

        if text.startswith(("-", "•", "·", "◦")) or re.match(r"^[a-z]\)", text):
            bullets.append(text)

        if is_placeholder(text):
            placeholders.append(text)
        elif len(text) > 20 and not is_numbered_section(text):
            filled.append(text)

    return {
        "sections": sections,
        "bullets": bullets,
        "placeholders": placeholders,
        "filled_samples": filled[:15],
        "yoe": list(dict.fromkeys(yoe_all)),
        "all_text": [p["text"] for p in paragraphs],
    }


FILES = {
    "data_center_manager": r"c:\Users\prakumar\Downloads\Data Center Manager JD (1).docx",
    "leader_template": r"c:\Users\prakumar\Downloads\JD Template_Leader position (1).docx",
    "non_leader_template": r"c:\Users\prakumar\Downloads\JD Template_Non-Leader position (2).docx",
}


def main():
    results = {}
    for key, path in FILES.items():
        print(f"\n{'='*80}\n{key.upper()}: {Path(path).name}\n{'='*80}")
        paras = extract_docx(path)
        analysis = analyze(paras)
        results[key] = {"paragraphs": paras, "analysis": analysis}

        print(f"\n--- FULL TEXT ({len(paras)} paragraphs) ---")
        for i, p in enumerate(paras, 1):
            style = f" [{p['style']}]" if p["style"] else ""
            print(f"{i:3d}{style}: {p['text']}")

        print(f"\n--- NUMBERED SECTIONS ({len(analysis['sections'])}) ---")
        for s in analysis["sections"]:
            print(f"  • {s}")

        print(f"\n--- YOE MENTIONS ---")
        for y in analysis["yoe"]:
            print(f"  • {y}")
        if not analysis["yoe"]:
            print("  (none found)")

        print(f"\n--- PLACEHOLDERS ({len(analysis['placeholders'])}) ---")
        for ph in analysis["placeholders"]:
            print(f"  • {ph}")

    # Comparison output
    print(f"\n{'='*80}\nCOMPARISON SUMMARY\n{'='*80}")

    leader_secs = set(results["leader_template"]["analysis"]["sections"])
    non_leader_secs = set(results["non_leader_template"]["analysis"]["sections"])
    dcm_secs = results["data_center_manager"]["analysis"]["sections"]

    print("\n--- Leader-only sections ---")
    for s in sorted(leader_secs - non_leader_secs):
        print(f"  • {s}")

    print("\n--- Non-Leader-only sections ---")
    for s in sorted(non_leader_secs - leader_secs):
        print(f"  • {s}")

    print("\n--- Shared template sections ---")
    for s in sorted(leader_secs & non_leader_secs):
        print(f"  • {s}")

    print("\n--- Data Center Manager section mapping ---")
    for s in dcm_secs:
        in_leader = any(s.split()[0] == ls.split()[0] for ls in leader_secs) if s else False
        print(f"  • {s}")

    return results


if __name__ == "__main__":
    main()
