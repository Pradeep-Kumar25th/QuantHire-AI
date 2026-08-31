"""LLM provider enum."""

from enum import Enum


class LLMProvider(str, Enum):
    """LLM provider options."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    GROQ = "groq"
    BEDROCK = "bedrock"
    OPENROUTER = "openrouter"
    VERTEXAI = "vertexai"
    AZURE_OPENAI = "azure_openai"
    LOCAL = "local"  # For future local model support

