"""
LLM Generator
=============

Generates responses using the configured LLM provider (OpenAI or Vertex AI).
"""

import os
import json
from typing import Optional
from ..config.logging_config import setup_logger
from ..config.settings import (
    LLM_PROVIDER, LLM_MODEL, LLM_FALLBACK_MODEL,
    GCP_PROJECT_ID, GCP_LOCATION
)

logger = setup_logger("llm_generator")

LLM_GENERATOR_AVAILABLE = True

class LLMGenerator:
    """
    LLM generator for QuantChat RAG (OpenAI or Vertex AI).
    """
    
    def __init__(self):
        from agents.llm.chat_factory import ensure_llm_env, llm_provider, primary_llm_model

        ensure_llm_env()
        self.provider = llm_provider()
        self.model = primary_llm_model()
        self.fallback_model = os.getenv("LLM_FALLBACK_MODEL") or self.model
        self.last_model_used = LLM_MODEL

        if self.provider == "openai":
            from agents.llm.chat_factory import is_openai_configured
            if not is_openai_configured():
                raise ValueError("OPENAI_API_KEY not configured. Required when LLM_PROVIDER=openai.")
        elif self.provider == "azure_openai":
            from agents.llm.chat_factory import is_azure_openai_configured
            if not is_azure_openai_configured():
                raise ValueError(
                    "Azure OpenAI not configured. Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY."
                )
        else:
            if not GCP_PROJECT_ID:
                raise ValueError("GCP_PROJECT_ID not configured. Required when LLM_PROVIDER=vertexai.")
            try:
                from langchain_google_vertexai import ChatVertexAI  # noqa: F401
            except ImportError:
                raise ImportError(
                    "langchain-google-vertexai not installed. Run: pip install langchain-google-vertexai"
                )
    
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        full_document_mode: bool = False
    ) -> str:
        """
        Generate response using the configured LLM provider.
        """
        if full_document_mode:
            effective_max_tokens = max_tokens or 16384
        else:
            effective_max_tokens = max_tokens or 8192
        
        try:
            self.last_model_used = self.model
            return self._call_llm(system_prompt, user_prompt, temperature, effective_max_tokens)
        except Exception as e:
            logger.error(f"LLM generation failed ({self.model}): {e}")
            try:
                logger.info(f"Trying fallback model: {self.fallback_model}")
                self.last_model_used = self.fallback_model
                return self._call_llm(
                    system_prompt, user_prompt, temperature, effective_max_tokens, use_fallback=True
                )
            except Exception as fallback_error:
                logger.error(f"Fallback model also failed: {fallback_error}")
                raise
    
    def _call_llm(
        self,
        system: str,
        user: str,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        use_fallback: bool = False
    ) -> str:
        """Call OpenAI or Vertex AI."""
        from langchain_core.messages import HumanMessage, SystemMessage
        from ..utils.tracing import traceable as ls_traceable
        from agents.llm.chat_factory import create_chat_llm
                
        @ls_traceable(run_type="llm", name="QuantChat_LLM_Call")
        def _execute_llm(sys_msg, usr_msg, temp, tokens):
            model = self.fallback_model if use_fallback else self.model
            
            llm = create_chat_llm(
                model=model,
                temperature=temp,
                max_tokens=tokens,
                provider=self.provider,
            )
            
            messages = [
                SystemMessage(content=sys_msg),
                HumanMessage(content=usr_msg)
            ]
            
            response = llm.invoke(messages)
            return response.content
            
        return _execute_llm(system, user, temperature, max_tokens or 8192)
