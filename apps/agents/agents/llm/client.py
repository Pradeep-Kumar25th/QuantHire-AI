"""Provider-agnostic LLM client."""

import os
import warnings
from typing import Any, Dict, List, Optional

# Suppress LangChain deprecation warning for ChatVertexAI
# Note: ChatVertexAI is still the correct class for Vertex AI (as of langchain-google-vertexai 3.2.1)
warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain_google_vertexai")

try:
    from langchain_core.messages import HumanMessage, SystemMessage
except ImportError:
    # Fallback for older LangChain versions
    try:
        from langchain.schema import HumanMessage, SystemMessage
    except ImportError:
        # Last resort - define minimal message classes
        from typing import TypedDict
        class HumanMessage:
            def __init__(self, content: str):
                self.content = content
        class SystemMessage:
            def __init__(self, content: str):
                self.content = content

# Optional provider imports - not all are required
try:
    from langchain_anthropic import ChatAnthropic
except ImportError:
    ChatAnthropic = None
try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None
try:
    from langchain_groq import ChatGroq
except ImportError:
    ChatGroq = None
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:
    ChatGoogleGenerativeAI = None
try:
    from langchain_google_vertexai import ChatVertexAI
except ImportError:
    ChatVertexAI = None
from pydantic import BaseModel

from agents.llm.provider import LLMProvider

try:
    from agents.llm.chat_factory import ensure_llm_env

    ensure_llm_env()
except Exception:
    pass


class LLMResponse(BaseModel):
    """LLM response model."""

    content: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str
    provider: str
    cost_usd: Optional[float] = None


class LLMClient:
    """Provider-agnostic LLM client."""

    # Cost per 1K tokens (approximate, update with actual pricing)
    COST_MAP = {
        # OpenAI models
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        # Anthropic models (direct API)
        "claude-sonnet-4-20250514": {"input": 0.003, "output": 0.015},
        "claude-haiku-3-20240307": {"input": 0.00025, "output": 0.00125},
        # Groq models
        "llama-3.3-70b-versatile": {"input": 0.00059, "output": 0.00079},
        "llama-3.1-8b-instant": {"input": 0.00005, "output": 0.00008},
        # Google Gemini models
        "gemini-1.5-pro": {"input": 0.0035, "output": 0.0105},
        "gemini-1.5-pro-002": {"input": 0.0035, "output": 0.0105},
        "gemini-1.5-flash": {"input": 0.000075, "output": 0.0003},
        "gemini-2.0-flash": {"input": 0.0001, "output": 0.0004},
        "gemini-2.0-flash-lite": {"input": 0.00005, "output": 0.0002},
        "gemini-2.5-pro": {"input": 0.0035, "output": 0.0105},
        "gemini-2.5-flash": {"input": 0.0001, "output": 0.0004},
        "gemini-2.5-flash-lite": {"input": 0.00005, "output": 0.0002},
        # Amazon Bedrock Claude models (Sonnet 4.x)
        "us.anthropic.claude-sonnet-4-5-20250929-v1:0": {"input": 0.003, "output": 0.015},
        "anthropic.claude-sonnet-4-5-20250929-v1:0": {"input": 0.003, "output": 0.015},
        "us.anthropic.claude-sonnet-4-20250514-v1:0": {"input": 0.003, "output": 0.015},
        "anthropic.claude-sonnet-4-20250514-v1:0": {"input": 0.003, "output": 0.015},
        # Amazon Bedrock Claude models (3.5)
        "us.anthropic.claude-3-5-sonnet-20241022-v2:0": {"input": 0.003, "output": 0.015},
        "anthropic.claude-3-5-sonnet-20241022-v2:0": {"input": 0.003, "output": 0.015},
        "anthropic.claude-3-sonnet-20240229-v1:0": {"input": 0.003, "output": 0.015},
        "anthropic.claude-3-haiku-20240307-v1:0": {"input": 0.00025, "output": 0.00125},
        # Amazon Bedrock Titan models
        "amazon.titan-text-express-v1": {"input": 0.0002, "output": 0.0006},
        "amazon.titan-text-lite-v1": {"input": 0.00015, "output": 0.0002},
        # Amazon Bedrock Llama models
        "meta.llama3-1-70b-instruct-v1:0": {"input": 0.00099, "output": 0.00099},
        "meta.llama3-1-8b-instruct-v1:0": {"input": 0.00022, "output": 0.00022},
        # OpenRouter models
        "anthropic/claude-3.5-sonnet": {"input": 0.003, "output": 0.015},
        "google/gemini-2.0-flash-001": {"input": 0.0001, "output": 0.0004},
    }

    def __init__(
        self,
        provider: str = os.getenv("LLM_PROVIDER", "google"),
        model: str = os.getenv("LLM_MODEL", os.getenv("LLM_MODEL_NAME", "gemini-2.5-pro")),
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        """Initialize LLM client.
        
        Args:
            provider: LLM provider name (bedrock, google, groq, openai, anthropic)
            model: Model name
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
        """
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._llm = self._initialize_llm()

    def _initialize_llm(self) -> Any:
        """Initialize the underlying LLM client with multi-provider support.
        
        Returns:
            Initialized LLM client
        """
        actual_provider = os.getenv("LLM_PROVIDER", self.provider)
        if actual_provider in (LLMProvider.AZURE_OPENAI, "azure_openai"):
            if not ChatOpenAI:
                raise ImportError(
                    "langchain_openai not installed. Run: pip install langchain-openai"
                )
            from agents.llm.chat_factory import (
                azure_openai_chat_deployment,
                create_chat_llm,
            )

            self.provider = "azure_openai"
            # Azure exposes deployments, not raw model names. Legacy agent configs
            # may still carry Groq/Gemini model names; always resolve to the
            # configured Azure deployment so requests don't 404.
            deployment = azure_openai_chat_deployment()
            if deployment and deployment != self.model:
                print(
                    f"LLMClient: Overriding model '{self.model}' with Azure deployment '{deployment}'"
                )
                self.model = deployment
            print(f"LLMClient: Using Azure OpenAI (Deployment: {self.model})")
            return create_chat_llm(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                provider="azure_openai",
            )

        if actual_provider == LLMProvider.OPENAI or actual_provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set")
            if not ChatOpenAI:
                raise ImportError("langchain_openai not installed. Run: pip install langchain-openai")
            print(f"LLMClient: Using OpenAI (Model: {self.model})")
            return ChatOpenAI(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                api_key=api_key,
            )

        if actual_provider == "vertexai" or actual_provider == LLMProvider.VERTEXAI:
            # Override provider to use Vertex AI
            self.provider = "vertexai"
            project = os.getenv("GCP_PROJECT_ID")
            location = os.getenv("GCP_LOCATION", "us-central1")
            
            if not project:
                raise ValueError("GCP_PROJECT_ID environment variable not set for Vertex AI")
            if not ChatVertexAI:
                raise ImportError("langchain_google_vertexai not installed. Run: pip install langchain-google-vertexai")
            
            print(f"🔒 LLMClient: Using Vertex AI (Project: {project}, Model: {self.model})")
            # Suppress deprecation warning at instantiation
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=DeprecationWarning)
                return ChatVertexAI(
                    model=self.model,
                    project=project,
                    location=location,
                    temperature=self.temperature,
                    max_output_tokens=self.max_tokens,
                )
        
        # Google Gemini provider - DEPRECATED, redirect to Vertex AI
        if self.provider == LLMProvider.GOOGLE or self.provider == "google":
            # Force redirect to Vertex AI
            print(f"⚠️ LLMClient: 'google' provider deprecated, using Vertex AI instead")
            project = os.getenv("GCP_PROJECT_ID")
            location = os.getenv("GCP_LOCATION", "us-central1")
            
            if not project:
                raise ValueError("GCP_PROJECT_ID environment variable not set. Vertex AI is required.")
            if not ChatVertexAI:
                raise ImportError("langchain_google_vertexai not installed. Run: pip install langchain-google-vertexai")
            
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=DeprecationWarning)
                return ChatVertexAI(
                    model=self.model,
                    project=project,
                    location=location,
                    temperature=self.temperature,
                    max_output_tokens=self.max_tokens,
                )
        
        # Vertex AI provider
        elif self.provider == LLMProvider.VERTEXAI or self.provider == "vertexai":
            project = os.getenv("GCP_PROJECT_ID")
            location = os.getenv("GCP_LOCATION", "us-central1")
            
            if not project:
                raise ValueError("GCP_PROJECT_ID environment variable not set for Vertex AI")
            if not ChatVertexAI:
                raise ImportError("langchain_google_vertexai not installed. Run: pip install langchain-google-vertexai")
            
            # Suppress deprecation warning at instantiation
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=DeprecationWarning)
                return ChatVertexAI(
                    model=self.model,
                    project=project,
                    location=location,
                    temperature=self.temperature,
                    max_output_tokens=self.max_tokens,
                )
        
        # Groq provider
        elif self.provider == LLMProvider.GROQ or self.provider == "groq":
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                raise ValueError("GROQ_API_KEY environment variable not set")
            if not ChatGroq:
                raise ImportError("langchain_groq not installed")
            
            return ChatGroq(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                api_key=api_key,
            )
        
        # OpenAI provider
        elif self.provider == LLMProvider.OPENAI or self.provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set")
            if not ChatOpenAI:
                raise ImportError("langchain_openai not installed. Run: pip install langchain-openai")
            
            return ChatOpenAI(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                api_key=api_key,
            )
        
        # Anthropic provider
        elif self.provider == LLMProvider.ANTHROPIC or self.provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable not set")
            if not ChatAnthropic:
                raise ImportError("langchain_anthropic not installed. Run: pip install langchain-anthropic")
            
            return ChatAnthropic(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                api_key=api_key,
            )
        
        # Amazon Bedrock provider
        elif self.provider == LLMProvider.BEDROCK or self.provider == "bedrock":
            api_key = os.getenv("AWS_BEARER_TOKEN_BEDROCK") or os.getenv("BEDROCK_API_KEY")
            region = os.getenv("AWS_REGION", "us-east-1")
            
            if not api_key:
                raise ValueError("AWS_BEARER_TOKEN_BEDROCK or BEDROCK_API_KEY environment variable not set")
            if not ChatBedrock:
                raise ImportError("langchain-aws not installed. Run: pip install langchain-aws")
            
            # Create boto3 session and client with bearer token
            import boto3
            from botocore.config import Config
            
            session = boto3.Session()
            # The config must specify signature_version='bearer' for Bedrock API keys
            config = Config(signature_version='bearer', region_name=region)
            
            bedrock_runtime = session.client(
                service_name='bedrock-runtime',
                region_name=region,
                config=config
            )
            
            # Inject the bearer token into the client's credentials
            # This is the required way to pass the Bedrock API key to boto3
            bedrock_runtime._request_signer._credentials = type('Credentials', (), {'token': api_key})()
            
            return ChatBedrock(
                model_id=self.model,
                client=bedrock_runtime,
                model_kwargs={
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                }
            )
        
        # OpenRouter provider
        elif self.provider == LLMProvider.OPENROUTER or self.provider == "openrouter":
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                raise ValueError("OPENROUTER_API_KEY environment variable not set")
            if not ChatOpenAI:
                raise ImportError("langchain_openai not installed. Run: pip install langchain-openai")
            
            return ChatOpenAI(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                openai_api_key=api_key,
                openai_api_base="https://openrouter.ai/api/v1",
                model_kwargs={
                    "extra_headers": {
                        "HTTP-Referer": "https://quanthire.ai",
                        "X-Title": "QuantHire AI",
                    }
                }
            )
        
        # Fallback to Vertex AI (primary)
        else:
            print(f"⚠️ Warning: Unsupported provider '{self.provider}'. Falling back to Vertex AI.")
            gcp_project = os.getenv("GCP_PROJECT_ID")
            gcp_location = os.getenv("GCP_LOCATION", "us-central1")
            
            if gcp_project:
                print(f"✅ Using Vertex AI (Project: {gcp_project})")
                if not ChatVertexAI:
                    raise ImportError("langchain_google_vertexai not installed. Run: pip install langchain-google-vertexai")
                return ChatVertexAI(
                    model=os.getenv("LLM_MODEL_NAME")
                    or os.getenv("LLM_MODEL")
                    or "gemini-2.5-pro",
                    project=gcp_project,
                    location=gcp_location,
                    temperature=self.temperature,
                    max_output_tokens=self.max_tokens,
                )
            
            # If Vertex AI is not set, try OpenRouter as fallback
            openrouter_key = os.getenv("OPENROUTER_API_KEY")
            if openrouter_key:
                print("⚠️ Falling back to OpenRouter backup.")
                return ChatOpenAI(
                    model="google/gemini-2.0-flash-exp:free",
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    openai_api_key=openrouter_key,
                    openai_api_base="https://openrouter.ai/api/v1",
                )
            
            # If OpenRouter is not set, try Bedrock
            bedrock_key = os.getenv("AWS_BEARER_TOKEN_BEDROCK") or os.getenv("BEDROCK_API_KEY")
            if bedrock_key:
                print("⚠️ Falling back to Amazon Bedrock backup.")
                from botocore.config import Config
                import boto3
                region = os.getenv("AWS_REGION", "us-east-1")
                session = boto3.Session()
                config = Config(signature_version='bearer', region_name=region)
                bedrock_runtime = session.client(service_name='bedrock-runtime', region_name=region, config=config)
                bedrock_runtime._request_signer._credentials = type('Credentials', (), {'token': bedrock_key})()
                return ChatBedrock(
                    model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                    client=bedrock_runtime,
                    model_kwargs={"temperature": self.temperature, "max_tokens": self.max_tokens}
                )
            raise ValueError(
                "No valid LLM provider configured. For Vertex with ADC: set GCP_PROJECT_ID and "
                "run `gcloud auth application-default login` (or set GCP_ALLOW_SERVICE_ACCOUNT_KEY=true "
                "and GCP_USE_ADC_ONLY=false with a service account JSON)."
            )


    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate cost in USD for the API call.
        
        Args:
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            
        Returns:
            Cost in USD
        """
        if self.model in self.COST_MAP:
            costs = self.COST_MAP[self.model]
            input_cost = (prompt_tokens / 1000) * costs["input"]
            output_cost = (completion_tokens / 1000) * costs["output"]
            return input_cost + output_cost
        return 0.0

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate completion from LLM.
        
        Args:
            system_prompt: System message
            user_prompt: User message
            **kwargs: Additional arguments to pass to LLM
            
        Returns:
            LLMResponse: Generated response with metadata
        """
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        # Invoke LLM
        response = await self._llm.ainvoke(messages, **kwargs)

        # Extract token usage
        usage = response.response_metadata.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)

        # Calculate cost
        cost_usd = self._calculate_cost(prompt_tokens, completion_tokens)

        return LLMResponse(
            content=response.content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            model=self.model,
            provider=self.provider,
            cost_usd=cost_usd,
        )

    @staticmethod
    def _extract_json_object(raw: Any) -> Dict[str, Any]:
        """Parse JSON from model text, including markdown fences / trailing prose."""
        import json
        import re

        if isinstance(raw, dict):
            return raw
        if not isinstance(raw, str):
            raw = str(raw or "")

        text = raw.strip()
        if not text:
            raise ValueError("Empty LLM response; expected JSON object")

        # Prefer fenced ```json ... ``` blocks when present
        fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if fence:
            text = fence.group(1).strip()

        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        # Fall back to outermost { ... } slice
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                parsed = json.loads(text[start : end + 1])
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError as exc:
                raise ValueError(f"Failed to parse LLM response as JSON: {exc}") from exc

        raise ValueError("Failed to parse LLM response as JSON: no JSON object found")

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Dict[str, Any],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Generate structured output matching a JSON schema.
        
        Args:
            system_prompt: System message
            user_prompt: User message
            schema: JSON schema for structured output
            **kwargs: Additional arguments
            
        Returns:
            Parsed structured output
        """
        full_system_prompt = f"""{system_prompt}

You must respond with valid JSON matching this schema:
{schema}

Respond ONLY with the JSON object, no additional text."""

        # Prefer native JSON mode on Azure/OpenAI when available; fall back to
        # plain generation + robust fence stripping if the model rejects it.
        try:
            from agents.llm.chat_factory import create_chat_llm

            json_llm = create_chat_llm(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                provider=self.provider if self.provider in ("azure_openai", "openai") else None,
                json_mode=True,
            )
            messages = [
                SystemMessage(content=full_system_prompt),
                HumanMessage(content=user_prompt),
            ]
            response = await json_llm.ainvoke(messages, **kwargs)
            content = getattr(response, "content", response)
            return self._extract_json_object(content)
        except Exception:
            response = await self.generate(full_system_prompt, user_prompt, **kwargs)
            return self._extract_json_object(response.content)

