"""
Constants for QuantHire AI Agents
==================================

All application constants in one place for maintainability.
"""

from enum import Enum
from typing import Final


class ParsingMethod(str, Enum):
    """Resume parsing methods."""
    
    TRUE_AI_AGENT_LANGCHAIN = "TRUE_AI_AGENT_LANGCHAIN"
    BASIC_REGEX_FALLBACK = "BASIC_REGEX_FALLBACK"
    AUTONOMOUS_AGENT_OFFLINE = "AUTONOMOUS_AGENT_OFFLINE"


class SecurityStatus(str, Enum):
    """Security status indicators."""
    
    HYBRID_SECURE = "HYBRID_SECURE"
    SECURE = "SECURE"
    INSECURE = "INSECURE"
    ERROR = "ERROR"


class AgentStatus(str, Enum):
    """Agent status indicators."""
    
    INITIALIZED = "INITIALIZED"
    NOT_INITIALIZED = "NOT_INITIALIZED"
    ERROR = "ERROR"


# Tool Names
class ToolName(str, Enum):
    """Agent tool names."""
    
    EXTRACT_PERSONAL_INFO = "extract_personal_info"
    EXTRACT_SKILLS = "extract_skills"
    EXTRACT_EXPERIENCE = "extract_experience"
    EXTRACT_EDUCATION = "extract_education"
    ENHANCE_WITH_RAG_AI = "enhance_with_rag_ai"


# Regex Patterns
class RegexPattern:
    """Compiled regex patterns for extraction."""
    
    EMAIL: Final[str] = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    PHONE: Final[str] = r'(\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})'
    LOCATION: Final[str] = r'([A-Za-z\s]+),\s*([A-Z]{2})'
    LINKEDIN: Final[str] = r'linkedin\.com/in/[\w-]+'
    GITHUB: Final[str] = r'github\.com/[\w-]+'
    YEARS_EXPERIENCE: Final[str] = r'(\d+)\+?\s*years?\s*(?:of\s*)?experience'
    GPA: Final[str] = r'GPA[:\s]+(\d+\.?\d*)'
    CERTIFICATION: Final[str] = r'\b([A-Z]{2,} Certified|AWS .+|Azure .+|Google Cloud .+)\b'


# Technical Skills Keywords
TECHNICAL_SKILLS: Final[list[str]] = [
    "Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "Go", "Rust",
    "React", "Angular", "Vue", "Node.js", "Next.js",
    "Django", "Flask", "FastAPI", "Spring", "Express", "NestJS",
    "SQL", "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch",
    "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform",
    "Machine Learning", "Deep Learning", "TensorFlow", "PyTorch", "Scikit-learn",
    "Git", "GitHub", "GitLab", "CI/CD", "Jenkins", "GitHub Actions"
]

SOFT_SKILLS_KEYWORDS: Final[list[str]] = [
    "Leadership", "Communication", "Teamwork", "Problem Solving",
    "Project Management", "Agile", "Scrum", "Mentoring", "Collaboration"
]

TOOLS_KEYWORDS: Final[list[str]] = [
    "Docker", "Kubernetes", "Jenkins", "Terraform", "Ansible",
    "Prometheus", "Grafana", "ELK", "Splunk"
]

# Default Values
DEFAULT_MATCH_PERCENTAGE: Final[int] = 95
DEFAULT_FALLBACK_MATCH_PERCENTAGE: Final[int] = 75
DEFAULT_ACTIVE_APPLICATIONS: Final[int] = 1

# Agent Version
AGENT_VERSION: Final[str] = "LangChain Agents Framework + Gemini 2.0"












