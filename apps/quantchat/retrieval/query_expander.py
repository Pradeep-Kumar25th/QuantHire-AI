"""
Query Expander
==============

Expands queries with synonyms, related terms, and multiple perspectives.
"""

from typing import List
from ..config.logging_config import setup_logger
from ..generation.llm_generator import LLMGenerator
from ..config.settings import ENABLE_QUERY_EXPANSION, MAX_QUERY_VARIATIONS, ENABLE_MULTI_QUERY
from ..utils.tracing import traceable, trace_metadata

logger = setup_logger("query_expander")

class QueryExpander:
    """
    Expands queries for better retrieval coverage.
    
    Strategies:
    1. Synonym expansion
    2. Abbreviation expansion
    3. Multi-query generation (LLM-based)
    """
    
    def __init__(self):
        try:
            self.llm_generator = LLMGenerator() if ENABLE_MULTI_QUERY else None
        except Exception as e:
            logger.warning(f"LLM generator not available for query expansion: {e}")
            self.llm_generator = None
        
        # Common synonyms for tech stack
        self.tech_synonyms = {
            "python": ["python programming", "python development", "python dev"],
            "java": ["java programming", "java development", "java dev"],
            "javascript": ["js", "javascript programming", "js development"],
            "machine learning": ["ml", "machine learning", "ml engineering"],
            "artificial intelligence": ["ai", "artificial intelligence", "ai development"],
            "rest": ["rest api", "restful api", "restful"],
            "sql": ["sql database", "sql queries", "structured query language"],
        }
    
    @traceable(run_type="chain", name="QueryExpander.expand")
    def expand(self, query: str) -> List[str]:
        """
        Expand query into multiple variations.
        
        Args:
            query: Original query
        
        Returns:
            List of expanded query variations
        """
        if not ENABLE_QUERY_EXPANSION:
            return [query]
        
        variations = [query]  # Always include original
        
        # 1. Synonym expansion
        synonym_variations = self._expand_synonyms(query)
        variations.extend(synonym_variations)
        
        # 2. Multi-query generation (LLM-based)
        if ENABLE_MULTI_QUERY and self.llm_generator:
            multi_queries = self._generate_multi_queries(query)
            variations.extend(multi_queries)
        
        # Limit to max variations
        variations = variations[:MAX_QUERY_VARIATIONS + 1]  # +1 for original
        
        logger.info(f"Expanded query into {len(variations)} variations")
        trace_metadata({
            "variation_count": len(variations),
            "multi_query_enabled": ENABLE_MULTI_QUERY and self.llm_generator is not None,
        })
        return variations
    
    def _expand_synonyms(self, query: str) -> List[str]:
        """Expand query with synonyms."""
        variations = []
        query_lower = query.lower()
        
        for term, synonyms in self.tech_synonyms.items():
            if term in query_lower:
                for synonym in synonyms:
                    if synonym != term:
                        expanded = query.replace(term, synonym)
                        if expanded != query:
                            variations.append(expanded)
        
        return variations[:3]  # Limit synonym expansions
    
    def _generate_multi_queries(self, query: str) -> List[str]:
        """Generate multiple query perspectives using LLM."""
        try:
            prompt = f"""Generate 2-3 alternative phrasings of this search query that would help find relevant information:

Original Query: {query}

Generate alternative phrasings that:
1. Use different wording but same meaning
2. Focus on different aspects of the query
3. Use synonyms or related terms

Return as a JSON array of strings:
["query variation 1", "query variation 2", "query variation 3"]

JSON:"""
            
            response = self.llm_generator.generate(
                system_prompt="You are a query expansion assistant. Return only valid JSON array.",
                user_prompt=prompt,
                temperature=0.3
            )
            
            # Parse JSON array
            import json
            import re
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                variations = json.loads(json_match.group())
                return variations[:MAX_QUERY_VARIATIONS]
        except Exception as e:
            logger.warning(f"Multi-query generation failed: {e}")
        
        return []
