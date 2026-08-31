"""
LLM-Based Intent Classifier
============================

Advanced intent classification using LLM for better accuracy.
Handles complex queries, multi-entity extraction, and comparison queries.
"""

import json
import re
from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from ..config.logging_config import setup_logger
from ..utils.tracing import traceable, trace_metadata

# Import LLM generator with robust error handling
try:
    from ..generation.llm_generator import LLMGenerator, LLM_GENERATOR_AVAILABLE
except ImportError:
    LLMGenerator = None
    LLM_GENERATOR_AVAILABLE = False

logger = setup_logger("intent_classifier")

class Intent(str, Enum):
    """Intent types for QuantChat queries."""
    RAG_QA = "RAG_QA"  # General questions about resumes/JDs
    SECTION_QUERY = "SECTION_QUERY"  # Questions about specific sections
    FULL_DOCUMENT = "FULL_DOCUMENT"  # Request for full document
    GENERAL_KNOWLEDGE = "GENERAL_KNOWLEDGE"  # General knowledge questions
    COMPARISON = "COMPARISON"  # Compare multiple entities

class Domain(str, Enum):
    """Document domain types."""
    RESUME = "resume"
    JD = "jd"
    BOTH = "both"  # Query spans both resumes and JDs
    GENERAL = "general"

@dataclass
class IntentResult:
    """Structured intent classification result."""
    intent: Intent
    domain: Domain
    entity_names: List[str]  # Multiple entities for comparisons
    section: Optional[str] = None
    confidence: float = 1.0
    query_complexity: str = "simple"  # simple, medium, complex
    classification_method: str = "unknown"  # "llm" or "regex_fallback"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent.value,
            "domain": self.domain.value,
            "entity_names": self.entity_names,
            "section": self.section,
            "confidence": self.confidence,
            "query_complexity": self.query_complexity,
            "classification_method": self.classification_method,
        }

class IntentClassifier:
    """
    LLM-based intent classifier with advanced query understanding.
    
    Uses LLM for accurate intent classification, entity extraction, and section detection.
    """
    
    def __init__(self):
        self.llm_generator = LLMGenerator() if (LLM_GENERATOR_AVAILABLE and LLMGenerator) else None
        self._init_section_patterns()
    
    def _init_section_patterns(self):
        """Initialize section keyword patterns."""
        self.resume_sections = {
            "skills": ["skill", "technical skill", "competency", "expertise", "proficient"],
            "experience": ["experience", "work history", "employment", "career", "role", "position"],
            "education": ["education", "degree", "university", "college", "academic", "qualification"],
            "projects": ["project", "portfolio", "work", "built", "developed"],
            "summary": ["summary", "profile", "bio", "about", "overview"],
        }
        
        self.jd_sections = {
            "requirements": ["requirement", "qualification", "prerequisite", "must have", "needed"],
            "responsibilities": ["responsibility", "duty", "task", "role", "expectation"],
            "compensation": ["compensation", "salary", "pay", "benefit", "package"],
            "tools": ["tool", "technology", "tech stack", "framework", "platform"],
            "about": ["about company", "company", "organization", "employer"],
        }
    
    @traceable(run_type="chain", name="IntentClassifier.classify")
    def classify(self, query: str, conversation_context: Optional[str] = None) -> IntentResult:
        """
        Classify query using LLM for accurate intent detection.
        
        Args:
            query: User query
            conversation_context: Previous conversation turns (for pronoun resolution)
        
        Returns:
            IntentResult with classified intent, entities, and metadata
        """
        logger.info(f"Classifying query: {query[:100]}")
        
        # Use LLM for intent classification
        try:
            result = self._llm_classify(query, conversation_context)
            logger.info(f"LLM classification result: {result.to_dict()}")
            trace_metadata({
                "classification_method": "llm",
                "intent": result.intent.value,
                "domain": result.domain.value,
                "entities": result.entity_names,
                "confidence": result.confidence,
            })
            return result
        except Exception as e:
            logger.warning(f"LLM classification failed, using fallback: {e}")
            result = self._fallback_classify(query)
            trace_metadata({"classification_method": "regex_fallback", "error": str(e)})
            return result
    
    def _llm_classify(self, query: str, context: Optional[str] = None) -> IntentResult:
        """Classify using LLM for better accuracy."""
        if not self.llm_generator or not LLM_GENERATOR_AVAILABLE:
            raise ValueError("LLM generator not available")
        
        context_block = ""
        if context:
            context_block = f"CONVERSATION CONTEXT (previous messages):\n{context}"

        prompt = f"""You are an expert query classifier for a resume and job description chatbot.

USER QUERY: {query}
{context_block}

Classify this query and extract information. Return ONLY valid JSON:

{{
    "intent": "RAG_QA" | "SECTION_QUERY" | "FULL_DOCUMENT" | "GENERAL_KNOWLEDGE" | "COMPARISON",
    "domain": "resume" | "jd" | "both" | "general",
    "entity_names": ["Name1", "Name2"],  // Extract all names/job titles mentioned (empty if none)
    "section": "skills" | "experience" | "education" | "projects" | "certifications" | "summary" | "requirements" | "compensation" | null,
    "confidence": 0.0-1.0,
    "query_complexity": "simple" | "medium" | "complex"
}}

CLASSIFICATION RULES:

1. **SECTION_QUERY** - Use when asking about a SPECIFIC SECTION of resume/JD:
   - "skills of X", "what are X's skills" → section: "skills"
   - "experience of X", "work history of X", "roles of X" → section: "experience"
   - "education of X", "degrees of X", "qualifications of X" → section: "education"
   - "projects of X", "AI projects of X" → section: "projects"
   - "certifications of X", "certificates of X" → section: "certifications"
   - "summary of X", "profile of X", "about X" → section: "summary"

2. **FULL_DOCUMENT** - User wants the COMPLETE document:
   - "show full resume", "get complete resume", "display entire JD"
   - "show me X's resume", "full profile of X"
   - "show me the full JD" → FULL_DOCUMENT with domain="jd"

3. **RAG_QA** - General questions about resume/JD content:
   - "who has Python skills?"
   - "tell me about X"
   - Questions without specific section focus

4. **COMPARISON** - Comparing multiple entities:
   - "compare X and Y", "who has more experience"

5. **GENERAL_KNOWLEDGE** - ONLY if no resume/JD/candidate/job context:
   - "what is machine learning?"
   - "hello", "hi", greetings
   - General knowledge questions NOT about stored data

CRITICAL - CONTEXT RESOLUTION:
- If the user query says "show me the full JD" or "show the resume" WITHOUT a name, look at CONVERSATION CONTEXT for the entity name!
- For example: If context shows user previously asked about "Senior Software Engineer" JD, and now asks "show me the full JD", entity_names should be ["Senior Software Engineer"]
- Extract job titles as entity_names for JDs (e.g., "Senior Software Engineer", "Data Analyst")
- Extract person names as entity_names for resumes (e.g., "Karan Kumar", "John Smith")
- If query mentions resume, candidate, JD, job → NOT general knowledge
- "Tell me about X's education" → SECTION_QUERY with section="education"

JSON:"""
        
        response = self.llm_generator.generate(
            system_prompt="You are a query classifier. Return only valid JSON.",
            user_prompt=prompt,
            temperature=0.1
        )
        
        # Parse JSON from response
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            return IntentResult(
                intent=Intent(data.get("intent", "RAG_QA")),
                domain=Domain(data.get("domain", "resume")),
                entity_names=data.get("entity_names", []),
                section=data.get("section"),
                confidence=float(data.get("confidence", 0.9)),
                query_complexity=data.get("query_complexity", "medium"),
                classification_method="llm",
            )
        else:
            raise ValueError("No JSON found in LLM response")
    
    def _fallback_classify(self, query: str) -> IntentResult:
        """Fallback regex-based classification if LLM fails."""
        query_lower = query.lower()
        
        # Check for full document
        full_doc_triggers = ["full resume", "full jd", "complete resume", "complete jd", 
                           "show full", "get full", "fetch full", "entire resume", "entire jd"]
        if any(trigger in query_lower for trigger in full_doc_triggers):
            jd_markers = (" jd", "job description", "job desc", "the jd", "this jd")
            domain = Domain.JD if any(marker in query_lower for marker in jd_markers) else Domain.RESUME
            return IntentResult(Intent.FULL_DOCUMENT, domain, [], confidence=0.8,
                                classification_method="regex_fallback")
        
        # Check for general knowledge
        if self._is_general_knowledge(query_lower):
            return IntentResult(Intent.GENERAL_KNOWLEDGE, Domain.GENERAL, [], confidence=0.8,
                                classification_method="regex_fallback")
        
        # Extract entities
        entities = self._extract_entities_simple(query)
        
        # Check for section
        section = self._extract_section_simple(query_lower)
        
        # Determine domain
        domain = self._extract_domain_simple(query_lower)
        
        # Check for comparison
        if any(word in query_lower for word in ["compare", "difference", "better", "more", "vs", "versus"]):
            return IntentResult(Intent.COMPARISON, domain, entities, section, confidence=0.7,
                                query_complexity="complex", classification_method="regex_fallback")
        
        # Determine intent
        intent = Intent.SECTION_QUERY if section else Intent.RAG_QA
        
        return IntentResult(intent, domain, entities, section, confidence=0.7,
                            classification_method="regex_fallback")
    
    def _is_general_knowledge(self, query: str) -> bool:
        """Check if query is general knowledge."""
        # If mentions resume/JD keywords, NOT general
        domain_keywords = ["resume", "jd", "job description", "candidate", "applicant", "job", "position"]
        if any(kw in query for kw in domain_keywords):
            return False
        
        # General knowledge patterns
        general_patterns = ["what is", "explain", "how to", "define", "tell me about"]
        greetings = ["hi", "hello", "hey", "thanks", "thank you"]
        
        return any(pattern in query for pattern in general_patterns) or query.strip() in greetings
    
    def _extract_entities_simple(self, query: str) -> List[str]:
        """Simple entity extraction using regex."""
        entities = []
        
        # Pattern: "does X have", "X's skills", "about X"
        patterns = [
            r"does\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)+)\s+have",
            r"([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)+)'s",
            r"about\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)+)",
            r"of\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)+)",
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, query)
            entities.extend(matches)
        
        # Remove duplicates and filter
        entities = list(set([e.strip() for e in entities if len(e.strip()) > 2]))
        return entities
    
    def _extract_section_simple(self, query: str) -> Optional[str]:
        """Simple section extraction."""
        query_lower = query.lower()
        
        # Check resume sections
        for section, keywords in self.resume_sections.items():
            if any(kw in query_lower for kw in keywords):
                return section
        
        # Check JD sections
        for section, keywords in self.jd_sections.items():
            if any(kw in query_lower for kw in keywords):
                return section
        
        return None
    
    def _extract_domain_simple(self, query: str) -> Domain:
        """Simple domain extraction."""
        query_lower = query.lower()
        
        resume_keywords = ["resume", "candidate", "applicant", "cv"]
        jd_keywords = ["jd", "job description", "job", "position", "role", "opening"]
        
        has_resume = any(kw in query_lower for kw in resume_keywords)
        has_jd = any(kw in query_lower for kw in jd_keywords)
        
        if has_resume and has_jd:
            return Domain.BOTH
        elif has_jd:
            return Domain.JD
        elif has_resume:
            return Domain.RESUME
        else:
            return Domain.RESUME  # Default to resume
