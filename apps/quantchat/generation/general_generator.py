"""
General Knowledge Generator
===========================

Handles general knowledge questions (not RAG-based).
"""

from typing import Dict, Any
from ..config.logging_config import setup_logger
from .llm_generator import LLMGenerator
from ..utils.tracing import traceable

logger = setup_logger("general_generator")

class GeneralAnswerGenerator:
    """
    Generates answers for general knowledge questions.
    """
    
    def __init__(self):
        try:
            self.llm_generator = LLMGenerator()
        except Exception as e:
            logger.error(f"Failed to initialize LLM generator: {e}")
            raise
    
    @traceable(run_type="chain", name="GeneralGenerator.generate")
    def generate(self, query: str) -> Dict[str, Any]:
        """
        Generate answer for general knowledge question.
        
        Args:
            query: User query
        
        Returns:
            Generated answer
        """
        logger.info(f"Generating general knowledge answer")
        
        prompt = f"""You are QuantChat AI, a helpful assistant.

USER QUERY: {query}

Answer the question helpfully and accurately. If it's a greeting, respond warmly.

Answer:"""
        
        try:
            response = self.llm_generator.generate(
                system_prompt="You are a helpful AI assistant. Answer questions accurately and helpfully.",
                user_prompt=prompt,
                temperature=0.7
            )
            
            return {
                "response": response,
                "source": "general_knowledge",
                "confidence": 0.8
            }
        
        except Exception as e:
            logger.error(f"General generation failed: {e}")
            return {
                "response": "I apologize, but I'm having trouble processing your request right now.",
                "source": "general_fallback",
                "confidence": 0.3
            }
