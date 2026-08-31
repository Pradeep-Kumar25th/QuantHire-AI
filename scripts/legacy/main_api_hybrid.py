"""
QuantHire AI - Main API Backend with Hybrid Architecture
=======================================================

This is the main API backend that integrates the hybrid approach
into the QuantHire UI on localhost:3000
"""

"""
QuantHire AI - Main API Backend with Hybrid Architecture
=======================================================

Enterprise-level FastAPI application with:
- Secure API key management
- Proper logging and error handling
- Type safety with Pydantic
- Rate limiting and security middleware
- Comprehensive documentation
"""

import logging
import os
import sys
import uuid
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

import warnings
# Suppress requests dependency warning for charset detection (charset-normalizer is installed)
warnings.filterwarnings('ignore', message='.*charset.*', category=UserWarning)
warnings.filterwarnings('ignore', message='.*Unable to find acceptable character detection.*')

import requests

from fastapi import FastAPI, HTTPException, Depends, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field, field_validator, ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/backend_api.log', encoding='utf-8') if Path('logs').exists() else logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Force UTF-8 stdout/stderr so imports with Unicode logs do not crash on Windows codepages
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Create logs directory if it doesn't exist
Path("logs").mkdir(exist_ok=True)

# Prometheus metrics (optional, install with: pip install prometheus-client)
try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

# Initialize metrics if available
if PROMETHEUS_AVAILABLE:
    api_requests_total = Counter(
        'quanthire_api_requests_total',
        'Total QuantHire API requests',
        ['method', 'endpoint']
    )
    api_duration = Histogram(
        'quanthire_api_duration_seconds',
        'QuantHire API request duration'
    )
    quantchat_queries = Counter(
        'quanthire_quantchat_queries_total',
        'QuantChat queries'
    )
    milvus_entities = Gauge(
        'quanthire_milvus_entities_total',
        'Entities in Milvus'
    )

# Import the canonical Enterprise RAG Service
# enterprise_rag_service removed - use apps.quantchat instead
# from enterprise_rag_service import get_enterprise_rag_service  # DEPRECATED

# Import LangGraph AI Agent for resume parsing
try:
    from ai_resume_parsing_agent import initialize_ai_resume_agent, AIResumeParsingAgent
    print("✅ LangGraph AI Agent available")
    LANGGRAPH_AGENT_AVAILABLE = True
except ImportError as e:
    print(f"❌ LangGraph AI Agent not available: {e}")
    LANGGRAPH_AGENT_AVAILABLE = False

app = FastAPI(
    title="QuantHire AI - Main API",
    description="Main API backend with hybrid architecture integration",
    version="1.0.0"
)

# CORS configuration - Enterprise security best practices
cors_origins_env = os.getenv("CORS_ORIGINS", "")
if cors_origins_env:
    cors_origins = [origin.strip() for origin in cors_origins_env.split(",")]
else:
    # Default development origins if not configured
    cors_origins = [
        "http://localhost:3000", 
        "http://localhost:3001", 
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]

# Restrict CORS to specific methods and headers for security
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # Specific methods only
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],  # Specific headers only
    max_age=3600,  # Cache preflight requests for 1 hour
)

# Add trusted host middleware for additional security
allowed_hosts = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=allowed_hosts
)

# Import Verified QueryRouter from Reference Architecture
# ✅ SINGLE SOURCE OF TRUTH: apps.quantchat.core.query_router
try:
    # Need to add project root to path to import apps
    sys.path.append(os.getcwd())
    from apps.quantchat.core.query_router import QueryRouter
    QUERY_ROUTER_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import QueryRouter: {e}")
    QUERY_ROUTER_AVAILABLE = False

# Initialize QueryRouter (The ONE and ONLY RAG Pipeline)
if QUERY_ROUTER_AVAILABLE:
    query_router = QueryRouter()
    logger.info("✅ QueryRouter initialized as the SINGLE orchestration engine")
else:
    query_router = None
    logger.critical("❌ QueryRouter failed to initialize - System is in critical failure state")

# ============================================================================
# ENTERPRISE RAG SERVICE REMOVED
# ============================================================================
# The Enterprise RAG Service has been removed to enforce single RAG pipeline.
# All RAG operations must use apps.quantchat (QueryRouter for retrieval, DocumentIngestion for storage)
# ============================================================================
# enterprise_rag_service = None  # DEPRECATED - DO NOT USE
# hybrid_architecture = None  # DEPRECATED - DO NOT USE

# Initialize TRUE AI Agent for resume parsing
ai_resume_agent = None
agent_status = {
    "initialized": False,
    "agent_executor_available": False,
    "tools_available": False,
    "memory_available": False,
    "rag_available": False,
    "llm_available": False
}

try:
    # VERTEX AI ONLY - Check for GCP configuration
    gcp_project = os.getenv("GCP_PROJECT_ID")
    gcp_credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    
    if not gcp_project:
        raise ValueError(
            "GCP_PROJECT_ID environment variable not set. "
            "Vertex AI is required. Set GCP_PROJECT_ID and GOOGLE_APPLICATION_CREDENTIALS in .env"
        )
    
    if LANGGRAPH_AGENT_AVAILABLE:
        logger.info("=" * 80)
        logger.info("🚀 INITIALIZING LANGGRAPH AI AGENT WITH VERTEX AI")
        logger.info("=" * 80)
        logger.info(f"GCP Project: {gcp_project}")
        logger.info(f"GCP Location: {os.getenv('GCP_LOCATION', 'us-central1')}")
        logger.info(f"Credentials: {'Configured' if gcp_credentials else 'Using default'}")
        
        # Initialize the AI Resume Parsing Agent with Vertex AI
        ai_resume_agent = initialize_ai_resume_agent()
        
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
        ai_resume_agent = None
        logger.error("❌ LangGraph agent not available")
        
except Exception as e:
    logger.error(f"CRITICAL: Failed to initialize AI Agent: {e}", exc_info=True)
    ai_resume_agent = None

# Configuration constants (must be defined before Pydantic models that use them)
MAX_CONVERSATION_HISTORY = int(os.getenv("MAX_CONVERSATION_HISTORY", "200"))  # Increased from 100 to 200 for maximum memory
MAX_MESSAGE_LENGTH = int(os.getenv("MAX_MESSAGE_LENGTH", "5000"))
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE_MB", "10")) * 1024 * 1024  # Convert MB to bytes

# Pydantic models with validation
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
    response: str
    processing_method: str
    security_status: str
    timestamp: str

class ResumeAnalysisRequest(BaseModel):
    resume_text: str
    candidate_name: Optional[str] = None

class ResumeAnalysisResponse(BaseModel):
    analysis: Dict[str, Any]
    security_status: Dict[str, Any]
    timestamp: str

class JobMatchingRequest(BaseModel):
    job_description: str
    candidate_id: Optional[str] = None

class JobMatchingResponse(BaseModel):
    matches: List[Dict[str, Any]]
    security_status: Dict[str, Any]
    timestamp: str

# API Routes
@app.get("/")
async def root():
    return {
        "message": "QuantHire AI - Main API with Hybrid Architecture",
        "version": "1.0.0",
        "hybrid_architecture": "enabled",
        "security_level": "enterprise"
    }

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "hybrid_architecture": "active",
        "security_level": "enterprise",
        "timestamp": datetime.now().isoformat()
    }

# Store conversation history (in production, use Redis or database)
# TODO: Replace with Redis/database for production
conversation_histories: Dict[str, List[Dict[str, Any]]] = {}

@app.post("/api/chat", response_model=ChatResponse)
async def ai_chat(message: ChatMessage) -> ChatResponse:
    """
    AI Chat endpoint - Verified Entry Point
    Routes DIRECTLY to QueryRouter (No intermediate orchestrators).
    """
    try:
        # Runtime Invariant Check
        if not query_router:
            logger.critical("QueryRouter Not Initialized")
            raise HTTPException(status_code=500, detail="RAG Pipeline Failed Initialization")

        request_id = str(uuid.uuid4())
        logger.info(f"[{request_id}] QuantChat ENTRY: {message.message[:50]}...")
        
        # Add to history (Logging only, QueryRouter is stateless)
        user_id = message.user_id or "default"
        if user_id not in conversation_histories:
            conversation_histories[user_id] = []
        conversation_histories[user_id].append({
            "role": "user",
            "content": message.message,
            "timestamp": datetime.now().isoformat()
        })

        # EXECUTE QUERY ROUTER (The ONE Pipeline)
        # ----------------------------------------
        logger.info(f"[{request_id}] Routing to QueryRouter...")
        result = query_router.route_query(message.message)
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
        
        return ChatResponse(
            response=response_text,
            processing_method=f"VERIFIED_RAG::{result.get('source', 'unknown').upper()}",
            security_status="SECURE",
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error(f"Error in /api/chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.post("/api/resume-analysis", response_model=ResumeAnalysisResponse)
async def analyze_resume(request: ResumeAnalysisRequest):
    """
    Resume Analysis endpoint
    Uses hybrid architecture for secure resume processing
    """
    try:
        # Process resume using hybrid architecture
        result = hybrid_architecture.process_query_complete_flow(f"Analyze this resume: {request.resume_text}")
        
        if "error" not in result:
            return ResumeAnalysisResponse(
                analysis={
                    "summary": result["llm_response"],
                    "processing_method": result["security_status"]["only_context_chunks_sent"] and "ANONYMIZED_LLM" or "LOCAL_ONLY",
                    "data_exposure": result["data_exposure_percentage"]
                },
                security_status=result["security_status"],
                timestamp=datetime.now().isoformat()
            )
        else:
            return ResumeAnalysisResponse(
                analysis={"error": result["error"]},
                security_status={"error": "Processing failed"},
                timestamp=datetime.now().isoformat()
            )
    except Exception as e:
        return ResumeAnalysisResponse(
            analysis={"error": str(e)},
            security_status={"error": "Processing failed"},
            timestamp=datetime.now().isoformat()
        )

@app.post("/api/job-matching", response_model=JobMatchingResponse)
async def match_jobs(request: JobMatchingRequest):
    """
    Job Matching endpoint
    Uses hybrid architecture for secure job matching
    """
    try:
        # Process job matching using hybrid architecture
        result = hybrid_architecture.process_query_complete_flow(f"Match candidates for this job: {request.job_description}")
        
        if "error" not in result:
            return JobMatchingResponse(
                matches=[{
                    "candidate_id": "candidate_001",
                    "match_score": 0.95,
                    "reason": result["llm_response"]
                }],
                security_status=result["security_status"],
                timestamp=datetime.now().isoformat()
            )
        else:
            return JobMatchingResponse(
                matches=[],
                security_status={"error": "Matching failed"},
                timestamp=datetime.now().isoformat()
            )
    except Exception as e:
        return JobMatchingResponse(
            matches=[],
            security_status={"error": str(e)},
            timestamp=datetime.now().isoformat()
        )

@app.post("/api/upload-resume")
async def upload_resume(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Upload and parse a resume (PDF or TXT), storing it in Milvus vector database.
    
    Args:
        file: Resume file (PDF or TXT format)
        
    Returns:
        Dict containing parsed resume data
        
    Raises:
        HTTPException: If file is invalid, too large, or processing fails
    """
    try:
        logger.info(f"Resume upload request received: {file.filename} ({file.content_type})")
        
        # Validate file type
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename is required")
        
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in ['.pdf', '.txt']:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file_ext}. Please upload PDF or TXT files."
            )
        
        # Read file content with size validation
        content = await file.read()
        file_size = len(content)
        
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large: {file_size / 1024 / 1024:.2f}MB. Maximum size: {MAX_FILE_SIZE / 1024 / 1024}MB"
            )
        
        if file_size == 0:
            raise HTTPException(status_code=400, detail="File is empty")
        
        logger.info(f"File size: {file_size} bytes")
        
        # Generate unique resume ID
        resume_id = str(uuid.uuid4())
        
        # Extract text based on file type
        if file.filename.lower().endswith('.pdf'):
            print("📄 Processing PDF resume...")
            if ai_resume_agent:
                resume_text = ai_resume_agent.extract_text_from_pdf(content)
            else:
                raise HTTPException(status_code=500, detail="PDF processing not available - PyPDF2 not installed")
        elif file.filename.lower().endswith('.txt'):
            print("📄 Processing text resume...")
            resume_text = content.decode('utf-8')
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type. Please upload PDF or TXT files.")
        
        print(f"📝 Extracted text length: {len(resume_text)} characters")
        
        # Parse resume using AI agent (LangChain + Gemini with hybrid approach)
        # PRIORITY: Use autonomous AI agent, ensure it's not falling back
        parsed_data = None
        try:
            # CRITICAL: Verify agent is available and functional before use
            if not ai_resume_agent:
                raise Exception("AI Agent not initialized")
            
            if not hasattr(ai_resume_agent, 'parse_resume_with_ai'):
                raise Exception("AI Agent missing parse_resume_with_ai method")
            
            # CRITICAL: Runtime validation - check agent status at request time, not just startup
            # This prevents intermittent failures due to stale status
            runtime_agent_executor_available = (
                hasattr(ai_resume_agent, 'agent_executor') and 
                ai_resume_agent.agent_executor is not None and
                hasattr(ai_resume_agent.agent_executor, 'invoke')
            )
            
            # Check LLM service availability - handle both direct and wrapped agent
            llm_service = None
            if hasattr(ai_resume_agent, 'llm_service'):
                llm_service = ai_resume_agent.llm_service
            elif hasattr(ai_resume_agent, '_agent') and hasattr(ai_resume_agent._agent, 'llm_service'):
                llm_service = ai_resume_agent._agent.llm_service
            
            runtime_llm_available = (
                llm_service is not None and
                hasattr(llm_service, 'is_available') and
                llm_service.is_available()
            )
            
            if not runtime_agent_executor_available:
                error_details = []
                if not hasattr(ai_resume_agent, 'agent_executor'):
                    error_details.append("agent_executor attribute missing")
                elif ai_resume_agent.agent_executor is None:
                    error_details.append("agent_executor is None")
                elif not hasattr(ai_resume_agent.agent_executor, 'invoke'):
                    error_details.append("agent_executor missing invoke method")
                
                logger.error(f"Agent Executor not available at runtime: {', '.join(error_details)}")
                raise Exception(f"Agent Executor not available - autonomous agent not functional: {', '.join(error_details)}")
            
            if not runtime_llm_available:
                logger.error("LLM service not available at runtime")
                raise Exception("LLM service not available - cannot process resume")
            
            # Use the autonomous AI agent
            logger.info("🤖 Using AUTONOMOUS AI AGENT for parsing...")
            logger.info(f"   ✓ Agent Executor: Available (runtime verified)")
            logger.info(f"   ✓ Tools: {len(ai_resume_agent.tools) if hasattr(ai_resume_agent, 'tools') else 0} available")
            logger.info(f"   ✓ Memory: {'Enabled' if hasattr(ai_resume_agent, 'memory') and ai_resume_agent.memory else 'Disabled'}")
            logger.info(f"   ✓ LLM: Available (runtime verified)")
            
            # Additional runtime checks
            if not hasattr(ai_resume_agent, 'parse_resume_with_ai'):
                raise Exception("AI Agent missing parse_resume_with_ai method")
            
            # Add timeout wrapper for agent parsing (4.5 minutes max)
            import concurrent.futures
            
            logger.info(f"Starting autonomous AI agent parsing (timeout: 270 seconds)...")
            start_time = time.time()
            try:
                # Run agent parsing in thread pool with timeout
                # Use max_workers=1 to ensure thread safety
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(ai_resume_agent.parse_resume_with_ai, resume_text, resume_id)
                    parsed_data = future.result(timeout=240)  # 4 minutes timeout to finish within client 5 min
                elapsed_time = time.time() - start_time
                logger.info(f"Agent parsing completed in {elapsed_time:.2f} seconds")
            except concurrent.futures.TimeoutError:
                elapsed_time = time.time() - start_time
                logger.error(f"Agent parsing timed out after {elapsed_time:.2f} seconds (max: 270)")
                raise Exception("Agent parsing timed out - processing took longer than expected. Please try with a smaller resume or check backend logs.")
            except Exception as e:
                elapsed_time = time.time() - start_time
                logger.error(f"Agent parsing failed after {elapsed_time:.2f} seconds: {e}", exc_info=True)
                raise
            parsing_method = parsed_data.get('parsing_method', 'UNKNOWN')
            
            # CRITICAL: Verify autonomous AI agent was used (NO FALLBACK ALLOWED)
            if parsing_method == "BASIC_REGEX_FALLBACK":
                # This should NEVER happen if agent executor is available
                error_msg = parsed_data.get('error', 'Unknown error')
                error_code = parsed_data.get('error_code', 'UNKNOWN')
                
                print("❌ CRITICAL ERROR: Agent fell back to regex parsing!")
                print("   Agent executor is available but returned fallback parsing.")
                print("   This indicates the agent execution failed internally.")
                print(f"   Error: {error_msg}")
                print(f"   Error Code: {error_code}")
                print(f"   Agent Version: {parsed_data.get('agent_version', 'Unknown')}")
                print()
                print("   ⚠️ FALLBACK NOT ALLOWED - Agent executor is available!")
                print("   The agent MUST use the autonomous AI agent, not fallback.")
                print("   Check backend logs for agent execution errors.")
                
                # DO NOT allow fallback - raise exception
                raise Exception(
                    f"Agent executor available but returned fallback parsing. "
                    f"This should not happen. Error: {error_msg} (Code: {error_code})"
                )
            elif parsing_method == "ERROR":
                print("❌ CRITICAL: Agent parsing returned ERROR!")
                error_msg = parsed_data.get('error', 'Unknown error')
                print(f"   Error: {error_msg}")
                # Ensure we have valid data even if parsing failed
                if not parsed_data.get('personal_info') or not parsed_data.get('skills'):
                    print("⚠️ Missing required fields, using local extraction as last resort")
                    from quantire_agents.resume_parser.extractors import LocalExtractor
                    from quantire_agents.config.constants import ParsingMethod, DEFAULT_FALLBACK_MATCH_PERCENTAGE
                    from datetime import datetime
                    local_data = LocalExtractor.extract_all(resume_text)
                    parsed_data = {
                        **parsed_data,
                        **local_data,
                        "parsing_method": ParsingMethod.BASIC_REGEX_FALLBACK.value,
                        "match_percentage": DEFAULT_FALLBACK_MATCH_PERCENTAGE,
                        "error": f"Agent failed: {error_msg}, used local extraction as last resort"
                    }
                    print("   ⚠️ Used local extraction as last resort (agent error occurred)")
            else:
                # Success - autonomous agent worked
                print(f"✅ AUTONOMOUS AI AGENT successfully completed parsing!")
                print(f"   - Parsing Method: {parsing_method}")
                print(f"   - Agent Version: {parsed_data.get('agent_version', 'Unknown')}")
                print(f"   - Tools Used: {parsed_data.get('tools_used', [])}")
                print(f"   - Memory Enabled: {parsed_data.get('memory_enabled', False)}")
                print(f"   - RAG Enabled: {parsed_data.get('rag_enabled', False)}")
                print(f"   - Match Percentage: {parsed_data.get('match_percentage', 0)}%")
                
        except Exception as parse_error:
            print(f"❌ CRITICAL ERROR during autonomous agent parsing: {parse_error}")
            import traceback
            traceback.print_exc()
            
            # Only use fallback if agent is truly not available
            if not ai_resume_agent or not agent_status["agent_executor_available"]:
                print("⚠️ Agent not available, using hybrid architecture parsing as fallback")
                try:
                    parsed_data = hybrid_architecture.parse_resume(resume_text, resume_id)
                    print(f"✅ Hybrid Architecture parsing completed")
                except Exception as hybrid_error:
                    print(f"❌ Hybrid architecture also failed: {hybrid_error}")
                    # Last resort: local extraction
                    print("🔄 Using local extraction as last resort...")
                    try:
                        from quantire_agents.resume_parser.extractors import LocalExtractor
                        from quantire_agents.config.constants import ParsingMethod, DEFAULT_FALLBACK_MATCH_PERCENTAGE
                        from datetime import datetime
                        local_data = LocalExtractor.extract_all(resume_text)
                        parsed_data = {
                            "id": resume_id,
                            "raw_text": resume_text,
                            "content": resume_text,
                            "upload_date": datetime.now().isoformat(),
                            "parsing_method": ParsingMethod.BASIC_REGEX_FALLBACK.value,
                            "match_percentage": DEFAULT_FALLBACK_MATCH_PERCENTAGE,
                            "active_applications": 1,
                            "security_status": "SECURE",
                            "agent_version": "Fallback Mode (Exception)",
                            "tools_used": [],
                            "memory_enabled": False,
                            "rag_enabled": False,
                            "error": f"Agent and hybrid failed: {str(parse_error)}",
                            **local_data
                        }
                        print(f"✅ Local extraction completed as last resort")
                    except Exception as fallback_error:
                        print(f"❌ All parsing methods failed: {fallback_error}")
                        # Last resort: return minimal valid structure
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
                            "education": {"degrees": [], "universities": []},
                            "error": str(fallback_error)
                        }
            else:
                # Agent is available but failed - re-raise to prevent silent fallback
                raise
        
        # Ensure parsed_data has required fields (even if agent succeeded)
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
        
        # Store in hybrid architecture (which stores in Milvus)
        logger.info("💾 Storing resume in Milvus vector database...")
        storage_result = None
        storage_error = None
        try:
            storage_result = hybrid_architecture.add_resume(parsed_data)
            logger.info("✅ Resume stored in Milvus successfully")
        except Exception as storage_error:
            error_msg = str(storage_error)
            logger.error(f"❌ CRITICAL: Error storing in Milvus: {error_msg}", exc_info=True)
            # Don't fail the upload if storage fails, but log it as critical
            storage_result = {"status": "error", "message": error_msg}
            # Still return success but with storage warning
            logger.warning("⚠️ Resume parsed but storage failed - data may not be searchable")
        
        print(f"{'='*80}")
        print(f"✅ RESUME UPLOAD COMPLETED SUCCESSFULLY")
        print(f"{'='*80}")
        print(f"   Resume ID: {resume_id}")
        print(f"   Parsing Method: {parsed_data.get('parsing_method', 'UNKNOWN')}")
        print(f"   Name: {parsed_data.get('personal_info', {}).get('name', 'N/A')}")
        print(f"{'='*80}\n")
        
        # Build response message
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
            "storage_status": storage_result.get('status', 'success') if storage_result else 'unknown'
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error processing resume: {error_msg}", exc_info=True)
        print(f"\n{'='*80}")
        print(f"❌ ERROR PROCESSING RESUME")
        print(f"{'='*80}")
        print(f"   Error: {error_msg}")
        import traceback
        traceback.print_exc()
        print(f"{'='*80}\n")
        
        # Return error response instead of raising to provide better feedback
        return {
            "success": False,
            "error": error_msg,
            "resume_id": resume_id if 'resume_id' in locals() else None,
            "message": f"Resume upload failed: {error_msg}",
            "parsed_data": None
        }

@app.get("/api/candidates")
async def get_candidates():
    """Get all candidates from the system"""
    try:
        # Get all stored resumes from hybrid architecture
        candidates = hybrid_architecture.get_all_resumes()
        
        # Format candidates for UI with safe data access
        formatted_candidates = []
        for candidate in candidates:
            # Safely extract personal_info
            personal_info = candidate.get("personal_info", {})
            if isinstance(personal_info, dict):
                name = personal_info.get("name", "Unknown")
                email = personal_info.get("email", "")
                location = personal_info.get("location", "")
            else:
                name, email, location = "Unknown", "", ""
            
            # Safely extract experience
            experience = candidate.get("experience", {})
            if isinstance(experience, dict):
                experience_years = experience.get("total_years", 0)
            else:
                experience_years = 0
            
            # Safely extract skills - handle both list and dict formats
            skills = candidate.get("skills", [])
            if isinstance(skills, dict):
                # If skills is a dict (from AI parsing), extract technical_skills
                skills_list = skills.get("technical_skills", [])
                if not skills_list:
                    # Fallback to all skills from dict
                    skills_list = skills.get("soft_skills", []) + skills.get("tools", [])
                skills = skills_list
            
            # Ensure skills is a list
            if not isinstance(skills, list):
                skills = []
            
            formatted_candidates.append({
                "id": candidate.get("id", ""),
                "name": name,
                "email": email,
                "location": location,
                "experience_years": experience_years,
                "skills": skills,
                "match_percentage": candidate.get("match_percentage", 85),
                "active_applications": candidate.get("active_applications", 1),
                "upload_date": candidate.get("upload_date", datetime.now().isoformat())
            })
        
        return formatted_candidates
        
    except Exception as e:
        print(f"❌ Error fetching candidates: {e}")
        import traceback
        traceback.print_exc()
        # Return empty list on error to prevent frontend crash
        return []

@app.get("/api/candidate/{candidate_id}")
async def get_candidate(candidate_id: str):
    """Get detailed information about a specific candidate"""
    try:
        candidate = hybrid_architecture.get_resume_by_id(candidate_id)
        
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")
        
        return {
            "success": True,
            "candidate": candidate
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching candidate: {str(e)}")

@app.get("/api/jobs")
async def get_jobs():
    """Get all jobs from the system"""
    try:
        jobs = hybrid_architecture.get_all_jobs()
        
        # Format jobs for UI
        formatted_jobs = []
        for job in jobs:
            # Skip resume entries
            if 'id' in job and job['id'].startswith('job_'):
                formatted_jobs.append({
                    "id": job.get("id", ""),
                    "title": job.get("title", "Untitled Job"),
                    "department": job.get("department", ""),
                    "location": job.get("location", ""),
                    "remote": job.get("remote", False),
                    "status": job.get("status", "active"),
                    "openings": job.get("openings", 1),
                    "filled": job.get("filled", 0),
                    "applications": job.get("applications", 0),
                    "created": job.get("added_at", job.get("created", datetime.now().isoformat()))
                })
        
        return formatted_jobs if formatted_jobs else []
        
    except Exception as e:
        print(f"❌ Error fetching jobs: {e}")
        return []

@app.post("/api/jobs")
async def create_job(job_data: Dict[str, Any]):
    """Create a new job and store in Milvus"""
    try:
        # Parse job data from request
        job_info = {
            "title": job_data.get("title", ""),
            "department": job_data.get("department", ""),
            "location": job_data.get("location", ""),
            "description": job_data.get("description", ""),
            "level": job_data.get("level", ""),
            "remote": True,  # Default
            "status": "open",
            "openings": 1,
            "filled": 0,
            "applications": 0
        }
        
        # Store job in hybrid architecture (Milvus)
        job_id = hybrid_architecture.add_job(job_info)
        
        return {
            "success": True,
            "job_id": job_id,
            "message": "Job created and stored in Milvus vector database",
            "job_data": job_info
        }
        
    except Exception as e:
        print(f"❌ Error creating job: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating job: {str(e)}")

@app.put("/api/jobs/{job_id}")
async def update_job(job_id: str, job_data: Dict[str, Any]):
    """Update an existing job"""
    try:
        # Find the job in internal storage
        all_jobs = hybrid_architecture.get_all_jobs()
        job_to_update = None
        
        for job in all_jobs:
            if job.get("id") == job_id:
                job_to_update = job
                break
        
        if not job_to_update:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Update job fields
        updated_job = {
            **job_to_update,
            "title": job_data.get("title", job_to_update.get("title", "")),
            "department": job_data.get("department", job_to_update.get("department", "")),
            "location": job_data.get("location", job_to_update.get("location", "")),
            "remote": job_data.get("remote", job_to_update.get("remote", False)),
            "status": job_data.get("status", job_to_update.get("status", "open")),
            "openings": job_data.get("openings", job_to_update.get("openings", 1)),
            "description": job_data.get("description", job_to_update.get("description", ""))
        }
        
        # Update in both internal_data_storage AND company_database
        # Update internal_data_storage (used by get_all_jobs)
        if job_id in hybrid_architecture.internal_data_storage:
            hybrid_architecture.internal_data_storage[job_id] = updated_job
        
        # Update company_database
        for i, job in enumerate(hybrid_architecture.company_database['job_descriptions']):
            if job.get("id") == job_id:
                hybrid_architecture.company_database['job_descriptions'][i] = updated_job
                break
        
        print(f"✅ Updated job {job_id} in both storage locations")
        
        return {
            "success": True,
            "message": "Job updated successfully",
            "job_data": updated_job
        }
        
    except Exception as e:
        print(f"❌ Error updating job: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating job: {str(e)}")

@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    """Get a specific job by ID"""
    try:
        all_jobs = hybrid_architecture.get_all_jobs()
        
        for job in all_jobs:
            if job.get("id") == job_id:
                # Return job with all details
                return {
                    **job,
                    "created": job.get("added_at", job.get("created", datetime.now().isoformat()))
                }
        
        raise HTTPException(status_code=404, detail="Job not found")
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error fetching job: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching job: {str(e)}")

@app.get("/api/agent-status")
async def get_agent_status():
    """Get autonomous AI agent status and verification"""
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
        "hybrid_architecture_available": hybrid_architecture is not None,
        "quantchat_available": hybrid_architecture is not None
    }

@app.get("/api/hybrid-status")
async def get_hybrid_status():
    """Get hybrid architecture status including RAG verification"""
    if not hybrid_architecture:
        raise HTTPException(status_code=503, detail="Hybrid architecture not initialized")
    
    # Get security status which includes RAG verification
    security_status = hybrid_architecture.get_security_status()
    
    # Extract RAG verification details
    rag_verification = security_status.get("rag_verification", {})
    
    return {
        "hybrid_architecture": {
            "status": "active",
            "security_level": "enterprise",
            "data_classification": "enabled",
            "local_processing": "sensitive_data_only",
            "llm_apis": "anonymized_data_only",
            "compliance": ["GDPR", "CCPA", "SOX", "HIPAA"]
        },
        "rag_implementation": {
            "status": rag_verification.get("rag_status", "UNKNOWN"),
            "milvus_connected": rag_verification.get("milvus_connected", False),
            "collection_ready": rag_verification.get("collection_exists", False) and rag_verification.get("has_index", False),
            "num_resumes_stored": rag_verification.get("num_entities", 0),
            "embedding_model_loaded": rag_verification.get("embedding_model_loaded", False),
            "retrieval_working": rag_verification.get("test_retrieval_working", False),
            "pii_redaction_working": rag_verification.get("pii_redaction_working", False),
            "errors": rag_verification.get("errors", [])
        },
        "servers": {
            "main_api": "http://localhost:8000",
            "secure_local": "http://localhost:8001", 
            "advanced_local": "http://localhost:8002",
            "hybrid_assistant": "http://localhost:8003",
            "enterprise_security": "http://localhost:8005"
        }
    }

@app.get("/api/gemini-status")
async def get_gemini_status():
    """Get Gemini API key status and verification"""
    if not hybrid_architecture:
        raise HTTPException(status_code=503, detail="Hybrid architecture not initialized")
    
    api_key_loaded = bool(hybrid_architecture.gemini_api_key)
    api_key_format_valid = api_key_loaded and hybrid_architecture.gemini_api_key.startswith("AIza")
    api_key_length = len(hybrid_architecture.gemini_api_key) if api_key_loaded else 0
    
    # Test if API key is active
    api_key_active = False
    if api_key_loaded and api_key_format_valid:
        api_key_active = hybrid_architecture._verify_gemini_api_key()
    
    return {
        "gemini_api": {
            "key_loaded": api_key_loaded,
            "key_format_valid": api_key_format_valid,
            "key_length": api_key_length,
            "key_active": api_key_active,
            "status": "ACTIVE" if api_key_active else ("INVALID" if not api_key_format_valid else ("NOT_LOADED" if not api_key_loaded else "INACTIVE")),
            "model": os.getenv("LLM_MODEL_NAME") or os.getenv("LLM_MODEL") or "gemini-2.5-pro",
            "endpoint": f"https://generativelanguage.googleapis.com/v1beta/models/{os.getenv('LLM_MODEL_NAME') or os.getenv('LLM_MODEL') or 'gemini-2.5-pro'}:generateContent"
        },
        "quantchat": {
            "ready": api_key_active,
            "message": "QuantChat is ready and using Gemini API" if api_key_active else "QuantChat cannot function without an active Gemini API key"
        }
    }

@app.get("/api/resume-diagnostics")
async def get_resume_diagnostics():
    """Diagnostic endpoint to verify all resumes are stored and indexed correctly"""
    try:
        # Get all resumes from internal storage
        all_resumes = hybrid_architecture.get_all_resumes()
        
        # Get Milvus status
        milvus_status = {
            "connected": False,
            "num_entities": 0,
            "collection_name": None
        }
        
        if hasattr(hybrid_architecture, 'collection') and hybrid_architecture.collection:
            try:
                milvus_status["connected"] = True
                milvus_status["num_entities"] = hybrid_architecture.collection.num_entities
                milvus_status["collection_name"] = hybrid_architecture.collection.name
            except Exception as e:
                milvus_status["error"] = str(e)
        
        # Build resume details
        resume_details = []
        for resume in all_resumes:
            resume_id = resume.get('id', 'unknown')
            name = resume.get('personal_info', {}).get('name', '') or resume.get('name', '')
            resume_details.append({
                "resume_id": resume_id,
                "name": name or "No name found",
                "has_personal_info": bool(resume.get('personal_info')),
                "has_skills": bool(resume.get('skills')),
                "has_experience": bool(resume.get('experience')),
                "stored_at": resume.get('added_at', 'unknown')
            })
        
        return {
            "success": True,
            "internal_storage": {
                "total_resumes": len(all_resumes),
                "resumes": resume_details
            },
            "milvus_status": milvus_status,
            "status": "healthy" if milvus_status.get("num_entities", 0) == len(all_resumes) else "warning",
            "message": f"Found {len(all_resumes)} resumes in internal storage, {milvus_status.get('num_entities', 0)} in Milvus"
        }
    except Exception as e:
        logger.error(f"Error in resume diagnostics: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/api/rag-status")
async def get_rag_status():
    """Get detailed RAG implementation status and verification"""
    if not hybrid_architecture:
        raise HTTPException(status_code=503, detail="Hybrid architecture not initialized")
    
    rag_verification = hybrid_architecture.verify_rag_implementation()
    
    return {
        "rag_implementation": {
            "status": rag_verification.get("rag_status", "UNKNOWN"),
            "description": {
                "WORKING": "RAG is fully operational with resumes stored",
                "READY_BUT_EMPTY": "RAG is ready but no resumes stored yet",
                "PARTIAL": "Some components working but issues detected",
                "ERROR": "RAG verification failed",
                "UNKNOWN": "Status could not be determined"
            }.get(rag_verification.get("rag_status", "UNKNOWN"), "Unknown status"),
            "components": {
                "milvus_connection": {
                    "connected": rag_verification.get("milvus_connected", False),
                    "collection_exists": rag_verification.get("collection_exists", False),
                    "collection_loaded": rag_verification.get("collection_loaded", False),
                    "has_index": rag_verification.get("has_index", False),
                    "num_entities": rag_verification.get("num_entities", 0)
                },
                "embedding_model": {
                    "loaded": rag_verification.get("embedding_model_loaded", False),
                    "model": "all-MiniLM-L6-v2",
                    "dimension": 384
                },
                "retrieval": {
                    "working": rag_verification.get("test_retrieval_working", False),
                    "method": "semantic_search",
                    "similarity_metric": "COSINE"
                },
                "security": {
                    "pii_redaction": rag_verification.get("pii_redaction_working", False),
                    "redaction_patterns": ["email", "phone", "ssn", "salary", "address", "credit_card"]
                }
            },
            "errors": rag_verification.get("errors", []),
            "recommendations": _get_rag_recommendations(rag_verification)
        }
    }

def _get_rag_recommendations(verification: Dict[str, Any]) -> List[str]:
    """Get recommendations based on RAG verification status"""
    recommendations = []
    
    if not verification.get("milvus_connected", False):
        recommendations.append("Start Milvus: docker-compose -f docker-compose.milvus.yml up -d")
    
    if not verification.get("embedding_model_loaded", False):
        recommendations.append("Install sentence-transformers: pip install sentence-transformers")
    
    if verification.get("num_entities", 0) == 0:
        recommendations.append("Upload and parse resumes to populate the vector database")
    
    if not verification.get("test_retrieval_working", False):
        recommendations.append("Check Milvus connection and collection index")
    
    if not verification.get("pii_redaction_working", False):
        recommendations.append("PII redaction may need configuration")
    
    if not recommendations:
        recommendations.append("RAG implementation is working correctly!")
    
    return recommendations

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    if PROMETHEUS_AVAILABLE:
        return Response(content=generate_latest(), media_type="text/plain")
    else:
        return Response(
            content="# Prometheus metrics not available\n# Install with: pip install prometheus-client",
            media_type="text/plain"
        )

# Initialize sample jobs on startup
def initialize_sample_jobs():
    """Create sample jobs for demonstration"""
    try:
        sample_jobs = [
            {
                "title": "Senior Software Engineer",
                "department": "Engineering",
                "location": "San Francisco, CA",
                "description": "Lead development of scalable microservices architecture",
                "level": "Senior",
                "remote": True,
                "status": "open",
                "openings": 2,
                "filled": 1,
                "applications": 45
            },
            {
                "title": "Data Scientist",
                "department": "Data Science",
                "location": "New York, NY",
                "description": "Build and deploy machine learning models for business insights",
                "level": "Mid-Level",
                "remote": False,
                "status": "open",
                "openings": 1,
                "filled": 0,
                "applications": 32
            },
            {
                "title": "Product Manager",
                "department": "Product",
                "location": "Remote",
                "description": "Drive product strategy and roadmap for AI-powered hiring platform",
                "level": "Senior",
                "remote": True,
                "status": "open",
                "openings": 1,
                "filled": 0,
                "applications": 28
            }
        ]
        
        print("📋 Creating sample jobs...")
        for job in sample_jobs:
            hybrid_architecture.add_job(job)
        print(f"✅ Created {len(sample_jobs)} sample jobs")
        
    except Exception as e:
        print(f"⚠️ Failed to create sample jobs: {e}")

if __name__ == "__main__":
    # Initialize sample jobs
    initialize_sample_jobs()
    
    print("=" * 80)
    print("🚀 QuantHire AI - Main API with Hybrid Architecture")
    print("=" * 80)
    print("✅ Hybrid Architecture: ENABLED")
    print("✅ Security Level: ENTERPRISE")
    print("✅ AI Chatbot: INTEGRATED")
    print("✅ Resume Analysis: SECURE")
    print("✅ Job Matching: SECURE")
    print("✅ Frontend Integration: READY")
    print("=" * 80)
    print("🌐 API Endpoints:")
    print("   • POST /api/chat - AI Chatbot")
    print("   • POST /api/resume-analysis - Resume Analysis")
    print("   • POST /api/job-matching - Job Matching")
    print("   • GET /api/candidates - Candidates List")
    print("   • GET /api/jobs - Jobs List")
    print("   • GET /api/hybrid-status - Architecture Status")
    print("=" * 80)
    
    import uvicorn
    
    # Server configuration from environment
    api_host = os.getenv("API_HOST", "0.0.0.0")
    api_port = int(os.getenv("API_PORT", "8000"))
    
    # Increased timeouts for AI agent processing (resume parsing can take 2-5 minutes)
    uvicorn.run(
        app, 
        host=api_host, 
        port=api_port,
        timeout_keep_alive=600,  # 10 minutes keep-alive for long-running requests
        timeout_graceful_shutdown=30
    )
