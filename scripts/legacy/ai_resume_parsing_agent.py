"""
AI-Powered Resume Parsing Agent using LangChain Agents and Gemini
================================================================

This module implements a REAL AI AGENT that uses LangChain Agents framework
with tools, memory, and autonomous decision-making for intelligent resume parsing.
"""

import os
import json
import uuid
import re
import warnings
from pathlib import Path
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional
import requests
from pydantic import BaseModel, Field

# Vertex ADC-only default (same as FastAPI main) when running this module standalone.
_agents_parent = Path(__file__).resolve().parent.parent.parent / "apps" / "agents"
if _agents_parent.is_dir() and str(_agents_parent) not in sys.path:
    sys.path.insert(0, str(_agents_parent))
try:
    if os.getenv("LLM_PROVIDER", "vertexai").strip().lower() != "openai":
        from agents.gcp_vertex_credentials import bootstrap_vertex_adc

        bootstrap_vertex_adc(load_env=True, log_status=False)
except Exception:
    pass

# Suppress LangChain deprecation warning for ChatVertexAI
# Note: ChatVertexAI is still the correct class for Vertex AI (as of langchain-google-vertexai 3.2.1)
# Note: ChatVertexAI is the correct class for Vertex AI (not ChatGoogleGenerativeAI / Gemini API key).
warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain_google_vertexai")

# LangChain imports
try:
    from langchain_core.prompts import PromptTemplate
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_core.output_parsers import PydanticOutputParser
    from langchain_core.tools import tool
    from langgraph.prebuilt import create_react_agent
    from langgraph.checkpoint.memory import MemorySaver
    LANGCHAIN_AVAILABLE = True
except ImportError as e:
    LANGCHAIN_AVAILABLE = False

# Vertex AI LLM
try:
    from langchain_google_vertexai import ChatVertexAI
    VERTEX_AI_AVAILABLE = True
except ImportError:
    ChatVertexAI = None
    VERTEX_AI_AVAILABLE = False

# Groq LLM (Fallback - deprecated)
try:
    from langchain_groq import ChatGroq
    GROQ_AVAILABLE = True
except ImportError:
    ChatGroq = None
    GROQ_AVAILABLE = False

# PDF parsing - Multiple libraries for robust extraction
import io
PDF_AVAILABLE = False
PDFPLUMBER_AVAILABLE = False
PYMUPDF_AVAILABLE = False
PDFMINER_AVAILABLE = False

# Try PyPDF2 (basic)
try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PyPDF2 = None

# Try pdfplumber (better for tables and complex layouts)
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    pdfplumber = None

# Try PyMuPDF/fitz (fast and accurate)
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    fitz = None

# Try pdfminer.six (good text extraction)
try:
    from pdfminer.high_level import extract_text as pdfminer_extract_text
    PDFMINER_AVAILABLE = True
except ImportError:
    pdfminer_extract_text = None

<<<M>>>
