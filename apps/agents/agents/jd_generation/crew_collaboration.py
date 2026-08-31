"""
CrewAI Multi-Agent Collaboration
=================================
True autonomous agent collaboration using CrewAI.
"""

import logging
import warnings
from typing import Any, Dict, List, Optional

from crewai import Agent, Crew, Process, Task
from crewai.llm import LLM
from langchain_core.language_models.chat_models import BaseChatModel

# Suppress LangChain deprecation warning for ChatVertexAI
warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain_google_vertexai")

try:
    from langchain_groq import ChatGroq
except ImportError:
    ChatGroq = None

try:
    from langchain_google_vertexai import ChatVertexAI
except ImportError:
    ChatVertexAI = None

# LangSmith is optional
try:
    from langsmith import traceable
except ImportError:
    # Create a no-op decorator if langsmith is not available
    def traceable(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

from agents.jd_generation.autonomous_agent import AutonomousAgent, Environment
from agents.jd_generation.config import JDGenerationConfig, get_config

logger = logging.getLogger(__name__)


class CrewAICollaboration:
    """
    CrewAI-based multi-agent collaboration system.
    
    Enables truly autonomous agents to collaborate:
    - Agents communicate autonomously
    - Agents delegate tasks
    - Agents share context
    - Agents coordinate actions
    """
    
    def __init__(self, config: Optional[JDGenerationConfig] = None):
        """
        Initialize CrewAI collaboration system.
        
        Args:
            config: Configuration (uses global if not provided)
        """
        self.config: JDGenerationConfig = config or get_config()
        
        # Initialize LLM for CrewAI
        llm_config = self.config.get_llm_config()
        self.llm = self._setup_crew_llm(llm_config)
        
        # Also keep LangChain LLM for direct usage
        self.langchain_llm = self._create_langchain_llm(llm_config)
        
        logger.info(
            f"✅ CrewAI Collaboration System initialized (Provider: {llm_config.get('provider', 'google')})",
            extra={
                "llm_model": llm_config["model"],
                "llm_type": type(self.llm).__name__ if self.llm else "None",
                "langchain_llm_type": type(self.langchain_llm).__name__ if self.langchain_llm else "None",
            }
        )
    
    def _setup_crew_llm(self, llm_config: dict) -> Any:
        """Setup LLM for CrewAI — ChatVertexAI + ADC (same as rest of QuantHire)."""
        try:
            from agents.gcp_vertex_credentials import bootstrap_vertex_adc

            bootstrap_vertex_adc(load_env=False, log_status=False)
        except Exception:
            pass
        # Prefer LangChain ChatVertexAI (ADC via GOOGLE_APPLICATION_CREDENTIALS / google.auth).
        # LiteLLM vertex_ai/* is not used by default — it can pick up API keys differently.
        return self._create_langchain_llm(llm_config)

    def _create_langchain_llm(self, llm_config: dict) -> BaseChatModel:
        """Create LangChain LLM from shared factory (OpenAI or Vertex)."""
        from agents.llm.chat_factory import create_chat_llm

        provider = llm_config.get("provider", "vertexai")
        model = llm_config["model"]
        logger.info("CrewAI LLM: provider=%s model=%s", provider, model)
        return create_chat_llm(
            model=model,
            temperature=llm_config["temperature"],
            max_tokens=llm_config["max_tokens"],
            provider=provider,
        )
    
    def create_autonomous_crew(
        self,
        agents: List[AutonomousAgent],
        goal: str,
        context: Dict[str, Any]
    ) -> Crew:
        """
        Create CrewAI crew with autonomous agents.
        
        Args:
            agents: List of autonomous agents
            goal: Common goal for the crew
            context: Shared context
            
        Returns:
            CrewAI Crew instance
        """
        # Convert autonomous agents to CrewAI agents
        crew_agents = []
        for agent in agents:
            crew_agent = Agent(
                role=agent.agent_name,
                goal=agent.goal,
                backstory=f"""You are an autonomous AI agent with the goal: {agent.goal}.
                You can observe, think, plan, and act autonomously. You collaborate with other
                agents to achieve common goals. You make decisions independently and adapt
                your approach based on observations and feedback.""",
                llm=self.llm,
                verbose=self.config.agent_verbose,
                allow_delegation=True,  # Enable delegation for true collaboration
                max_iter=self.config.agent_max_iterations,
            )
            crew_agents.append(crew_agent)
        
        # Create collaborative tasks
        tasks = self._create_collaborative_tasks(agents, goal, context, crew_agents)
        
        # Create crew with collaboration
        # Explicitly set Gemini LLM for manager/coordination
        crew = Crew(
            agents=crew_agents,
            tasks=tasks,
            process=Process.hierarchical,  # Hierarchical for better collaboration
            verbose=self.config.agent_verbose,
            manager_llm=self.llm,  # Gemini LLM for manager/coordination
        )
        
        # Log that Crew is using the configured LLM
        llm_config = self.config.get_llm_config()
        logger.info(
            f"✅ CrewAI Crew initialized with {llm_config.get('provider', 'google')} LLM",
            extra={
                "manager_llm_type": type(self.llm).__name__,
                "agents_count": len(crew_agents),
                "model": llm_config["model"],
            }
        )
        
        logger.info(
            f"CrewAI crew created with {len(agents)} agents",
            extra={
                "agent_count": len(agents),
                "goal": goal,
                "process": "hierarchical",
            }
        )
        
        return crew
    
    def _create_collaborative_tasks(
        self,
        agents: List[AutonomousAgent],
        goal: str,
        context: Dict[str, Any],
        crew_agents: List[Agent],
    ) -> List[Task]:
        """
        Create collaborative tasks for agents.
        
        Args:
            agents: List of agents
            goal: Common goal
            context: Shared context
            
        Returns:
            List of CrewAI tasks
        """
        tasks = []
        
        # Create task for each agent based on their role
        for i, agent in enumerate(agents):
            # Determine task based on agent type
            if "Generator" in agent.agent_name:
                task_description = f"""
                AUTONOMOUS TASK: Generate Job Description
                
                Goal: {goal}
                Context: {context}
                
                AUTONOMOUS INSTRUCTIONS:
                1. OBSERVE: Analyze the context and requirements
                2. THINK: Reason about what needs to be generated
                3. PLAN: Create a plan for JD generation
                4. ACT: Generate the Job Description autonomously
                5. REFLECT: Evaluate the generated JD
                
                You are fully autonomous - make decisions independently.
                Collaborate with other agents if needed.
                """
            elif "Refiner" in agent.agent_name:
                task_description = f"""
                AUTONOMOUS TASK: Refine Job Description
                
                Goal: {goal}
                Context: {context}
                
                AUTONOMOUS INSTRUCTIONS:
                1. OBSERVE: Analyze the initial JD
                2. THINK: Identify improvements needed
                3. PLAN: Create refinement plan
                4. ACT: Refine the JD autonomously
                5. REFLECT: Evaluate improvements
                
                You are fully autonomous - make decisions independently.
                Collaborate with Generator and Validator agents.
                """
            elif "Validator" in agent.agent_name:
                task_description = f"""
                AUTONOMOUS TASK: Validate Job Description
                
                Goal: {goal}
                Context: {context}
                
                AUTONOMOUS INSTRUCTIONS:
                1. OBSERVE: Analyze the JD for validation
                2. THINK: Determine validation criteria
                3. PLAN: Create validation plan
                4. ACT: Validate the JD autonomously
                5. REFLECT: Evaluate validation results
                
                You are fully autonomous - make decisions independently.
                Collaborate with Generator and Refiner agents.
                """
            else:
                task_description = f"""
                AUTONOMOUS TASK: {agent.agent_name}
                
                Goal: {goal}
                Context: {context}
                
                AUTONOMOUS INSTRUCTIONS:
                1. OBSERVE: Analyze the environment
                2. THINK: Reason about what to do
                3. PLAN: Create action plan
                4. ACT: Execute autonomously
                5. REFLECT: Evaluate outcome
                
                You are fully autonomous - make decisions independently.
                Collaborate with other agents as needed.
                """
            
            task = Task(
                description=task_description,
                agent=crew_agents[i],
                expected_output=f"Autonomous execution result from {agent.agent_name}",
            )
            tasks.append(task)
        
        return tasks
    
    @traceable(name="collaborative_execution")
    def execute_collaboratively(
        self,
        agents: List[AutonomousAgent],
        goal: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute collaborative task with autonomous agents.
        
        Args:
            agents: List of autonomous agents
            goal: Common goal
            context: Shared context
            
        Returns:
            Collaboration result
        """
        logger.info(
            "Starting collaborative execution",
            extra={
                "agent_count": len(agents),
                "goal": goal,
            }
        )
        
        # Create environment for agents
        environment = Environment({
            "state": context,
            "data": context,
            "constraints": {},
            "tools": [],
            "agents": [agent.agent_name for agent in agents],
        })
        
        # Each agent executes autonomous cycle
        agent_results = []
        for agent in agents:
            logger.info(
                f"Agent {agent.agent_name} starting autonomous cycle",
                extra={"agent": agent.agent_name}
            )
            
            cycle_result = agent.execute_autonomous_cycle(environment, goal)
            agent_results.append({
                "agent": agent.agent_name,
                "result": cycle_result,
            })
        
        # Create CrewAI crew for collaboration
        crew = self.create_autonomous_crew(agents, goal, context)
        
        # Execute crew collaboration
        try:
            crew_result = crew.kickoff()
            
            collaboration_result = {
                "success": True,
                "goal": goal,
                "agent_results": agent_results,
                "crew_result": str(crew_result),
                "collaboration": True,
            }
            
            logger.info(
                "Collaborative execution completed",
                extra={"success": True, "agent_count": len(agents)}
            )
            
            return collaboration_result
            
        except Exception as e:
            logger.error(
                f"Collaborative execution failed: {e}",
                exc_info=True
            )
            
            return {
                "success": False,
                "goal": goal,
                "agent_results": agent_results,
                "error": str(e),
                "collaboration": True,
            }
