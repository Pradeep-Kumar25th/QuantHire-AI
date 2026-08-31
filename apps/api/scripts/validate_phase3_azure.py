#!/usr/bin/env python3
"""Validate Phase 3 Azure integrations against live secrets (no secret values printed)."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
API_ROOT = REPO_ROOT / "apps" / "api"
AGENTS_ROOT = REPO_ROOT / "apps" / "agents" / "agents"
SCRIPTS_ROOT = Path(__file__).resolve().parent

for path in (str(API_ROOT), str(AGENTS_ROOT), str(SCRIPTS_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from dotenv import load_dotenv

load_dotenv(REPO_ROOT / ".env")
load_dotenv(REPO_ROOT / "output" / "azure_deployment" / "env" / "azure-nonprod.env")

from app.config import get_settings
from app.core.azure_env import sync_azure_env_from_settings


def _mask(value: str | None) -> str:
    if not value:
        return "(not set)"
    text = str(value).strip()
    if len(text) <= 8:
        return "(set, len=%d)" % len(text)
    return f"(set, prefix={text[:4]}..., len={len(text)})"


def check_env() -> dict[str, Any]:
    keys = {
        "DEPLOYMENT_TARGET": os.getenv("DEPLOYMENT_TARGET"),
        "LLM_PROVIDER": os.getenv("LLM_PROVIDER"),
        "AZURE_OPENAI_ENDPOINT": os.getenv("AZURE_OPENAI_ENDPOINT"),
        "AZURE_OPENAI_API_KEY": os.getenv("AZURE_OPENAI_API_KEY"),
        "AZURE_OPENAI_CHAT_DEPLOYMENT": os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
        "AZURE_STORAGE_CONNECTION_STRING": os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
        "AZURE_STORAGE_ACCOUNT_NAME": os.getenv("AZURE_STORAGE_ACCOUNT_NAME"),
        "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT": os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"),
        "AZURE_DOCUMENT_INTELLIGENCE_API_KEY": os.getenv("AZURE_DOCUMENT_INTELLIGENCE_API_KEY"),
        "AZURE_DOCUMENT_INTELLIGENCE_KEY": os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY"),
    }
    return {k: _mask(v) for k, v in keys.items()}


def validate_azure_openai() -> dict[str, Any]:
    from agents.llm.chat_factory import create_chat_llm, is_azure_openai_configured

    if not is_azure_openai_configured():
        return {"status": "skip", "reason": "Azure OpenAI not configured"}

    try:
        llm = create_chat_llm(provider="azure_openai", max_tokens=32, temperature=0)
        response = llm.invoke("Reply with exactly: OK")
        content = getattr(response, "content", str(response))
        preview = str(content).strip()[:80]
        return {
            "status": "pass",
            "deployment": settings.azure_openai_chat_deployment,
            "response_preview": preview,
        }
    except Exception as exc:
        return {"status": "fail", "error": str(exc)}


def validate_azure_blob() -> dict[str, Any]:
    from app.integrations.azure_blob import get_blob_storage

    blob = get_blob_storage()
    if not blob.is_configured():
        return {"status": "skip", "reason": "Blob storage not configured"}

    test_name = f"validation/{uuid.uuid4().hex}/phase3-test.txt"
    payload = b"QuantHire Phase 3 blob validation"
    try:
        ref = blob._upload_bytes_sync(
            blob.uploads_container,
            test_name,
            payload,
            "text/plain",
        )
        downloaded = blob._download_bytes_sync(ref)
        ok = downloaded == payload
        return {
            "status": "pass" if ok else "fail",
            "blob_ref": ref,
            "uploads_container": blob.uploads_container,
            "roundtrip": ok,
        }
    except Exception as exc:
        return {"status": "fail", "error": str(exc)}


def validate_document_intelligence() -> dict[str, Any]:
    from app.integrations.document_intelligence import get_document_intelligence_client

    di = get_document_intelligence_client()
    if not di.is_configured():
        return {"status": "skip", "reason": "Document Intelligence not configured"}

    # Minimal valid PDF header — DI may reject; we report API reachability separately.
    minimal_pdf = (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n"
        b"0000000052 00000 n \n0000000101 00000 n \ntrailer<</Size 4/Root 1 0 R>>\n"
        b"startxref\n149\n%%EOF"
    )
    try:
        text = di.extract_text_from_pdf_sync(minimal_pdf)
        return {
            "status": "pass",
            "model": di.model_id,
            "chars_extracted": len(text or ""),
        }
    except Exception as exc:
        err = str(exc)
        # Auth/endpoint errors are hard fails; empty PDF content may still mean API works.
        if any(token in err.lower() for token in ("401", "403", "unauthorized", "invalid subscription key")):
            return {"status": "fail", "error": err}
        if "InvalidRequest" in err or "InvalidContent" in err:
            return {
                "status": "pass",
                "model": di.model_id,
                "note": "API reachable; minimal test PDF rejected (expected)",
                "detail": err[:200],
            }
        return {"status": "fail", "error": err}


def validate_readiness_fields() -> dict[str, Any]:
    from app.core.readiness import check_azure_blob, check_document_intelligence

    async def _aoai():
        from app.core.readiness import check_azure_openai

        return await check_azure_openai()

    aoai = asyncio.run(_aoai())
    return {
        "azure_openai": aoai,
        "azure_blob": check_azure_blob(),
        "document_intelligence": check_document_intelligence(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Phase 3 Azure integrations")
    parser.add_argument(
        "--from-aks",
        action="store_true",
        help="Load secrets from AKS namespace quanthire-nonprod via kubectl",
    )
    parser.add_argument(
        "--namespace",
        default="quanthire-nonprod",
        help="Kubernetes namespace for --from-aks (default: quanthire-nonprod)",
    )
    args = parser.parse_args()

    if args.from_aks:
        from load_azure_secrets_from_aks import load_aks_secrets

        aks_summary = load_aks_secrets(namespace=args.namespace, overwrite=True)
        print("AKS secret load summary:")
        print(f"  context: {aks_summary.get('kubectl_context', '(unknown)')}")
        print(f"  loaded keys: {aks_summary.get('loaded') or '(none)'}")
        if aks_summary.get("missing_secrets"):
            print(f"  missing secrets: {aks_summary['missing_secrets']}")
        if aks_summary.get("missing_keys"):
            print(f"  missing keys: {aks_summary['missing_keys']}")
        if aks_summary.get("errors"):
            print(f"  errors: {aks_summary['errors']}")
        print()

    get_settings.cache_clear()
    settings = get_settings()
    sync_azure_env_from_settings(settings)

    print("=" * 72)
    print("QuantHire Phase 3 — Live Azure Validation")
    print("=" * 72)
    print("\nEnvironment (secrets masked):")
    for key, val in check_env().items():
        print(f"  {key}: {val}")

    results = {
        "azure_openai_chat": validate_azure_openai(),
        "azure_blob": validate_azure_blob(),
        "document_intelligence": validate_document_intelligence(),
        "readiness_checks": validate_readiness_fields(),
    }

    print("\nLive checks:")
    for name, result in results.items():
        if name == "readiness_checks":
            continue
        status = result.get("status", "unknown")
        symbol = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP"}.get(status, status.upper())
        print(f"  [{symbol}] {name}: {result}")

    print("\nReadiness probe fields:")
    for key, val in results["readiness_checks"].items():
        print(f"  {key}: {val}")

    statuses = [
        results["azure_openai_chat"].get("status"),
        results["azure_blob"].get("status"),
        results["document_intelligence"].get("status"),
    ]
    if all(s == "skip" for s in statuses):
        print(
            "\nNo live secrets found. Set AZURE_OPENAI_API_KEY, "
            "AZURE_STORAGE_CONNECTION_STRING, and AZURE_DOCUMENT_INTELLIGENCE_API_KEY "
            "in .env or load from AKS secrets, then re-run."
        )
        return 2

    if any(s == "fail" for s in statuses):
        return 1
    if any(s == "skip" for s in statuses):
        return 3
    print("\nAll Phase 3 Azure integrations validated successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
