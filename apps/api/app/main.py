"""Main FastAPI application with enterprise-grade configuration."""

# Load environment variables from .env file FIRST (before any other imports)
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (parent of apps/api)
project_root = Path(__file__).resolve().parent.parent.parent.parent
env_file = project_root / ".env"
if env_file.exists():
    load_dotenv(env_file)
else:
    # Also try apps/api/.env
    api_env = Path(__file__).resolve().parent.parent / ".env"
    if api_env.exists():
        load_dotenv(api_env)

from app.config import settings
from app.core.azure_env import sync_azure_env_from_settings

sync_azure_env_from_settings(settings)

# --- Vertex: ADC-only by default (before any router imports) -----------------
import sys

_agents_parent = Path(__file__).resolve().parent.parent.parent / "agents"
if _agents_parent.is_dir() and str(_agents_parent) not in sys.path:
    sys.path.insert(0, str(_agents_parent))
try:
    from agents.llm.chat_factory import ensure_llm_env, llm_provider, llm_status

    ensure_llm_env()
    if llm_provider() not in ("openai", "azure_openai"):
        from agents.gcp_vertex_credentials import bootstrap_vertex_adc

        bootstrap_vertex_adc(load_env=True, log_status=True)
except Exception:
    pass

from contextlib import asynccontextmanager
from typing import AsyncGenerator

# Optional import for Sentry (only used if configured)
try:
    import sentry_sdk
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
# Optional import for Prometheus (only used if enabled)
try:
    from prometheus_client import make_asgi_app
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    make_asgi_app = None

from app.api.v1 import router as api_v1_router
from app.core.exceptions import QuantHireException
from app.core.logging import configure_logging
from app.core.milvus_init import connect_and_load_collections, disconnect_milvus
from app.core.middleware import (
    ErrorHandlerMiddleware,
    PerformanceMonitoringMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from app.database import check_db_health, close_db, init_db
from app.middleware.logging import LoggingMiddleware
from app.middleware.rate_limit import RateLimitMiddleware

# Configure structured logging
configure_logging()

import asyncio
import logging
import os

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan manager with comprehensive startup/shutdown.
    
    Handles:
    - Database initialization
    - External service connections
    - Monitoring setup
    - Resource cleanup
    """
    # Startup
    logger.info(f"🚀 QuantHireAI API v{settings.app_version} ({settings.app_env})")
    
    try:
        # Milvus: connect + load collections (skip on Azure Non-Prod path)
        if settings.milvus_auto_load and settings.milvus_enabled:
            try:
                await asyncio.to_thread(
                    connect_and_load_collections,
                    load_timeout=settings.milvus_load_timeout,
                )
            except Exception as exc:
                logger.error("Milvus startup load failed: %s", exc, exc_info=True)
                if settings.is_production:
                    raise

        if settings.is_hardened:
            from app.core.security import _validate_jwt_secret

            _validate_jwt_secret()
            logger.info("JWT secret validated for hardened environment")

        # Initialize database (required on Azure Non-Prod; optional locally)
        try:
            await init_db()

            db_health = await check_db_health()
            if db_health.get("status") == "healthy":
                logger.debug("Database connected")
            elif settings.is_hardened:
                raise RuntimeError(
                    f"Database not healthy in hardened environment: {db_health}"
                )
        except Exception as e:
            if settings.is_hardened:
                logger.error("Database init failed in hardened environment: %s", e, exc_info=True)
                raise
            logger.warning("Database init skipped (local dev): %s", e)
        
        # Initialize Sentry if configured and available
        if settings.sentry_dsn and SENTRY_AVAILABLE:
            try:
                sentry_sdk.init(
                    dsn=settings.sentry_dsn,
                    environment=settings.app_env,
                    traces_sample_rate=0.1 if settings.is_hardened else 1.0,
                    profiles_sample_rate=0.1,
                    send_default_pii=False,  # Never send PII to Sentry
                )
            except Exception:
                pass
        
        # Initialize LLM Gateway if enabled (optional - not required for core functionality)
        # These are optional MLOps features - system works without them
        try:
            import sys
            from pathlib import Path
            # Add agents path
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent.parent.parent
            agents_path = project_root / "apps" / "agents" / "agents"
            if agents_path.exists() and str(agents_path) not in sys.path:
                sys.path.insert(0, str(agents_path))
            
            from agents.llm.gateway import init_gateway
            init_gateway(
                redis_url=settings.redis_url,
                daily_budget_usd=settings.llm_daily_budget_usd,
                enable_budget_enforcement=True,
            )
        except Exception:
            pass
        
        # Initialize MLflow tracker if enabled (optional)
        try:
            import sys
            from pathlib import Path
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent.parent.parent
            agents_path = project_root / "apps" / "agents" / "agents"
            if agents_path.exists() and str(agents_path) not in sys.path:
                sys.path.insert(0, str(agents_path))
            
            from agents.mlops.mlflow_tracker import init_mlflow_tracker
            import os
            if os.getenv("ENABLE_MLFLOW", "false").lower() == "true":
                init_mlflow_tracker()
        except Exception:
            pass
        
        # Initialize LangSmith if enabled (optional - JD generation handles its own LangSmith)
        try:
            import sys
            from pathlib import Path
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent.parent.parent
            agents_path = project_root / "apps" / "agents" / "agents"
            if agents_path.exists() and str(agents_path) not in sys.path:
                sys.path.insert(0, str(agents_path))
            
            from agents.mlops.langsmith_integration import init_langsmith
            import os
            if os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true":
                init_langsmith()
        except Exception:
            pass
        
        logger.info("✅ Ready")
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}", exc_info=True)
        raise
    
    yield
    
    # Shutdown
    logger.info("👋 Shutting down QuantHireAI API...")
    
    try:
        await asyncio.to_thread(disconnect_milvus)

        await close_db()
        logger.info("✓ Database connections closed")
        
        # Close LLM Gateway (optional)
        try:
            import sys
            from pathlib import Path
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent.parent.parent
            agents_path = project_root / "apps" / "agents" / "agents"
            if agents_path.exists() and str(agents_path) not in sys.path:
                sys.path.insert(0, str(agents_path))
            
            from agents.llm.gateway import get_gateway
            gateway = get_gateway()
            await gateway.close()
            logger.info("✓ LLM Gateway closed")
        except (ImportError, ModuleNotFoundError, AttributeError):
            pass  # LLM Gateway not available - ignore
        except Exception as e:
            logger.debug(f"Error closing LLM Gateway: {e}")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}", exc_info=True)
    
    logger.info("✅ Shutdown complete")


# Create FastAPI app with comprehensive configuration
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Enterprise Agentic AI Hiring Platform API - Production-Ready with Full Observability",
    openapi_url="/openapi.json" if not settings.is_hardened else None,
    lifespan=lifespan,
    contact={
        "name": "QuantHire AI Team",
        "email": "pradeep.kumar@malomatia.qa",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    docs_url="/docs" if not settings.is_hardened else None,
    redoc_url="/redoc" if not settings.is_hardened else None,
)

# Store settings in app state for access in middleware
app.state.settings = settings

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Add trusted host middleware in hardened environments
if settings.is_hardened:
    default_hosts = "api.quanthire.ai,*.quanthire.ai,localhost,127.0.0.1"
    if settings.is_azure_nonprod:
        default_hosts += (
            ",*.svc.cluster.local,quanthire-backend,"
            "quanthire-backend.quanthire-nonprod.svc.cluster.local"
        )
    allowed_hosts = [
        h.strip()
        for h in os.getenv("ALLOWED_HOSTS", default_hosts).split(",")
        if h.strip()
    ]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

# Add CORS middleware
cors_origins = settings.cors_origins
if settings.is_development:
    cors_origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True if not settings.is_development else False,  # Can't use credentials with wildcard
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-ID", "X-Process-Time"],
    max_age=3600,
)

# Add GZip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add request context middleware (correlation ID, timing) - NO logging, just context
app.add_middleware(RequestContextMiddleware)

# Add error handler middleware
app.add_middleware(ErrorHandlerMiddleware)

# Add performance monitoring middleware
app.add_middleware(PerformanceMonitoringMiddleware, slow_request_threshold=1.0)

# Rate limiting middleware
app.add_middleware(RateLimitMiddleware, rate_limit=settings.rate_limit_per_minute)

# NOTE: LoggingMiddleware removed - Uvicorn provides access logs
# For detailed request logging in production, enable via LOG_LEVEL=DEBUG

# Include API routes
app.include_router(api_v1_router, prefix="/api/v1")

# Global handler for auth/authorization errors raised from dependencies
@app.exception_handler(QuantHireException)
async def quanthire_exception_handler(request: Request, exc: QuantHireException) -> JSONResponse:
    body = exc.to_dict()
    body["error"]["path"] = str(request.url.path)
    return JSONResponse(status_code=exc.status_code, content=body)


# Health check at root level for easier access
try:
    from app.api.health import router as health_router_root

    app.include_router(health_router_root, prefix="/api", tags=["Health"])
except Exception as health_import_error:
    logger.warning("Health router unavailable: %s", health_import_error)

# Prometheus metrics — internal only; not exposed on hardened public-facing API
if settings.prometheus_enabled and not settings.is_hardened:
    if PROMETHEUS_AVAILABLE and make_asgi_app:
        try:
            metrics_app = make_asgi_app()
            app.mount("/metrics", metrics_app)
        except Exception:
            pass
    else:
        logger.warning("Prometheus enabled but prometheus_client not installed. Install with: pip install prometheus-client")


@app.get("/", tags=["Root"])
async def root() -> dict:
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "operational",
        "environment": settings.app_env,
        "docs": "/docs" if not settings.is_hardened else None,
    }


@app.get("/health", tags=["Health"])
@app.get("/healthz", tags=["Health"])
async def health() -> dict:
    """Liveness probe — process is up."""
    return {
        "status": "healthy",
        "version": settings.app_version,
        "environment": settings.app_env,
        "deployment_target": settings.deployment_target,
    }


@app.get("/ready", tags=["Health"])
@app.get("/readyz", tags=["Health"])
async def ready() -> JSONResponse:
    """
    Readiness probe — dependency health for Kubernetes.

    Returns HTTP 503 when blocking checks fail (Azure Non-Prod: Postgres required).
    """
    from app.core.readiness import build_readiness_report

    report = await build_readiness_report()
    status_code = 200 if report["status"] == "ready" else 503
    return JSONResponse(content=report, status_code=status_code)


if __name__ == "__main__":
    import uvicorn
    
    # Automatically include project root in reload directories
    # This ensures changes to real_hybrid_architecture_complete.py trigger reload
    reload_dirs = None
    if settings.debug:
        # Get project root (parent of apps/api)
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        api_dir = Path(__file__).resolve().parent.parent.parent
        reload_dirs = [
            str(api_dir),  # Watch apps/api
            str(project_root),  # Watch project root (real_hybrid_architecture_complete.py, etc.)
        ]
        print(f"🔄 Auto-reload enabled: watching project directories")
        print(f"   📁 {api_dir}")
        print(f"   📁 {project_root}")

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        reload_dirs=reload_dirs if settings.debug else None,
        log_level=settings.log_level.lower(),
    )

