"""
Query Normalizer
================

Preprocesses and normalizes user queries for better retrieval.
Enhanced with proper text cleaning and pronoun resolution.
"""

import re
from typing import List, Optional
from ..config.logging_config import setup_logger
from ..utils.tracing import traceable

logger = setup_logger("query_normalizer")

# Common typos in resume/job queries
TYPO_CORRECTIONS = {
    "experince": "experience",
    "experiance": "experience",
    "educaton": "education",
    "eduction": "education",
    "skils": "skills",
    "skillz": "skills",
    "resum": "resume",
    "resumee": "resume",
    "certifcate": "certificate",
    "certfication": "certification",
    "qualfication": "qualification",
    "resposibilities": "responsibilities",
    "responsibilites": "responsibilities",
    "requirments": "requirements",
    "requiremets": "requirements",
    "tecnical": "technical",
    "techincal": "technical",
    "progamming": "programming",
    "programing": "programming",
}

# Stopwords to optionally remove for keyword matching
RETRIEVAL_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", 
    "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "can", "shall",
    "about", "what", "who", "which", "when", "where", "how",
    "please", "tell", "show", "get", "give", "find", "list"
}


class QueryNormalizer:
    """
    Normalizes queries for better retrieval.
    
    Features:
    - Whitespace normalization
    - Common typo correction
    - Pronoun resolution with context
    - Query keyword extraction
    """
    
    @traceable(run_type="chain", name="QueryNormalizer.normalize")
    def normalize(self, query: str) -> str:
        """
        Normalize query text.
        
        Args:
            query: Raw user query
        
        Returns:
            Normalized query
        """
        if not query:
            return ""
        
        # 1. Basic cleanup
        normalized = " ".join(query.split())  # Normalize whitespace
        normalized = normalized.strip()
        
        # 2. Fix common typos (case-insensitive)
        for typo, correction in TYPO_CORRECTIONS.items():
            # Case-insensitive replacement preserving first letter case
            pattern = re.compile(re.escape(typo), re.IGNORECASE)
            def replace_match(match):
                matched = match.group(0)
                if matched[0].isupper():
                    return correction.capitalize()
                return correction
            normalized = pattern.sub(replace_match, normalized)
        
        # 3. Normalize quotes and special chars
        normalized = normalized.replace('"', '"').replace('"', '"')
        normalized = normalized.replace(''', "'").replace(''', "'")
        
        # 4. Remove excessive punctuation
        normalized = re.sub(r'[?!]{2,}', '?', normalized)
        normalized = re.sub(r'\.{2,}', '.', normalized)
        
        logger.debug(f"Normalized query: '{query[:50]}' -> '{normalized[:50]}'")
        return normalized
    
    @traceable(run_type="chain", name="QueryNormalizer.enhance_with_context")
    def enhance_with_context(self, query: str, tracked_entities: list) -> str:
        """
        Enhance query with conversation context.
        Properly resolves pronouns to entity names.
        
        Args:
            query: User query
            tracked_entities: Previously mentioned entities
        
        Returns:
            Enhanced query with resolved pronouns
        """
        if not tracked_entities:
            return query
        
        query_lower = query.lower()
        
        # Pronoun patterns to resolve
        pronoun_patterns = {
            # Possessive pronouns
            r'\bhis\b': "{entity}'s",
            r'\bher\b': "{entity}'s",
            r'\btheir\b': "{entity}'s",
            r'\bits\b': "{entity}'s",
            # Subject pronouns (start of sentence or after comma)
            r'(?:^|,\s+)\b(he)\b': "{entity}",
            r'(?:^|,\s+)\b(she)\b': "{entity}",
            r'(?:^|,\s+)\b(they)\b': "{entity}",
            # Object pronouns
            r'\bhim\b': "{entity}",
            r'\bthem\b': "{entity}",
        }
        
        # Check if query has pronouns that need resolution
        has_resolvable_pronoun = any(
            re.search(pattern, query_lower) 
            for pattern in pronoun_patterns.keys()
        )
        
        if not has_resolvable_pronoun:
            return query
        
        # Use most recent entity (append order in ConversationMemory)
        entity = tracked_entities[-1]
        enhanced = query
        
        # Apply pronoun replacements
        for pattern, replacement in pronoun_patterns.items():
            replacement_text = replacement.format(entity=entity)
            enhanced = re.sub(pattern, replacement_text, enhanced, flags=re.IGNORECASE)
        
        # Clean up double possessives like "John's's"
        enhanced = re.sub(r"'s's", "'s", enhanced)
        
        if enhanced != query:
            logger.info(f"Enhanced query with context: '{query}' -> '{enhanced}'")
        
        return enhanced
    
    def extract_keywords(self, query: str, include_stopwords: bool = False) -> List[str]:
        """
        Extract meaningful keywords from query for retrieval.
        
        Args:
            query: User query
            include_stopwords: Whether to include common stopwords
        
        Returns:
            List of keywords
        """
        # Split into words
        words = re.findall(r'\b[a-zA-Z]{2,}\b', query.lower())
        
        if include_stopwords:
            return words
        
        # Filter stopwords
        keywords = [w for w in words if w not in RETRIEVAL_STOPWORDS]
        
        return keywords
    
    def detect_query_type(self, query: str) -> str:
        """
        Detect query type for routing hints.
        
        Returns:
            'listing', 'comparison', 'specific', 'general'
        """
        query_lower = query.lower()
        
        # Listing queries
        if any(kw in query_lower for kw in ["list all", "show all", "how many", "count"]):
            return "listing"
        
        # Comparison queries
        if any(kw in query_lower for kw in ["compare", "difference", "versus", " vs ", "better"]):
            return "comparison"
        
        # Specific entity queries (has proper nouns)
        if re.search(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b', query):
            return "specific"
        
        return "general"
