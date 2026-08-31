"""
LLM Client for the Job Matching Swarm
=====================================
Thin wrapper around Vertex AI (ChatVertexAI) with:
* Sync + async invocation helpers.
* Robust JSON extraction (handles markdown fences / leading prose).
* Per-call temperature override.
* Per-tier model override (cheap model for specialists, primary for synthesis).
* Native ``response_schema`` support so the happy path skips text-extraction.

We intentionally bypass CrewAI here — the swarm runs many short, structured
calls and CrewAI's verbose orchestration would add latency and noise.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import warnings
from typing import Any, Optional, Type

warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain_google_vertexai")

from pydantic import BaseModel

from agents.job_matching.config import JobMatchingConfig
from agents.llm.chat_factory import create_chat_llm, llm_provider

logger = logging.getLogger(__name__)

# Fence: ```json / ```JSON / ``` etc. (models vary; avoid missing captures due to case)
_JSON_FENCE_RE = re.compile(r"```[a-zA-Z0-9_-]*\s*\n?(.*?)```", re.DOTALL)

# Process-wide cap on concurrent Vertex calls (job matching fires many LLM requests).
_vertex_llm_semaphore: asyncio.Semaphore | None = None
_vertex_llm_semaphore_limit: int | None = None


def _get_vertex_llm_semaphore(limit: int) -> asyncio.Semaphore:
    global _vertex_llm_semaphore, _vertex_llm_semaphore_limit
    if _vertex_llm_semaphore is None or _vertex_llm_semaphore_limit != limit:
        _vertex_llm_semaphore = asyncio.Semaphore(limit)
        _vertex_llm_semaphore_limit = limit
    return _vertex_llm_semaphore


def _is_rate_limit_error(exc: BaseException) -> bool:
    """True for Vertex/Gemini 429 quota exhaustion (retrying usually makes it worse)."""
    try:
        from google.api_core import exceptions as gexc

        targets = (gexc.ResourceExhausted,)
        chain: list[BaseException] = [exc]
        cur: BaseException | None = exc
        for _ in range(8):
            nxt = getattr(cur, "__cause__", None) or getattr(cur, "__context__", None)
            if nxt is None or nxt is cur:
                break
            chain.append(nxt)
            cur = nxt
        if any(isinstance(e, targets) for e in chain):
            return True
    except ImportError:
        pass
    msg = str(exc).lower()
    return "resource exhausted" in msg or "429" in msg


class JobMatchingLLM:
    """Vertex AI LLM client tuned for the Job Matching swarm."""

    def __init__(
        self,
        config: JobMatchingConfig,
        temperature: float | None = None,
        model_override: Optional[str] = None,
    ) -> None:
        self.config = config
        self._temperature_override = temperature
        self._model_override = (model_override or "").strip() or None
        self._llm = self._build_llm(temperature)

    @property
    def model_name(self) -> str:
        """The currently active primary model. Used for cache-key derivation."""
        return self._model_override or self.config.llm_model

    # ------------------------------------------------------------------ build
    def _effective_temperature(self, temperature: float | None) -> float:
        llm_cfg = self.config.get_llm_config()
        if temperature is not None:
            return temperature
        return float(llm_cfg["temperature"])

    def _create_chat(
        self,
        model_name: str,
        temperature: float,
        *,
        json_mime: bool | None = None,
    ):
        """Build LangChain chat model (OpenAI or Vertex)."""
        llm_cfg = self.config.get_llm_config()
        use_json = (
            self.config.vertex_json_response if json_mime is None else json_mime
        )
        prov = (llm_cfg.get("provider") or llm_provider()).strip().lower()
        if prov == "openai":
            return create_chat_llm(
                model=model_name,
                temperature=temperature,
                max_tokens=llm_cfg["max_tokens"],
                json_mode=bool(use_json),
                provider="openai",
            )
        if prov == "azure_openai":
            return create_chat_llm(
                model=model_name,
                temperature=temperature,
                max_tokens=llm_cfg["max_tokens"],
                json_mode=bool(use_json),
                provider="azure_openai",
            )
        return create_chat_llm(
            model=model_name,
            temperature=temperature,
            max_tokens=llm_cfg["max_tokens"],
            json_mode=bool(use_json),
            provider="vertexai",
            max_retries=self.config.vertex_max_retries,
        )

    def _build_llm(self, temperature: float | None):
        return self._create_chat(
            self.model_name,
            self._effective_temperature(temperature),
        )

    def _should_try_fallback_model(self, exc: BaseException) -> bool:
        if not self.config.enable_error_recovery:
            return False
        if _is_rate_limit_error(exc):
            return False
        primary = (self.model_name or "").strip()
        fallback = (self.config.llm_fallback_model or "").strip()
        if not primary or not fallback or primary == fallback:
            return False
        try:
            from google.api_core import exceptions as gexc

            targets = (
                gexc.NotFound,
                gexc.InvalidArgument,
                gexc.ServiceUnavailable,
                gexc.DeadlineExceeded,
            )
            chain: list[BaseException] = [exc]
            cur: BaseException | None = exc
            for _ in range(8):
                nxt = getattr(cur, "__cause__", None) or getattr(cur, "__context__", None)
                if nxt is None or nxt is cur:
                    break
                chain.append(nxt)
                cur = nxt
            return any(isinstance(e, targets) for e in chain)
        except ImportError:
            return False

    # ------------------------------------------------------------------ invoke
    def invoke(self, prompt: str) -> str:
        """Synchronous invocation — returns raw text."""
        temp = self._effective_temperature(self._temperature_override)
        try:
            response = self._llm.invoke(prompt)
            return response.content if hasattr(response, "content") else str(response)
        except Exception as exc:
            if not self._should_try_fallback_model(exc):
                raise
            fb_name = self.config.llm_fallback_model.strip()
            logger.warning(
                "Vertex primary model failed (%s: %s); sync retry with %s",
                type(exc).__name__,
                exc,
                fb_name,
            )
            fallback_llm = self._create_chat(fb_name, temp)
            response = fallback_llm.invoke(prompt)
            return response.content if hasattr(response, "content") else str(response)

    async def ainvoke(self, prompt: str) -> str:
        """Async invocation — used by the swarm fan-out."""
        temp = self._effective_temperature(self._temperature_override)
        sem = _get_vertex_llm_semaphore(self.config.swarm_llm_max_concurrent)

        async def _call_llm(llm) -> str:
            try:
                response = await llm.ainvoke(prompt)
                return response.content if hasattr(response, "content") else str(response)
            except AttributeError:

                def _sync_invoke() -> str:
                    r = llm.invoke(prompt)
                    return r.content if hasattr(r, "content") else str(r)

                return await asyncio.to_thread(_sync_invoke)

        async with sem:
            try:
                return await _call_llm(self._llm)
            except Exception as exc:
                if not self._should_try_fallback_model(exc):
                    raise
                fb_name = self.config.llm_fallback_model.strip()
                logger.warning(
                    "Vertex primary model failed (%s: %s); retrying once with %s",
                    type(exc).__name__,
                    exc,
                    fb_name,
                )
                fallback_llm = self._create_chat(fb_name, temp)
                return await _call_llm(fallback_llm)

    # ------------------------------------------------------------------ JSON helpers
    def extract_json(self, text: str) -> Optional[dict[str, Any]]:
        """Best-effort JSON extraction from an LLM response."""
        if not text:
            return None
        # Gemini response_mime_type=application/json often returns a bare object
        stripped = text.strip()
        if stripped.startswith("{"):
            direct = self._safe_loads(stripped)
            if direct is not None:
                return direct
            obj = self._first_json_object(stripped)
            if obj is not None:
                return obj
        # 1) Fenced code blocks (possibly multiple)
        for match in _JSON_FENCE_RE.finditer(text):
            payload = match.group(1).strip()
            # Some models repeat the word "json" on its own line inside the fence
            if payload.lower().startswith("json"):
                nl = payload.find("\n")
                if nl != -1:
                    payload = payload[nl + 1 :].strip()
            obj = self._safe_loads(payload)
            if obj is not None:
                return obj
            obj = self._first_json_object(payload)
            if obj is not None:
                return obj

        # 2) First balanced JSON object anywhere in the text
        obj = self._first_json_object(text)
        if obj is not None:
            return obj

        # 3) Legacy: first { to last } (can fail on nested strings; last resort)
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace > first_brace:
            payload = text[first_brace : last_brace + 1]
            obj = self._safe_loads(payload)
            if obj is not None:
                return obj
        return None

    @staticmethod
    def _first_json_object(text: str) -> Optional[dict[str, Any]]:
        """Parse the first top-level JSON object via raw_decode (handles trailing junk)."""
        decoder = json.JSONDecoder()
        i = 0
        while True:
            brace = text.find("{", i)
            if brace == -1:
                return None
            try:
                obj, _end = decoder.raw_decode(text, brace)
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                pass
            i = brace + 1

    @staticmethod
    def _safe_loads(payload: str) -> Optional[dict[str, Any]]:
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            cleaned = re.sub(r",\s*([}\]])", r"\1", payload)
            cleaned = cleaned.replace("\n", " ")
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                return None

    # ------------------------------------------------------------------ structured call
    async def acall_json(
        self,
        prompt: str,
        retry_on_parse_error: int = 3,
    ) -> dict[str, Any]:
        """Async LLM call that guarantees a dict (raises ValueError on hard failure)."""
        last_error: str | None = None
        attempts = retry_on_parse_error + 1
        for attempt in range(attempts):
            text = await self.ainvoke(prompt)
            obj = self.extract_json(text)
            if obj is not None:
                return obj
            last_error = (text or "")[:800]
            logger.warning(
                "LLM did not return parseable JSON (attempt %d/%d). Snippet=%r",
                attempt + 1,
                attempts,
                last_error,
            )
        raise ValueError(
            f"LLM failed to return valid JSON after {attempts} attempts. "
            f"Last response snippet: {last_error}"
        )

    def call_json(self, prompt: str, retry_on_parse_error: int = 3) -> dict[str, Any]:
        """Synchronous variant of :meth:`acall_json`."""
        return asyncio.run(self.acall_json(prompt, retry_on_parse_error=retry_on_parse_error))

    # ------------------------------------------------------------------ structured output
    async def acall_structured(
        self,
        prompt: str,
        schema_model: Type[BaseModel],
        retry_on_parse_error: int = 2,
    ) -> dict[str, Any]:
        """Call Vertex with native schema-enforced JSON output.

        On the happy path this delegates to LangChain's
        ``with_structured_output`` which knows how to flatten nested Pydantic
        ``$ref``/``$defs`` graphs into a Vertex-compatible function-calling
        schema. The result already comes back as a Pydantic instance that we
        immediately ``.model_dump()`` so callers can keep treating it as a
        dict — same shape as ``acall_json``.

        Falls back to ``acall_json`` automatically when:
        * ``config.enable_structured_output`` is ``False``,
        * the bound LangChain version doesn't expose
          ``with_structured_output`` (very old installs), or
        * the structured call raises (region/preview/quota issues).

        This makes the method always safe to call from any agent.
        """
        if not self.config.enable_structured_output:
            return await self.acall_json(prompt, retry_on_parse_error=retry_on_parse_error + 1)

        # Structured output uses Vertex function-calling; cannot combine with
        # response_mime_type=application/json on gemini-2.5-pro.
        structured_llm = self._create_chat(
            self.model_name,
            self._effective_temperature(self._temperature_override),
            json_mime=False,
        )
        wso = getattr(structured_llm, "with_structured_output", None)
        if wso is None:
            return await self.acall_json(prompt, retry_on_parse_error=retry_on_parse_error + 1)

        try:
            structured_runnable = wso(schema_model)
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "with_structured_output construction failed (%s); using JSON mode.", exc
            )
            return await self.acall_json(prompt, retry_on_parse_error=retry_on_parse_error + 1)

        sem = _get_vertex_llm_semaphore(self.config.swarm_llm_max_concurrent)
        last_exc: BaseException | None = None
        for attempt in range(retry_on_parse_error + 1):
            # Reset per-iteration so a previous failure doesn't poison this attempt's
            # success branch.
            iter_exc: BaseException | None = None
            parsed: Any = None

            try:
                async with sem:
                    if hasattr(structured_runnable, "ainvoke"):
                        parsed = await structured_runnable.ainvoke(prompt)
                    else:  # pragma: no cover - very old runnables
                        parsed = await asyncio.to_thread(
                            structured_runnable.invoke, prompt
                        )
            except Exception as exc:
                iter_exc = exc
                # Try the fallback model on the first attempt only (cheap retry).
                if attempt == 0 and self._should_try_fallback_model(exc):
                    fb_name = self.config.llm_fallback_model.strip()
                    logger.warning(
                        "Structured primary failed (%s); retrying with %s",
                        type(exc).__name__,
                        fb_name,
                    )
                    try:
                        fb_llm = self._create_vertex_chat(
                            fb_name,
                            self._effective_temperature(self._temperature_override),
                            json_mime=False,
                        )
                        fb_runnable = fb_llm.with_structured_output(schema_model)
                        parsed = await fb_runnable.ainvoke(prompt)
                        iter_exc = None  # fallback succeeded
                    except Exception as fb_exc:  # noqa: BLE001
                        iter_exc = fb_exc

            if iter_exc is not None:
                last_exc = iter_exc
                continue

            if parsed is None:
                # Structured runnable returned nothing — treat as parse failure.
                last_exc = ValueError("Structured output returned None")
                continue

            if isinstance(parsed, BaseModel):
                return parsed.model_dump(mode="json")
            if isinstance(parsed, dict):
                return parsed
            # Unexpected return shape — treat as parse failure for the next iter.
            last_exc = TypeError(
                f"Structured output returned {type(parsed).__name__}; expected dict/BaseModel"
            )

        if last_exc is not None and _is_rate_limit_error(last_exc):
            logger.warning(
                "Structured output hit Vertex rate limit (429); not falling back to "
                "JSON-mode (would add more quota pressure). Specialist will use placeholder."
            )
            raise last_exc

        logger.warning(
            "Structured output exhausted retries (last_exc=%s); falling back to JSON-mode.",
            last_exc,
        )
        return await self.acall_json(prompt, retry_on_parse_error=2)


def ensure_vertex_credentials(config: JobMatchingConfig) -> None:
    """Raise if the configured LLM provider is not ready."""
    provider = (config.llm_provider or "vertexai").strip().lower()
    if provider == "azure_openai":
        from agents.llm.chat_factory import is_azure_openai_configured

        if not is_azure_openai_configured():
            raise RuntimeError(
                "Azure OpenAI is not configured. Set AZURE_OPENAI_ENDPOINT and "
                "AZURE_OPENAI_API_KEY when LLM_PROVIDER=azure_openai."
            )
        return
    if provider == "openai":
        from agents.llm.chat_factory import is_openai_configured

        if not is_openai_configured():
            raise RuntimeError(
                "OpenAI is not configured. Set OPENAI_API_KEY when LLM_PROVIDER=openai."
            )
        return

    from agents.gcp_vertex_credentials import vertex_credential_source_available

    project = config.gcp_project or os.getenv("GCP_PROJECT_ID")
    if not project:
        raise RuntimeError(
            "Vertex AI is not configured. Set GCP_PROJECT_ID (or GOOGLE_CLOUD_PROJECT)."
        )
    if not vertex_credential_source_available():
        raise RuntimeError(
            "Vertex AI credentials not found. Run `gcloud auth application-default login` "
            "or set LLM_PROVIDER=openai with OPENAI_API_KEY."
        )
