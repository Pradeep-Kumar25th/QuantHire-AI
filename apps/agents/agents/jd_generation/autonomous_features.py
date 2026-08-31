"""
Autonomous Features for Pure Agentic AI
=======================================
Enhances agents with true autonomy: self-reflection, adaptive planning, error recovery.
"""

import logging
from typing import Any, Dict, List

from langchain_core.language_models.chat_models import BaseChatModel

# LangSmith is optional
try:
    from langsmith import traceable
except ImportError:
    # Create a no-op decorator if langsmith is not available
    def traceable(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

logger = logging.getLogger(__name__)


class AutonomousReasoning:
    """Enables autonomous reasoning with self-reflection."""
    
    def __init__(self, llm: BaseChatModel):
        self.llm = llm
    
    @traceable(name="autonomous_reasoning")
    def reason(self, context: Dict[str, Any], goal: str) -> Dict[str, Any]:
        """
        Autonomous reasoning process: Observe → Think → Plan → Act → Reflect.
        
        This is the core of pure agentic AI - the agent autonomously:
        1. Observes the current situation
        2. Thinks about what needs to be done
        3. Plans the approach
        4. Acts on the plan
        5. Reflects on the outcome
        """
        reasoning_prompt = f"""
        You are an autonomous AI agent. Your goal: {goal}
        
        Current Context:
        {context}
        
        AUTONOMOUS REASONING PROCESS:
        
        1. OBSERVE: Analyze the current situation
           - What information do I have?
           - What is the current state?
           - What are the constraints?
        
        2. THINK: Reason about what needs to be done
           - What is my objective?
           - What are the requirements?
           - What challenges might I face?
        
        3. PLAN: Create an action plan
           - What steps should I take?
           - In what order?
           - What tools/resources do I need?
        
        4. ACT: Execute the plan
           - Take the planned actions
           - Use tools as needed
           - Generate outputs
        
        5. REFLECT: Evaluate the outcome
           - Did I achieve my goal?
           - What worked well?
           - What could be improved?
           - Should I adjust my approach?
        
        Provide your complete reasoning process, including:
        - Observation analysis
        - Thinking process
        - Action plan
        - Reflection on approach
        
        Be specific and detailed in your reasoning.
        """
        
        try:
            response = self.llm.invoke(reasoning_prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Handle list content (common in some newer LangChain/VertexAI versions)
            if isinstance(content, list):
                reasoning_text = " ".join([
                    str(item.get("text", item) if isinstance(item, dict) else item) 
                    for item in content
                ])
            else:
                reasoning_text = str(content)
            
            return {
                "reasoning": reasoning_text,
                "observation": self._extract_section(reasoning_text, "OBSERVE"),
                "thinking": self._extract_section(reasoning_text, "THINK"),
                "plan": self._extract_section(reasoning_text, "PLAN"),
                "action": self._extract_section(reasoning_text, "ACT"),
                "reflection": self._extract_section(reasoning_text, "REFLECT"),
            }
        except Exception as e:
            logger.error(f"Autonomous reasoning failed: {e}")
            return {
                "reasoning": f"Reasoning error: {str(e)}",
                "observation": "",
                "thinking": "",
                "plan": "",
                "action": "",
                "reflection": "",
            }
    
    def _extract_section(self, text: str, section: str) -> str:
        """Extract a section from reasoning text."""
        lines = text.split('\n')
        in_section = False
        section_lines = []
        
        for line in lines:
            if section in line.upper():
                in_section = True
                continue
            if in_section:
                if any(s in line.upper() for s in ["OBSERVE", "THINK", "PLAN", "ACT", "REFLECT"]):
                    break
                section_lines.append(line)
        
        return '\n'.join(section_lines).strip()


class SelfReflection:
    """Enables agents to reflect on their actions and improve."""
    
    def __init__(self, llm: BaseChatModel):
        self.llm = llm
    
    @traceable(name="self_reflection")
    def reflect(self, action: str, result: Any, goal: str) -> Dict[str, Any]:
        """
        Self-reflection: Agent evaluates its own performance.
        
        The agent autonomously:
        - Analyzes what it did
        - Evaluates the outcome
        - Identifies what worked
        - Identifies what didn't work
        - Decides how to improve
        """
        reflection_prompt = f"""
        You are an autonomous AI agent reflecting on your actions.
        
        Goal: {goal}
        Action Taken: {action}
        Result: {result}
        
        REFLECT on your performance:
        
        1. What did I do?
        2. Did I achieve my goal?
        3. What worked well?
        4. What didn't work?
        5. What should I do differently next time?
        6. How can I improve?
        
        Provide honest, detailed reflection.
        """
        
        try:
            response = self.llm.invoke(reflection_prompt)
            reflection_text = response.content if hasattr(response, 'content') else str(response)
            
            return {
                "reflection": reflection_text,
                "goal_achieved": "yes" in reflection_text.lower() or "achieved" in reflection_text.lower(),
                "improvements": self._extract_improvements(reflection_text),
            }
        except Exception as e:
            logger.error(f"Self-reflection failed: {e}")
            return {
                "reflection": f"Reflection error: {str(e)}",
                "goal_achieved": False,
                "improvements": [],
            }
    
    def _extract_improvements(self, text: str) -> List[str]:
        """Extract improvement suggestions from reflection."""
        improvements = []
        lines = text.split('\n')
        
        for line in lines:
            if any(word in line.lower() for word in ["improve", "better", "should", "could"]):
                improvements.append(line.strip())
        
        return improvements[:5]  # Top 5 improvements


class AdaptivePlanning:
    """Enables agents to adapt their plans based on feedback and context."""
    
    def __init__(self, llm: BaseChatModel):
        self.llm = llm
    
    @traceable(name="adaptive_planning")
    def adapt_plan(self, original_plan: str, feedback: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adaptive planning: Agent adjusts its plan based on feedback.
        
        The agent autonomously:
        - Analyzes feedback
        - Evaluates current plan
        - Identifies needed changes
        - Creates adapted plan
        """
        adaptation_prompt = f"""
        You are an autonomous AI agent adapting your plan.
        
        Original Plan:
        {original_plan}
        
        Feedback:
        {feedback}
        
        Current Context:
        {context}
        
        ADAPT your plan:
        
        1. Analyze the feedback - what does it tell me?
        2. Evaluate current plan - what needs to change?
        3. Identify adaptations - what should I do differently?
        4. Create adapted plan - new approach
        
        Provide:
        - Analysis of feedback
        - Changes needed
        - Adapted plan
        """
        
        try:
            response = self.llm.invoke(adaptation_prompt)
            adaptation_text = response.content if hasattr(response, 'content') else str(response)
            
            return {
                "adapted_plan": adaptation_text,
                "changes": self._extract_changes(adaptation_text),
                "reasoning": adaptation_text,
            }
        except Exception as e:
            logger.error(f"Adaptive planning failed: {e}")
            return {
                "adapted_plan": original_plan,
                "changes": [],
                "reasoning": f"Adaptation error: {str(e)}",
            }
    
    def _extract_changes(self, text: str) -> List[str]:
        """Extract changes from adaptation text."""
        changes = []
        lines = text.split('\n')
        
        for line in lines:
            if any(word in line.lower() for word in ["change", "adapt", "modify", "adjust"]):
                changes.append(line.strip())
        
        return changes[:5]  # Top 5 changes


class ErrorRecovery:
    """Enables agents to autonomously recover from errors."""
    
    def __init__(self, llm: BaseChatModel):
        self.llm = llm
    
    @traceable(name="error_recovery")
    def recover(self, error: Exception, context: Dict[str, Any], max_retries: int = 3) -> Dict[str, Any]:
        """
        Error recovery: Agent autonomously recovers from failures.
        
        The agent autonomously:
        - Analyzes the error
        - Understands what went wrong
        - Plans recovery strategy
        - Attempts recovery
        - Learns from the error
        """
        recovery_prompt = f"""
        You are an autonomous AI agent recovering from an error.
        
        Error: {str(error)}
        Error Type: {type(error).__name__}
        
        Context:
        {context}
        
        RECOVER from this error:
        
        1. Analyze the error - what went wrong?
        2. Understand the cause - why did it happen?
        3. Plan recovery - how can I fix this?
        4. Attempt recovery - try the fix
        5. Learn - what should I remember for next time?
        
        Provide:
        - Error analysis
        - Recovery strategy
        - Recovery attempt
        - Learning points
        """
        
        try:
            response = self.llm.invoke(recovery_prompt)
            recovery_text = response.content if hasattr(response, 'content') else str(response)
            
            return {
                "recovery_strategy": recovery_text,
                "error_analysis": self._extract_analysis(recovery_text),
                "recovery_plan": self._extract_plan(recovery_text),
                "learning": self._extract_learning(recovery_text),
                "should_retry": "retry" in recovery_text.lower() or "fix" in recovery_text.lower(),
            }
        except Exception as e:
            logger.error(f"Error recovery failed: {e}")
            return {
                "recovery_strategy": f"Recovery error: {str(e)}",
                "error_analysis": str(error),
                "recovery_plan": "Manual intervention needed",
                "learning": [],
                "should_retry": False,
            }
    
    def _extract_analysis(self, text: str) -> str:
        """Extract error analysis."""
        if "analyze" in text.lower():
            return text.split("analyze")[1].split("understand")[0] if "understand" in text.lower() else text[:500]
        return text[:500]
    
    def _extract_plan(self, text: str) -> str:
        """Extract recovery plan."""
        if "plan" in text.lower() or "strategy" in text.lower():
            return text.split("plan")[1] if "plan" in text.lower() else text.split("strategy")[1] if "strategy" in text.lower() else text[:500]
        return text[:500]
    
    def _extract_learning(self, text: str) -> List[str]:
        """Extract learning points."""
        learning = []
        lines = text.split('\n')
        
        for line in lines:
            if any(word in line.lower() for word in ["learn", "remember", "should", "avoid"]):
                learning.append(line.strip())
        
        return learning[:5]  # Top 5 learning points

