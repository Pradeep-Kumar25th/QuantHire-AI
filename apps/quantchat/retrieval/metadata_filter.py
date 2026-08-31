"""
Metadata Filter
===============

Builds Milvus filter expressions for efficient metadata-based filtering.
"""

from typing import Dict, Any, Optional
from ..config.logging_config import setup_logger
from ..utils.tracing import traceable

logger = setup_logger("metadata_filter")

# Section mapping: intent section -> stored section_type
RESUME_SECTION_MAP = {
    "skills": "Skills",
    "experience": "Experience",
    "education": "Education",
    "projects": "Projects",
    "certifications": "Certifications",
    "summary": "Summary",
    "personal": "Personal Info",
    "contact": "Personal Info",
}

JD_SECTION_MAP = {
    "requirements": "Required Qualifications",
    "responsibilities": "Responsibilities",
    "compensation": "Compensation & Benefits",
    "tools": "Tools & Technologies",
    "about": "About Company",
    "position": "Position Summary",
    "benefits": "Compensation & Benefits",
}

class MetadataFilter:
    """
    Builds Milvus filter expressions for metadata filtering.
    """
    
    @traceable(run_type="chain", name="MetadataFilter.build_filters")
    def build_filters(self, intent_result: Any) -> Dict[str, Any]:
        """
        Build filter dictionary from intent result.
        
        Args:
            intent_result: IntentResult from classifier
        
        Returns:
            Dictionary of filters
        """
        filters = {}
        
        # Document type filter
        if intent_result.domain.value == "resume":
            filters["document_type"] = "resume"
        elif intent_result.domain.value == "jd":
            filters["document_type"] = "jd"
        elif intent_result.domain.value == "both":
            # Search both - no document_type filter
            pass
        
        # Entity name filter (prefix matching for multiple entities)
        if intent_result.entity_names:
            filters["entity_names"] = intent_result.entity_names
        
        # Section filter
        if intent_result.section:
            stored_section = self._map_section(intent_result.domain, intent_result.section)
            if stored_section:
                filters["section_type"] = stored_section
        
        logger.debug(f"Built filters: {filters}")
        return filters
    
    def build_milvus_expression(self, filters: Dict[str, Any]) -> str:
        """
        Convert filter dictionary to Milvus boolean expression.
        
        Args:
            filters: Filter dictionary
        
        Returns:
            Milvus expression string
        """
        expr_parts = []
        
        # Document type filter
        if "document_type" in filters:
            expr_parts.append(f'document_type == "{filters["document_type"]}"')
        
        # Section filter
        if "section_type" in filters:
            expr_parts.append(f'section_type == "{filters["section_type"]}"')
        
        # Entity name filter - use exact equality matching
        # NOTE: Milvus Lite/Standalone doesn't support LIKE operations on VARCHAR
        # We use equality matching which is faster and more reliable
        # The vector search will handle semantic matching for variations
        if "entity_names" in filters and filters["entity_names"]:
            entity_conditions = []
            for entity in filters["entity_names"]:
                if entity:
                    # Clean the entity name
                    clean_name = entity.strip()
                    # Try multiple case variations with equality
                    entity_conditions.append(f'entity_name == "{clean_name}"')
                    entity_conditions.append(f'entity_name == "{clean_name.upper()}"')
                    entity_conditions.append(f'entity_name == "{clean_name.lower()}"')
                    entity_conditions.append(f'entity_name == "{clean_name.title()}"')
            
            if entity_conditions:
                # Deduplicate conditions
                entity_conditions = list(dict.fromkeys(entity_conditions))
                
                # OR condition for all entity variations
                if len(entity_conditions) == 1:
                    expr_parts.append(entity_conditions[0])
                else:
                    expr_parts.append(f"({' || '.join(entity_conditions)})")
        
        expression = " && ".join(expr_parts) if expr_parts else ""
        logger.debug(f"Milvus expression: {expression}")
        return expression
    
    def _map_section(self, domain: Any, section: str) -> Optional[str]:
        """Map intent section to stored section_type."""
        section_lower = section.lower() if section else ""
        
        if domain.value == "resume":
            return RESUME_SECTION_MAP.get(section_lower)
        elif domain.value == "jd":
            return JD_SECTION_MAP.get(section_lower)
        
        return None
    
    def build_relaxed_filters(self, filters: Dict[str, Any], 
                             drop_section: bool = False, 
                             drop_entity: bool = False) -> Dict[str, Any]:
        """
        Build relaxed filters for fallback retrieval.
        
        Args:
            filters: Original filters
            drop_section: Whether to drop section filter
            drop_entity: Whether to drop entity filter
        
        Returns:
            Relaxed filter dictionary
        """
        relaxed = dict(filters)
        
        if drop_section:
            relaxed.pop("section_type", None)
        
        if drop_entity:
            relaxed.pop("entity_names", None)
        
        return relaxed
