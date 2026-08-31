#!/usr/bin/env python3
"""Full validation for EVERY aspect of delete (jobs/JDs + candidates/resumes).

Automated coverage (no browser required):
  A. Backend syntax compile
  B. Static UI/API wiring (14+ checks)
  C. ResourceDeletionService unit tests (purge, guards, sync delete)
  D. Frontend/API wiring tests
  E. Simulated user journeys (duplicate JD, cancel, soft-delete)
  F. QuantChat retrieval impact (document_chunks purge path)
  G. Job-matching embedding purge (job_embeddings / candidate_embeddings)
  H. API guards (404, 409, inactive 404, idempotent delete)
  I. Frontend UX (confirm text, stopPropagation, list refresh)

Optional live smoke (destructive — test IDs only):
  scripts\\validate_delete_e2e.cmd --live-api http://localhost:8000 --token JWT ^
    --job-id JOB_UUID --candidate-id CANDIDATE_UUID

Usage (CMD from repo root):
  scripts\\validate_delete_e2e.cmd
  python scripts\\validate_delete_e2e.py
  python scripts\\validate_delete_e2e.py --verbose
  python scripts\\validate_delete_e2e.py --skip-pytest
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# All pytest modules grouped by validation aspect
PYTEST_ASPECTS: list[tuple[str, Path]] = [
    ("A. ResourceDeletionService (purge + guards)", REPO_ROOT / "tests/unit/test_resource_deletion.py"),
    ("B. UI/API wiring", REPO_ROOT / "tests/unit/test_delete_e2e_wiring.py"),
    ("C. Simulated delete journeys", REPO_ROOT / "tests/unit/test_delete_workflow_simulation.py"),
    ("D. QuantChat + matching + guards + UX (full aspects)", REPO_ROOT / "tests/unit/test_delete_full_aspects.py"),
]

PYTEST_FILES = [path for _, path in PYTEST_ASPECTS]

WIRING_CHECKS: list[tuple[str, Path, str]] = [
    ("Backend: purge_job_vectors", REPO_ROOT / "apps/api/app/services/resource_deletion_service.py", "purge_job_vectors"),
    ("Backend: purge_candidate_vectors", REPO_ROOT / "apps/api/app/services/resource_deletion_service.py", "purge_candidate_vectors"),
    ("Backend: JobEmbedding purge", REPO_ROOT / "apps/api/app/services/resource_deletion_service.py", "JobEmbedding"),
    ("Backend: CandidateEmbedding purge", REPO_ROOT / "apps/api/app/services/resource_deletion_service.py", "CandidateEmbedding"),
    ("Backend: _job_document_ids helper", REPO_ROOT / "apps/api/app/services/resource_deletion_service.py", "_job_document_ids"),
    ("Backend: soft-delete candidate", REPO_ROOT / "apps/api/app/services/resource_deletion_service.py", "candidate.is_active = False"),
    ("API: jobs DELETE endpoint", REPO_ROOT / "apps/api/app/api/v1/jobs.py", "await deletion.delete_job(job)"),
    ("API: candidates DELETE endpoint", REPO_ROOT / "apps/api/app/api/v1/candidates.py", "await deletion.delete_candidate(candidate)"),
    ("API: active candidates default", REPO_ROOT / "apps/api/app/api/v1/candidates.py", "is_active: bool = Query(True"),
    ("API: inactive candidate 404", REPO_ROOT / "apps/api/app/api/v1/candidates.py", "if not candidate.is_active:"),
    ("QuantChat: delete_document", REPO_ROOT / "apps/api/app/services/pgvector_ingestion.py", "delete_document"),
    ("QuantChat: visibility filter", REPO_ROOT / "apps/api/app/services/pgvector_ingestion.py", "_quantchat_visibility_clauses"),
    ("QuantChat: pgvector retriever", REPO_ROOT / "apps/quantchat/retrieval/pgvector_retriever.py", "search_chunks"),
    ("Frontend: deleteJobWithConfirm", REPO_ROOT / "apps/web/src/lib/delete-resource.ts", "deleteJobWithConfirm"),
    ("Frontend: deleteCandidateWithConfirm", REPO_ROOT / "apps/web/src/lib/delete-resource.ts", "deleteCandidateWithConfirm"),
    ("Frontend: jobs list onDelete", REPO_ROOT / "apps/web/src/app/dashboard/jobs/page.tsx", "onDelete={handleDeleteJob}"),
    ("Frontend: job card trash", REPO_ROOT / "apps/web/src/components/jobs/job-card.tsx", 'aria-label="Delete job"'),
    ("Frontend: job detail delete", REPO_ROOT / "apps/web/src/app/dashboard/jobs/[id]/page.tsx", "Delete Job"),
    ("Frontend: candidates list onDelete", REPO_ROOT / "apps/web/src/app/dashboard/candidates/page.tsx", "onDelete={handleDeleteCandidate}"),
    ("Frontend: candidates is_active=true", REPO_ROOT / "apps/web/src/app/dashboard/candidates/page.tsx", "is_active=true"),
    ("Frontend: profile Remove from pool", REPO_ROOT / "apps/web/src/components/candidates/candidate-profile-view.tsx", "Remove from pool"),
    ("Frontend: api.ts delete routes", REPO_ROOT / "apps/web/src/lib/api.ts", "apiClient.delete"),
    ("Matching: vector_store embeddings", REPO_ROOT / "apps/agents/agents/rag/vector_store.py", "job_embeddings"),
]

SYNTAX_FILES = [
    REPO_ROOT / "apps/api/app/services/resource_deletion_service.py",
    REPO_ROOT / "apps/api/app/api/v1/jobs.py",
    REPO_ROOT / "apps/api/app/api/v1/candidates.py",
    REPO_ROOT / "apps/api/app/services/pgvector_ingestion.py",
    REPO_ROOT / "apps/quantchat/retrieval/pgvector_retriever.py",
    REPO_ROOT / "apps/quantchat/retrieval/full_doc_retriever.py",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def run_py_compile() -> list[str]:
    errors: list[str] = []
    for path in SYNTAX_FILES:
        if not path.is_file():
            errors.append(f"Missing file: {path.relative_to(REPO_ROOT)}")
            continue
        try:
            compile(_read(path), str(path), "exec")
        except SyntaxError as exc:
            errors.append(f"Syntax error in {path.relative_to(REPO_ROOT)}: {exc}")
    return errors


def run_static_wiring_checks() -> list[str]:
    errors: list[str] = []
    for label, path, needle in WIRING_CHECKS:
        if not path.is_file():
            errors.append(f"[{label}] missing: {path.relative_to(REPO_ROOT)}")
            continue
        if needle not in _read(path):
            errors.append(f"[{label}] missing '{needle}' in {path.relative_to(REPO_ROOT)}")

    deletion = _read(REPO_ROOT / "apps/api/app/services/resource_deletion_service.py")
    if "await self.session.delete(job)" in deletion:
        errors.append("Must use sync session.delete(job), not await")
    if "self.session.delete(job)" not in deletion:
        errors.append("Must call self.session.delete(job) for hard job delete")

    job_detail = _read(REPO_ROOT / "apps/web/src/app/dashboard/jobs/[id]/page.tsx")
    if "applications: displayJob.applications" in job_detail:
        errors.append("Job detail delete must not use mock applications guard")

    return errors


def run_pytest(skip: bool, verbose: bool) -> tuple[int, str, dict[str, str]]:
    if skip:
        return 0, "skipped", {}

    missing = [p for p in PYTEST_FILES if not p.is_file()]
    if missing:
        return 1, "\n".join(f"Missing: {p}" for p in missing), {}

    aspect_results: dict[str, str] = {}
    combined_output: list[str] = []
    overall_code = 0

    for label, path in PYTEST_ASPECTS:
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            str(path),
            "-q" if not verbose else "-v",
            "--tb=short",
        ]
        result = subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True)
        output = (result.stdout or "") + (result.stderr or "")
        combined_output.append(f"--- {label} ---")
        combined_output.append(output.strip())
        aspect_results[label] = "PASS" if result.returncode == 0 else "FAIL"
        if result.returncode != 0:
            overall_code = result.returncode

    # Also run all together for single summary line count
    if overall_code == 0:
        cmd = [sys.executable, "-m", "pytest", *[str(p) for p in PYTEST_FILES], "-q", "--tb=no"]
        summary = subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True)
        combined_output.append("--- Combined summary ---")
        combined_output.append((summary.stdout or "").strip())
        if summary.returncode != 0:
            overall_code = summary.returncode

    return overall_code, "\n".join(combined_output), aspect_results


def _api_request(method: str, url: str, *, token: str | None = None, timeout: float = 15.0) -> tuple[int, str]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def check_live_api_health(base_url: str) -> list[str]:
    base = base_url.rstrip("/")
    for path in ("/healthz", "/health"):
        if _api_request("GET", f"{base}{path}")[0] == 200:
            return []
    return [f"Health check failed for {base}"]


def run_live_delete_smoke(
    base_url: str,
    *,
    token: str | None,
    job_id: str | None,
    candidate_id: str | None,
    verify_gone: bool,
) -> list[str]:
    errors: list[str] = []
    if not token:
        print("  SKIP: pass --token or set QH_API_TOKEN")
        return errors

    api = f"{base_url.rstrip('/')}/api/v1"

    if job_id:
        print(f"  -> DELETE job {job_id}")
        status, body = _api_request("DELETE", f"{api}/jobs/{job_id}", token=token)
        if status not in (204, 404, 409):
            errors.append(f"DELETE job HTTP {status}: {body[:200]}")
        elif verify_gone and status == 204 and _api_request("GET", f"{api}/jobs/{job_id}", token=token)[0] != 404:
            errors.append("Deleted job still returned by GET")

    if candidate_id:
        print(f"  -> DELETE candidate {candidate_id}")
        status, body = _api_request("DELETE", f"{api}/candidates/{candidate_id}", token=token)
        if status not in (204, 404, 409):
            errors.append(f"DELETE candidate HTTP {status}: {body[:200]}")
        if verify_gone and status == 204:
            if _api_request("GET", f"{api}/candidates/{candidate_id}", token=token)[0] != 404:
                errors.append("Removed candidate still returned by GET")
            _, list_body = _api_request("GET", f"{api}/candidates?is_active=true", token=token)
            try:
                payload = json.loads(list_body)
                items = payload if isinstance(payload, list) else payload.get("candidates", [])
                if any(str(i.get("id")) == candidate_id for i in items):
                    errors.append("Removed candidate still in active list")
            except json.JSONDecodeError:
                errors.append("Could not parse candidates list")

    if not job_id and not candidate_id:
        print("  SKIP: pass --job-id and/or --candidate-id")

    return errors


def print_aspect_matrix(aspect_results: dict[str, str]) -> None:
    if not aspect_results:
        return
    print()
    print("  Aspect results:")
    for label, status in aspect_results.items():
        mark = "OK" if status == "PASS" else "FAIL"
        print(f"    [{mark}] {label}")


def print_coverage_matrix() -> None:
    print()
    print("  Automated aspect coverage:")
    rows = [
        ("Job/JD hard delete", "ResourceDeletionService.delete_job + session.delete"),
        ("JD vector purge (QuantChat)", "delete_document + document_chunks.job_id"),
        ("JD document id resolution", "_job_document_ids (metadata + spec_json + job.id)"),
        ("Job matching purge", "JobEmbedding delete by job_id"),
        ("Resume soft delete", "is_active=false, deletion_requested=true"),
        ("Resume vector purge (QuantChat)", "delete_document + candidate_id + dedupe"),
        ("Candidate matching purge", "CandidateEmbedding delete"),
        ("List visibility", "GET /candidates?is_active=true, inactive GET 404"),
        ("Application guards", "409 when applications exist"),
        ("UI: jobs list + detail", "deleteJobWithConfirm, fetchJobs, redirect"),
        ("UI: candidates list + profile", "deleteCandidateWithConfirm, fetchCandidates, redirect"),
        ("QuantChat retrievers", "vector + keyword + full_doc -> document_chunks + visibility SQL"),
        ("Duplicate JD cleanup", "simulation: delete one card at a time"),
        ("Cancel delete", "simulation: list unchanged when user cancels"),
    ]
    for aspect, mechanism in rows:
        print(f"    - {aspect}: {mechanism}")


def print_manual_uat() -> None:
    print()
    print("=" * 60)
    print("  Manual browser UAT (post-deploy)")
    print("=" * 60)
    print("  JD:  card trash | detail Delete Job | QuantChat no retrieval")
    print("  Resume: card trash | Remove from pool | profile 404 | QuantChat no retrieval")
    print("  Guards: job/candidate with applications blocked")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate every aspect of delete E2E")
    parser.add_argument("--skip-pytest", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose pytest output")
    parser.add_argument("--live-api", metavar="URL")
    parser.add_argument("--token", default=os.environ.get("QH_API_TOKEN"))
    parser.add_argument("--job-id")
    parser.add_argument("--candidate-id")
    parser.add_argument("--no-verify-gone", action="store_true")
    args = parser.parse_args()

    failed = False
    step = 0
    total = 3 + (0 if args.skip_pytest else 1)
    if args.live_api:
        total += 1
    if args.live_api and args.token and (args.job_id or args.candidate_id):
        total += 1

    def step_header(title: str) -> None:
        nonlocal step
        step += 1
        print()
        print("-" * 60)
        print(f"  STEP {step}/{total}: {title}")
        print("-" * 60)

    print()
    print("=" * 60)
    print("  QuantHire AI - DELETE Full Validation (All Aspects)")
    print("=" * 60)
    print_coverage_matrix()

    step_header("Backend + QuantChat syntax compile")
    syntax_errors = run_py_compile()
    if syntax_errors:
        failed = True
        for e in syntax_errors:
            print(f"  FAIL: {e}")
    else:
        print(f"  OK: {len(SYNTAX_FILES)} files compile")

    step_header(f"Static wiring ({len(WIRING_CHECKS)} checks)")
    wiring_errors = run_static_wiring_checks()
    if wiring_errors:
        failed = True
        for e in wiring_errors:
            print(f"  FAIL: {e}")
    else:
        print(f"  OK: all {len(WIRING_CHECKS)} wiring checks passed")

    if not args.skip_pytest:
        step_header(f"Pytest ({sum(1 for _ in PYTEST_ASPECTS)} modules, all aspects)")
        code, output, aspect_results = run_pytest(skip=False, verbose=args.verbose)
        if args.verbose and output:
            print(output)
        elif output and code != 0:
            print(output)
        print_aspect_matrix(aspect_results)
        if code != 0:
            failed = True
            print(f"  FAIL: pytest exit code {code}")
        else:
            print("  OK: all delete aspect tests passed")

    if args.live_api:
        step_header(f"Live API health ({args.live_api})")
        health_errs = check_live_api_health(args.live_api)
        if health_errs:
            failed = True
            for e in health_errs:
                print(f"  FAIL: {e}")
        else:
            print("  OK: API reachable")

        if args.token and (args.job_id or args.candidate_id):
            step_header("Live delete smoke (destructive)")
            smoke_errs = run_live_delete_smoke(
                args.live_api,
                token=args.token,
                job_id=args.job_id,
                candidate_id=args.candidate_id,
                verify_gone=not args.no_verify_gone,
            )
            if smoke_errs:
                failed = True
                for e in smoke_errs:
                    print(f"  FAIL: {e}")
            else:
                print("  OK: live smoke completed")

    print()
    if failed:
        print("=" * 60)
        print("  VALIDATION FAILED")
        print("=" * 60)
        print("\nRe-run: scripts\\validate_delete_e2e.cmd")
        return 1

    print("=" * 60)
    print("  ALL DELETE ASPECTS VALIDATED SUCCESSFULLY")
    print("=" * 60)
    print_manual_uat()
    print("Re-run:")
    print("  scripts\\validate_delete_e2e.cmd")
    print("  scripts\\validate_delete_e2e.cmd -v")
    print("  scripts\\validate_delete_e2e.cmd --live-api URL --token JWT --job-id UUID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
