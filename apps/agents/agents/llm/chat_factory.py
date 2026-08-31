"""
Shared LangChain chat model factory for QuantHire production agents.

Set ``LLM_PROVIDER=openai`` + ``OPENAI_API_KEY`` for OpenAI,
``LLM_PROVIDER=azure_openai`` + ``AZURE_OPENAI_*`` for Azure Non-Prod, or
``LLM_PROVIDER=vertexai`` + GCP ADC for Vertex AI.
"""

from __future__ import annotations

import logging
import os
import warnings
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_ENV_LOADED = False


def _repo_root() -> Path:
    """Best-effort repo root for local .env discovery; safe in Docker (/app, /agents)."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "apps" / "api").is_dir():
            return parent
    app_dir = Path("/app")
    if app_dir.is_dir():
        return app_dir
    # Avoid IndexError when the image layout is shallower than the dev tree.
    depth = min(4, len(here.parents) - 1)
    return here.parents[depth]


def project_env_file_candidates() -> list[Path]:
    """Ordered .env paths: repo root first (dev); empty-safe in containers."""
    root = _repo_root()
    cwd = Path.cwd()
    candidates = [
        root / ".env",
        cwd / ".env",
    ]
    if (root / "apps" / "api").is_dir():
        candidates.extend(
            [
                cwd / "apps" / "api" / ".env",
                root / "apps" / "api" / ".env",
                root / "apps" / "agents" / ".env",
                root / "apps" / "agents" / "agents" / "jd_generation" / ".env",
            ]
        )
    seen: set[str] = set()
    out: list[Path] = []
    for p in candidates:
        key = str(p.resolve()) if p.exists() else str(p)
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def ensure_llm_env() -> None:
    """Load repo ``.env`` once so all agents share OPENAI_API_KEY / LLM_MODEL."""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    try:
        from dotenv import load_dotenv

        for env_path in project_env_file_candidates():
            if env_path.is_file():
                # Never override explicit env (K8s secrets, Azure workload env).
                load_dotenv(env_path, override=False)
    except ImportError:
        pass
    _ENV_LOADED = True


def llm_provider() -> str:
    ensure_llm_env()
    return os.getenv("LLM_PROVIDER", "openai").strip().lower()


def fast_llm_model() -> str:
    """Optional faster/cheaper tier; defaults to primary model."""
    ensure_llm_env()
    raw = os.getenv("LLM_FAST_MODEL")
    if raw and raw.strip():
        return raw.strip()
    return primary_llm_model()


def primary_llm_model() -> str:
    ensure_llm_env()
    for key in ("LLM_MODEL_NAME", "LLM_MODEL", "OPENAI_MODEL"):
        raw = os.getenv(key)
        if raw and raw.strip():
            return raw.strip()
    prov = llm_provider()
    if prov == "azure_openai":
        deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")
        if deployment and deployment.strip():
            return deployment.strip()
        return "gpt-4o"
    return "gpt-4o" if prov == "openai" else "gemini-2.5-pro"


def fallback_llm_model() -> str:
    ensure_llm_env()
    raw = os.getenv("LLM_FALLBACK_MODEL")
    if raw and raw.strip():
        return raw.strip()
    return primary_llm_model()


def openai_api_key() -> str:
    ensure_llm_env()
    key = os.getenv("OPENAI_API_KEY")
    if not key or not str(key).strip():
        raise ValueError(
            "OPENAI_API_KEY environment variable not set. "
            "Add it to the repo root .env when LLM_PROVIDER=openai."
        )
    return str(key).strip()


def is_openai_configured() -> bool:
    ensure_llm_env()
    key = os.getenv("OPENAI_API_KEY")
    return bool(key and str(key).strip())


def azure_openai_endpoint() -> str:
    ensure_llm_env()
    return os.getenv("AZURE_OPENAI_ENDPOINT", "").strip().rstrip("/")


def azure_openai_api_version() -> str:
    ensure_llm_env()
    return os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview").strip()


def azure_openai_chat_deployment() -> str:
    ensure_llm_env()
    for key in ("AZURE_OPENAI_CHAT_DEPLOYMENT", "LLM_MODEL", "LLM_MODEL_NAME"):
        raw = os.getenv(key)
        if raw and raw.strip():
            return raw.strip()
    return "gpt-4o"


def azure_openai_api_key() -> Optional[str]:
    ensure_llm_env()
    key = os.getenv("AZURE_OPENAI_API_KEY")
    if key and str(key).strip():
        return str(key).strip()
    return None


def is_azure_openai_configured() -> bool:
    ensure_llm_env()
    if not azure_openai_endpoint():
        return False
    if azure_openai_api_key():
        return True
    try:
        import azure.identity  # noqa: F401

        return True
    except ImportError:
        return False


def _build_azure_chat_openai(
    *,
    deployment: str,
    temperature: float,
    max_tokens: Optional[int],
    max_retries: Optional[int],
    json_mode: bool,
) -> Any:
    from langchain_openai import AzureChatOpenAI

    kwargs: dict[str, Any] = {
        "azure_endpoint": azure_openai_endpoint(),
        "azure_deployment": deployment,
        "api_version": azure_openai_api_version(),
        "temperature": temperature,
    }
    api_key = azure_openai_api_key()
    if api_key:
        kwargs["api_key"] = api_key
    else:
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider

        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(),
            "https://cognitiveservices.azure.com/.default",
        )
        kwargs["azure_ad_token_provider"] = token_provider
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    if max_retries is not None:
        kwargs["max_retries"] = max_retries
    if json_mode:
        kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}
    return AzureChatOpenAI(**kwargs)


def create_chat_llm(
    model: Optional[str] = None,
    temperature: float = 0.5,
    max_tokens: Optional[int] = None,
    *,
    json_mode: bool = False,
    provider: Optional[str] = None,
    max_retries: Optional[int] = None,
) -> Any:
    """Return a LangChain chat model for the configured provider."""
    prov = (provider or llm_provider()).strip().lower()
    model_name = (model or primary_llm_model()).strip()

    if prov == "openai":
        from langchain_openai import ChatOpenAI

        kwargs: dict[str, Any] = {
            "model": model_name,
            "temperature": temperature,
            "api_key": openai_api_key(),
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if max_retries is not None:
            kwargs["max_retries"] = max_retries
        if json_mode:
            kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}
        return ChatOpenAI(**kwargs)

    if prov in ("vertexai", "google"):
        from langchain_google_vertexai import ChatVertexAI

        project = os.getenv("GCP_PROJECT_ID")
        if not project:
            raise ValueError("GCP_PROJECT_ID environment variable not set for Vertex AI.")
        location = os.getenv("GCP_LOCATION", "us-central1")
        vertex_kwargs: dict[str, Any] = {
            "model_name": model_name,
            "project": project,
            "location": location,
            "temperature": temperature,
        }
        if max_tokens is not None:
            vertex_kwargs["max_output_tokens"] = max_tokens
        if max_retries is not None:
            vertex_kwargs["max_retries"] = max_retries
        if json_mode:
            vertex_kwargs["response_mime_type"] = "application/json"
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            return ChatVertexAI(**vertex_kwargs)

    if prov == "azure_openai":
        if not is_azure_openai_configured():
            raise ValueError(
                "Azure OpenAI is not configured. Set AZURE_OPENAI_ENDPOINT and "
                "AZURE_OPENAI_API_KEY (or install azure-identity for managed identity)."
            )
        deployment = model_name or azure_openai_chat_deployment()
        return _build_azure_chat_openai(
            deployment=deployment,
            temperature=temperature,
            max_tokens=max_tokens,
            max_retries=max_retries,
            json_mode=json_mode,
        )

    raise ValueError(
        f"Unsupported LLM_PROVIDER: {prov!r}. Use 'openai', 'azure_openai', or 'vertexai'."
    )


def llm_status() -> dict[str, Any]:
    """Runtime LLM config for health endpoints."""
    ensure_llm_env()
    prov = llm_provider()
    status: dict[str, Any] = {
        "llm_provider": prov,
        "llm_model": primary_llm_model(),
        "llm_fallback_model": fallback_llm_model(),
        "llm_fast_model": fast_llm_model(),
        "openai_api_key_set": is_openai_configured(),
    }
    if prov == "openai":
        status["openai_configured"] = is_openai_configured()
        if is_openai_configured():
            key = os.getenv("OPENAI_API_KEY", "")
            status["openai_api_key_prefix"] = key[:7] + "..." if len(key) > 10 else "(set)"
    elif prov == "azure_openai":
        status["azure_openai_configured"] = is_azure_openai_configured()
        status["azure_openai_endpoint"] = azure_openai_endpoint()
        status["azure_openai_chat_deployment"] = azure_openai_chat_deployment()
        status["azure_openai_api_key_set"] = bool(azure_openai_api_key())
    else:
        try:
            from agents.gcp_vertex_credentials import adc_status

            status["vertex_adc"] = adc_status()
        except Exception as exc:
            status["vertex_adc"] = {"error": str(exc)}
    return status
