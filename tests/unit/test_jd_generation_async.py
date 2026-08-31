"""Unit tests for async JD generation task registry and pgvector query helpers."""

from app.services import jd_generation_tasks
from app.services.pgvector_ingestion import _format_pgvector_literal


def test_create_and_complete_task():
    task = jd_generation_tasks.create_task(
        "task-1",
        job_title="Solution Architect",
        department="IT",
    )
    assert task.status == "pending"
    assert task.job_title == "Solution Architect"

    jd_generation_tasks.mark_running("task-1")
    assert jd_generation_tasks.get_task("task-1").status == "running"

    jd_generation_tasks.mark_completed("task-1", {"success": True, "job_id": "abc"})
    payload = jd_generation_tasks.get_task("task-1").to_status_payload()
    assert payload["status"] == "completed"
    assert payload["result"]["job_id"] == "abc"


def test_mark_failed_task():
    jd_generation_tasks.create_task("task-2")
    jd_generation_tasks.mark_failed("task-2", "LLM timeout")
    payload = jd_generation_tasks.get_task("task-2").to_status_payload()
    assert payload["status"] == "failed"
    assert payload["error"] == "LLM timeout"


def test_format_pgvector_literal():
    literal = _format_pgvector_literal([0.1, 0.2, 0.3])
    assert literal == "[0.1,0.2,0.3]"
