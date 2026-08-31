"""Validation for JD generate dedup fixes: in-flight guard, session draft id, postgres job id."""

from __future__ import annotations

import uuid
from copy import deepcopy
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

JD_DRAFT_JOB_ID_KEY = "quanthire:jd-draft-job-id"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def resolve_replace_job_id(
    draft_job_id: str | None,
    *candidates: str | None,
) -> str | None:
    """Mirror of jd-generation-dialog resolveReplaceJobId() after dedup fix."""
    for candidate in [draft_job_id, *candidates]:
        if candidate and str(candidate).strip():
            return str(candidate).strip()
    return None


def build_generate_payload(
    *,
    draft_job_id: str | None,
    replace_job_id: str | None,
    edit_job_id: str | None,
    generated_jd: dict | None,
    job_title: str,
    department: str,
) -> dict:
    existing_job_id = resolve_replace_job_id(
        draft_job_id,
        replace_job_id,
        edit_job_id,
        (generated_jd or {}).get("job_id"),
        (generated_jd or {}).get("id"),
    )
    payload = {
        "job_title": job_title,
        "department": department,
        "job_level": "Senior",
    }
    if existing_job_id:
        payload["job_id"] = existing_job_id
    return payload


def apply_generate_to_jobs_list(
    jobs: list[dict],
    *,
    request_job_id: str | None,
    job_title: str,
) -> tuple[list[dict], str]:
    stored_id = request_job_id or str(uuid.uuid4())
    updated = deepcopy(jobs)
    match = next((job for job in updated if job["id"] == stored_id), None)
    if match:
        match["title"] = job_title
    else:
        updated.append({"id": stored_id, "title": job_title, "department": "Engineering"})
    return updated, stored_id


class GenerationGuard:
    """Mirror of generationInFlightRef behavior in handleGenerate()."""

    def __init__(self) -> None:
        self.in_flight = False
        self.starts = 0

    def try_start(self) -> bool:
        if self.in_flight:
            return False
        self.in_flight = True
        self.starts += 1
        return True

    def finish(self) -> None:
        self.in_flight = False


def test_resolve_replace_job_id_prefers_session_draft():
    draft_id = "11111111-1111-1111-1111-111111111111"
    resolved = resolve_replace_job_id(
        draft_id,
        None,
        "22222222-2222-2222-2222-222222222222",
    )
    assert resolved == draft_id


def test_generate_payload_includes_draft_job_id_on_regenerate():
    draft_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    payload = build_generate_payload(
        draft_job_id=draft_id,
        replace_job_id=None,
        edit_job_id=None,
        generated_jd=None,
        job_title="Senior Software Engineer",
        department="Managed Infrastructure Services",
    )
    assert payload["job_id"] == draft_id


def test_parallel_generate_attempts_are_blocked():
    guard = GenerationGuard()
    assert guard.try_start() is True
    assert guard.try_start() is False
    assert guard.starts == 1
    guard.finish()
    assert guard.try_start() is True
    assert guard.starts == 2


def test_session_draft_keeps_one_card_after_dialog_reopen_simulation():
    """Simulate: generate -> store draft id -> reopen dialog -> regenerate."""
    jobs: list[dict] = []
    session_draft: str | None = None

    jobs, first_id = apply_generate_to_jobs_list(
        jobs,
        request_job_id=None,
        job_title="Senior Software Engineer",
    )
    session_draft = first_id

    payload = build_generate_payload(
        draft_job_id=session_draft,
        replace_job_id=None,
        edit_job_id=None,
        generated_jd=None,
        job_title="Senior Software Engineer",
        department="Managed Infrastructure Services",
    )
    jobs, second_id = apply_generate_to_jobs_list(
        jobs,
        request_job_id=payload.get("job_id"),
        job_title=payload["job_title"],
    )
    assert len(jobs) == 1
    assert second_id == first_id


def test_clearing_session_draft_on_new_job_button_allows_fresh_create():
    session_draft = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    session_draft = None  # mirrors handleOpenNewJdDialog clearing sessionStorage
    payload = build_generate_payload(
        draft_job_id=session_draft,
        replace_job_id=None,
        edit_job_id=None,
        generated_jd=None,
        job_title="Senior Software Engineer",
        department="Managed Infrastructure Services",
    )
    assert "job_id" not in payload


def test_triple_parallel_generate_without_guard_creates_three_cards():
    jobs: list[dict] = []
    for _ in range(3):
        jobs, _ = apply_generate_to_jobs_list(
            jobs,
            request_job_id=None,
            job_title="Senior Software Engineer",
        )
    assert len(jobs) == 3


def test_triple_parallel_generate_with_guard_creates_one_card():
    jobs: list[dict] = []
    guard = GenerationGuard()
    draft_id: str | None = None
    for _ in range(3):
        if not guard.try_start():
            continue
        jobs, draft_id = apply_generate_to_jobs_list(
            jobs,
            request_job_id=draft_id,
            job_title="Senior Software Engineer",
        )
        guard.finish()
    assert len(jobs) == 1


def test_generation_in_flight_ref_wiring():
    source = _read(
        REPO_ROOT / "apps" / "web" / "src" / "components" / "jobs" / "jd-generation-dialog.tsx"
    )
    assert "generationInFlightRef" in source
    assert "if (generationInFlightRef.current)" in source
    assert "generationInFlightRef.current = true" in source
    assert "generationInFlightRef.current = false" in source


def test_session_draft_storage_wiring():
    source = _read(
        REPO_ROOT / "apps" / "web" / "src" / "components" / "jobs" / "jd-generation-dialog.tsx"
    )
    assert JD_DRAFT_JOB_ID_KEY in source
    assert "readDraftJobId" in source
    assert "writeDraftJobId" in source
    assert "readDraftJobId()" in source
    assert "...candidates" in source


def test_jobs_page_clears_draft_on_ai_generate_click():
    source = _read(REPO_ROOT / "apps" / "web" / "src" / "app" / "dashboard" / "jobs" / "page.tsx")
    assert 'sessionStorage.removeItem("quanthire:jd-draft-job-id")' in source
    assert "handleOpenNewJdDialog" in source


def test_generate_response_includes_postgres_job_id():
    source = _read(REPO_ROOT / "apps" / "api" / "app" / "api" / "v1" / "jd_generation.py")
    assert "postgres_job_id: Optional[str]" in source.split("class JDGenerationResponse", 1)[1].split("class JDGenerationAsyncResponse", 1)[0]
    assert 'result["postgres_job_id"]' in source


def test_store_jd_returns_effective_postgres_job_id():
    source = _read(REPO_ROOT / "apps" / "api" / "app" / "services" / "jd_pipeline_service.py")
    assert "effective_job_id = str(job_uuid or document_id)" in source
    assert '"job_id": effective_job_id' in source


def test_notify_jobs_list_after_generate_wiring():
    source = _read(
        REPO_ROOT / "apps" / "web" / "src" / "components" / "jobs" / "jd-generation-dialog.tsx"
    )
    generate_block = source.split("const handleGenerate = async () => {", 1)[1].split("const handleSave = async () => {", 1)[0]
    assert "notifyJobsListUpdated()" in generate_block


def test_persisted_job_id_prefers_postgres_job_id():
    source = _read(
        REPO_ROOT / "apps" / "web" / "src" / "components" / "jobs" / "jd-generation-dialog.tsx"
    )
    assert "result.postgres_job_id" in source
    assert "writeDraftJobId(String(persistedJobId))" in source
