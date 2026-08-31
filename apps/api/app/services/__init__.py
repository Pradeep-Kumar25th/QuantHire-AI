"""Business logic services.

Import service classes from their modules directly, e.g.
``from app.services.jd_pipeline_service import JDPipelineService``.

Avoid eager imports here — some services depend on optional packages (Celery
``worker``) that are not installed in the API container on Azure Non-Prod.
"""

__all__ = ["JobService", "CandidateService", "ApplicationService"]
