"""
QuantChat AI Chatbot API Endpoints
===================================
Enterprise-grade QuantChat chatbot using hybrid architecture.
"""

import asyncio
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.config import settings
from app.core.auth_policy import auth_enforced, require_user_when_basic_auth
from app.database import get_session
from app.core.query_router_lifecycle import (
    QUERY_ROUTER_AVAILABLE,
    QUERY_ROUTER_INIT_ERROR,
    ensure_query_router,
)

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter(tags=["QuantChat AI"])

# Warm QueryRouter at import; request handlers call ensure_query_router() again.
ensure_query_router()

# Configuration constants
MAX_CONVERSATION_HISTORY = int(os.getenv("MAX_CONVERSATION_HISTORY", "200"))
MAX_MESSAGE_LENGTH = int(os.getenv("MAX_MESSAGE_LENGTH", "5000"))

# Store conversation history (in production, use Redis or database)
# TODO: Replace with Redis/database for production
conversation_histories: Dict[str, List[Dict[str, Any]]] = {}


def _sync_router_memory_from_api_history(router: Any, user_id: str) -> None:
    """Hydrate QueryRouter in-process memory from API history after worker restarts."""
    history = conversation_histories.get(user_id) or []
    if not history or not getattr(router, "memory", None):
        return

    existing = router.memory.sessions.get(user_id)
    if existing and existing.messages:
        return

    from quantchat.memory.conversation_memory import Message, Session

    session = Session(session_id=user_id)
    for entry in history[-MAX_CONVERSATION_HISTORY:]:
        role = str(entry.get("role") or "user")
        content = str(entry.get("content") or "").strip()
        if not content:
            continue
        session.messages.append(
            Message(role, content, str(entry.get("timestamp") or datetime.now().isoformat()))
        )
    router.memory.sessions[user_id] = session


class ChatMessage(BaseModel):
    """Chat message model with validation."""
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_LENGTH, description="User message")
    user_id: Optional[str] = Field(None, max_length=100, description="Optional user identifier")
    
    @field_validator('message')
    @classmethod
    def validate_message(cls, v: str) -> str:
        """Validate message is not empty after stripping."""
        if not v.strip():
            raise ValueError("Message cannot be empty")
        return v.strip()


class ChatResponse(BaseModel):
    """Chat response model."""
    response: str
    processing_method: str
    security_status: str
    timestamp: str


@router.post("/chat", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def ai_chat(
    message: ChatMessage,
    current_user: Optional[dict] = Depends(require_user_when_basic_auth),
) -> ChatResponse:
    """
    AI Chat endpoint - Main chatbot/assistant functionality (QuantChat)
    
    Routes DIRECTLY to QueryRouter (No intermediate orchestrators).
    """
    try:
        router = ensure_query_router()
        # Runtime Invariant Check
        if not router:
            logger.critical("QueryRouter Not Initialized")
            detail = "RAG Pipeline Service Unavailable"
            if QUERY_ROUTER_INIT_ERROR:
                detail = f"{detail}: {QUERY_ROUTER_INIT_ERROR}"
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=detail,
            )
        
        logger.info(
            f"QuantChat v1: Processing query from user "
            f"{(current_user or {}).get('id') or message.user_id or 'anonymous'}: "
            f"{message.message[:100]}"
        )
        request_id = str(uuid.uuid4())

        # Bind conversation history to authenticated user (never trust client user_id).
        if current_user and current_user.get("id"):
            user_id = str(current_user["id"])
        elif auth_enforced():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        elif message.user_id:
            user_id = message.user_id
        else:
            user_id = "anonymous"
        if user_id not in conversation_histories:
            conversation_histories[user_id] = []
        
        # Add user message to history
        conversation_histories[user_id].append({
            "role": "user",
            "content": message.message,
            "timestamp": datetime.now().isoformat()
        })
        
        # EXECUTE QUERY ROUTER (The ONE Pipeline)
        # ----------------------------------------
        logger.info(f"[{request_id}] Routing to QueryRouter...")
        _sync_router_memory_from_api_history(router, user_id)
        
        # Use user_id as session_id for conversation tracking.
        # The pipeline is synchronous (embedding + retrieval + LLM call, can
        # take seconds) — run it on a worker thread so the event loop stays
        # responsive for health probes and other requests.
        result = await asyncio.to_thread(
            router.route_query, message.message, session_id=user_id
        )
        
        logger.info(f"[{request_id}] QueryRouter returned source: {result.get('source', 'unknown')}")
        # ----------------------------------------
        
        # Map to ChatResponse
        response_text = result.get("response", "")
        if not response_text:
            response_text = "I apologize, but I could not generate a response."
            
        # Add assistant response to history
        conversation_histories[user_id].append({
            "role": "assistant",
            "content": response_text,
            "timestamp": datetime.now().isoformat()
        })
        
        # Keep only last N messages
        if len(conversation_histories[user_id]) > MAX_CONVERSATION_HISTORY:
            conversation_histories[user_id] = conversation_histories[user_id][-MAX_CONVERSATION_HISTORY:]
            
        return ChatResponse(
            response=response_text,
            processing_method=f"VERIFIED_RAG::{result.get('source', 'unknown').upper()}",
            security_status="SECURE",
            timestamp=datetime.now().isoformat()
        )
            
    except ValidationError as e:
        logger.warning(f"Validation error in chat endpoint: {e}")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid request: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {e}", exc_info=True)
        detail = (
            f"QuantChat error: {e}"
            if settings.app_env in ("nonprod", "development", "dev")
            else "An internal error occurred. Please try again later."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
        )


@router.get("/status")
async def get_quantchat_status(
    session: AsyncSession = Depends(get_session),
):
    """Get QuantChat QueryRouter status"""
    router = ensure_query_router()
    if not QUERY_ROUTER_AVAILABLE or not router:
        return {
            "status": "UNAVAILABLE",
            "architecture": "quantchat_queryrouter",
            "available": False,
            "message": "QueryRouter not initialized",
            "error": QUERY_ROUTER_INIT_ERROR,
        }

    # Get QueryRouter component status (check actual components)
    components_status = {
        "normalizer": hasattr(router, 'normalizer') and router.normalizer is not None,
        "classifier": hasattr(router, 'classifier') and router.classifier is not None,
        "query_expander": hasattr(router, 'query_expander') and router.query_expander is not None,
        "metadata_filter": hasattr(router, 'metadata_filter') and router.metadata_filter is not None,
        "vector_retriever": hasattr(router, 'vector_retriever') and router.vector_retriever is not None,
        "keyword_retriever": hasattr(router, 'keyword_retriever') and router.keyword_retriever is not None,
        "full_doc_retriever": hasattr(router, 'full_doc_retriever') and router.full_doc_retriever is not None,
        "rrf": hasattr(router, 'rrf') and router.rrf is not None,
        "reranker": hasattr(router, 'reranker') and router.reranker is not None,
        "context_builder": hasattr(router, 'context_builder') and router.context_builder is not None,
        "rag_generator": hasattr(router, 'rag_generator') and router.rag_generator is not None,
        "general_generator": hasattr(router, 'general_generator') and router.general_generator is not None,
        "formatter": hasattr(router, 'formatter') and router.formatter is not None,
        "memory": hasattr(router, 'memory') and router.memory is not None,
        "monitor": hasattr(router, 'monitor') and router.monitor is not None
    }
    
    # Vector store connection (pgvector on Azure Non-Prod, Milvus locally)
    from app.services.storage_diagnostics import get_vector_store_stats

    vector_stats = await get_vector_store_stats(session)
    vector_connected = bool(vector_stats.get("connected"))
    
    return {
        "status": "AVAILABLE",
        "architecture": "quantchat_queryrouter",
        "available": True,
        "message": "✅ QueryRouter is the SINGLE canonical RAG pipeline",
        "components": components_status,
        "storage_backend": vector_stats.get("storage_backend"),
        "vector_store_connected": vector_connected,
        "num_jds": vector_stats.get("num_jds", 0),
        "num_resumes": vector_stats.get("num_resumes", 0),
        "milvus_connected": vector_connected if not settings.use_pgvector_pipeline else False,
        "vector_store_status": vector_stats,
        "all_components_ready": all(components_status.values())
    }

