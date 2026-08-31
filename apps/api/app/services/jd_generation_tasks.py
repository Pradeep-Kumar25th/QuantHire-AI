"""In-memory JD generation task registry for async generate + poll."""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional

logger = logging.getLogger(__name__)

TaskStatus = Literal["pending", "running", "completed", "failed"]

_TASK_TTL_SECONDS = 60 * 60
_tasks: Dict[str, "JDGenerationTask"] = {}
_lock = threading.Lock()


@dataclass
class JDGenerationTask:
    task_id: str
    status: TaskStatus = "pending"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    job_title: Optional[str] = None
    department: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_status_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "task_id": self.task_id,
            "status": self.status,
            "job_title": self.job_title,
            "department": self.department,
        }
        if self.status == "completed" and self.result is not None:
            payload["result"] = self.result
        if self.status == "failed" and self.error:
            payload["error"] = self.error
        return payload


def _cleanup_expired() -> None:
    cutoff = time.time() - _TASK_TTL_SECONDS
    expired = [task_id for task_id, task in _tasks.items() if task.updated_at < cutoff]
    for task_id in expired:
        _tasks.pop(task_id, None)


def create_task(
    task_id: str,
    *,
    job_title: Optional[str] = None,
    department: Optional[str] = None,
) -> JDGenerationTask:
    with _lock:
        _cleanup_expired()
        task = JDGenerationTask(
            task_id=task_id,
            job_title=job_title,
            department=department,
        )
        _tasks[task_id] = task
        return task


def mark_running(task_id: str) -> None:
    with _lock:
        task = _tasks.get(task_id)
        if not task:
            return
        task.status = "running"
        task.updated_at = time.time()


def mark_completed(task_id: str, result: Dict[str, Any]) -> None:
    with _lock:
        task = _tasks.get(task_id)
        if not task:
            return
        task.status = "completed"
        task.result = result
        task.updated_at = time.time()


def mark_failed(task_id: str, error: str) -> None:
    with _lock:
        task = _tasks.get(task_id)
        if not task:
            return
        task.status = "failed"
        task.error = error
        task.updated_at = time.time()


def get_task(task_id: str) -> Optional[JDGenerationTask]:
    with _lock:
        _cleanup_expired()
        return _tasks.get(task_id)


def serialize_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure task result is JSON-serializable for status polling."""
    return json.loads(json.dumps(result, default=str))
