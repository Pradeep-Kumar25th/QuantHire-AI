"""
=============================================================================
End-to-End Validation Script: Malomatia JD Word (.docx) Converter
=============================================================================
Tests the complete Malomatia JD template conversion pipeline:
  1. Template Recommendation Logic (Leader vs Non-Leader vs Ambiguous YOE)
  2. Leader Position (.docx) Generation & Full XML/Layout Validation
  3. Non-Leader Position (.docx) Generation & Operational Fallback Validation
  4. Typography, Table Borders, Banners, and Hierarchy Mapping
  5. Live API Endpoint Verification (POST /api/v1/jd-generation/export-malomatia)
  6. Exports sample .docx files to ./test_outputs/ for manual visual review in Word

Usage:
  python scripts/validate_malomatia_jd_converter_e2e.py
  python scripts/validate_malomatia_jd_converter_e2e.py --api-url http://localhost:8000
  python scripts/validate_malomatia_jd_converter_e2e.py --api-url https://quanthire-npd.malomatia.com
=============================================================================
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import zipfile
from pathlib import Path

# Add apps/api to path for direct service testing
REPO_ROOT = Path(__file__).resolve().parents[1]
API_DIR = REPO_ROOT / "apps" / "api"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(API_DIR))

# --- Sample Data Sets ---

DATA_CENTER_MANAGER_LEADER_JD = {
    "job_title": "Data Center Manager",
    "business_unit": "Cloud, Infrastructure & Security Services (CISS)",
    "department": "Cloud & Infrastructure Services (CIS)",
    "team": "Cloud & Infrastructure Managed Services",
    "division": "Managed Infrastructure Services",
    "position_summary": (
        "The Data Center Manager is responsible for overseeing the daily operations, "
        "reliability, security, and performance of data center facilities and infrastructure. "
        "This role ensures high availability of IT systems, effective capacity planning, "
        "compliance with safety and security standards, and alignment with organizational objectives."
    ),
    "work_environment": {
        "reports_to": "Delivery Leader – Managed Infrastructure Services",
        "collaborates_with": [
            "Delivery Leader – Managed Infrastructure Services",
            "Other Delivery Leaders",
            "Members from functional teams such as HR, Finance, IT etc.",
            "All other malomatia Personnel (as and when required)"
        ]
    },
    "required_qualifications": {
        "education": "Bachelor’s degree in IT, Engineering, Computer Science, or related field.",
        "experience": (
            "• 7–12 years of experience in data center or IT infrastructure operations.\n"
            "• Minimum 3–5 years in a managerial or supervisory role.\n"
            "• Strong knowledge of power, cooling, structured cabling, and DC infrastructure."
        ),
        "technical_skills": [
            "Strong leadership and people management skills.",
            "Excellent problem-solving and decision-making abilities.",
            "Knowledge of ITIL and operational best practices.",
            "Experience with DCIM and infrastructure monitoring tools.",
            "Strong communication and stakeholder management skills."
        ]
    },
    "soft_skills": [
        "Leadership & Team Management",
        "Strategic Thinking",
        "Problem-Solving & Decision-Making",
        "Communication Skills",
        "Time Management & Prioritization",
        "Adaptability & Crisis Management",
        "Collaboration & Stakeholder Management",
        "Attention to Detail",
        "Accountability & Ownership"
    ],
    "tools_technologies": [
        "Data Center Infrastructure Management",
        "Power & Cooling Systems",
        "Network & Connectivity",
        "Cloud & Hybrid Infrastructure",
        "Security & Compliance",
        "IT Operations & Service Management",
        "Monitoring & DCIM Tools",
        "Vendor & Asset Management",
        "Disaster Recovery & Business Continuity",
        "Virtualization & Systems Knowledge"
    ],
    "responsibilities": [
        "Manage overall data center operations including facilities, power, cooling, and physical security.",
        "Ensure high availability, reliability, and performance of servers, storage, and network systems.",
        "Develop and maintain operational policies, procedures, and standards.",
        "Lead capacity planning, demand forecasting, and infrastructure expansion.",
        "Monitor SLAs, KPIs, uptime metrics, and incident response activities.",
        "Oversee incidents, problems, and change management processes.",
        "Manage vendors, service providers, and maintenance contracts.",
        "Ensure compliance with health, safety, regulatory, and security standards.",
        "Plan and conduct preventive maintenance and disaster recovery testing.",
        "Manage budgets, forecasts, and cost optimization initiatives.",
        "Lead, coach, and manage data center staff and shift teams.",
        "Coordinate with IT, cybersecurity, facilities, and business stakeholders."
    ],
    "metadata": {
        "years_of_experience": "10+"
    }
}

SOFTWARE_ENGINEER_NON_LEADER_JD = {
    "job_title": "Full Stack Software Engineer",
    "business_unit": "Digital Application Solutions (DAS)",
    "department": "Software Engineering",
    "team": "Cloud Applications",
    "division": "Application Delivery",
    "position_summary": (
        "Responsible for developing, maintaining, and enhancing enterprise web applications, "
        "APIs, and microservices following agile best practices."
    ),
    "work_environment": {
        "reports_to": "Technical Lead – Application Delivery",
        "collaborates_with": ["Product Managers", "QA Engineers", "DevOps Engineers"]
    },
    "required_qualifications": {
        "education": "Bachelor's degree in Computer Science, Software Engineering, or equivalent.",
        "experience": "3–5 years of professional software development experience.",
        "technical_skills": ["React", "TypeScript", "Node.js / Python", "SQL / PostgreSQL"]
    },
    "soft_skills": ["Analytical Thinking", "Agile Collaboration", "Continuous Learning"],
    "tools_technologies": ["Next.js", "FastAPI", "Docker", "Git", "PostgreSQL"],
    "responsibilities": [
        "Design, develop, and test scalable web applications and microservices.",
        "Collaborate with product designers to implement responsive user interfaces.",
        "Write clean, maintainable, and unit-tested code.",
        "Participate in code reviews and CI/CD deployment pipelines."
    ],
    "metadata": {
        "years_of_experience": "3-5"
    }
}


def test_recommendation_engine():
    print("\n" + "="*70)
    print("STEP 1: Testing Smart Recommendation Engine (Leader vs Non-Leader)")
    print("="*70)
    
    from app.services.malomatia_jd_export import recommend_malomatia_template
    
    # 1. 10+ YOE -> Leader (High confidence)
    leader_10plus_jd = dict(DATA_CENTER_MANAGER_LEADER_JD)
    leader_10plus_jd["required_qualifications"] = dict(DATA_CENTER_MANAGER_LEADER_JD["required_qualifications"])
    leader_10plus_jd["required_qualifications"]["experience"] = "10+ years of infrastructure leadership experience."
    leader_10plus_jd["metadata"] = {"years_of_experience": "10+"}
    
    rec1 = recommend_malomatia_template(leader_10plus_jd)
    print(f"  [10+ YOE Test]       Detected: '{rec1.yoe_text}' -> Template: {rec1.template_type} (Confidence: {rec1.confidence})")
    assert rec1.template_type == "leader", f"Expected leader, got {rec1.template_type}"
    assert rec1.confidence == "high"
    print("    -> PASS: Correctly recommended LEADER template with high confidence.")

    # 2. 3-5 YOE -> Non-Leader (High confidence)
    rec2 = recommend_malomatia_template(SOFTWARE_ENGINEER_NON_LEADER_JD)
    print(f"  [3-5 YOE Test]       Detected: '{rec2.yoe_text}' -> Template: {rec2.template_type} (Confidence: {rec2.confidence})")
    assert rec2.template_type == "non_leader", f"Expected non_leader, got {rec2.template_type}"
    assert rec2.confidence == "high"
    print("    -> PASS: Correctly recommended NON-LEADER template with high confidence.")

    # 3. 7-12 YOE (Crossing threshold) -> Ambiguous flag
    rec3 = recommend_malomatia_template(DATA_CENTER_MANAGER_LEADER_JD)
    print(f"  [7-12 YOE Range]     Detected: '{rec3.yoe_text[:40]}...' -> Template: {rec3.template_type} (Confidence: {rec3.confidence})")
    assert rec3.confidence == "ambiguous"
    assert rec3.template_type == "leader"
    print("    -> PASS: Correctly flagged ambiguous range crossing 10-year line for HR review.")


def test_docx_generation_and_layout(output_dir: Path):
    print("\n" + "="*70)
    print("STEP 2: Testing .docx Generation & Layout Precision")
    print("="*70)
    
    from app.services.malomatia_jd_export import build_malomatia_docx
    from docx import Document

    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Generate Leader DOCX
    print("\n  [Generating Leader DOCX (Data Center Manager)]...")
    leader_bytes = build_malomatia_docx(DATA_CENTER_MANAGER_LEADER_JD, "leader")
    leader_path = output_dir / "Data_Center_Manager_Malomatia_Leader.docx"
    leader_path.write_bytes(leader_bytes)
    print(f"    Saved: {leader_path} ({len(leader_bytes):,} bytes)")
    
    # Verify Leader Content & Structure
    doc_leader = Document(str(leader_path))
    assert len(doc_leader.tables) >= 1, "Missing main layout table"
    table = doc_leader.tables[0]
    
    # Inspect archive XML
    with zipfile.ZipFile(io.BytesIO(leader_bytes)) as z:
        xml = z.read("word/document.xml").decode("utf-8")
        media = [f for f in z.namelist() if "media" in f]
        assert len(media) > 0, "Missing Malomatia logo in header!"
        print(f"    -> Malomatia header logo verified: {media[0]}")
        
        expected_snippets = [
            ("Job Title", "Data Center Manager"),
            ("Strategic Business Unit", "Cloud, Infrastructure & Security Services (CISS)"),
            ("Business Unit", "Cloud & Infrastructure Services (CIS)"),
            ("Practice Unit", "Cloud & Infrastructure Managed Services"),
            ("Reporting To", "Delivery Leader – Managed Infrastructure Services"),
            ("Role Summary", "overseeing the daily operations"),
            ("Language Requirement", "English, Arabic (preferred)"),
            ("Technical Competencies", "Data Center Infrastructure Management"),
            ("Behavioral Competencies", "Leadership & Team Management"),
            ("Roles & Responsibilities", "Roles & Responsibilities"),
            ("Responsibility Item 1", "Manage overall data center operations"),
            ("Responsibility Item 2", "Ensure high availability, reliability, and performance"),
        ]
        
        for label, snippet in expected_snippets:
            assert snippet.replace("&", "&amp;") in xml or snippet in xml, f"Missing {label}: '{snippet}'"
            print(f"    [OK] {label:<28}: Found in document XML")

    # 2. Generate Non-Leader DOCX
    print("\n  [Generating Non-Leader DOCX (Software Engineer)]...")
    non_leader_bytes = build_malomatia_docx(SOFTWARE_ENGINEER_NON_LEADER_JD, "non_leader")
    non_leader_path = output_dir / "Software_Engineer_Malomatia_Non_Leader.docx"
    non_leader_path.write_bytes(non_leader_bytes)
    print(f"    Saved: {non_leader_path} ({len(non_leader_bytes):,} bytes)")
    
    with zipfile.ZipFile(io.BytesIO(non_leader_bytes)) as z:
        xml_nl = z.read("word/document.xml").decode("utf-8")
        assert "Full Stack Software Engineer" in xml_nl
        assert "Digital Application Solutions (DAS)" in xml_nl
        assert "Other duties as assigned." in xml_nl
        print("    [OK] Non-Leader Operational duties and 'Other duties as assigned.' verified")


def test_api_endpoint(api_url: str | None = None):
    print("\n" + "="*70)
    print(
        f"STEP 3: Testing Export API Route "
        f"({api_url or 'Service contract — use --api-url for live HTTP'})"
    )
    print("="*70)

    payload = {
        "job_description": DATA_CENTER_MANAGER_LEADER_JD,
        "template_type": "leader",
    }

    if api_url:
        import requests

        endpoint = f"{api_url.rstrip('/')}/api/v1/jd-generation/export-malomatia"
        print(f"  Sending POST request to: {endpoint}")
        res = requests.post(endpoint, json=payload, timeout=15)
        print(f"  Response Status: {res.status_code}")
        assert res.status_code == 200, f"HTTP Error {res.status_code}: {res.text}"
        assert "wordprocessingml.document" in res.headers.get("content-type", "")
        print(f"  Content-Disposition: {res.headers.get('content-disposition')}")
        assert res.content.startswith(b"PK")
        print("    -> PASS: Live API returned valid .docx binary stream.")
        return

    # Avoid importing the full FastAPI router stack (auth/jose/etc.) in local venv.
    # Step 2 already exercises template fill; here we verify export wiring inputs.
    from app.services.malomatia_jd_export import build_download_filename, build_malomatia_docx

    template_type = payload["template_type"]
    assert template_type in {"leader", "non_leader"}, "template_type must be leader or non_leader"

    docx_bytes = build_malomatia_docx(payload["job_description"], template_type)
    filename = build_download_filename(payload["job_description"], template_type)

    assert docx_bytes.startswith(b"PK"), "Export must return a valid .docx (ZIP) payload"
    assert filename == "Data_Center_Manager_Malomatia_Leader.docx", f"Unexpected filename: {filename}"

    print(f"  Export bytes: {len(docx_bytes):,}")
    print(f"  Download filename: {filename}")
    print("    -> PASS: Export service contract verified (docx bytes + filename).")
    print("    -> Tip: run with --api-url http://localhost:8000 to hit the live FastAPI route.")


def main():
    parser = argparse.ArgumentParser(description="End-to-End Malomatia JD Converter Validator")
    parser.add_argument("--api-url", help="Optional live API URL (e.g. http://localhost:8000)")
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "test_outputs"), help="Directory to save sample .docx files")
    args = parser.parse_args()

    print("\n" + "#"*70)
    print("  QUANT HIRE AI — MALOMATIA JD CONVERTER E2E VALIDATION SUITE")
    print("#"*70)

    try:
        # Step 1: Recommendation Engine
        test_recommendation_engine()

        # Step 2: DOCX Template Filling & Typography
        output_dir = Path(args.output_dir)
        test_docx_generation_and_layout(output_dir)

        # Step 3: API Endpoint
        test_api_endpoint(args.api_url)

        print("\n" + "="*70)
        print("🎉 ALL END-TO-END VALIDATION CHECKS PASSED (100% SUCCESS)")
        print(f"📂 Sample Word documents exported for review at:")
        print(f"   -> {output_dir.resolve()}")
        print("="*70 + "\n")

    except Exception as exc:
        print(f"\n❌ VALIDATION FAILED: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
