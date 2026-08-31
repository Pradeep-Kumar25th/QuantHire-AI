"""
Secure Configuration Loader for QuantHire AI
Enterprise-level secure API key management - VERTEX AI ONLY
"""
import os
from pathlib import Path
from typing import Optional


class SecureConfig:
    """Secure configuration loader that uses Vertex AI (no standard Gemini API key)."""

    @staticmethod
    def _adc_or_allowed_sa() -> bool:
        if os.getenv("GCP_ALLOW_SERVICE_ACCOUNT_KEY", "").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        ):
            raw = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if raw:
                p = os.path.expandvars(os.path.expanduser(raw.strip().strip('"')))
                if os.path.isfile(p):
                    return True
        appdata = os.environ.get("APPDATA")
        paths: list[str] = []
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
        return any(os.path.isfile(x) for x in paths)

    # Project root (assuming this file is in apps/agents/src/quantire_agents/config/)
    _PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent
    _SECRETS_DIR = _PROJECT_ROOT / "secrets"
    
    @classmethod
    def is_vertex_ai_configured(cls) -> bool:
        """True if GCP project is set and ADC (or allowed SA key) is present."""
        gcp_project = os.getenv("GCP_PROJECT_ID")
        return bool(gcp_project and cls._adc_or_allowed_sa())
    
    @classmethod
    def get_vertex_ai_config(cls) -> dict:
        """
        Get Vertex AI configuration from environment.
        
        Returns:
            Dictionary with project, location, and credentials path
        """
        return {
            "project": os.getenv("GCP_PROJECT_ID"),
            "location": os.getenv("GCP_LOCATION", "us-central1"),
            # May be unset when using ADC-only (GOOGLE_APPLICATION_CREDENTIALS cleared at runtime).
            "credentials": os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
        }
    
    @classmethod
    def get_openai_api_key(cls) -> Optional[str]:
        """
        Get OpenAI API key from environment variable.
        
        Returns:
            API key string or None if not found
        """
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            return api_key.strip()
        return None
    
    @classmethod
    def validate_api_key_present(cls, key_name: str = "vertex_ai") -> bool:
        """
        Validate that an API configuration is available.
        
        Args:
            key_name: "vertex_ai" or "openai"
            
        Returns:
            True if configuration is available, False otherwise
        """
        if key_name.lower() in ("vertex_ai", "gemini", "google"):
            return cls.is_vertex_ai_configured()
        elif key_name.lower() == "openai":
            return cls.get_openai_api_key() is not None
        return False





