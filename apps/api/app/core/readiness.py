"""Readiness and liveness helpers for Kubernetes probes (Azure Non-Prod path)."""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


async def check_redis() -> dict[str, Any]:
    try:
        import redis.asyncio as redis

        client = redis.from_url(settings.redis_url)
        await client.ping()
        await client.close()
        return {"status": "healthy"}
    except ImportError:
        return {"status": "not_configured"}
    except Exception as exc:
        logger.debug("Redis check failed (optional): %s", exc)
        return {"status": "not_configured"}


async def check_llm_gateway() -> dict[str, Any]:
    try:
        import sys
        from pathlib import Path

        agents_path = (
            Path(__file__).resolve().parent.parent.parent.parent / "agents" / "agents"
        )
        if agents_path.exists() and str(agents_path) not in sys.path:
            sys.path.insert(0, str(agents_path))

        from agents.llm.gateway import get_gateway

        gateway = get_gateway()
        budget_status = await gateway.get_budget_status()
        return {
            "status": "healthy",
            "budget_utilization": f"{budget_status.utilization_pct:.1%}",
        }
    except (ImportError, ModuleNotFoundError, AttributeError):
        return {"status": "not_configured"}
    except Exception as exc:
        logger.debug("LLM gateway check skipped (optional): %s", exc)
        return {"status": "not_configured"}


def check_milvus() -> dict[str, Any]:
    if not settings.milvus_enabled:
        return {"status": "disabled", "reason": settings.deployment_target}

    try:
        from app.core.milvus_init import milvus_status

        mv = milvus_status()
        if mv.get("connected"):
            loaded = all(
                c.get("loaded")
                for c in mv.get("collections", {}).values()
                if c.get("exists")
            )
            return {
                "status": "healthy" if loaded else "collections_not_loaded",
                "collections": mv.get("collections", {}),
            }
        return {"status": "not_connected"}
    except Exception as exc:
        logger.debug("Milvus check failed: %s", exc)
        return {"status": "unavailable", "error": str(exc)}


def _azure_openai_is_configured() -> bool:
    """Use API settings (same source as blob/DI checks), not os.getenv after dotenv."""
    endpoint = (settings.azure_openai_endpoint or "").strip().rstrip("/")
    if not endpoint:
        return False
    api_key = settings.azure_openai_api_key
    if api_key and str(api_key).strip():
        return True
    try:
        import azure.identity  # noqa: F401

        return True
    except ImportError:
        return False


async def check_azure_openai() -> dict[str, Any]:
    if settings.llm_provider != "azure_openai":
        return {"status": "not_applicable"}
    try:
        configured = _azure_openai_is_configured()
        return {
            "status": "healthy" if configured else "not_configured",
            "endpoint": settings.azure_openai_endpoint,
            "chat_deployment": settings.azure_openai_chat_deployment,
            "api_key_set": bool(
                settings.azure_openai_api_key and str(settings.azure_openai_api_key).strip()
            ),
        }
    except Exception as exc:
        logger.debug("Azure OpenAI check failed: %s", exc)
        return {"status": "not_configured", "error": str(exc)}


def check_azure_blob() -> dict[str, Any]:
    if settings.storage_backend != "azure_blob":
        return {"status": "not_applicable"}
    try:
        from app.integrations.azure_blob import get_blob_storage

        blob = get_blob_storage()
        configured = blob.is_configured()
        return {
            "status": "healthy" if configured else "not_configured",
            "uploads_container": settings.azure_storage_container,
        }
    except Exception as exc:
        logger.debug("Azure Blob check failed: %s", exc)
        return {"status": "not_configured", "error": str(exc)}


def check_document_intelligence() -> dict[str, Any]:
    if not settings.azure_document_intelligence_enabled:
        return {"status": "disabled"}
    try:
        from app.integrations.document_intelligence import get_document_intelligence_client

        di = get_document_intelligence_client()
        configured = di.is_configured()
        return {
            "status": "healthy" if configured else "not_configured",
            "endpoint": settings.azure_document_intelligence_endpoint,
            "model": settings.azure_document_intelligence_model,
        }
    except Exception as exc:
        logger.debug("Document Intelligence check failed: %s", exc)
        return {"status": "not_configured", "error": str(exc)}


async def build_readiness_report() -> dict[str, Any]:
    """Build readiness payload used by /ready and /readyz."""
    from app.database import check_db_health

    checks: dict[str, Any] = {
        "deployment_target": settings.deployment_target,
        "auth_mode": settings.auth_mode,
        "vector_store": settings.vector_store_type,
        "llm_provider": settings.llm_provider,
    }

    db_health = await check_db_health()
    checks["database"] = db_health.get("status", "not_configured")

    checks["redis"] = (await check_redis())["status"]
    checks["llm_gateway"] = (await check_llm_gateway())["status"]
    checks["milvus"] = check_milvus()["status"]
    checks["azure_openai"] = (await check_azure_openai())["status"]
    checks["azure_blob"] = check_azure_blob()["status"]
    checks["document_intelligence"] = check_document_intelligence()["status"]
    if settings.use_pgvector_pipeline:
        checks["vector_pipeline"] = "pgvector"
    else:
        checks["vector_pipeline"] = "milvus"

    blocking: list[str] = []

    if settings.postgres_required:
        if checks["database"] != "healthy":
            blocking.append("database")

    if settings.milvus_required:
        if checks["milvus"] not in ("healthy", "disabled"):
            blocking.append("milvus")

    # On Azure Non-Prod, block readiness until platform dependencies are configured.
    if settings.is_azure_nonprod:
        if checks.get("azure_openai") not in ("healthy",):
            blocking.append("azure_openai")
        if settings.azure_document_intelligence_enabled:
            if checks.get("document_intelligence") not in ("healthy",):
                blocking.append("document_intelligence")
        if settings.storage_backend == "azure_blob":
            if checks.get("azure_blob") not in ("healthy",):
                blocking.append("azure_blob")

    overall = "ready" if not blocking else "not_ready"

    return {
        "status": overall,
        "version": settings.app_version,
        "environment": settings.app_env,
        "deployment_target": settings.deployment_target,
        "checks": checks,
        "blocking": blocking,
    }
