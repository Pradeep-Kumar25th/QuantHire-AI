"""Load Azure Non-Prod secrets from AKS into process environment (validation only)."""

from __future__ import annotations

import base64
import json
import os
import subprocess
from typing import Any

DEFAULT_NAMESPACE = "quanthire-nonprod"

SECRET_BINDINGS: dict[str, list[str]] = {
    "quanthire-aoai-secret": ["AZURE_OPENAI_API_KEY"],
    "quanthire-blob-secret": ["AZURE_STORAGE_CONNECTION_STRING"],
    "quanthire-di-secret": [
        "AZURE_DOCUMENT_INTELLIGENCE_KEY",
        "AZURE_DOCUMENT_INTELLIGENCE_API_KEY",
    ],
}


def _run_kubectl(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["kubectl", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def kubectl_available() -> bool:
    proc = _run_kubectl(["version", "--client", "--output=json"])
    return proc.returncode == 0


def load_aks_secrets(
    namespace: str = DEFAULT_NAMESPACE,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Fetch K8s secrets and set env vars. Returns summary (no secret values)."""
    summary: dict[str, Any] = {
        "namespace": namespace,
        "loaded": [],
        "missing_secrets": [],
        "missing_keys": [],
        "errors": [],
    }

    if not kubectl_available():
        summary["errors"].append("kubectl not available or not on PATH")
        return summary

    ctx = _run_kubectl(["config", "current-context"])
    summary["kubectl_context"] = (ctx.stdout or ctx.stderr or "").strip()

    for secret_name, env_keys in SECRET_BINDINGS.items():
        proc = _run_kubectl(
            ["get", "secret", secret_name, "-n", namespace, "-o", "json"]
        )
        if proc.returncode != 0:
            summary["missing_secrets"].append(secret_name)
            err = (proc.stderr or proc.stdout or "").strip()
            if err:
                summary["errors"].append(f"{secret_name}: {err[:200]}")
            continue

        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            summary["errors"].append(f"{secret_name}: invalid JSON ({exc})")
            continue

        data = payload.get("data") or {}
        for env_key in env_keys:
            encoded = data.get(env_key)
            if not encoded:
                continue
            value = base64.b64decode(encoded).decode("utf-8")
            target_key = env_key
            if env_key == "AZURE_DOCUMENT_INTELLIGENCE_KEY":
                target_key = "AZURE_DOCUMENT_INTELLIGENCE_API_KEY"
            if overwrite or not os.getenv(target_key):
                os.environ[target_key] = value
            if target_key not in summary["loaded"]:
                summary["loaded"].append(target_key)

        for env_key in env_keys:
            if env_key not in data:
                summary["missing_keys"].append(f"{secret_name}/{env_key}")

    # Non-secret Azure config for validation runs
    os.environ.setdefault("DEPLOYMENT_TARGET", "azure-nonprod")
    os.environ.setdefault("LLM_PROVIDER", "azure_openai")
    os.environ.setdefault("STORAGE_TYPE", "azure_blob")
    os.environ.setdefault(
        "AZURE_OPENAI_ENDPOINT",
        "https://aif-ail-npd-we-01.openai.azure.com/",
    )
    os.environ.setdefault("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
    os.environ.setdefault("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o")
    os.environ.setdefault("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")
    os.environ.setdefault("AZURE_STORAGE_ACCOUNT_NAME", "dlsailnpdqc01")
    os.environ.setdefault("AZURE_STORAGE_CONTAINER", "quanthire-uploads")
    os.environ.setdefault("AZURE_STORAGE_CONTAINER_PROCESSED", "quanthire-processed")
    os.environ.setdefault(
        "AZURE_STORAGE_BLOB_ENDPOINT",
        "https://dlsailnpdqc01.blob.core.windows.net/",
    )
    os.environ.setdefault(
        "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT",
        "https://di-ail-npd-we-01.cognitiveservices.azure.com/",
    )
    os.environ.setdefault("AZURE_DOCUMENT_INTELLIGENCE_MODEL", "prebuilt-layout")
    os.environ.setdefault("AZURE_DOCUMENT_INTELLIGENCE_ENABLED", "true")

    return summary
