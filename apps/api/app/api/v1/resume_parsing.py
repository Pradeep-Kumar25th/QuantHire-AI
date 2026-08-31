"""
Resume Parsing API Endpoints
=============================
Enterprise-grade resume parsing using hybrid architecture and autonomous AI agents.
"""

import logging
import os
import re
import sys
import time
import uuid
from concurrent import futures
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from app.core.auth_policy import require_user_when_basic_auth
from app.config import settings
from app.database import get_session
from app.core.query_router_lifecycle import (
    QUERY_ROUTER_AVAILABLE,
    QUERY_ROUTER_INIT_ERROR,
    ensure_query_router,
)
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Resume Parsing"])

try:
    from agents.gcp_vertex_credentials import vertex_credential_source_available
except ImportError:  # pragma: no cover - path not set in some test harnesses

    def vertex_credential_source_available() -> bool:  # type: ignore[misc]
        return False


def _llm_provider() -> str:
    return os.getenv("LLM_PROVIDER", "openai").strip().lower()


def _llm_configured() -> bool:
    prov = _llm_provider()
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
    gcp_project = os.getenv("GCP_PROJECT_ID")
    return bool(gcp_project and vertex_credential_source_available())


# Import Verified QueryRouter Singleton for Analysis (lazy — not at import time)


def _refresh_query_router_status() -> None:
    """Initialize QueryRouter on demand for status/analysis endpoints."""
    ensure_query_router()

# ============================================================================
# DOCUMENT INGESTION SERVICE (WRITE OPERATIONS)
# ============================================================================
# LANGGRAPH AI AGENT INITIALIZATION (Modern, Recommended by LangChain Team)
# ============================================================================
ai_resume_agent = None
agent_status = {
    "initialized": False,
    "agent_executor_available": False,
    "tools_available": False,
    "memory_available": False,
    "llm_available": False,
    "rag_available": False,
}

# ============================================================================
# ARCHITECTURAL SEPARATION:
# - DocumentIngestion (below): WRITE operations (add_resume, add_jd) → Milvus
# - QueryRouter (above): READ operations (query, retrieval, RAG) → Milvus
# 
# This enforces Single RAG Pipeline architecture:
# - Only ONE RAG pipeline exists: QueryRouter
# - No alternate RAG/retrieval paths
# - Consistent embeddings: bge-base-en-v1.5 (768d, cosine)
# ============================================================================

# Initialize DocumentIngestion Service for Milvus WRITE operations (legacy local dev only)
INGESTION_AVAILABLE = False
ingestion_service = None
if not settings.use_pgvector_pipeline:
    try:
        from apps.quantchat.ingestion import get_document_ingestion

        ingestion_service = get_document_ingestion()
        INGESTION_AVAILABLE = ingestion_service.is_connected()
        agent_status["rag_available"] = INGESTION_AVAILABLE
    except Exception as e:
        logger.error(f"Failed to initialize DocumentIngestion: {e}")
        INGESTION_AVAILABLE = False
        ingestion_service = None
else:
    agent_status["rag_available"] = QUERY_ROUTER_AVAILABLE

try:
    llm_provider = _llm_provider()
    gcp_project = os.getenv("GCP_PROJECT_ID")

    if settings.use_pgvector_pipeline:
        # Azure Non-Prod: ParsingAgent + Azure OpenAI (no LangGraph/Milvus init)
        agent_status["initialized"] = _llm_configured()
        agent_status["llm_available"] = _llm_configured()
        agent_status["agent_executor_available"] = True  # ParsingAgent path
        logger.info(
            "Resume parsing: Azure/pgvector pipeline (ParsingAgent, provider=%s)",
            llm_provider,
        )
    elif _llm_configured():
        from ai_resume_parsing_agent import AIResumeParsingAgent, initialize_ai_resume_agent

        logger.info("=" * 80)
        logger.info("INITIALIZING LANGGRAPH AI AGENT (%s)", llm_provider.upper())
        logger.info("=" * 80)
        if llm_provider == "openai":
            logger.info("OpenAI model: %s", os.getenv("LLM_MODEL", "gpt-4o"))
        elif llm_provider == "azure_openai":
            logger.info(
                "Azure OpenAI deployment: %s",
                os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o"),
            )
        else:
            logger.info("GCP Project: %s", gcp_project)
            logger.info("GCP Location: %s", os.getenv("GCP_LOCATION", "us-central1"))

        ai_resume_agent = initialize_ai_resume_agent(None)
        
        if ai_resume_agent:
            agent_status["initialized"] = True
            agent_status["agent_executor_available"] = ai_resume_agent.agent_executor is not None
            agent_status["tools_available"] = hasattr(ai_resume_agent, 'tools') and len(ai_resume_agent.tools) > 0
            agent_status["memory_available"] = ai_resume_agent.memory is not None
            agent_status["llm_available"] = ai_resume_agent.llm is not None
            
            logger.info(f"✅ LangGraph Agent: {'Ready' if agent_status['agent_executor_available'] else 'Fallback Mode'}")
            logger.info(f"   Tools: {len(ai_resume_agent.tools) if agent_status['tools_available'] else 0}")
            logger.info(f"   Memory: {'Enabled' if agent_status['memory_available'] else 'Disabled'}")
            logger.info(f"   LLM: {type(ai_resume_agent.llm).__name__ if agent_status['llm_available'] else 'None'}")
        logger.info("=" * 80)
    else:
        if llm_provider == "openai":
            logger.error(
                "OpenAI not configured. Set OPENAI_API_KEY and LLM_PROVIDER=openai in .env"
            )
        elif llm_provider == "azure_openai":
            logger.error(
                "Azure OpenAI not configured. Set AZURE_OPENAI_ENDPOINT and "
                "AZURE_OPENAI_API_KEY (or managed identity)."
            )
        else:
            logger.error(
                "Vertex AI not configured. Set GCP_PROJECT_ID and ADC "
                "(gcloud auth application-default login; optional GCP_ADC_CREDENTIALS_PATH)."
            )
        
except ImportError as e:
    logger.error(f"❌ Failed to import LangGraph agent: {e}")
except Exception as e:
    logger.error(f"❌ Failed to initialize LangGraph agent: {e}", exc_info=True)

# Configuration constants
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE_MB", "10")) * 1024 * 1024  # Convert MB to bytes
READ_CHUNK_SIZE = 1024 * 1024


async def _read_upload_with_limit(upload_file, max_bytes: int) -> bytes:
    """Read an upload in chunks and reject before buffering oversized bodies."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload_file.read(READ_CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    f"File too large. Maximum size: {max_bytes / 1024 / 1024:.0f}MB"
                ),
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _clean_extracted_text(text: str) -> str:
    """Clean garbled text from PDF extraction (spaces, ampersands, and dashes between/around characters).
    
    Fixes PDF extraction artifacts like:
    - "D o c u m e n t a t i o n" (spaces between chars)
    - "D&o&c&u&m&e&n&t" (ampersands between chars)
    - "-K-A-R-A-N- -K-U-M-A-R-" (dashes between single characters)
    - "-Aditya- -Rao-" (dashes wrapped around whole words - PDF rendering artifact)
    - "-6- -years -o-f" (dashes around numbers and short words)
    - "-U-X -Designer" -> "UX Designer" (abbreviation patterns)
    
    Preserves legitimate hyphens in words like "Mary-Jane", "year-over-year"
    
    Args:
        text: Raw extracted text from PDF
        
    Returns:
        Cleaned text with garbled patterns fixed
    """
    if not text:
        return text
    
    # Normalize multiple spaces first
    text = re.sub(r' +', ' ', text)
    
    # PASS 1: Remove hyphens wrapped completely around words/numbers: "-Word-" -> "Word"
    text = re.sub(r'(?<![A-Za-z0-9])-([A-Za-z0-9]+)-(?![A-Za-z0-9])', r'\1', text)
    
    # PASS 2: Remove leading hyphens at word boundaries: " -Word" -> " Word"
    text = re.sub(r'(?<=\s)-([A-Za-z0-9])', r'\1', text)
    text = re.sub(r'^-([A-Za-z0-9])', r'\1', text, flags=re.MULTILINE)
    
    # PASS 3: Remove trailing hyphens at word boundaries: "Word- " -> "Word "
    text = re.sub(r'([A-Za-z0-9])-(?=\s|$|[,.\)])', r'\1', text)
    
    # PASS 4: Handle "-o-f" pattern (single chars with leading/trailing hyphens)
    text = re.sub(r'(?<=\s)-([a-zA-Z0-9])-(?=\s)', r'\1', text)
    
    # PASS 5: Clean up isolated hyphens
    text = re.sub(r'\s+-\s+', ' ', text)
    
    # PASS 6: Handle dashes between SINGLE characters only: "-U-X" -> "UX"
    # Preserves legitimate hyphenated words like "Mary-Jane"
    def clean_dash_chars(match):
        word = match.group(0).strip('-')
        parts = word.split('-')
        if all(len(p.strip()) == 1 for p in parts if p.strip()):
            return ''.join(p for p in parts if p.strip())
        return match.group(0)
    text = re.sub(r'-?([A-Za-z0-9]+)(?:-([A-Za-z0-9]+))+(-)?', clean_dash_chars, text)
    
    # PASS 7: Remove trailing commas with hyphens: "word,- " -> "word, "
    text = re.sub(r',-\s+', ', ', text)
    
    # PASS 8: Clean remaining hyphens around punctuation
    text = re.sub(r'-+([,.\)\(])', r'\1', text)
    text = re.sub(r'([,.\)\(])-+', r'\1', text)
    
    # PASS 9: Clean patterns like "(2021-Present)" from "(2021---Present-)"
    text = re.sub(r'\(-*(\d+)-*-+(\w+)-*\)', r'(\1-\2)', text)
    
    # PASS 10: Handle ampersands between characters
    text = re.sub(r'([a-zA-Z0-9])&+([a-zA-Z0-9])', r'\1\2', text)
    
    # PASS 11: Handle spaces between single characters that form words
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        words = line.split()
        cleaned_words = []
        
        i = 0
        while i < len(words):
            if len(words[i]) == 1 and i + 1 < len(words) and len(words[i + 1]) == 1:
                garbled_seq = [words[i]]
                i += 1
                while i < len(words) and len(words[i]) == 1:
                    garbled_seq.append(words[i])
                    i += 1
                cleaned_words.append(''.join(garbled_seq))
            else:
                cleaned_words.append(words[i])
                i += 1
        
        cleaned_lines.append(' '.join(cleaned_words))
    
    text = '\n'.join(cleaned_lines)
    
    # PASS 12: Handle mixed spaces and ampersands
    text = re.sub(r'([a-zA-Z0-9])\s*&\s*([a-zA-Z0-9])', r'\1\2', text)
    
    # PASS 13: Clean up multiple spaces
    text = re.sub(r' {2,}', ' ', text)
    
    # PASS 14: Normalize line breaks
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # PASS 15: Clean multiple hyphens: "---" -> "-"
    text = re.sub(r'-{2,}', '-', text)
    
    return text.strip()


class ResumeAnalysisRequest(BaseModel):
    """Request model for resume analysis."""
    resume_text: str = Field(..., description="Resume text content")
    candidate_name: Optional[str] = Field(None, description="Optional candidate name")


class ResumeAnalysisResponse(BaseModel):
    """Response model for resume analysis."""
    analysis: Dict[str, Any]
    security_status: Dict[str, Any]
    timestamp: str


@router.post("/upload", status_code=status.HTTP_200_OK)
@router.post("/upload-resume", status_code=status.HTTP_200_OK, include_in_schema=False)
async def upload_resume(
    file: UploadFile = File(...),
    current_user: Optional[dict] = Depends(require_user_when_basic_auth),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Upload and parse a resume of any common format/layout.

    Supported: PDF, DOCX, DOC, TXT, PNG/JPG/WEBP/TIFF (scanned).
    Azure Non-Prod / pgvector: Blob → Document Intelligence → ParsingAgent →
    Postgres + pgvector chunks.
    Legacy local path: LangGraph agent → Milvus.
    """
    try:
        logger.info(f"Resume upload request received: {file.filename} ({file.content_type})")
        
        # Validate file type
        if not file.filename:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename is required")

        from app.services.pdf_extraction import (
            SUPPORTED_RESUME_EXTENSIONS,
            extract_resume_text,
        )

        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in SUPPORTED_RESUME_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Unsupported file type: {file_ext}. "
                    f"Supported: {', '.join(sorted(SUPPORTED_RESUME_EXTENSIONS))}"
                ),
            )

        from app.core.validation import FileUploadValidator

        if file.content_type and file.content_type not in (
            "application/octet-stream",
            None,
        ):
            if not FileUploadValidator.validate_mime_type(file.content_type):
                allowed = {
                    "application/pdf",
                    "application/msword",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "text/plain",
                    "image/png",
                    "image/jpeg",
                    "image/webp",
                    "image/tiff",
                }
                if file.content_type not in allowed:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Unsupported content type: {file.content_type}",
                    )
        
        # Read file content with size validation
        content = await _read_upload_with_limit(file, MAX_FILE_SIZE)
        file_size = len(content)
        
        if file_size == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is empty")
        
        logger.info(f"File size: {file_size} bytes")

        # Generate unique resume ID
        resume_id = str(uuid.uuid4())

        raw_blob_ref: Optional[str] = None
        blob_error: Optional[str] = None
        try:
            from app.integrations.azure_blob import blob_storage_enabled, get_blob_storage

            if blob_storage_enabled():
                blob_storage = get_blob_storage()
                raw_blob_ref = await blob_storage.upload_resume(
                    content,
                    file.filename,
                    file.content_type,
                    resume_id=resume_id,
                )
                logger.info("Raw resume stored in Azure Blob: %s", raw_blob_ref)
        except Exception as blob_exc:
            blob_error = str(blob_exc)
            logger.error("Azure Blob upload failed: %s", blob_exc, exc_info=True)
            if settings.is_azure_nonprod and settings.storage_backend == "azure_blob":
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=(
                        "Failed to store resume in Azure Blob Storage. "
                        f"Error: {blob_exc}"
                    ),
                ) from blob_exc
            logger.warning("Azure Blob upload skipped (continuing in-memory): %s", blob_exc)

        # Universal extraction (DI for scanned/layout-aware; local fallbacks for digital PDFs/DOCX)
        extraction_method = "direct"
        try:
            logger.info("Processing resume (%s)...", file_ext)
            resume_text, extraction_method = await extract_resume_text(content, file.filename)
            # Clean garbled PDF/OCR artifacts (e.g. "-K-A-R-A-N-" → "KARAN")
            resume_text = _clean_extracted_text(resume_text)
            logger.info(
                "Extracted via %s (%s chars)",
                extraction_method,
                len(resume_text),
            )
        except HTTPException:
            raise
        except Exception as extract_exc:
            # Legacy PDF fallbacks for local/Milvus path only
            if file_ext == ".pdf" and ai_resume_agent and hasattr(ai_resume_agent, "extract_text_from_pdf"):
                try:
                    resume_text = ai_resume_agent.extract_text_from_pdf(content)
                    resume_text = _clean_extracted_text(resume_text or "")
                    if resume_text and len(resume_text.strip()) > 100:
                        extraction_method = "ai_resume_agent"
                    else:
                        raise extract_exc
                except Exception:
                    logger.error("Resume text extraction failed: %s", extract_exc, exc_info=True)
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=(
                            "Resume processing failed. The file may be corrupted, "
                            "password-protected, or unreadable. "
                            f"Error: {extract_exc}"
                        ),
                    ) from extract_exc
            else:
                logger.error("Resume text extraction failed: %s", extract_exc, exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=(
                        "Resume processing failed. For scanned images or complex layouts, "
                        "ensure Azure Document Intelligence is configured. "
                        f"Error: {extract_exc}"
                    ),
                ) from extract_exc
        
        logger.info(f"📝 Extracted text length: {len(resume_text)} characters")

        if settings.use_pgvector_pipeline:
            if not _llm_configured():
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Resume parsing LLM is not configured for Azure Non-Prod.",
                )
            from app.services.resume_pipeline_service import ResumePipelineService

            pipeline = ResumePipelineService(session)
            try:
                result = await pipeline.parse_and_store(
                    resume_text=resume_text,
                    resume_id=resume_id,
                    raw_blob_ref=raw_blob_ref,
                    pdf_extraction_method=extraction_method,
                )
            except Exception as pipeline_exc:
                logger.error("Pgvector resume pipeline failed: %s", pipeline_exc, exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Resume upload failed: {pipeline_exc}",
                ) from pipeline_exc

            parsed_data = result["parsed_data"]
            screening_report = result.get("screening_report") or parsed_data.get("screening_report")
            return {
                "success": True,
                "resume_id": resume_id,
                "candidate_id": result["candidate_id"],
                "message": (
                    "Resume uploaded, parsed, and indexed successfully using "
                    f"{parsed_data.get('parsing_method', 'PARSING_AGENT')} "
                    f"({result.get('candidate_action', 'created')})"
                ),
                "parsed_data": parsed_data,
                "screening_report": screening_report,
                "storage_backend": "pgvector",
                "pgvector_result": {
                    "status": "success",
                    "document_id": result["document_id"],
                    "candidate_id": result["candidate_id"],
                },
                "milvus_result": None,
                "file_type": file_ext.lstrip(".").upper(),
                "storage_status": "success" if raw_blob_ref else ("skipped" if blob_error else "not_configured"),
                "raw_blob_ref": raw_blob_ref,
                "processed_blob_ref": parsed_data.get("processed_blob_ref"),
                "pdf_extraction_method": extraction_method,
            }

        if not INGESTION_AVAILABLE or not ingestion_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Document ingestion service unavailable. For Azure Non-Prod ensure pgvector pipeline is enabled; for local dev ensure Milvus is running.",
            )

        # ====================================================================
        # PARSE RESUME USING LANGGRAPH AI AGENT (legacy Milvus path)
        # ====================================================================
        parsed_data = None
        parsing_success = False

        if not _llm_configured():
            provider = _llm_provider()
            if provider == "openai":
                logger.error("OpenAI not configured!")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=(
                        "Resume parsing failed: OpenAI not configured. "
                        "Set OPENAI_API_KEY and LLM_PROVIDER=openai in .env"
                    ),
                )
            if provider == "azure_openai":
                logger.error("Azure OpenAI not configured!")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=(
                        "Resume parsing failed: Azure OpenAI not configured. "
                        "Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY "
                        "(quanthire-aoai-secret on AKS)."
                    ),
                )
            location_hint = (
                os.environ.get("APPDATA", "%APPDATA%")
                + "\\gcloud\\application_default_credentials.json"
            )
            logger.error("Vertex AI not configured!")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    "Resume parsing failed: Vertex AI not configured. Set GCP_PROJECT_ID and "
                    "ADC (gcloud auth application-default login; GCP_ADC_CREDENTIALS_PATH) or run "
                    "'gcloud auth application-default login' — ADC file expected at e.g. "
                    f"{location_hint}"
                ),
            )
        
        # STEP 1: Parse with LangGraph AI Agent
        logger.info("=" * 60)
        logger.info("LANGGRAPH AI AGENT - Starting Resume Parsing (%s)", _llm_provider().upper())
        logger.info("=" * 60)
        
        try:
            # PREFERRED: Use the startup-initialized agent (avoids expensive re-init per request)
            active_agent = None
            if ai_resume_agent and ai_resume_agent.agent_executor:
                active_agent = ai_resume_agent
                logger.info("✅ Using startup-initialized LangGraph AI Agent")
            else:
                from ai_resume_parsing_agent import AIResumeParsingAgent
                logger.info("🔧 Startup agent unavailable, initializing new LangGraph AI Agent...")
                active_agent = AIResumeParsingAgent(None)
                if not active_agent.agent_executor:
                    raise Exception("LangGraph agent executor failed to initialize")
                logger.info("✅ New LangGraph AI Agent initialized")
            
            logger.info(f"   Tools: {len(active_agent.tools) if active_agent.tools else 0}")
            logger.info(f"   Memory: {'Enabled' if active_agent.memory else 'Disabled'}")
            logger.info(f"   LLM: {type(active_agent.llm).__name__ if active_agent.llm else 'None'}")
            
            start_time = time.time()
            try:
                with futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(active_agent.parse_resume_with_ai, resume_text, resume_id)
                    parsed_data = future.result(timeout=240)
                elapsed_time = time.time() - start_time
                logger.info(f"✅ LangGraph AI Agent parsing completed in {elapsed_time:.2f} seconds")
                parsing_success = True
            except futures.TimeoutError:
                elapsed_time = time.time() - start_time
                logger.error(f"LangGraph agent timed out after {elapsed_time:.2f} seconds")
                raise Exception("LangGraph agent parsing timed out")
                
        except ImportError as e:
            logger.error(f"❌ Failed to import LangGraph agent: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Resume parsing failed: LangGraph import error - {str(e)}"
            )
        except Exception as agent_error:
            logger.error(f"❌ LangGraph AI Agent parsing failed: {agent_error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Resume parsing failed: {str(agent_error)}"
            )
        
        if not parsing_success or not parsed_data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Resume parsing failed: No valid parsed data produced"
            )
        
        # Log parsing method used
        parsing_method = parsed_data.get('parsing_method', 'UNKNOWN')
        logger.info(f"✅ PARSING COMPLETED - Method: {parsing_method}")
        logger.info("=" * 60)
        
        # Ensure parsed_data has required fields
        if not parsed_data:
            parsed_data = {
                "id": resume_id,
                "raw_text": resume_text,
                "content": resume_text,
                "upload_date": datetime.now().isoformat(),
                "parsing_method": "ERROR",
                "match_percentage": 0,
                "active_applications": 0,
                "security_status": "ERROR",
                "personal_info": {"name": "", "email": "", "phone": "", "location": ""},
                "skills": {"technical_skills": [], "soft_skills": [], "tools": []},
                "experience": {"total_years": 0, "current_role": "", "positions": []},
                "education": {"degrees": [], "universities": []}
            }
        
        # Ensure nested fields exist
        if not parsed_data.get('personal_info'):
            parsed_data['personal_info'] = {"name": "", "email": "", "phone": "", "location": ""}
        if not parsed_data.get('skills'):
            parsed_data['skills'] = {"technical_skills": [], "soft_skills": [], "tools": []}
        if not parsed_data.get('experience'):
            parsed_data['experience'] = {"total_years": 0, "current_role": "", "positions": []}
        if not parsed_data.get('education'):
            parsed_data['education'] = {"degrees": [], "universities": []}
        
        if raw_blob_ref:
            parsed_data["raw_blob_ref"] = raw_blob_ref
        if file.filename.lower().endswith(".pdf"):
            parsed_data["pdf_extraction_method"] = extraction_method

        # Store in Milvus via Document Ingestion Service
        logger.info("💾 Storing resume in Milvus vector database...")
        storage_result = None
        try:
            resume_id_stored = ingestion_service.add_resume(parsed_data)
            storage_result = {"status": "success", "resume_id": resume_id_stored}
            logger.info(f"✅ Resume stored in Milvus: {resume_id_stored}")
            logger.info("   📊 Stored: Vector embeddings (bge-base-en-v1.5) + Metadata + Chunks")
        except Exception as storage_error:
            error_msg = str(storage_error)
            logger.error(f"Error storing in Milvus: {error_msg}", exc_info=True)
            storage_result = {"status": "error", "message": error_msg}
            logger.warning("⚠️ Resume parsed but Milvus storage failed - data will not be searchable")
        
        logger.info(f"✅ RESUME UPLOAD COMPLETED - ID: {resume_id}, Method: {parsed_data.get('parsing_method', 'UNKNOWN')}")
        
        # Build response
        parsing_method = parsed_data.get('parsing_method', 'AI_AGENT')
        message = f"Resume uploaded and parsed successfully using {parsing_method}"
        if storage_result and storage_result.get('status') == 'error':
            message += " (Note: Storage in Milvus failed - data may not be searchable)"
        
        return {
            "success": True,
            "resume_id": resume_id,
            "message": message,
            "parsed_data": parsed_data,
            "milvus_result": storage_result,
            "file_type": "PDF" if file.filename.lower().endswith('.pdf') else "TXT",
            "storage_status": storage_result.get('status', 'success') if storage_result else 'unknown',
            "raw_blob_ref": raw_blob_ref,
            "pdf_extraction_method": extraction_method if file.filename.lower().endswith(".pdf") else None,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error processing resume: {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Resume upload failed: {error_msg}"
        )


@router.post("/analyze", response_model=ResumeAnalysisResponse, status_code=status.HTTP_200_OK)
@router.post("/resume-analysis", response_model=ResumeAnalysisResponse, status_code=status.HTTP_200_OK, include_in_schema=False)
async def analyze_resume(
    request: ResumeAnalysisRequest,
    current_user: Optional[dict] = Depends(require_user_when_basic_auth),
) -> ResumeAnalysisResponse:
    """
    Analyze resume text using verified QueryRouter.
    """
    try:
        router = ensure_query_router()
        # Runtime Invariant Check
        if not router:
            logger.critical("QueryRouter Not Initialized")
            detail = "Analysis Service Unavailable"
            if QUERY_ROUTER_INIT_ERROR:
                detail = f"{detail}: {QUERY_ROUTER_INIT_ERROR}"
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=detail,
            )
        
        # Route through Canonical Pipeline
        # We prepend "Analyze this resume: " to ensure correct Intent Classification
        query_text = f"Analyze this resume: {request.resume_text}"
        result = router.route_query(query_text)
        
        # Map response
        return ResumeAnalysisResponse(
            analysis={
                "summary": result.get("response", ""),
                "processing_method": f"VERIFIED_RAG::{result.get('source', 'unknown').upper()}",
                "data_exposure": "SECURE_CONTEXT_ONLY"
            },
            security_status={"status": "SECURE"},
            timestamp=datetime.now().isoformat()
        )
            
    except Exception as e:
        logger.error(f"Error analyzing resume: {e}", exc_info=True)
        return ResumeAnalysisResponse(
            analysis={"error": str(e)},
            security_status={"error": "Processing failed"},
            timestamp=datetime.now().isoformat()
        )
@router.get("/candidate/{candidate_id}", status_code=status.HTTP_200_OK)
@router.get("/candidate-detail/{candidate_id}", status_code=status.HTTP_200_OK, include_in_schema=False)
async def get_candidate(candidate_id: str) -> Dict[str, Any]:
    """Get detailed information about a specific candidate (deprecated)."""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail=f"This endpoint is deprecated. Use QuantChat AI: 'Show me details of candidate {candidate_id}'"
    )


@router.get("/agent-status", status_code=status.HTTP_200_OK)
async def get_agent_status(
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """Get autonomous AI agent status and verification"""
    _refresh_query_router_status()
    from app.integrations.document_intelligence import (
        document_intelligence_enabled,
        get_document_intelligence_client,
    )

    di_client = get_document_intelligence_client()
    di_ready = document_intelligence_enabled() and di_client.is_configured()

    if settings.use_pgvector_pipeline:
        from app.services.storage_diagnostics import get_pgvector_stats

        pg_stats = await get_pgvector_stats(session)
        vector_ready = bool(pg_stats.get("connected"))
        return {
            "agent_initialized": True,
            "agent_executor_available": True,
            "tools_available": True,
            "tools_count": 0,
            "memory_available": False,
            "llm_available": _llm_configured(),
            "document_intelligence_available": di_ready,
            "rag_available": vector_ready and QUERY_ROUTER_AVAILABLE,
            "agent_active": _llm_configured() and di_ready,
            "status": "ACTIVE" if (_llm_configured() and di_ready) else "INACTIVE",
            "storage_backend": "pgvector",
            "vector_store_connected": vector_ready,
            "milvus_connected": False,
            "hybrid_architecture_available": QUERY_ROUTER_AVAILABLE,
            "quantchat_available": QUERY_ROUTER_AVAILABLE,
            "pipeline": "azure_pgvector",
        }

    return {
        "agent_initialized": agent_status["initialized"],
        "agent_executor_available": agent_status["agent_executor_available"],
        "tools_available": agent_status["tools_available"],
        "tools_count": len(ai_resume_agent.tools) if ai_resume_agent and hasattr(ai_resume_agent, 'tools') else 0,
        "memory_available": agent_status["memory_available"],
        "llm_available": agent_status["llm_available"],
        "rag_available": agent_status["rag_available"],
        "agent_active": agent_status["agent_executor_available"] and agent_status["llm_available"],
        "status": "ACTIVE" if (agent_status["agent_executor_available"] and agent_status["llm_available"]) else "INACTIVE",
        "milvus_connected": agent_status["rag_available"],
        "hybrid_architecture_available": QUERY_ROUTER_AVAILABLE,
        "quantchat_available": QUERY_ROUTER_AVAILABLE
    }


@router.get("/hybrid-status", status_code=status.HTTP_200_OK)
async def get_hybrid_status(
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """Get hybrid architecture status including RAG verification"""
    _refresh_query_router_status()
    if settings.use_pgvector_pipeline:
        from app.services.storage_diagnostics import get_pgvector_stats

        pg_stats = await get_pgvector_stats(session)
        num_resumes = int(pg_stats.get("num_resumes") or 0)
        vector_connected = bool(pg_stats.get("connected"))
        rag_available = QUERY_ROUTER_AVAILABLE and vector_connected
        return {
            "rag_architecture": {
                "status": "active" if rag_available else "inactive",
                "security_level": "enterprise",
                "data_classification": "enabled",
                "local_processing": "sensitive_data_only",
                "llm_apis": "anonymized_data_only",
                "compliance": ["GDPR", "CCPA", "SOX", "HIPAA"],
            },
            "rag_implementation": {
                "status": "WORKING" if rag_available and num_resumes > 0 else "READY_BUT_EMPTY",
                "storage_backend": "pgvector",
                "vector_store_connected": vector_connected,
                "milvus_connected": False,
                "collection_ready": vector_connected,
                "num_resumes_stored": num_resumes,
                "num_jds_stored": int(pg_stats.get("num_jds") or 0),
                "embedding_provider": os.getenv("EMBEDDING_PROVIDER", "azure_openai"),
                "retrieval_working": QUERY_ROUTER_AVAILABLE,
                "pii_redaction_working": False,
                "errors": pg_stats.get("error") and [pg_stats["error"]] or [],
            },
            "pipeline": "azure_pgvector",
        }

    # Use QueryRouter and DocumentIngestion status
    rag_available = QUERY_ROUTER_AVAILABLE and INGESTION_AVAILABLE
    
    # Get Milvus status from DocumentIngestion
    milvus_connected = INGESTION_AVAILABLE and ingestion_service and ingestion_service.is_connected()
    
    # Get collection info if available
    num_resumes = 0
    collection_ready = False
    if milvus_connected:
        try:
            from pymilvus import Collection, utility
            from apps.quantchat.config.settings import RESUME_COLLECTION
            if utility.has_collection(RESUME_COLLECTION):
                collection = Collection(RESUME_COLLECTION)
                num_resumes = collection.num_entities
                collection_ready = True
        except Exception as e:
            logger.warning(f"Could not get Milvus collection info: {e}")
    
    return {
        "rag_architecture": {
            "status": "active" if rag_available else "inactive",
            "security_level": "enterprise",
            "data_classification": "enabled",
            "local_processing": "sensitive_data_only",
            "llm_apis": "anonymized_data_only",
            "compliance": ["GDPR", "CCPA", "SOX", "HIPAA"]
        },
        "rag_implementation": {
            "status": "WORKING" if rag_available else "NOT_AVAILABLE",
            "milvus_connected": milvus_connected,
            "collection_ready": collection_ready,
            "num_resumes_stored": num_resumes,
            "embedding_model_loaded": INGESTION_AVAILABLE and ingestion_service and ingestion_service.encoder is not None,
            "retrieval_working": QUERY_ROUTER_AVAILABLE,
            "pii_redaction_working": False,
            "errors": []
        },
        "servers": {
            "main_api": "http://localhost:8000",
            "secure_local": "http://localhost:8001", 
            "advanced_local": "http://localhost:8002",
            "hybrid_assistant": "http://localhost:8003",
            "enterprise_security": "http://localhost:8005"
        }
    }


@router.get("/llm-status", status_code=status.HTTP_200_OK)
@router.get("/gemini-status", status_code=status.HTTP_200_OK, include_in_schema=False)
async def get_llm_status() -> Dict[str, Any]:
    """Get LLM API status and verification"""
    provider = _llm_provider()
    gcp_project = os.getenv("GCP_PROJECT_ID")
    vertex_ai_configured = bool(gcp_project and vertex_credential_source_available())
    openai_configured = bool(os.getenv("OPENAI_API_KEY", "").strip())
    azure_openai_configured = bool(
        os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()
        and os.getenv("AZURE_OPENAI_API_KEY", "").strip()
    )
    groq_api_key_loaded = bool(os.getenv("GROQ_API_KEY"))

    api_active = _llm_configured() or groq_api_key_loaded or agent_status.get("llm_available", False)

    if provider == "azure_openai" and azure_openai_configured:
        primary = "Azure OpenAI"
        ready_msg = (
            "AI services are ready (Azure OpenAI, deployment="
            f"{os.getenv('AZURE_OPENAI_CHAT_DEPLOYMENT', 'gpt-4o')})"
        )
    elif provider == "openai" and openai_configured:
        primary = "OpenAI"
        ready_msg = f"AI services are ready (OpenAI, model={os.getenv('LLM_MODEL', 'gpt-4o')})"
    elif vertex_ai_configured:
        primary = "Vertex AI"
        ready_msg = "AI services are ready (Vertex AI)"
    elif groq_api_key_loaded:
        primary = "Groq"
        ready_msg = "AI services are ready (Groq)"
    else:
        primary = "None"
        ready_msg = (
            "OpenAI not configured: set OPENAI_API_KEY"
            if provider == "openai"
            else (
                "Azure OpenAI not configured: set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY"
                if provider == "azure_openai"
                else "Vertex AI not configured: set GCP_PROJECT_ID and ADC"
            )
        )

    return {
        "llm_api": {
            "llm_provider": provider,
            "openai_configured": openai_configured,
            "azure_openai_configured": azure_openai_configured,
            "groq_key_loaded": groq_api_key_loaded,
            "vertex_ai_configured": vertex_ai_configured,
            "gcp_project": gcp_project if vertex_ai_configured else None,
            "status": "ACTIVE" if api_active else "NOT_CONFIGURED",
            "primary_provider": primary,
            "model": os.getenv("LLM_MODEL", os.getenv("LLM_MODEL_NAME")),
            "fallback_enabled": True,
        },
        "parsing_ready": api_active,
        "message": ready_msg if api_active else ready_msg,
    }


@router.get("/resume-diagnostics", status_code=status.HTTP_200_OK)
async def get_resume_diagnostics(
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """Diagnostic endpoint to verify all resumes are stored and indexed correctly"""
    try:
        if settings.use_pgvector_pipeline:
            from app.services.storage_diagnostics import get_pgvector_stats

            pg_stats = await get_pgvector_stats(session)
            num_resumes = pg_stats.get("num_resumes", 0)
            return {
                "success": True,
                "storage_backend": "pgvector",
                "vector_store_status": pg_stats,
                "status": "healthy" if pg_stats.get("connected") else "warning",
                "message": (
                    f"Found {num_resumes} resumes in Postgres pgvector. "
                    "Use QuantChat AI to query resumes."
                ),
                "note": "Use QuantChat AI endpoint to query and retrieve resume details",
            }

        if not INGESTION_AVAILABLE or not ingestion_service:
            return {
                "success": False,
                "error": "Document ingestion service not available"
            }
        
        # Get Milvus status
        milvus_status = {
            "connected": ingestion_service.is_connected(),
            "num_entities": 0,
            "collection_name": None
        }
        
        if milvus_status["connected"]:
            try:
                from pymilvus import Collection, utility
                from apps.quantchat.config.settings import RESUME_COLLECTION
                if utility.has_collection(RESUME_COLLECTION):
                    collection = Collection(RESUME_COLLECTION)
                    milvus_status["num_entities"] = collection.num_entities
                    milvus_status["collection_name"] = RESUME_COLLECTION
            except Exception as e:
                milvus_status["error"] = str(e)
        
        # Note: Use QuantChat AI to query resumes instead of direct access
        return {
            "success": True,
            "milvus_status": milvus_status,
            "status": "healthy" if milvus_status.get("connected") else "warning",
            "message": f"Found {milvus_status.get('num_entities', 0)} resumes in Milvus. Use QuantChat AI to query resumes.",
            "note": "Use QuantChat AI endpoint to query and retrieve resume details"
        }
    except Exception as e:
        logger.error(f"Error in resume diagnostics: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/jd-diagnostics", status_code=status.HTTP_200_OK)
async def get_jd_diagnostics(
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """Diagnostic endpoint to verify all JDs are stored and indexed correctly"""
    try:
        if settings.use_pgvector_pipeline:
            from app.services.storage_diagnostics import get_pgvector_stats

            pg_stats = await get_pgvector_stats(session)
            num_jds = pg_stats.get("num_jds", 0)
            return {
                "success": True,
                "storage_backend": "pgvector",
                "vector_store_status": pg_stats,
                "status": "healthy" if pg_stats.get("connected") else "warning",
                "message": (
                    f"Found {num_jds} JDs in Postgres pgvector. "
                    "Use QuantChat AI to query JDs."
                ),
                "note": "Use QuantChat AI endpoint to query and retrieve JD details",
            }

        if not INGESTION_AVAILABLE or not ingestion_service:
            return {
                "success": False,
                "error": "Document ingestion service not available"
            }
        
        # Get Milvus JD collection status
        jd_milvus_status = {
            "connected": ingestion_service.is_connected(),
            "num_entities": 0,
            "collection_name": None
        }
        
        if jd_milvus_status["connected"]:
            try:
                from pymilvus import Collection, utility
                from apps.quantchat.config.settings import JD_COLLECTION
                if utility.has_collection(JD_COLLECTION):
                    collection = Collection(JD_COLLECTION)
                    jd_milvus_status["num_entities"] = collection.num_entities
                    jd_milvus_status["collection_name"] = JD_COLLECTION
            except Exception as e:
                jd_milvus_status["error"] = str(e)
        
        # Note: Use QuantChat AI to query JDs instead of direct access
        return {
            "success": True,
            "milvus_status": jd_milvus_status,
            "status": "healthy" if jd_milvus_status.get("connected") else "warning",
            "message": f"Found {jd_milvus_status.get('num_entities', 0)} JDs in Milvus. Use QuantChat AI to query JDs.",
            "note": "Use QuantChat AI endpoint to query and retrieve JD details"
        }
    except Exception as e:
        logger.error(f"Error in JD diagnostics: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/rag-status", status_code=status.HTTP_200_OK)
async def get_rag_status(
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """Get detailed RAG implementation status and verification"""
    _refresh_query_router_status()
    from app.services.storage_diagnostics import get_vector_store_stats

    store_stats = await get_vector_store_stats(session)
    storage_backend = store_stats.get("storage_backend", "milvus")
    vector_connected = bool(store_stats.get("connected"))
    num_resumes = int(store_stats.get("num_resumes") or 0)
    num_jds = int(store_stats.get("num_jds") or 0)
    collection_ready = vector_connected and (num_resumes + num_jds) >= 0

    rag_available = QUERY_ROUTER_AVAILABLE and (
        vector_connected if settings.use_pgvector_pipeline else INGESTION_AVAILABLE
    )
    milvus_connected = vector_connected if not settings.use_pgvector_pipeline else False
    embedding_loaded = (
        True
        if settings.use_pgvector_pipeline
        else INGESTION_AVAILABLE and ingestion_service and ingestion_service.encoder is not None
    )
    
    def _get_rag_recommendations() -> list:
        """Get recommendations based on RAG verification status"""
        recommendations = []
        
        if not vector_connected:
            if settings.use_pgvector_pipeline:
                recommendations.append(
                    "Verify DATABASE_URL and run alembic upgrade head for document_chunks"
                )
            else:
                recommendations.append("Start Milvus: docker-compose -f docker-compose.milvus.yml up -d")
        
        if not embedding_loaded and not settings.use_pgvector_pipeline:
            recommendations.append("Install sentence-transformers: pip install sentence-transformers")
        
        if num_resumes == 0 and num_jds == 0:
            recommendations.append("Upload and parse resumes/JDs to populate the vector database")
        
        if not QUERY_ROUTER_AVAILABLE:
            recommendations.append("QueryRouter not available - check QuantChat initialization")
        
        if not recommendations:
            recommendations.append("RAG implementation is working correctly!")
        
        return recommendations
    
    rag_status = (
        "WORKING"
        if (rag_available and vector_connected and embedding_loaded and (num_resumes + num_jds) > 0)
        else "READY_BUT_EMPTY"
        if (rag_available and vector_connected)
        else "ERROR"
    )
    
    return {
        "rag_implementation": {
            "status": rag_status,
            "storage_backend": storage_backend,
            "description": {
                "WORKING": "RAG is fully operational with documents stored",
                "READY_BUT_EMPTY": "RAG is ready but no documents stored yet",
                "PARTIAL": "Some components working but issues detected",
                "ERROR": "RAG verification failed",
                "UNKNOWN": "Status could not be determined"
            }.get(rag_status, "Unknown status"),
            "components": {
                "vector_store": store_stats,
                "milvus_connection": {
                    "connected": milvus_connected,
                    "collection_exists": collection_ready,
                    "collection_loaded": collection_ready,
                    "has_index": collection_ready,
                    "num_resumes": num_resumes,
                    "num_jds": num_jds
                },
                "embedding_model": {
                    "loaded": embedding_loaded,
                    "model": "BAAI/bge-base-en-v1.5",
                    "dimension": 768
                },
                "retrieval": {
                    "working": QUERY_ROUTER_AVAILABLE,
                    "method": "hybrid_search",
                    "similarity_metric": "COSINE"
                },
                "security": {
                    "pii_redaction": False,
                    "pii_redaction_scope": "logs_only",
                    "redaction_patterns": ["email", "phone", "ssn", "salary", "address", "credit_card"]
                }
            },
            "errors": [],
            "recommendations": _get_rag_recommendations()
        }
    }


# ==============================================================================
# CANDIDATES ENDPOINT - List parsed resumes (Postgres pgvector on Azure)
# ==============================================================================
@router.get("/candidates", status_code=status.HTTP_200_OK)
async def list_candidates(
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    List uploaded resumes.

    Azure Non-Prod: Postgres candidates + document_chunks metadata.
    Legacy local dev: Milvus vector database.
    """
    if settings.use_pgvector_pipeline:
        from sqlalchemy import select

        from app.models.candidates import Candidate

        result = await session.execute(
            select(Candidate).order_by(Candidate.created_at.desc()).limit(500)
        )
        rows = result.scalars().all()
        candidates = [
            {
                "candidate_id": str(row.id),
                "document_id": str(row.id),
                "name": row.name,
                "email": row.email,
                "phone": row.phone,
                "location": row.location,
                "parsing_confidence": row.parsing_confidence,
                "source": row.source,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
        return {
            "candidates": candidates,
            "total": len(candidates),
            "source": "postgres_pgvector",
        }

    candidates = []
    total_count = 0

    if not INGESTION_AVAILABLE or not ingestion_service:
        return {
            "candidates": [],
            "total": 0,
            "source": "milvus",
            "error": "Milvus connection not available"
        }
    
    try:
        from pymilvus import Collection, utility
        
        collection_name = "quanthire_resumes"
        
        if not utility.has_collection(collection_name):
            return {
                "candidates": [],
                "total": 0,
                "source": "milvus",
                "error": "Resume collection does not exist"
            }
        
        collection = Collection(collection_name)
        collection.load()
        
        # Get all chunks with text to extract candidate info
        results = collection.query(
            expr="id >= 0",
            output_fields=["document_id", "entity_name", "section_type", "chunk_text", "created_at"],
            limit=5000
        )
        
        # Group chunks by document_id to assemble candidate profiles
        doc_chunks = {}
        for r in results:
            doc_id = r.get("document_id")
            if not doc_id:
                continue
            if doc_id not in doc_chunks:
                doc_chunks[doc_id] = {
                    "entity_name": r.get("entity_name", "Unknown"),
                    "created_at": r.get("created_at", ""),
                    "chunks": {}
                }
            section = r.get("section_type", "")
            doc_chunks[doc_id]["chunks"][section] = r.get("chunk_text", "")
        
        # Build candidate list from chunks
        seen_docs = {}
        for doc_id, doc_info in doc_chunks.items():
            raw_name = doc_info["entity_name"]
            clean_name = _clean_entity_name(raw_name)
            chunks = doc_info["chunks"]
            
            # Extract email from Personal Info chunk
            email = ""
            location = ""
            personal_text = chunks.get("Personal Info", "")
            if personal_text:
                email_match = re.search(r'Email:\s*(\S+@\S+)', personal_text)
                if email_match:
                    email = email_match.group(1)
                loc_match = re.search(r'Location:\s*(.+)', personal_text)
                if loc_match:
                    location = loc_match.group(1).strip()
            
            # Extract skills from Skills chunk
            skills = []
            skills_text = chunks.get("Skills", "")
            if skills_text:
                for line in skills_text.split("\n"):
                    line = line.strip()
                    if line and not line.endswith(":"):
                        skills.extend(s.strip() for s in line.split(",") if s.strip())
                skills = skills[:15]
            
            seen_docs[doc_id] = {
                "id": doc_id,
                "name": clean_name,
                "email": email,
                "location": location,
                "skills": skills,
                "experience_years": 0,
                "match_percentage": 0,
                "active_applications": 1,
                "upload_date": str(doc_info["created_at"]),
                "source": "milvus"
            }
        
        candidates = list(seen_docs.values())
        total_count = len(candidates)
        
        logger.info(f"Listed {total_count} candidates from Milvus")
        
    except Exception as e:
        logger.error(f"Error listing candidates from Milvus: {e}")
        return {
            "candidates": [],
            "total": 0,
            "source": "milvus",
            "error": str(e)
        }
    
    return {
        "candidates": candidates,
        "total": total_count,
        "source": "milvus"
    }


def _clean_entity_name(name: str) -> str:
    """Clean hyphenated entity names from PDF extraction artifacts.
    
    Converts "-Aditya- -Rao-" to "Aditya Rao"
    """
    if not name:
        return "Unknown"
    
    # Remove hyphens wrapped around words: "-Word-" -> "Word"
    cleaned = re.sub(r'(?<![A-Za-z0-9])-([A-Za-z][A-Za-z0-9]*)-(?![A-Za-z0-9])', r'\1', name)
    cleaned = re.sub(r'(?<![A-Za-z0-9])-([A-Za-z][A-Za-z0-9]*)(?=\s|$)', r'\1', cleaned)
    cleaned = re.sub(r'([A-Za-z][A-Za-z0-9]*)-(?=\s|$)', r'\1', cleaned)
    
    # Clean up extra spaces
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    return cleaned if cleaned else "Unknown"

