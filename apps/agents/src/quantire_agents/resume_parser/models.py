"""
Data Models for Resume Parsing Agent
=====================================

Enterprise-level Pydantic models for type safety and validation.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class PersonalInfo(BaseModel):
    """Personal information schema."""
    
    name: str = Field(description="Full name of the candidate")
    email: str = Field(default="", description="Email address")
    phone: str = Field(default="", description="Phone number")
    location: str = Field(default="", description="City, State/Country")
    linkedin: Optional[str] = Field(default="", description="LinkedIn URL")
    github: Optional[str] = Field(default="", description="GitHub URL")
    website: Optional[str] = Field(default="", description="Personal website URL")
    
    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Validate email format."""
        if v and "@" not in v:
            return ""
        return v


class Experience(BaseModel):
    """Work experience schema."""
    
    total_years: int = Field(
        default=0,
        ge=0,
        description="Total years of experience"
    )
    positions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Work positions with details"
    )
    companies: List[str] = Field(
        default_factory=list,
        description="Companies worked at"
    )
    current_role: Optional[str] = Field(
        default="",
        description="Current job title"
    )
    achievements: List[str] = Field(
        default_factory=list,
        description="Key achievements"
    )


class Education(BaseModel):
    """Education schema."""
    
    degrees: List[str] = Field(
        default_factory=list,
        description="Degrees obtained"
    )
    institutions: List[str] = Field(
        default_factory=list,
        description="Educational institutions"
    )
    graduation_years: List[str] = Field(
        default_factory=list,
        description="Graduation years"
    )
    gpa: Optional[str] = Field(
        default="",
        description="GPA if mentioned"
    )
    coursework: List[str] = Field(
        default_factory=list,
        description="Relevant coursework"
    )


class Skills(BaseModel):
    """Skills schema."""
    
    technical_skills: List[str] = Field(
        default_factory=list,
        description="Technical skills and programming languages"
    )
    soft_skills: List[str] = Field(
        default_factory=list,
        description="Soft skills and competencies"
    )
    tools: List[str] = Field(
        default_factory=list,
        description="Tools and frameworks"
    )
    certifications: List[str] = Field(
        default_factory=list,
        description="Professional certifications"
    )
    languages: List[str] = Field(
        default_factory=list,
        description="Programming languages"
    )


class EnhancedData(BaseModel):
    """Enhanced data from RAG and AI."""
    
    summary: str = Field(default="", description="Professional summary")
    strengths: List[str] = Field(
        default_factory=list,
        description="Key strengths"
    )
    career_insights: List[str] = Field(
        default_factory=list,
        description="Career progression insights"
    )
    additional_skills: List[str] = Field(
        default_factory=list,
        description="Suggested additional skills"
    )


class ParsedResumeData(BaseModel):
    """Complete parsed resume data structure."""
    
    # Metadata
    id: str = Field(description="Resume ID")
    raw_text: str = Field(description="Raw resume text")
    content: str = Field(description="Resume content (for Milvus)")
    upload_date: str = Field(description="Upload date in ISO format")
    
    # Parsing metadata
    parsing_method: str = Field(description="Parsing method used")
    match_percentage: int = Field(
        ge=0,
        le=100,
        description="Match percentage confidence"
    )
    active_applications: int = Field(
        default=1,
        ge=0,
        description="Number of active applications"
    )
    security_status: str = Field(description="Security status")
    agent_version: str = Field(description="Agent version")
    tools_used: List[str] = Field(
        default_factory=list,
        description="List of tools used"
    )
    memory_enabled: bool = Field(
        default=False,
        description="Whether memory is enabled"
    )
    rag_enabled: bool = Field(
        default=False,
        description="Whether RAG is enabled"
    )
    
    # Extracted data
    personal_info: PersonalInfo = Field(description="Personal information")
    skills: Skills = Field(description="Skills information")
    experience: Experience = Field(description="Work experience")
    education: Education = Field(description="Education information")
    summary: str = Field(default="", description="Professional summary")
    strengths: List[str] = Field(
        default_factory=list,
        description="Key strengths"
    )
    career_insights: List[str] = Field(
        default_factory=list,
        description="Career insights"
    )


class ResumeParsingResult(BaseModel):
    """Result of resume parsing operation."""
    
    success: bool = Field(description="Whether parsing succeeded")
    data: Optional[ParsedResumeData] = Field(
        default=None,
        description="Parsed resume data"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if failed"
    )
    error_code: Optional[str] = Field(
        default=None,
        description="Error code if failed"
    )
    processing_time_ms: Optional[float] = Field(
        default=None,
        description="Processing time in milliseconds"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )















