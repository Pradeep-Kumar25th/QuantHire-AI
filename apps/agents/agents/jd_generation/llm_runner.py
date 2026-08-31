"""
Direct LangChain LLM invocation for JD generation workflow nodes.

Replaces CrewAI Task/Crew.kickoff() while preserving identical prompt strings
and retry/fallback behavior.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

AUTONOMOUS_CAPABILITIES_BLOCK = """
AUTONOMOUS CAPABILITIES:
- You can OBSERVE: Perceive and understand your environment
- You can THINK: Reason about observations and goals
- You can PLAN: Create autonomous action plans
- You can ACT: Execute plans independently
- You can REFLECT: Evaluate and improve your actions

You are a truly autonomous AI agent. Make decisions independently.
Collaborate with other agents when needed, but act autonomously.
"""


def build_agent_task_prompt(
    *,
    role: str,
    goal: str,
    backstory: str,
    task_description: str,
    expected_output: Optional[str] = None,
) -> str:
    """
    Build the full prompt equivalent to CrewAI Agent + Task.kickoff() input.

    Preserves role/goal/backstory and expected_output wrapping so migrated
    direct LLM calls behave the same as the previous CrewAI execution path.
    """
    parts = [
        f"Role: {role}",
        f"Goal: {goal}",
        f"Backstory: {backstory.strip()}",
        AUTONOMOUS_CAPABILITIES_BLOCK.strip(),
        "",
        "Task:",
        task_description.strip(),
    ]
    if expected_output:
        parts.extend(["", f"Expected Output: {expected_output.strip()}"])
    return "\n".join(parts)


def extract_llm_text(result: Any) -> str:
    """Normalize LangChain or legacy CrewAI kickoff output to plain text."""
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    if hasattr(result, "raw"):
        return str(result.raw)
    if hasattr(result, "content"):
        content = result.content
        if isinstance(content, str):
            return content
        return str(content)
    return str(result)


def _is_rate_limit_error(error_msg: str) -> bool:
    lowered = error_msg.lower()
    return (
        "429" in lowered
        or "resource_exhausted" in lowered
        or "rate limit" in lowered
    )


def invoke_prompt_with_retry(
    llm: Any,
    prompt: str,
    *,
    agent_name: str,
    max_attempts: int = 2,
    switch_fallback_fn: Optional[Callable[[], bool]] = None,
    get_llm_fn: Optional[Callable[[], Any]] = None,
    operation: str = "LLM invocation",
) -> str:
    """Invoke a prompt on a LangChain chat model with rate-limit fallback retry."""
    attempts = 0
    last_error: Optional[Exception] = None
    active_llm = llm

    while attempts < max_attempts:
        attempts += 1
        try:
            logger.info(
                "%s: starting %s (attempt %s/%s)",
                agent_name,
                operation,
                attempts,
                max_attempts,
            )
            response = active_llm.invoke(prompt)
            result_text = extract_llm_text(response)
            logger.info(
                "%s: %s completed. Response length: %s",
                agent_name,
                operation,
                len(result_text),
            )
            return result_text
        except Exception as e:
            last_error = e
            error_msg = str(e)
            if (
                _is_rate_limit_error(error_msg)
                and attempts < max_attempts
                and switch_fallback_fn
            ):
                logger.warning(
                    "%s: rate limit on attempt %s for %s; switching fallback model",
                    agent_name,
                    attempts,
                    operation,
                )
                if switch_fallback_fn():
                    if get_llm_fn is not None:
                        active_llm = get_llm_fn()
                    continue

            logger.error(
                "%s: %s failed on attempt %s: %s",
                agent_name,
                operation,
                attempts,
                e,
                exc_info=True,
            )
            raise

    if last_error is not None:
        raise last_error
    raise RuntimeError(f"{agent_name}: {operation} failed without response")
