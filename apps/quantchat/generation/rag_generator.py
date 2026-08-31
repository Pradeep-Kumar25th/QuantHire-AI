"""
RAG Answer Generator
====================

Generates answers using RAG with strict grounding to prevent hallucinations.
"""

from typing import Dict, Any
from ..config.logging_config import setup_logger
from .llm_generator import LLMGenerator
from ..utils.tracing import traceable, trace_metadata

logger = setup_logger("rag_generator")

class RAGAnswerGenerator:
    """
    Generates answers from retrieved context with strict grounding.
    """
    
    def __init__(self):
        try:
            self.llm_generator = LLMGenerator()
        except Exception as e:
            logger.error(f"Failed to initialize LLM generator: {e}")
            raise
    
    @traceable(run_type="chain", name="RAGAnswerGenerator.generate")
    def generate(
        self,
        query: str,
        context: str,
        intent: str,
        entity_names: list = None,
        section: str = None
    ) -> Dict[str, Any]:
        """
        Generate answer from context.
        
        Args:
            query: User query
            context: Retrieved context
            intent: Query intent
            entity_names: Extracted entity names
            section: Requested section (if any)
        
        Returns:
            Generated answer with metadata
        """
        logger.info(f"Generating RAG answer for intent: {intent}")
        
        # Calculate context-based confidence score
        confidence = self._calculate_confidence(query, context, entity_names)
        
        # Determine if this is a full document request (needs higher output tokens)
        is_full_document = intent == "FULL_DOCUMENT"
        
        # Build prompt based on intent
        if is_full_document:
            prompt = self._build_full_doc_prompt(query, context, entity_names)
        elif intent == "SECTION_QUERY":
            prompt = self._build_section_prompt(query, context, entity_names, section)
        else:
            prompt = self._build_rag_prompt(query, context, entity_names)
        
        # Generate response with appropriate token limit
        try:
            response_text = self.llm_generator.generate(
                system_prompt="You are QuantChat AI, an enterprise assistant for QuantHire. Answer questions accurately using only the provided context.",
                user_prompt=prompt,
                temperature=0.2,
                full_document_mode=is_full_document  # Use higher token limit for full docs
            )
            
            # Validate response against context (hallucination detection)
            validation_result = self._validate_response(response_text, context, entity_names)
            if not validation_result["valid"]:
                logger.warning(f"Response validation issue: {validation_result['reason']}")
                confidence = min(confidence, validation_result["adjusted_confidence"])
            
            # Detect potential hallucination signals in response
            hallucination_signals = ["i don't have", "not in the database", "cannot determine", 
                                     "no information", "not mentioned", "unable to find"]
            if any(signal in response_text.lower() for signal in hallucination_signals):
                confidence = min(confidence, 0.5)
            
            trace_metadata({
                "intent": intent,
                "confidence": confidence,
                "context_length": len(context),
                "response_length": len(response_text),
                "validation_valid": validation_result["valid"],
                "is_full_document": is_full_document,
            })
            
            return {
                "response": response_text,
                "source": "rag",
                "confidence": confidence,
                "validation": validation_result
            }
        
        except Exception as e:
            logger.error(f"RAG generation failed: {e}")
            # Fallback: Return context summary
            return {
                "response": self._fallback_response(context),
                "source": "rag_fallback",
                "confidence": 0.3
            }
    
    def _validate_response(self, response: str, context: str, entity_names: list = None) -> Dict[str, Any]:
        """
        Validate response against context to detect potential hallucinations.
        
        Checks:
        1. Entity names mentioned in response exist in context
        2. Numbers/statistics in response exist in context
        3. Response doesn't claim information not present
        
        Returns:
            Dictionary with validation results
        """
        import re
        
        issues = []
        adjusted_confidence = 0.9
        
        # Check 1: Entity names in response should be in context
        if entity_names:
            response_lower = response.lower()
            context_lower = context.lower()
            
            for entity in entity_names:
                # If response mentions entity but context doesn't have it
                if entity.lower() in response_lower and entity.lower() not in context_lower:
                    issues.append(f"Entity '{entity}' mentioned but not in context")
                    adjusted_confidence -= 0.2
        
        # Check 2: Numbers in response should appear in context
        response_numbers = set(re.findall(r'\b\d+(?:\.\d+)?\s*(?:years?|%|months?|k|million|billion)?\b', response.lower()))
        context_numbers = set(re.findall(r'\b\d+(?:\.\d+)?\s*(?:years?|%|months?|k|million|billion)?\b', context.lower()))
        
        for num in response_numbers:
            # Skip common numbers like years
            if num in ['1', '2', '3', '4', '5', '10', '20']:
                continue
            if num not in context_numbers and len(num) > 1:
                issues.append(f"Number '{num}' not found in context")
                adjusted_confidence -= 0.1
        
        # Check 3: Detect fabricated details patterns
        fabrication_patterns = [
            r'\b(?:according to|based on)\s+(?!the context|the database|the document)',
            r'specifically\s+\d+',  # "specifically 5 years" without context support
        ]
        for pattern in fabrication_patterns:
            if re.search(pattern, response.lower()):
                issues.append(f"Potential fabrication pattern detected")
                adjusted_confidence -= 0.15
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "adjusted_confidence": max(0.3, adjusted_confidence),
            "reason": "; ".join(issues) if issues else "No issues"
        }
    
    def _calculate_confidence(self, query: str, context: str, entity_names: list = None) -> float:
        """Calculate confidence based on context coverage and relevance."""
        confidence = 0.5  # Base confidence
        
        # Factor 1: Context length (more context = higher confidence)
        context_len = len(context)
        if context_len > 5000:
            confidence += 0.2
        elif context_len > 2000:
            confidence += 0.15
        elif context_len > 500:
            confidence += 0.1
        else:
            confidence -= 0.1  # Very little context
        
        # Factor 2: Entity presence in context
        if entity_names:
            entities_found = sum(1 for name in entity_names if name.lower() in context.lower())
            if entities_found == len(entity_names):
                confidence += 0.15  # All entities found
            elif entities_found > 0:
                confidence += 0.1   # Some entities found
            else:
                confidence -= 0.1  # No entities found in context
        
        # Factor 3: Query keywords in context
        query_words = [w.lower() for w in query.split() if len(w) > 3]
        if query_words:
            words_found = sum(1 for w in query_words if w in context.lower())
            coverage = words_found / len(query_words)
            if coverage > 0.7:
                confidence += 0.1
            elif coverage < 0.3:
                confidence -= 0.1
        
        # Clamp to valid range
        return max(0.1, min(0.95, confidence))
    
    def _build_rag_prompt(self, query: str, context: str, entity_names: list = None) -> str:
        """Build standard RAG prompt."""
        entity_context = ""
        if entity_names:
            entity_context = f"\nNOTE: The query mentions: {', '.join(entity_names)}"
        
        return f"""You are QuantChat AI, an enterprise assistant for QuantHire.

CONTEXT FROM DATABASE:
{context}

USER QUERY: {query}{entity_context}

INSTRUCTIONS:
1. Answer ONLY using information from the CONTEXT above
2. If information is not in CONTEXT, say "I don't have that information in the database"
3. Format your response clearly:
   - Use bullet points for lists
   - Use sections with headers for structured data
   - Use bold text for important information
4. Add source citation ONLY ONCE at the END of your response in this format:
   **Source:** JD - [Job Title] OR **Source:** Resume - [Candidate Name]
   DO NOT add "(Source: ...)" after every line or paragraph.
5. Be concise but comprehensive
6. Do NOT hallucinate or make up information
7. If the query asks about specific entities, focus on those entities

Answer:"""
    
    def _build_section_prompt(self, query: str, context: str, entity_names: list = None, section: str = None) -> str:
        """Build section-specific prompt."""
        section_note = f"\nNOTE: Focus specifically on the {section} section."
        
        return self._build_rag_prompt(query, context, entity_names) + section_note
    
    def _build_full_doc_prompt(self, query: str, context: str, entity_names: list = None) -> str:
        """Build full document prompt with proper Markdown formatting."""
        entity_hint = ""
        if entity_names:
            entity_hint = f"\nThe user is asking about: {', '.join(entity_names)}"
        
        return f"""You are QuantChat AI. Display the COMPLETE document requested by the user.

CONTEXT FROM DATABASE:
{context}

USER QUERY: {query}{entity_hint}

CRITICAL INSTRUCTIONS FOR FULL DOCUMENT DISPLAY:

1. **DISPLAY EVERYTHING** - Show ALL information from the context. Do NOT truncate or summarize.

2. **USE PROPER MARKDOWN FORMATTING:**
   - Use `# Title` for the document title (job title or person's name)
   - Use `## Section Name` for main sections
   - Use `**Bold**` for important labels
   - Use `- ` bullet points for lists
   - Use proper line breaks between sections
   - Use `---` horizontal rules to separate major sections

3. **FOR JOB DESCRIPTIONS, organize in this order:**
   
   # [Job Title]
   **Department:** [Department] | **Location:** [City, Country] ([Work Model])
   
   ---
   
   ## About Company
   [Company description]
   
   ## Position Summary
   [Summary text]
   
   ## Key Responsibilities
   - [Responsibility 1]
   - [Responsibility 2]
   
   ## Required Qualifications
   **Education:** [Required education]
   **Experience:** [Required experience]
   **Technical Skills:**
   - [Skill 1]
   - [Skill 2]
   
   ## Preferred Qualifications
   - [Preferred qualification 1]
   - [Preferred qualification 2]
   
   ## Soft Skills
   - [Soft skill 1]
   - [Soft skill 2]
   
   ## Tools & Technologies
   - [Tool 1]
   - [Tool 2]
   
   ## Work Environment
   **Reports To:** [Manager title]
   **Team Size:** [Number]
   **Collaborates With:** [Team 1], [Team 2]
   
   ## Compensation & Benefits
   - [Benefit 1]
   - [Benefit 2]
   
   ## How to Apply
   **Apply URL:** [URL]
   **Email:** [Email]
   **Required Materials:** Resume, Cover Letter

4. **FOR RESUMES, organize in this order:**
   
   # [Candidate Name]
   **[Current Title/Role]** | [Email] | [Location]
   
   ---
   
   ## Professional Summary
   [Summary text]
   
   ## Experience
   **[Job Title]** at **[Company]** | [Start Date] - [End Date]
   - [Responsibility/Achievement 1]
   - [Responsibility/Achievement 2]
   
   ## Education
   **[Degree]** - [Institution] | [Year]
   
   ## Skills
   **Technical:** [Skill1], [Skill2], [Skill3]
   **Tools:** [Tool1], [Tool2]
   
   ## Certifications
   - [Certification 1]
   - [Certification 2]

5. **PRESERVE ALL DATA** - Include every skill, every item, every detail mentioned in the context.

6. **NO TRUNCATION** - The full document must be displayed completely.

7. **DO NOT show raw JSON or dict format** - Convert all structured data into readable text.

Complete Document:"""
    
    def _fallback_response(self, context: str) -> str:
        """Fallback response when LLM fails."""
        # Return a summary of the context
        lines = context.split('\n')[:20]  # First 20 lines
        summary = "\n".join(lines)
        return f"Based on the available information:\n\n{summary}\n\n(Note: Full response generation unavailable)"
