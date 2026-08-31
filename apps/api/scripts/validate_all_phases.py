#!/usr/bin/env python3
"""
Validate Phases 0–4 of QuantHire Azure replatform (static + optional live checks).

Usage:
  python apps/api/scripts/validate_all_phases.py
  python apps/api/scripts/validate_all_phases.py --from-aks
  python apps/api/scripts/validate_all_phases.py --live
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

REPO_ROOT = Path(__file__).resolve().parents[3]
API_ROOT = REPO_ROOT / "apps" / "api"
AGENTS_ROOT = REPO_ROOT / "apps" / "agents" / "agents"
WEB_ROOT = REPO_ROOT / "apps" / "web"
SCRIPTS_ROOT = Path(__file__).resolve().parent

for path in (str(API_ROOT), str(AGENTS_ROOT), str(SCRIPTS_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from dotenv import load_dotenv

load_dotenv(REPO_ROOT / ".env")
load_dotenv(REPO_ROOT / "output" / "azure_deployment" / "env" / "azure-nonprod.env")

Status = Literal["PASS", "FAIL", "SKIP", "WARN"]


@dataclass
class Check:
    name: str
    status: Status
    detail: str = ""


@dataclass
class PhaseReport:
    phase: str
    title: str
    checks: list[Check] = field(default_factory=list)

    @property
    def overall(self) -> Status:
        if any(c.status == "FAIL" for c in self.checks):
            return "FAIL"
        if any(c.status == "WARN" for c in self.checks):
            return "WARN"
        if all(c.status == "SKIP" for c in self.checks):
            return "SKIP"
        return "PASS"


def _file_contains(path: Path, needle: str) -> bool:
    if not path.is_file():
        return False
    return needle in path.read_text(encoding="utf-8", errors="ignore")


def _module_importable(dotted: str) -> tuple[bool, str]:
    try:
        parts = dotted.split(".")
        if parts[0] == "app":
            __import__(dotted)
        elif parts[0] == "agents":
            __import__(dotted)
        elif parts[0] == "quantchat":
            apps = str(REPO_ROOT / "apps")
            if apps not in sys.path:
                sys.path.insert(0, apps)
            __import__(dotted)
        else:
            __import__(dotted)
        return True, "import ok"
    except Exception as exc:
        return False, str(exc)


# ---------------------------------------------------------------------------
# Phase 0 — Foundation
# ---------------------------------------------------------------------------


def validate_phase_0() -> PhaseReport:
    report = PhaseReport("0", "Foundation (config, health probes, Helm template)")
    from app.config import Settings, get_settings

    get_settings.cache_clear()
    saved = {
        k: os.environ.get(k)
        for k in ("DEPLOYMENT_TARGET", "LLM_PROVIDER", "VECTOR_STORE", "MILVUS_ENABLED")
    }
    try:
        os.environ["DEPLOYMENT_TARGET"] = "azure-nonprod"
        os.environ["LLM_PROVIDER"] = "azure_openai"
        os.environ.setdefault("VECTOR_STORE", "pgvector")
        os.environ.setdefault("MILVUS_ENABLED", "false")
        get_settings.cache_clear()
        azure = Settings(deployment_target="azure-nonprod")
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()

    real_values = {
        "azure_openai_endpoint": "aif-ail-npd-we-01.openai.azure.com",
        "postgres_host": "psql-ail-npd-we-01.postgres.database.azure.com",
        "azure_storage_account_name": "dlsailnpdqc01",
        "azure_document_intelligence_endpoint": "di-ail-npd-we-01.cognitiveservices.azure.com",
        "acr_login_server": "crailnpdwe01.azurecr.io",
        "k8s_namespace": "quanthire-nonprod",
    }
    for field_name, fragment in real_values.items():
        val = str(getattr(azure, field_name, ""))
        ok = fragment in val
        report.checks.append(
            Check(
                f"config.{field_name}",
                "PASS" if ok else "FAIL",
                val if ok else f"expected fragment {fragment!r} in {val!r}",
            )
        )

    report.checks.append(
        Check(
            "azure-nonprod switches",
            "PASS"
            if azure.llm_provider == "azure_openai"
            and azure.storage_backend == "azure_blob"
            and azure.use_pgvector_pipeline
            and not azure.milvus_enabled
            else "FAIL",
            f"llm={azure.llm_provider}, storage={azure.storage_backend}, "
            f"pgvector={azure.use_pgvector_pipeline}, milvus={azure.milvus_enabled}",
        )
    )

    main_py = API_ROOT / "app" / "main.py"
    report.checks.append(
        Check("/healthz route", "PASS" if _file_contains(main_py, '"/healthz"') else "FAIL")
    )
    report.checks.append(
        Check("/readyz route", "PASS" if _file_contains(main_py, '"/readyz"') else "FAIL")
    )
    report.checks.append(
        Check(
            "Helm values-nonprod.yaml",
            "PASS" if (REPO_ROOT / "infra/kubernetes/helm/quanthire/values-nonprod.yaml").is_file() else "FAIL",
        )
    )
    report.checks.append(
        Check(
            "azure-nonprod.env template",
            "PASS"
            if (REPO_ROOT / "output/azure_deployment/env/azure-nonprod.env").is_file()
            else "FAIL",
        )
    )
    return report


# ---------------------------------------------------------------------------
# Phase 1 — BFF
# ---------------------------------------------------------------------------


def validate_phase_1() -> PhaseReport:
    report = PhaseReport("1", "BFF (Next.js /api proxy)")
    bff_route = WEB_ROOT / "src" / "app" / "api" / "[...path]" / "route.ts"
    api_ts = WEB_ROOT / "src" / "lib" / "api.ts"
    api_client = WEB_ROOT / "src" / "lib" / "api-client.ts"

    report.checks.append(Check("BFF route.ts exists", "PASS" if bff_route.is_file() else "FAIL"))
    report.checks.append(
        Check(
            "BFF_BACKEND_URL in route",
            "PASS" if _file_contains(bff_route, "BFF_BACKEND_URL") else "FAIL",
        )
    )
    report.checks.append(
        Check(
            "Browser api baseURL = /api",
            "PASS" if _file_contains(api_ts, 'const API_URL = "/api"') else "FAIL",
        )
    )
    report.checks.append(Check("api-client.ts exists", "PASS" if api_client.is_file() else "FAIL"))
    helm = REPO_ROOT / "infra/kubernetes/helm/quanthire/values-nonprod.yaml"
    report.checks.append(
        Check(
            "Helm BFF backend DNS",
            "PASS"
            if _file_contains(helm, "quanthire-backend.quanthire-nonprod.svc.cluster.local")
            else "FAIL",
        )
    )
    return report


# ---------------------------------------------------------------------------
# Phase 2 — Basic auth (v1)
# ---------------------------------------------------------------------------


def validate_phase_2() -> PhaseReport:
    report = PhaseReport("2", "Basic auth v1 (frontend + partial backend JWT)")
    auth_py = API_ROOT / "app" / "api" / "v1" / "auth.py"
    auth_policy = API_ROOT / "app" / "core" / "auth_policy.py"
    middleware = WEB_ROOT / "middleware.ts"
    login_page = WEB_ROOT / "src" / "app" / "login" / "page.tsx"
    auth_provider = WEB_ROOT / "src" / "contexts" / "auth-provider.tsx"

    for label, path in [
        ("auth API (login/me/logout)", auth_py),
        ("auth_policy.py", auth_policy),
        ("Next.js middleware", middleware),
        ("/login page", login_page),
        ("AuthProvider", auth_provider),
    ]:
        report.checks.append(Check(label, "PASS" if path.is_file() else "FAIL"))

    resume_py = API_ROOT / "app" / "api" / "v1" / "resume_parsing.py"
    jd_py = API_ROOT / "app" / "api" / "v1" / "jd_generation.py"
    protected_routes = [
        (resume_py, "require_user_when_basic_auth"),
        (jd_py, "require_user_when_basic_auth"),
        (API_ROOT / "app/api/v1/quantchat.py", "require_user_when_basic_auth"),
        (API_ROOT / "app/api/v1/job_matching.py", "require_user_when_basic_auth"),
        (API_ROOT / "app/api/v1/llm_gateway.py", "require_user_when_basic_auth"),
    ]
    protected_count = sum(
        1
        for path, needle in protected_routes
        if path.is_file() and needle in path.read_text(encoding="utf-8", errors="ignore")
    )
    report.checks.append(
        Check(
            "Backend JWT on Phase 1 AI/write routes",
            "PASS" if protected_count >= len(protected_routes) else "FAIL",
            f"{protected_count}/{len(protected_routes)} route modules protected",
        )
    )
    report.checks.append(
        Check(
            "Backend JWT on CRUD routes (candidates/jobs)",
            "WARN",
            "Optional for v1 — Phase 1 flows use resume/JD/quantchat/job-matching endpoints",
        )
    )
    azure_env = REPO_ROOT / "output/azure_deployment/env/azure-nonprod.env"
    report.checks.append(
        Check(
            "AUTH_MODE=basic in azure-nonprod template",
            "PASS" if _file_contains(azure_env, "AUTH_MODE=basic") else "FAIL",
        )
    )
    return report


# ---------------------------------------------------------------------------
# Phase 3 — Azure clients
# ---------------------------------------------------------------------------


def validate_phase_3(live: bool, from_aks: bool) -> PhaseReport:
    report = PhaseReport("3", "Azure OpenAI + Blob + Document Intelligence")
    modules = [
        ("integrations.azure_blob", API_ROOT / "app/integrations/azure_blob.py"),
        ("integrations.document_intelligence", API_ROOT / "app/integrations/document_intelligence.py"),
        ("core.azure_env", API_ROOT / "app/core/azure_env.py"),
        ("agents.llm.chat_factory", AGENTS_ROOT / "llm/chat_factory.py"),
    ]
    for label, path in modules:
        report.checks.append(Check(f"{label} module", "PASS" if path.is_file() else "FAIL"))

    cf = AGENTS_ROOT / "llm/chat_factory.py"
    report.checks.append(
        Check(
            "chat_factory azure_openai branch",
            "PASS" if _file_contains(cf, 'prov == "azure_openai"') else "FAIL",
        )
    )
    req = (API_ROOT / "requirements.txt").read_text(encoding="utf-8", errors="ignore")
    for pkg in ("azure-storage-blob", "azure-ai-documentintelligence", "azure-identity"):
        report.checks.append(
            Check(f"requirements: {pkg}", "PASS" if pkg in req else "FAIL")
        )

    ok, msg = _module_importable("agents.llm.chat_factory")
    report.checks.append(Check("import chat_factory", "PASS" if ok else "FAIL", msg))

    from agents.llm.chat_factory import is_azure_openai_configured

    configured = is_azure_openai_configured()
    report.checks.append(
        Check(
            "Azure OpenAI env configured",
            "PASS" if configured else "SKIP",
            "Set AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY (or use --from-aks)" if not configured else "configured",
        )
    )

    if live or from_aks:
        if from_aks:
            from load_azure_secrets_from_aks import load_aks_secrets

            summary = load_aks_secrets(overwrite=True)
            report.checks.append(
                Check(
                    "AKS secrets loaded",
                    "PASS" if summary.get("loaded") else "FAIL",
                    str(summary.get("loaded") or summary.get("errors")),
                )
            )
            from app.config import get_settings
            from app.core.azure_env import sync_azure_env_from_settings

            get_settings.cache_clear()
            sync_azure_env_from_settings(get_settings())

        try:
            from validate_phase3_azure import (
                validate_azure_blob,
                validate_azure_openai,
                validate_document_intelligence,
            )

            for name, fn in [
                ("LIVE Azure OpenAI chat", validate_azure_openai),
                ("LIVE Azure Blob roundtrip", validate_azure_blob),
                ("LIVE Document Intelligence", validate_document_intelligence),
            ]:
                result = fn()
                st = result.get("status", "fail")
                if st == "pass":
                    status: Status = "PASS"
                elif st == "skip":
                    status = "SKIP"
                else:
                    status = "FAIL"
                report.checks.append(Check(name, status, str(result)))
        except Exception as exc:
            report.checks.append(Check("LIVE Azure integration suite", "FAIL", str(exc)))
    else:
        report.checks.append(
            Check(
                "LIVE Azure calls",
                "SKIP",
                "Re-run with --live or --from-aks for live validation",
            )
        )
    return report


# ---------------------------------------------------------------------------
# Phase 4 — Resume → pgvector
# ---------------------------------------------------------------------------


def validate_phase_4() -> PhaseReport:
    report = PhaseReport("4", "Resume pipeline → Postgres + pgvector")
    files = {
        "DocumentChunk model": API_ROOT / "app/models/document_chunks.py",
        "Alembic migration": API_ROOT / "alembic/versions/add_document_chunks_pgvector.py",
        "pgvector_ingestion service": API_ROOT / "app/services/pgvector_ingestion.py",
        "resume_pipeline_service": API_ROOT / "app/services/resume_pipeline_service.py",
        "resume_profile_converter": API_ROOT / "app/services/resume_profile_converter.py",
        "pgvector_retriever": REPO_ROOT / "apps/quantchat/retrieval/pgvector_retriever.py",
        "job_matching data_access_pg": AGENTS_ROOT / "job_matching/data_access_pg.py",
    }
    for label, path in files.items():
        report.checks.append(Check(label, "PASS" if path.is_file() else "FAIL"))

    resume_py = API_ROOT / "app" / "api" / "v1" / "resume_parsing.py"
    report.checks.append(
        Check(
            "resume upload pgvector branch",
            "PASS" if _file_contains(resume_py, "use_pgvector_pipeline") else "FAIL",
        )
    )
    vr = REPO_ROOT / "apps/quantchat/retrieval/vector_retriever.py"
    report.checks.append(
        Check(
            "VectorRetriever pgvector delegation",
            "PASS" if _file_contains(vr, "PgVectorRetriever") else "FAIL",
        )
    )

    from app.config import Settings

    azure = Settings(deployment_target="azure-nonprod")
    report.checks.append(
        Check(
            "use_pgvector_pipeline on azure-nonprod",
            "PASS" if azure.use_pgvector_pipeline else "FAIL",
        )
    )

    db_url = os.getenv("DATABASE_URL", "").strip()
    report.checks.append(
        Check(
            "DATABASE_URL set (live DB test)",
            "PASS" if db_url else "SKIP",
            "Required for E2E upload on Azure path" if not db_url else "set",
        )
    )

    report.checks.append(
        Check(
            "JD → pgvector",
            "PASS"
            if _file_contains(API_ROOT / "app/services/pgvector_ingestion.py", "async def add_jd")
            and _file_contains(API_ROOT / "app/services/jd_pipeline_service.py", "JDPipelineService")
            else "FAIL",
            "JD save/list path uses Postgres pgvector on azure-nonprod",
        )
    )
    report.checks.append(
        Check(
            "QuantChat keyword retriever → pgvector",
            "PASS"
            if _file_contains(
                REPO_ROOT / "apps/quantchat/retrieval/keyword_retriever.py",
                "_retrieve_pgvector",
            )
            else "FAIL",
        )
    )
    report.checks.append(
        Check(
            "JD generate auto-save → pgvector",
            "PASS"
            if _file_contains(API_ROOT / "app/api/v1/jd_generation.py", "JD auto-saved to pgvector")
            else "FAIL",
        )
    )
    report.checks.append(
        Check(
            "Candidates upload azure branch",
            "PASS"
            if _file_contains(API_ROOT / "app/api/v1/candidates.py", "use_pgvector_pipeline")
            else "FAIL",
        )
    )
    report.checks.append(
        Check(
            "Azure storage diagnostics helper",
            "PASS"
            if (API_ROOT / "app/services/storage_diagnostics.py").is_file()
            else "FAIL",
        )
    )
    report.checks.append(
        Check(
            "Unified Azure embeddings module",
            "PASS"
            if (AGENTS_ROOT / "rag/unified_embeddings.py").is_file()
            else "FAIL",
        )
    )
    emb_factory = AGENTS_ROOT / "rag/embedding_factory.py"
    report.checks.append(
        Check(
            "Azure embeddings default on azure-nonprod",
            "PASS"
            if _file_contains(emb_factory, "azure-nonprod")
            and _file_contains(emb_factory, "is_azure_embeddings_configured")
            else "FAIL",
        )
    )
    report.checks.append(
        Check(
            "LangGraph resume agent",
            "WARN",
            "ai_resume_parsing_agent truncated; Azure path uses ParsingAgent instead",
        )
    )
    return report


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


def validate_unit_tests() -> PhaseReport:
    report = PhaseReport("T", "Automated unit tests (pytest)")
    import subprocess

    unit_dir = REPO_ROOT / "tests" / "unit"
    if not unit_dir.is_dir():
        report.checks.append(Check("pytest", "FAIL", f"Missing {unit_dir}"))
        return report

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(unit_dir),
        "-q",
        "--tb=no",
    ]
    env = os.environ.copy()
    env.setdefault("APP_ENV", "testing")
    env.setdefault("AUTH_MODE", "none")
    env.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-with-32-chars-minimum")
    env.setdefault("DEPLOYMENT_TARGET", "local")
    env.setdefault(
        "PYTHONPATH",
        os.pathsep.join(
            [
                str(REPO_ROOT / "apps"),
                str(API_ROOT),
                str(AGENTS_ROOT),
                str(REPO_ROOT / "apps" / "quantchat"),
            ]
        ),
    )
    env.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, env=env)
    out = (proc.stdout or "") + (proc.stderr or "")
    report.checks.append(
        Check(
            "pytest exit code 0",
            "PASS" if proc.returncode == 0 else "FAIL",
            out.strip()[-500:] if out else f"exit {proc.returncode}",
        )
    )
    return report


def print_report(reports: list[PhaseReport]) -> int:
    print("=" * 72)
    print("QuantHire Replatform — Phase Validation Report (0–4)")
    print("=" * 72)
    has_fail = False
    for rep in reports:
        symbol = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️", "SKIP": "⏭️"}.get(rep.overall, "?")
        print(f"\n{symbol} Phase {rep.phase}: {rep.title} — {rep.overall}")
        for chk in rep.checks:
            ic = {"PASS": "  ✓", "FAIL": "  ✗", "WARN": "  !", "SKIP": "  -"}.get(chk.status, "  ?")
            line = f"{ic} {chk.name}"
            if chk.detail:
                line += f" — {chk.detail}"
            print(line)
            if chk.status == "FAIL":
                has_fail = True

    print("\n" + "=" * 72)
    if has_fail:
        print("RESULT: FAIL — fix failed checks before Docker/AKS deploy")
        return 1
    warn = any(r.overall == "WARN" for r in reports)
    if warn:
        print("RESULT: PASS WITH WARNINGS — safe to proceed to Phase 5 pilot; address warnings before production")
        return 0
    print("RESULT: PASS — static validation complete; run --live or --from-aks for Azure smoke tests")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Run live Azure API checks (needs secrets in env)")
    parser.add_argument("--from-aks", action="store_true", help="Load secrets from kubectl then run live checks")
    parser.add_argument("--skip-tests", action="store_true", help="Skip pytest")
    args = parser.parse_args()

    reports = [
        validate_phase_0(),
        validate_phase_1(),
        validate_phase_2(),
        validate_phase_3(live=args.live or args.from_aks, from_aks=args.from_aks),
        validate_phase_4(),
    ]
    if not args.skip_tests:
        reports.append(validate_unit_tests())
    return print_report(reports)


if __name__ == "__main__":
    raise SystemExit(main())
