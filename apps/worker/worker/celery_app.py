"""Celery application configuration."""

import os

from celery import Celery
from celery.schedules import crontab

# Get broker URL from environment
BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")

# Create Celery app
app = Celery(
    "quanthire",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
    include=[
        "worker.tasks.parsing",
        "worker.tasks.embeddings",
        "worker.tasks.notifications",
    ],
)

# Configuration
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour
    task_soft_time_limit=3300,  # 55 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    # Retry configuration
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Result expiration
    result_expires=86400,  # 24 hours
)

# Periodic tasks (Celery Beat schedule)
app.conf.beat_schedule = {
    "send-interview-reminders": {
        "task": "worker.tasks.notifications.send_interview_reminders",
        "schedule": crontab(hour="*/1"),  # Every hour
    },
    "cleanup-expired-data": {
        "task": "worker.tasks.maintenance.cleanup_expired_data",
        "schedule": crontab(hour=2, minute=0),  # Daily at 2 AM
    },
}

