"""
Vertex AI credential policy for QuantHire.

Default: **Application Default Credentials (ADC) only** — from
``gcloud auth application-default login`` (well-known JSON path), or optionally
from ``GCP_ADC_CREDENTIALS_PATH`` / ``GOOGLE_ADC_CREDENTIALS`` pointing at the same
OAuth-style ADC JSON file. In ADC-only mode the process **clears** any prior
``GOOGLE_APPLICATION_CREDENTIALS`` (service-account paths) and optionally **rebinds**
it to ``GCP_ADC_CREDENTIALS_PATH`` so all Google client libraries load user ADC.

Opt-out of ADC-only (e.g. CI with a service-account key file):
  GCP_USE_ADC_ONLY=false
  GCP_ALLOW_SERVICE_ACCOUNT_KEY=true
  GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_BOOTSTRAPPED = False


def _env_truthy(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


def primary_vertex_model() -> str:
    """Canonical Vertex model ID for all production LLM calls."""
    for key in ("LLM_MODEL_NAME", "LLM_MODEL", "GEMINI_MODEL"):
        raw = os.getenv(key)
        if raw and raw.strip():
            return raw.strip()
    return "gemini-2.5-pro"


def fallback_vertex_model() -> str:
    """Retry model on transient Vertex errors; defaults to primary (gemini-2.5-pro)."""
    raw = os.getenv("LLM_FALLBACK_MODEL")
    if raw and raw.strip():
        return raw.strip()
    return primary_vertex_model()


def project_env_file_candidates() -> list[Path]:
    """Ordered .env paths: repo root first, then common app subdirs."""
    here = Path(__file__).resolve()
    # .../apps/agents/agents/gcp_vertex_credentials.py -> repo root is parents[3]
    repo_root = here.parents[3]
    cwd = Path.cwd()
    candidates = [
        repo_root / ".env",
        cwd / ".env",
        cwd / "apps" / "api" / ".env",
        repo_root / "apps" / "api" / ".env",
        repo_root / "apps" / "agents" / ".env",
        repo_root / "apps" / "agents" / "agents" / "jd_generation" / ".env",
    ]
    seen: set[str] = set()
    out: list[Path] = []
    for p in candidates:
        key = str(p.resolve()) if p.exists() else str(p)
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def bootstrap_vertex_adc(*, load_env: bool = True, log_status: bool = False) -> None:
    """Load repo ``.env``, then enforce ADC-only Vertex auth. Safe to call repeatedly."""
    global _BOOTSTRAPPED
    if load_env:
        try:
            from dotenv import load_dotenv

            for env_path in project_env_file_candidates():
                if env_path.is_file():
                    load_dotenv(env_path, override=False)
        except ImportError:
            pass
    prepare_vertex_runtime_for_adc_only()
    if log_status and not _BOOTSTRAPPED:
        project = os.getenv("GCP_PROJECT_ID", "(unset)")
        creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or "(google.auth.default)"
        logger.info(
            "Vertex ADC bootstrap: project=%s model=%s credentials=%s",
            project,
            primary_vertex_model(),
            creds,
        )
    _BOOTSTRAPPED = True


def adc_status() -> dict[str, str | bool | None]:
    """Snapshot for health endpoints / debugging."""
    return {
        "gcp_project_id": os.getenv("GCP_PROJECT_ID"),
        "gcp_use_adc_only": os.getenv("GCP_USE_ADC_ONLY", "true"),
        "gcp_adc_credentials_path": os.getenv("GCP_ADC_CREDENTIALS_PATH"),
        "google_application_credentials": os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
        "llm_model": primary_vertex_model(),
        "vertex_adc_available": vertex_credential_source_available(),
    }


def adc_json_candidate_paths() -> list[str]:
    paths: list[str] = []
    # Optional explicit ADC file (same format as `gcloud auth application-default login`)
    custom = os.getenv("GCP_ADC_CREDENTIALS_PATH") or os.getenv("GOOGLE_ADC_CREDENTIALS")
    if custom:
        p = os.path.expandvars(os.path.expanduser(custom.strip().strip('"')))
        if p:
            paths.append(p)
    appdata = os.environ.get("APPDATA")
    if appdata:
        paths.append(
            os.path.join(appdata, "gcloud", "application_default_credentials.json")
        )
    paths.append(
        os.path.join(
            os.path.expanduser("~"),
            ".config",
            "gcloud",
            "application_default_credentials.json",
        )
    )
    return paths


def prepare_vertex_runtime_for_adc_only() -> None:
    """Enforce ADC-first auth for Vertex when ``GCP_USE_ADC_ONLY`` is true (default).

    1. Drops any ``GOOGLE_APPLICATION_CREDENTIALS`` value (typically a service-account
       JSON path from .env, the shell, or the OS) so we do **not** use a key file as
       the primary mechanism.
    2. If ``GCP_ADC_CREDENTIALS_PATH`` / ``GOOGLE_ADC_CREDENTIALS`` points at your
       **application-default** JSON (from ``gcloud auth application-default login``),
       sets ``GOOGLE_APPLICATION_CREDENTIALS`` to that path so every Google client
       loads the same user ADC file (still not a service account key).
    3. If no explicit ADC path is set, leaves the variable unset so
       ``google.auth.default()`` uses the normal ADC search order (including
       ``%APPDATA%\\gcloud\\application_default_credentials.json`` on Windows).

    Call this once, as early as possible after ``load_dotenv``, before Vertex clients
    are constructed. This does **not** use ``GEMINI_API_KEY`` / ``GOOGLE_API_KEY``;
    those are for the separate Generative Language API, not Vertex.
    """
    if not _env_truthy("GCP_USE_ADC_ONLY", "true"):
        return
    removed = os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)

    pinned = False
    custom = os.getenv("GCP_ADC_CREDENTIALS_PATH") or os.getenv("GOOGLE_ADC_CREDENTIALS")
    if custom:
        adc_path = os.path.expandvars(os.path.expanduser(custom.strip().strip('"')))
        if adc_path and os.path.isfile(adc_path):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = adc_path
            pinned = True
            if removed and os.path.normcase(removed) == os.path.normcase(adc_path):
                logger.info(
                    "Vertex AI auth: using Application Default Credentials at %s "
                    "(user ADC from gcloud auth application-default login).",
                    adc_path,
                )
            else:
                logger.info(
                    "Vertex AI auth: using Application Default Credentials at %s "
                    "(rebound from prior GOOGLE_APPLICATION_CREDENTIALS=%s).",
                    adc_path,
                    removed or "(unset)",
                )
        elif adc_path:
            logger.warning(
                "GCP_ADC_CREDENTIALS_PATH is set but file not found: %s",
                adc_path,
            )

    if not pinned:
        if removed:
            logger.info(
                "GCP_USE_ADC_ONLY: former GOOGLE_APPLICATION_CREDENTIALS was cleared; "
                "using google.auth.default() / standard ADC locations. "
                "Set GCP_ADC_CREDENTIALS_PATH to pin your application_default_credentials.json."
            )
        else:
            logger.info(
                "GCP_USE_ADC_ONLY: using google.auth.default() / standard ADC locations "
                "(no service-account JSON as primary auth)."
            )


def vertex_credential_source_available() -> bool:
    """Return True if this process can authenticate to Vertex.

    * Default: only checks for gcloud **ADC** JSON on disk.
    * If ``GCP_ALLOW_SERVICE_ACCOUNT_KEY=true``, also accepts an existing
      ``GOOGLE_APPLICATION_CREDENTIALS`` file path.
    """
    if _env_truthy("GCP_ALLOW_SERVICE_ACCOUNT_KEY", "false"):
        raw = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if raw:
            path = os.path.expandvars(os.path.expanduser(raw.strip().strip('"')))
            if os.path.isfile(path):
                return True
    return any(os.path.isfile(p) for p in adc_json_candidate_paths())
