"""
Enterprise-Grade LLM Router
Cost-efficient model routing based on query complexity
"""

from typing import Dict, Any, Optional
import os


class LLMRouter:
    """
    Production-grade model router for cost efficiency.
    Routes queries to appropriate models based on complexity.
    """
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        
        # Model configuration
        self.flash_model = os.getenv("FLASH_MODEL", "gemini-2.0-flash-exp")
        self.reasoning_model = os.getenv("REASONING_MODEL", "gemini-2.5-pro")
        
        # Cost thresholds (complexity scores)
        self.flash_threshold = 0.4  # Use flash for complexity < 0.4
        self.reasoning_threshold = 0.7  # Use reasoning for complexity > 0.7
    
    def route(
        self,
        query: str,
        complexity_score: float,
        intent: str = "general",
        has_context: bool = True
    ) -> Dict[str, Any]:
        """
        Route query to appropriate model based on:
        - Query complexity
        - Intent
        - Context presence
        
        Returns:
            Dict with model name and routing metadata
        """
        # Determine model based on complexity
        if complexity_score < self.flash_threshold:
            model = "flash"
            model_name = self.flash_model
            routing_reason = f"Low complexity ({complexity_score:.2f})"
        elif complexity_score > self.reasoning_threshold or intent in ["compare", "analyze"]:
            model = "reasoning"
            model_name = self.reasoning_model
            routing_reason = f"High complexity ({complexity_score:.2f}) or complex intent ({intent})"
        else:
            # Medium complexity - use flash but with more tokens
            model = "flash"
            model_name = self.flash_model
            routing_reason = f"Medium complexity ({complexity_score:.2f})"
        
        # Override for specific intents that need reasoning
        if intent in ["explain", "analyze", "compare"]:
            model = "reasoning"
            model_name = self.reasoning_model
            routing_reason = f"Complex intent requires reasoning: {intent}"
        
        return {
            "model": model,
            "model_name": model_name,
            "routing_reason": routing_reason,
            "complexity_score": complexity_score,
            "estimated_cost_tier": "low" if model == "flash" else "high"
        }
    
    def generate(
        self,
        prompt: str,
        routing_info: Dict[str, Any],
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate response using routed model.
        
        Args:
            prompt: Input prompt
            routing_info: Routing information from route()
            max_tokens: Maximum output tokens
            
        Returns:
            Dict with response text and metadata
        """
        if not self.llm_client:
            return {"success": False, "error": "No LLM client available"}
        
        model_name = routing_info.get("model_name")
        
        try:
            # Generate with appropriate model
            if hasattr(self.llm_client, 'generate'):
                response = self.llm_client.generate(
                    prompt,
                    model=model_name,
                    max_tokens=max_tokens
                )
            elif hasattr(self.llm_client, '_get_llm_response_with_fallback'):
                # Use existing client interface
                result = self.llm_client._get_llm_response_with_fallback(
                    prompt,
                    preferred_model=model_name
                )
                if result.get("success"):
                    response = result.get("text", "")
                else:
                    return {"success": False, "error": result.get("error")}
            else:
                return {"success": False, "error": "LLM client interface not supported"}
            
            return {
                "success": True,
                "text": response,
                "model": model_name,
                "routing_info": routing_info
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "model": model_name
            }
