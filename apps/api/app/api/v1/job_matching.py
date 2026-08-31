"""
Job Matching API Endpoints
==========================
REST + Server-Sent-Events (SSE) endpoints powered by the
``JobMatchingOrchestrator`` swarm.

Routes
------
* ``GET  /v1/job-matching/candidates``       — list candidates available to match.
* ``GET  /v1/job-matching/jds``              — list JDs available to match against.
* ``POST /v1/job-matching/match``            — blocking match → MatchResult JSON.
* ``GET  /v1/job-matching/match-stream``     — SSE stream of live agent thoughts.
* ``POST /v1/job-matching/rank``             — rank N candidates against one JD.
* ``GET  /v1/job-matching/health``           — quick readiness probe.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.auth_policy import require_user_when_basic_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/job-matching", tags=["Job Matching"])


# ----------------------------------------------------------------------- bootstrap path
def _ensure_agents_path() -> None:
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent.parent.parent.parent
    agents_path = project_root / "apps" / "agents" / "agents"
    if not agents_path.exists():
        cwd = Path.cwd()
        candidates = [
            cwd / "apps" / "agents" / "agents",
            cwd.parent / "apps" / "agents" / "agents",
            current_file.parent.parent.parent.parent.parent / "apps" / "agents" / "agents",
        ]
        for cand in candidates:
            if cand.exists():
                agents_path = cand
                break
    if agents_path.exists() and str(agents_path) not in sys.path:
        sys.path.insert(0, str(agents_path))
    parent = agents_path.parent
    if parent.exists() and str(parent) not in sys.path:
        sys.path.insert(0, str(parent))


_ensure_agents_path()

_ORCHESTRATOR_CACHE: dict[str, Any] = {"instance": None}
_orchestrator_lock = threading.Lock()


def _llm_configured() -> bool:
    prov = os.getenv("LLM_PROVIDER", "openai").strip().lower()
    if prov == "openai":
        return bool(os.getenv("OPENAI_API_KEY", "").strip())
    if prov == "azure_openai":
        try:
            from agents.llm.chat_factory import is_azure_openai_configured

            return is_azure_openai_configured()
        except Exception:
            endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()
            api_key = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
            return bool(endpoint and api_key)
    gcp_project = os.getenv("GCP_PROJECT_ID", "").strip()
    return bool(gcp_project)


def _ensure_llm_configured_for_matching() -> None:
    if _llm_configured():
        return
    prov = os.getenv("LLM_PROVIDER", "openai").strip().lower()
    if prov == "azure_openai":
        detail = (
            "Azure OpenAI not configured for HSS-D matching. Set AZURE_OPENAI_ENDPOINT "
            "and AZURE_OPENAI_API_KEY (quanthire-aoai-secret on AKS)."
        )
    elif prov == "openai":
        detail = "OpenAI not configured. Set OPENAI_API_KEY and LLM_PROVIDER=openai."
    else:
        detail = "LLM not configured for job matching."
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)


def _raise_match_http_error(exc: Exception, *, operation: str) -> None:
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"{operation} timed out: {exc}",
        ) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"{operation} failed: {exc}",
    ) from exc


def _get_orchestrator():
    """Lazy, cached singleton so the module imports even if Vertex AI is misconfigured."""
    global _ORCHESTRATOR_CACHE
    if _ORCHESTRATOR_CACHE["instance"] is not None:
        return _ORCHESTRATOR_CACHE["instance"]

    with _orchestrator_lock:
        if _ORCHESTRATOR_CACHE["instance"] is not None:
            return _ORCHESTRATOR_CACHE["instance"]
        _ensure_llm_configured_for_matching()
        from agents.job_matching import JobMatchingOrchestrator  # type: ignore

        instance = JobMatchingOrchestrator()
        _ORCHESTRATOR_CACHE["instance"] = instance
        logger.info("JobMatchingOrchestrator singleton initialized")
        return instance


# ----------------------------------------------------------------------- DTOs
class WeightOverride(BaseModel):
    skills: Optional[float] = None
    experience: Optional[float] = None
    education: Optional[float] = None
    domain: Optional[float] = None
    culture: Optional[float] = None
    growth: Optional[float] = None
    projects: Optional[float] = None
    risk: Optional[float] = None


class MatchRequest(BaseModel):
    candidate_id: str = Field(..., description="Resume document_id from pgvector/Milvus")
    jd_id: str = Field(..., description="JD document_id from pgvector/Milvus")
    weights: Optional[WeightOverride] = None


class RankRequest(BaseModel):
    jd_id: str
    candidate_ids: Optional[list[str]] = None
    weights: Optional[WeightOverride] = None
    max_concurrency: int = Field(default=3, ge=1, le=8)


def _weights_dict(w: Optional[WeightOverride]) -> Optional[dict[str, float]]:
    if not w:
        return None
    out: dict[str, float] = {}
    for key in (
        "skills",
        "experience",
        "education",
        "domain",
        "culture",
        "growth",
        "projects",
        "risk",
    ):
        val = getattr(w, key)
        if val is not None:
            out[key] = float(val)
    return out or None


def _list_candidates_sync() -> list[Any]:
    """Lightweight Milvus listing — do not init the full swarm orchestrator."""
    from agents.job_matching.config import get_config
    from agents.job_matching.data_access import list_candidates

    cfg = get_config()
    return list_candidates(cfg.resume_collection_name)


def _list_jds_sync() -> list[Any]:
    from agents.job_matching.config import get_config
    from agents.job_matching.data_access import list_jds

    cfg = get_config()
    return list_jds(cfg.jd_collection_name)


# ----------------------------------------------------------------------- listings
@router.get("/candidates")
async def list_candidates_for_matching() -> dict[str, Any]:
    """Return every candidate in the vector store (pgvector on Azure, Milvus locally)."""
    try:
        profiles = await asyncio.to_thread(_list_candidates_sync)
        return {
            "total": len(profiles),
            "candidates": [
                {
                    "candidate_id": p.candidate_id,
                    "name": p.name,
                    "email": p.email,
                    "headline": p.headline or p.current_role,
                    "total_years_experience": p.total_years_experience,
                    "skills": p.technical_skills[:10],
                    "location": p.location,
                }
                for p in profiles
            ],
        }
    except Exception as exc:
        logger.error("list_candidates_for_matching failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list candidates: {exc}",
        )


@router.get("/jds")
async def list_jds_for_matching() -> dict[str, Any]:
    """Return every JD in the vector store (pgvector on Azure, Milvus locally)."""
    try:
        jds = await asyncio.to_thread(_list_jds_sync)
        return {
            "total": len(jds),
            "jds": [
                {
                    "jd_id": jd.jd_id,
                    "job_title": jd.job_title,
                    "department": jd.department,
                    "location": jd.location,
                    "job_level": jd.job_level,
                    "required_skills": jd.required_skills[:10],
                    "summary": (jd.position_summary or "")[:280],
                }
                for jd in jds
            ],
        }
    except Exception as exc:
        logger.error("list_jds_for_matching failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list JDs: {exc}",
        )


# ----------------------------------------------------------------------- blocking match
@router.post("/match")
async def match(
    request: MatchRequest,
    current_user: Optional[dict] = Depends(require_user_when_basic_auth),
) -> dict[str, Any]:
    try:
        orchestrator = _get_orchestrator()
    except Exception as exc:
        logger.error("Orchestrator init failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialise matching system: {exc}",
        )

    try:
        result = await orchestrator.amatch(
            candidate_id=request.candidate_id,
            jd_id=request.jd_id,
            weights=_weights_dict(request.weights),
        )
        return result.model_dump(mode="json")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Matching failed: %s", exc, exc_info=True)
        _raise_match_http_error(exc, operation="Matching")


# ----------------------------------------------------------------------- streaming match
@router.get("/match-stream")
async def match_stream(
    candidate_id: str = Query(..., description="Resume document_id"),
    jd_id: str = Query(..., description="JD document_id"),
    weights: Optional[str] = Query(
        None,
        description=(
            "Optional URL-encoded JSON weight overrides, "
            'e.g. {"skills":0.4,"experience":0.2,"culture":0.1}'
        ),
    ),
    current_user: Optional[dict] = Depends(require_user_when_basic_auth),
) -> StreamingResponse:
    """Server-Sent-Events stream of agent thoughts followed by the final result."""

    parsed_weights: Optional[dict[str, float]] = None
    if weights:
        try:
            parsed_weights = json.loads(weights)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="`weights` must be a valid JSON object",
            )

    try:
        orchestrator = _get_orchestrator()
    except Exception as exc:
        logger.error("Orchestrator init failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialise matching system: {exc}",
        )

    async def event_source():
        # Heartbeat: tells the browser the connection is alive.
        yield "event: open\ndata: {}\n\n"
        try:
            async for evt in orchestrator.stream(
                candidate_id=candidate_id,
                jd_id=jd_id,
                weights=parsed_weights,
            ):
                event_name = evt.get("event") or "message"
                payload = json.dumps(evt.get("data", {}), default=str)
                yield f"event: {event_name}\ndata: {payload}\n\n"
        except asyncio.CancelledError:  # pragma: no cover
            logger.info("SSE client disconnected")
            raise
        except TimeoutError as exc:
            logger.error("SSE stream timed out: %s", exc, exc_info=True)
            yield (
                "event: error\n"
                f"data: {json.dumps({'message': f'HSS-D matching timed out: {exc}'})}\n\n"
            )
        except Exception as exc:
            logger.error("SSE stream failed: %s", exc, exc_info=True)
            yield (
                "event: error\n"
                f"data: {json.dumps({'message': str(exc)})}\n\n"
            )
        finally:
            yield "event: close\ndata: {}\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ----------------------------------------------------------------------- ranking
@router.post("/rank")
async def rank(
    request: RankRequest,
    current_user: Optional[dict] = Depends(require_user_when_basic_auth),
) -> dict[str, Any]:
    try:
        orchestrator = _get_orchestrator()
    except Exception as exc:
        logger.error("Orchestrator init failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialise matching system: {exc}",
        )

    try:
        result = await orchestrator.arank(
            jd_id=request.jd_id,
            candidate_ids=request.candidate_ids,
            weights=_weights_dict(request.weights),
            max_concurrency=request.max_concurrency,
        )
        return result.model_dump(mode="json")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Ranking failed: %s", exc, exc_info=True)
        _raise_match_http_error(exc, operation="Ranking")


# ----------------------------------------------------------------------- health
@router.get("/health")
async def health() -> dict[str, Any]:
    llm_ready = _llm_configured()
    try:
        orchestrator = _get_orchestrator()
    except HTTPException as exc:
        return {
            "status": "degraded",
            "pipeline": "hss-d",
            "llm_available": llm_ready,
            "error": exc.detail,
        }
    except Exception as exc:
        return {
            "status": "degraded",
            "pipeline": "hss-d",
            "llm_available": llm_ready,
            "error": str(exc),
        }
    try:
        from agents.llm.chat_factory import llm_status

        llm_info = llm_status()
        from app.config import settings

        storage_backend = "pgvector" if settings.use_pgvector_pipeline else "milvus"
        return {
            "status": "ok" if llm_ready else "degraded",
            "pipeline": "hss-d",
            "storage_backend": storage_backend,
            "llm_available": llm_ready,
            "swarm_size": len(orchestrator._specialists) + 1,  # +risk
            "debate_enabled": orchestrator.config.enable_critic_debate,
            "bias_audit_enabled": orchestrator.config.enable_bias_audit,
            "parallel_swarm": orchestrator.config.parallel_swarm,
            "swarm_llm_max_concurrent": orchestrator.config.swarm_llm_max_concurrent,
            "llm_provider": orchestrator.config.llm_provider,
            "model": orchestrator.config.llm_model,
            "swarm_model": orchestrator._llm_swarm.model_name,
            "synthesis_model": orchestrator._llm_debate.model_name,
            "gcp_project": orchestrator.config.gcp_project,
            "gcp_location": orchestrator.config.gcp_location,
            "llm": llm_info,
            "vertex_json_response": orchestrator.config.vertex_json_response,
            "vertex_max_retries": orchestrator.config.vertex_max_retries,
            "jd_collection": orchestrator.config.jd_collection_name,
            "resume_collection": orchestrator.config.resume_collection_name,
            "milvus_jd_collection": orchestrator.config.jd_collection_name,
            "milvus_resume_collection": orchestrator.config.resume_collection_name,
            "thresholds": {
                "STRONG_HIRE": orchestrator.config.strong_hire_threshold,
                "HIRE": orchestrator.config.hire_threshold,
                "CONSIDER": orchestrator.config.consider_threshold,
            },
            "endpoints": {
                "match": "/api/v1/job-matching/match",
                "match_stream": "/api/v1/job-matching/match-stream",
                "rank": "/api/v1/job-matching/rank",
            },
        }
    except Exception as exc:
        return {
            "status": "degraded",
            "pipeline": "hss-d",
            "llm_available": llm_ready,
            "error": str(exc),
        }
