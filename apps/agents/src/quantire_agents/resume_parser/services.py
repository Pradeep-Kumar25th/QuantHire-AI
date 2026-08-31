"""
Services for Resume Parsing Agent
==================================

Enterprise-level services for Milvus, embeddings, and LLM integration.
"""

import json
import os
import warnings
from typing import Dict, List, Any, Optional
from quantire_agents.config.settings import AgentSettings
from quantire_agents.config.logging_config import AgentLogger
from quantire_agents.resume_parser.exceptions import (
    MilvusConnectionError,
    EmbeddingModelError,
    LLMServiceError,
)

# Suppress LangChain deprecation warning for ChatVertexAI
# Note: ChatVertexAI is still the correct class for Vertex AI (as of langchain-google-vertexai 3.2.1)
warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain_google_vertexai")

logger = AgentLogger.get_logger(__name__)


class EmbeddingService:
    """Service for embedding generation."""
    
    def __init__(self, settings: AgentSettings):
        """Initialize embedding service.
        
        Args:
            settings: Agent configuration settings
        """
        self.settings = settings
        self.model = None
        self._load_model()
    
    def _load_model(self) -> None:
        """Load embedding model."""
        try:
            from sentence_transformers import SentenceTransformer
            
            logger.info(f"Loading embedding model: {self.settings.embedding_model_name}")
            self.model = SentenceTransformer(self.settings.embedding_model_name)
            logger.info("Embedding model loaded successfully")
            
        except ImportError:
            logger.warning("sentence-transformers not available")
            self.model = None
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise EmbeddingModelError(
                f"Failed to load embedding model: {str(e)}",
                details={"model_name": self.settings.embedding_model_name, "error": str(e)}
            )
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text.
        
        Args:
            text: Input text
            
        Returns:
            Embedding vector
            
        Raises:
            EmbeddingModelError: If embedding generation fails
        """
        if not self.model:
            raise EmbeddingModelError(
                "Embedding model not loaded",
                details={"model_name": self.settings.embedding_model_name}
            )
        
        try:
            embedding = self.model.encode(text).tolist()
            return embedding
        except Exception as e:
            logger.error(f"Embedding generation error: {e}")
            raise EmbeddingModelError(
                f"Failed to generate embedding: {str(e)}",
                details={"error": str(e)}
            )
    
    def is_available(self) -> bool:
        """Check if embedding service is available.
        
        Returns:
            True if available, False otherwise
        """
        return self.model is not None


class LLMService:
    """Service for LLM operations."""
    
    def __init__(self, settings: AgentSettings):
        """Initialize LLM service.
        
        Args:
            settings: Agent configuration settings
        """
        self.settings = settings
        self.llm = None
        self._initialize_llm()
    
    def _initialize_llm(self) -> None:
        """Initialize LLM with Bedrock-first support."""
        try:
            # Import providers
            try:
                from langchain_aws import ChatBedrock
            except ImportError:
                ChatBedrock = None
            
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
            except ImportError:
                ChatGoogleGenerativeAI = None
            
            try:
                from langchain_groq import ChatGroq
            except ImportError:
                ChatGroq = None
            
            try:
                from langchain_google_vertexai import ChatVertexAI
            except ImportError:
                ChatVertexAI = None
            
            model_name = self.settings.llm_model_name
            provider = (self.settings.llm_provider or "openai").strip().lower()

            # Unified factory (OpenAI, Azure OpenAI, or Vertex) — same as main QuantHire agents
            if provider in ("openai", "vertexai", "google", "azure_openai"):
                try:
                    from agents.llm.chat_factory import (
                        create_chat_llm,
                        ensure_llm_env,
                        is_azure_openai_configured,
                        is_openai_configured,
                    )

                    ensure_llm_env()
                    if provider == "openai" and not is_openai_configured():
                        logger.warning("OPENAI_API_KEY not configured for LLM")
                        return
                    if provider == "azure_openai" and not is_azure_openai_configured():
                        logger.warning("Azure OpenAI not configured for LLM")
                        return
                    self.llm = create_chat_llm(
                        model=model_name,
                        temperature=self.settings.llm_temperature,
                        max_tokens=self.settings.llm_max_output_tokens,
                        provider=provider,
                    )
                    logger.info("LLM initialized via factory: provider=%s model=%s", provider, model_name)
                    return
                except ImportError:
                    logger.warning("agents.llm.chat_factory not on path; trying legacy providers")

            if not self.settings.is_api_key_configured:
                logger.warning("API key not configured for LLM")
                return
            
            # OpenRouter provider (new priority)
            if provider == "openrouter":
                try:
                    from langchain_openai import ChatOpenAI
                    api_key = os.getenv("OPENROUTER_API_KEY")
                    if api_key:
                        self.llm = ChatOpenAI(
                            model=model_name,
                            openai_api_key=api_key,
                            openai_api_base="https://openrouter.ai/api/v1",
                            temperature=self.settings.llm_temperature,
                            max_tokens=self.settings.llm_max_output_tokens,
                            model_kwargs={
                                "extra_headers": {
                                    "HTTP-Referer": "https://quanthire.ai",
                                    "X-Title": "QuantHire AI",
                                }
                            }
                        )
                        logger.info(f"LLM initialized with OpenRouter: {model_name}")
                        return
                except ImportError:
                    logger.warning("langchain-openai not installed for OpenRouter")
            
            # Bedrock provider (primary)
            if provider == "bedrock":
                if not ChatBedrock:
                    logger.warning("langchain-aws not installed, falling back to Gemini")
                else:
                    import os
                    import boto3
                    from botocore.config import Config
                    
                    api_key = os.getenv("AWS_BEARER_TOKEN_BEDROCK") or os.getenv("BEDROCK_API_KEY")
                    region = os.getenv("AWS_REGION", "us-east-1")
                    
                    if not api_key:
                        logger.warning("AWS_BEARER_TOKEN_BEDROCK or BEDROCK_API_KEY not set")
                    else:
                        # Create bedrock-runtime client with bearer signature
                        session = boto3.Session()
                        config = Config(signature_version='bearer', region_name=region)
                        
                        bedrock_runtime = session.client(
                            service_name='bedrock-runtime',
                            region_name=region,
                            config=config
                        )
                        
                        # Inject bearer token (Required for Bedrock API keys)
                        bedrock_runtime._request_signer._credentials = type('Credentials', (), {'token': api_key})()
                        
                        self.llm = ChatBedrock(
                            model_id=model_name,
                            client=bedrock_runtime,
                            model_kwargs={
                                "temperature": self.settings.llm_temperature,
                                "max_tokens": self.settings.llm_max_output_tokens,
                            }
                        )
                        logger.info(f"LLM initialized with Bedrock-runtime: {model_name}")
                        return
            
            # Groq provider
            if provider == "groq" or "llama" in model_name.lower() or model_name.startswith("groq/"):
                if ChatGroq:
                    api_key = self.settings.groq_api_key
                    if api_key:
                        self.llm = ChatGroq(
                            model_name=model_name.replace("groq/", ""),
                            api_key=api_key,
                            temperature=self.settings.llm_temperature,
                            max_tokens=self.settings.llm_max_output_tokens
                        )
                        logger.info(f"LLM initialized with Groq: {model_name}")
                        return
            
            # Fallback for LLM types not matched above
            logger.info("Proceeding to final check...")
            
            logger.warning("No LLM provider could be initialized")
            
        except ImportError as e:
            logger.warning(f"LLM import error: {e}")
            self.llm = None
        except AttributeError as e:
            error_msg = str(e)
            if "MediaResolution" in error_msg or "GenerationConfig" in error_msg:
                logger.info(
                    f"LLM version compatibility issue (non-critical): {error_msg}. "
                    "Using fallback parsing mode."
                )
                self.llm = None
            else:
                logger.error(f"Failed to initialize LLM: {e}")
                raise LLMServiceError(
                    f"Failed to initialize LLM: {str(e)}",
                    details={"model_name": self.settings.llm_model_name, "error": str(e)}
                )
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            raise LLMServiceError(
                f"Failed to initialize LLM: {str(e)}",
                details={"model_name": self.settings.llm_model_name, "error": str(e)}
            )
    
    def invoke(self, messages: List[Any]) -> str:
        """Invoke LLM with messages.
        
        Args:
            messages: List of message objects
            
        Returns:
            LLM response content
            
        Raises:
            LLMServiceError: If LLM invocation fails
        """
        if not self.llm:
            raise LLMServiceError(
                "LLM not initialized",
                details={"model_name": self.settings.llm_model_name}
            )
        
        try:
            response = self.llm.invoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"LLM invocation error: {e}")
            raise LLMServiceError(
                f"LLM invocation failed: {str(e)}",
                details={"error": str(e)}
            )
    
    def is_available(self) -> bool:
        """Check if LLM service is available.
        
        Returns:
            True if available, False otherwise
        """
        return self.llm is not None and self.settings.is_api_key_configured


