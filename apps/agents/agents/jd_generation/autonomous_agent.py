""" Agentic AI - Autonomous Agent Framework
============================================
True autonomous agents that observe, perceive, think, plan, and act.
"""

import logging
import os
import warnings
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from langchain_core.language_models.chat_models import BaseChatModel

# Suppress LangChain deprecation warning for ChatVertexAI
warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain_google_vertexai")

try:
    from langchain_google_vertexai import ChatVertexAI
    VERTEX_AI_AVAILABLE = True
except ImportError:
    VERTEX_AI_AVAILABLE = False
    ChatVertexAI = None

# Groq support is optional
try:
    from langchain_groq import ChatGroq
except ImportError:
    ChatGroq = None

# LangSmith is optional
try:
    from langsmith import traceable
except ImportError:
    # Create a no-op decorator if langsmith is not available
    def traceable(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

from agents.jd_generation.config import JDGenerationConfig, get_config
from agents.jd_generation.autonomous_features import (
    AutonomousReasoning,
    SelfReflection,
    AdaptivePlanning,
    ErrorRecovery,
)

logger = logging.getLogger(__name__)


class Environment:
    """Represents the agent's environment for observation and perception."""
    
    def __init__(self, context: Dict[str, Any]):
        """
        Initialize environment with context.
        
        Args:
            context: Environment context (state, data, constraints, etc.)
        """
        self.context = context
        self.state = context.get("state", {})
        self.data = context.get("data", {})
        self.constraints = context.get("constraints", {})
        self.available_tools = context.get("tools", [])
        self.other_agents = context.get("agents", [])
    
    def get_state(self) -> Dict[str, Any]:
        """Get current environment state."""
        return self.state
    
    def get_data(self) -> Dict[str, Any]:
        """Get environment data."""
        return self.data
    
    def get_constraints(self) -> Dict[str, Any]:
        """Get environment constraints."""
        return self.constraints
    
    def get_available_tools(self) -> List[str]:
        """Get list of available tools."""
        return self.available_tools
    
    def get_other_agents(self) -> List[str]:
        """Get list of other agents in environment."""
        return self.other_agents


class AutonomousAgent(ABC):
    """
    Base class for truly autonomous agents.
    
    Implements pure agentic AI principles:
    1. OBSERVE: Perceive and understand the environment
    2. THINK: Reason about observations and goals
    3. PLAN: Create autonomous action plans
    4. ACT: Execute plans independently
    5. REFLECT: Evaluate and improve
    """
    
    def __init__(
        self,
        agent_name: str,
        goal: str,
        config: Optional[JDGenerationConfig] = None,
    ):
        """
        Initialize autonomous agent.
        
        Args:
            agent_name: Name of the agent
            goal: Agent's goal
            config: Configuration (uses global if not provided)
        """
        self.agent_name = agent_name
        self.goal = goal
        self.config: JDGenerationConfig = config or get_config()
        
        # Initialize LLM and autonomous features
        self._setup_llm()
        
        # Agent memory (for learning and context)
        self.memory: List[Dict[str, Any]] = []
        
        logger.info(
            f"Autonomous Agent '{agent_name}' initialized",
            extra={
                "agent": agent_name,
                "goal": goal,
                "autonomous_features": {
                    "reasoning": self.reasoning is not None,
                    "reflection": self.reflection is not None,
                    "planning": self.planning is not None,
                    "error_recovery": self.error_recovery is not None,
                }
            }
        )

    def _setup_llm(self, model_name: Optional[str] = None):
        """Initialize or re-initialize LLM and autonomous components (Gemini-Exclusive)."""
        llm_config = self.config.get_llm_config()
        active_model = model_name or llm_config["model"]
        provider = llm_config.get("provider", "google")  # Default to google
        
        logger.info(f"🔄 Setting up LLM for '{self.agent_name}' with model: {active_model} (Provider: {provider})")
        
        from agents.llm.chat_factory import create_chat_llm

        self.llm = create_chat_llm(
            model=active_model,
            temperature=llm_config["temperature"],
            max_tokens=llm_config["max_tokens"],
            provider=provider,
        )
        logger.info(
            "LLM initialized for '%s': provider=%s model=%s",
            self.agent_name,
            provider,
            active_model,
        )
        
        # Initialize autonomous capabilities with the new LLM
        if self.config.enable_autonomous_reasoning:
            self.reasoning = AutonomousReasoning(self.llm)
        else:
            self.reasoning = None
        
        if self.config.enable_self_reflection:
            self.reflection = SelfReflection(self.llm)
        else:
            self.reflection = None
        
        if self.config.enable_adaptive_planning:
            self.planning = AdaptivePlanning(self.llm)
        else:
            self.planning = None
        
        if self.config.enable_error_recovery:
            self.error_recovery = ErrorRecovery(self.llm)
        else:
            self.error_recovery = None

    def switch_to_fallback_model(self) -> bool:
        """
        Switch to fallback model if current model hits rate limits.
        Returns: True if switched successfully, False if no fallback available.
        """
        fallback_model = self.config.llm_fallback_model
        if not fallback_model:
            logger.warning(f"⚠️ No fallback model configured for '{self.agent_name}'")
            return False
        
        # Get current model name - handle different LLM types
        current_model = None
        if hasattr(self.llm, 'model_name'):
            current_model = self.llm.model_name
        elif hasattr(self.llm, 'model'):
            current_model = self.llm.model
        elif hasattr(self.llm, '_model_name'):
            current_model = self.llm._model_name
            
        if fallback_model == current_model:
            logger.warning(f"⚠️ Already using fallback model: {fallback_model}")
            return False
            
        logger.warning(f"🚨 Rate limit hit or error for '{self.agent_name}'. Switching to fallback: {fallback_model}")
        self._setup_llm(model_name=fallback_model)
        return True
    
    @traceable(name="observe_environment")
    def observe(self, environment: Environment) -> Dict[str, Any]:
        """
        OBSERVE: Perceive and understand the environment.
        
        The agent autonomously:
        - Perceives current state
        - Understands available data
        - Recognizes constraints
        - Identifies available tools
        - Notices other agents
        
        Args:
            environment: Environment to observe
            
        Returns:
            Observation dictionary
        """
        self._log_autonomous_action("OBSERVE", "Perceiving environment")
        
        observation = {
            "state": environment.get_state(),
            "data": environment.get_data(),
            "constraints": environment.get_constraints(),
            "available_tools": environment.get_available_tools(),
            "other_agents": environment.get_other_agents(),
            "timestamp": self._get_timestamp(),
        }
        
        # Enhanced observation with reasoning
        if self.reasoning:
            try:
                observation_analysis = self.reasoning.reason(
                    context=observation,
                    goal=f"Observe environment to understand current situation for: {self.goal}"
                )
                observation["analysis"] = observation_analysis
            except Exception as e:
                logger.warning(f"Observation analysis failed: {e}")
        
        self._log_autonomous_action("OBSERVE", f"Observed: {len(observation.get('state', {}))} state items")
        
        return observation
    
    @traceable(name="think_autonomously")
    def think(self, observation: Dict[str, Any], goal: Optional[str] = None) -> Dict[str, Any]:
        """
        THINK: Reason about observations and determine what to do.
        
        The agent autonomously:
        - Analyzes observations
        - Understands the situation
        - Identifies what needs to be done
        - Considers options
        - Makes decisions
        
        Args:
            observation: Observation from environment
            goal: Specific goal (uses agent goal if not provided)
            
        Returns:
            Thinking process dictionary
        """
        self._log_autonomous_action("THINK", "Reasoning about observations")
        
        goal_to_use = goal or self.goal
        
        if self.reasoning:
            try:
                thinking = self.reasoning.reason(
                    context={
                        "observation": observation,
                        "goal": goal_to_use,
                        "agent_memory": self.memory[-5:] if self.memory else [],  # Recent memory
                    },
                    goal=goal_to_use
                )
                
                self._log_autonomous_action(
                    "THINK",
                    f"Thinking complete. Analysis: {thinking.get('thinking', '')[:100]}..."
                )
                
                return thinking
            except Exception as e:
                logger.error(f"Thinking failed: {e}", exc_info=True)
                return {
                    "thinking": f"Thinking error: {str(e)}",
                    "observation": observation,
                    "goal": goal_to_use,
                }
        else:
            # Basic thinking without reasoning module
            thinking = {
                "thinking": f"Analyzing observation to achieve: {goal_to_use}",
                "observation": observation,
                "goal": goal_to_use,
            }
            return thinking
    
    @traceable(name="plan_autonomously")
    def plan(self, thinking: Dict[str, Any]) -> Dict[str, Any]:
        """
        PLAN: Create autonomous action plan.
        
        The agent autonomously:
        - Determines steps needed
        - Orders actions logically
        - Identifies required tools
        - Considers dependencies
        - Plans for contingencies
        
        Args:
            thinking: Result from think() method
            
        Returns:
            Action plan dictionary
        """
        self._log_autonomous_action("PLAN", "Creating action plan")
        
        if self.planning:
            try:
                # Extract plan from thinking if available
                existing_plan = thinking.get("plan", "")
                
                if existing_plan:
                    # Enhance existing plan
                    enhanced_plan = self.planning.adapt_plan(
                        original_plan=existing_plan,
                        feedback={"thinking": thinking},
                        context={"goal": self.goal}
                    )
                    plan = {
                        "plan": enhanced_plan.get("adapted_plan", existing_plan),
                        "steps": self._extract_plan_steps(enhanced_plan.get("adapted_plan", existing_plan)),
                        "reasoning": enhanced_plan.get("reasoning", ""),
                    }
                else:
                    # Create new plan
                    plan_prompt = f"""
                    Create a detailed action plan to achieve: {self.goal}
                    
                    Based on thinking:
                    {thinking.get('thinking', '')}
                    
                    Create a step-by-step plan with:
                    1. Clear steps
                    2. Order of execution
                    3. Required tools
                    4. Expected outcomes
                    """
                    
                    response = self.llm.invoke(plan_prompt)
                    plan_text = response.content if hasattr(response, 'content') else str(response)
                    
                    plan = {
                        "plan": plan_text,
                        "steps": self._extract_plan_steps(plan_text),
                        "reasoning": plan_text,
                    }
                
                self._log_autonomous_action("PLAN", f"Plan created with {len(plan.get('steps', []))} steps")
                
                return plan
                
            except Exception as e:
                logger.error(f"Planning failed: {e}", exc_info=True)
                return {
                    "plan": f"Planning error: {str(e)}",
                    "steps": [],
                    "reasoning": "",
                }
        else:
            # Basic planning
            plan = {
                "plan": f"Execute actions to achieve: {self.goal}",
                "steps": ["Execute plan"],
                "reasoning": thinking.get("thinking", ""),
            }
            return plan
    
    @traceable(name="act_autonomously")
    @abstractmethod
    def act(self, plan: Dict[str, Any], environment: Environment) -> Dict[str, Any]:
        """
        ACT: Execute plan autonomously.
        
        The agent autonomously:
        - Executes planned actions
        - Uses tools as needed
        - Adapts to results
        - Handles errors
        - Produces outputs
        
        Args:
            plan: Action plan from plan() method
            environment: Environment to act in
            
        Returns:
            Action result dictionary
            
        Note:
            Must be implemented by subclasses
        """
        pass
    
    @traceable(name="reflect_autonomously")
    def reflect(self, action: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        REFLECT: Evaluate actions and improve.
        
        The agent autonomously:
        - Evaluates what was done
        - Assesses outcome
        - Identifies improvements
        - Learns from experience
        - Updates memory
        
        Args:
            action: Action that was taken
            result: Result of the action
            
        Returns:
            Reflection dictionary
        """
        self._log_autonomous_action("REFLECT", "Reflecting on action and outcome")
        
        if self.reflection:
            try:
                reflection_result = self.reflection.reflect(
                    action=action,
                    result=result,
                    goal=self.goal
                )
                
                # Store in memory for learning
                self.memory.append({
                    "action": action,
                    "result": result,
                    "reflection": reflection_result,
                    "timestamp": self._get_timestamp(),
                })
                
                self._log_autonomous_action(
                    "REFLECT",
                    f"Reflection complete. Goal achieved: {reflection_result.get('goal_achieved', False)}"
                )
                
                return reflection_result
                
            except Exception as e:
                logger.error(f"Reflection failed: {e}", exc_info=True)
                return {
                    "reflection": f"Reflection error: {str(e)}",
                    "goal_achieved": False,
                    "improvements": [],
                }
        else:
            return {
                "reflection": "Basic reflection: Action completed",
                "goal_achieved": True,
                "improvements": [],
            }
    
    def execute_autonomous_cycle(
        self,
        environment: Environment,
        goal: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute complete autonomous cycle: Observe → Think → Plan → Act → Reflect.
        
        This is the core of pure agentic AI - the agent autonomously completes
        the full cycle without external intervention.
        
        Args:
            environment: Environment to operate in
            goal: Specific goal (uses agent goal if not provided)
            
        Returns:
            Complete cycle result
        """
        cycle_result = {
            "agent": self.agent_name,
            "goal": goal or self.goal,
            "cycle": [],
            "final_result": None,
        }
        
        try:
            # 1. OBSERVE
            self._log_autonomous_action("CYCLE", "Starting autonomous cycle: OBSERVE")
            observation = self.observe(environment)
            cycle_result["cycle"].append({
                "step": "OBSERVE",
                "result": observation,
            })
            
            # 2. THINK
            self._log_autonomous_action("CYCLE", "Continuing cycle: THINK")
            thinking = self.think(observation, goal)
            cycle_result["cycle"].append({
                "step": "THINK",
                "result": thinking,
            })
            
            # 3. PLAN
            self._log_autonomous_action("CYCLE", "Continuing cycle: PLAN")
            plan = self.plan(thinking)
            cycle_result["cycle"].append({
                "step": "PLAN",
                "result": plan,
            })
            
            # 4. ACT
            self._log_autonomous_action("CYCLE", "Continuing cycle: ACT")
            action_result = self.act(plan, environment)
            cycle_result["cycle"].append({
                "step": "ACT",
                "result": action_result,
            })
            
            # 5. REFLECT
            self._log_autonomous_action("CYCLE", "Completing cycle: REFLECT")
            reflection = self.reflect(
                action=f"Executed plan: {plan.get('plan', '')[:100]}",
                result=action_result
            )
            cycle_result["cycle"].append({
                "step": "REFLECT",
                "result": reflection,
            })
            
            cycle_result["final_result"] = action_result
            cycle_result["success"] = reflection.get("goal_achieved", False)
            
            self._log_autonomous_action("CYCLE", f"Autonomous cycle complete. Success: {cycle_result['success']}")
            
        except Exception as e:
            logger.error(
                f"Autonomous cycle failed: {e}",
                exc_info=True,
                extra={"agent": self.agent_name}
            )
            
            # Attempt error recovery
            if self.error_recovery:
                try:
                    recovery = self.error_recovery.recover(
                        error=e,
                        context={"cycle_result": cycle_result},
                        max_retries=1
                    )
                    cycle_result["error_recovery"] = recovery
                except Exception as recovery_error:
                    logger.error(f"Error recovery failed: {recovery_error}")
            
            cycle_result["success"] = False
            cycle_result["error"] = str(e)
        
        return cycle_result
    
    def _log_autonomous_action(self, phase: str, message: str) -> None:
        """Log autonomous action for visibility."""
        # Note: "message" is a reserved field in LogRecord, so we use "log_message" instead
        logger.info(
            f"🤖 [{self.agent_name}] [{phase}] {message}",
            extra={
                "agent": self.agent_name,
                "phase": phase,
                "log_message": message,  # Changed from "message" to avoid LogRecord conflict
                "autonomous": True,
            }
        )
    
    def _extract_plan_steps(self, plan_text: str) -> List[str]:
        """Extract steps from plan text."""
        steps = []
        lines = plan_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith('-') or line.startswith('*')):
                steps.append(line)
        
        return steps[:20]  # Limit to 20 steps
    
    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.utcnow().isoformat()
    
    def collaborate_with(self, other_agent: "AutonomousAgent", message: str) -> Dict[str, Any]:
        """
        Collaborate with another agent.
        
        Args:
            other_agent: Other agent to collaborate with
            message: Message or request for collaboration
            
        Returns:
            Collaboration result
        """
        self._log_autonomous_action(
            "COLLABORATE",
            f"Collaborating with {other_agent.agent_name}: {message[:100]}"
        )
        
        # Create collaboration environment
        collaboration_env = Environment({
            "state": {"collaboration": True},
            "data": {"message": message, "from_agent": self.agent_name},
            "agents": [other_agent.agent_name],
        })
        
        # Other agent observes and responds
        observation = other_agent.observe(collaboration_env)
        thinking = other_agent.think(observation, goal=f"Respond to collaboration: {message}")
        
        return {
            "from_agent": self.agent_name,
            "to_agent": other_agent.agent_name,
            "message": message,
            "response": thinking,
            "timestamp": self._get_timestamp(),
        }

