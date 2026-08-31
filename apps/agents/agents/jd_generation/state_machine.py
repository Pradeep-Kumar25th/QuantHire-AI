"""
LangGraph State Machine for JD Generation Workflow
==================================================
Orchestrates the complete JD generation process with autonomous state transitions.
"""

# CRITICAL: Add project root to Python path for LangGraph Studio
import sys
from pathlib import Path

# Get the apps directory (D:\QuantHire AI\apps)
apps_dir = Path(__file__).parent.parent.parent
if str(apps_dir) not in sys.path:
    sys.path.insert(0, str(apps_dir))

import logging
import os
import warnings
from typing import Annotated, Literal, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel

# Suppress LangChain deprecation warning for ChatVertexAI
warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain_google_vertexai")

try:
    from langchain_google_vertexai import ChatVertexAI
except ImportError:
    ChatVertexAI = None

try:
    from langchain_groq import ChatGroq
except ImportError:
    ChatGroq = None
from langgraph.graph import END, START, StateGraph

# LangSmith is optional
try:
    from langsmith import traceable
except ImportError:
    # Create a no-op decorator if langsmith is not available
    def traceable(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

from agents.jd_generation.crew_agents import (
    JDGeneratorAgent,
    JDRefinerAgent,
    JDValidatorAgent,
    RAGAgent,
    MilvusStorageAgent,
)
from agents.jd_generation.autonomous_features import (
    AutonomousReasoning,
    SelfReflection,
    AdaptivePlanning,
    ErrorRecovery,
)

logger = logging.getLogger(__name__)


class JDGenerationState(TypedDict, total=False):
    """State for JD generation workflow."""
    
    # Input
    job_title: str
    job_level: str
    department: str
    location: str | None
    remote_allowed: bool
    user_requirements: str | None
    
    # Context
    similar_jobs: list[dict] | None
    market_context: dict | None
    
    # Generated Content
    initial_jd: dict | None
    refined_jd: dict | None
    validated_jd: dict | None
    
    # Customization
    user_edits: dict | None
    final_jd: dict | None
    
    # Storage
    job_id: str | None
    embedding: list[float] | None
    milvus_id: str | None
    
    # Metadata
    current_state: str
    errors: list[str]
    agent_thoughts: list[dict]  # Store agent thinking process
    workflow_complete: bool


class JDGenerationWorkflow:
    """
    LangGraph State Machine for JD Generation.
    
    States:
    1. INITIALIZE - Receive user input
    2. GATHER_CONTEXT - RAG retrieval from Milvus
    3. GENERATE_JD - Generate initial JD
    4. REFINE_JD - Refine based on context
    5. VALIDATE_JD - Validate completeness
    6. CUSTOMIZE_JD - Handle user edits
    7. GENERATE_EMBEDDINGS - Create embeddings using sentence-transformers
    8. STORE_IN_MILVUS - Store in Milvus vector database
    9. COMPLETE - Finish workflow
    """
    
    def __init__(self, config=None):
        """
        Initialize workflow with configuration.
        
        Args:
            config: JDGenerationConfig instance or dict (uses global config if not provided)
        """
        from agents.jd_generation.config import JDGenerationConfig, get_config
        
        # Handle both JDGenerationConfig objects and dicts (for LangGraph Studio)
        if config is None:
            self.config: JDGenerationConfig = get_config()
        elif isinstance(config, dict):
            # LangGraph Studio passes a dict - ignore it and use global config
            logger.info("Received dict config from LangGraph Studio, using global config instead")
            self.config: JDGenerationConfig = get_config()
        else:
            self.config: JDGenerationConfig = config
        
        if not self.config.is_llm_configured:
            raise ValueError(
                f"LLM provider '{self.config.llm_provider}' is not properly configured. "
                "Please check your environment variables (.env file)."
            )
        
        # Initialize LLM with configuration
        llm_config = self.config.get_llm_config()
        self.llm = self._create_llm(llm_config)
        
        # Initialize agents with configuration (dependency injection)
        self.rag_agent = RAGAgent(config=self.config)
        self.generator_agent = JDGeneratorAgent(config=self.config)
        self.refiner_agent = JDRefinerAgent(config=self.config)
        self.validator_agent = JDValidatorAgent(config=self.config)
        self.storage_agent = MilvusStorageAgent(config=self.config)
        
        # Initialize autonomous features (only if enabled)
        if self.config.enable_autonomous_reasoning:
            self.autonomous_reasoning = AutonomousReasoning(self.llm)
        else:
            self.autonomous_reasoning = None
        
        if self.config.enable_self_reflection:
            self.self_reflection = SelfReflection(self.llm)
        else:
            self.self_reflection = None
        
        if self.config.enable_adaptive_planning:
            self.adaptive_planning = AdaptivePlanning(self.llm)
        else:
            self.adaptive_planning = None
        
        if self.config.enable_error_recovery:
            self.error_recovery = ErrorRecovery(self.llm)
        else:
            self.error_recovery = None
        
        # Build graph
        self.graph = self._build_graph()
        from agents.langgraph_checkpointer import get_langgraph_checkpointer

        checkpointer = get_langgraph_checkpointer()
        self.compiled_graph = self.graph.compile(checkpointer=checkpointer)
        checkpointer_name = type(checkpointer).__name__
        
        logger.info(
            "JD Generation Workflow initialized (checkpointer=%s)",
            checkpointer_name,
            extra={
                "model": llm_config["model"],
                "autonomous_reasoning": self.config.enable_autonomous_reasoning,
                "self_reflection": self.config.enable_self_reflection,
            }
        )
    
    def _create_llm(self, llm_config: dict) -> BaseChatModel:
        """Create LLM based on configuration (OpenAI or Vertex)."""
        from agents.llm.chat_factory import create_chat_llm

        model = llm_config["model"]
        provider = llm_config.get("provider", "vertexai")
        logger.info("Initializing workflow LLM: %s (provider=%s)", model, provider)
        return create_chat_llm(
            model=model,
            temperature=llm_config["temperature"],
            max_tokens=llm_config["max_tokens"],
            provider=provider,
        )

    def _get_best_jd(self, state: JDGenerationState) -> dict | None:
        """Get the best available JD with actual content.
        
        This method checks JDs in priority order:
        1. final_jd
        2. validated_jd (if has content)
        3. refined_jd (if has content)
        4. initial_jd
        
        A JD is considered valid if it has:
        - A non-empty position_summary OR
        - Non-empty responsibilities list
        """
        def has_content(jd: dict) -> bool:
            if not jd or not isinstance(jd, dict):
                return False
            # Check for actual content
            summary = jd.get('position_summary', '')
            responsibilities = jd.get('responsibilities', [])
            return (
                (isinstance(summary, str) and len(summary) > 50) or
                (isinstance(responsibilities, list) and len(responsibilities) > 0)
            )
        
        # Try in priority order
        candidates = [
            ("final_jd", state.get("final_jd")),
            ("validated_jd", state.get("validated_jd")),
            ("refined_jd", state.get("refined_jd")),
            ("initial_jd", state.get("initial_jd")),
        ]
        
        for name, jd in candidates:
            if has_content(jd):
                logger.info(
                    f"✅ Selected {name} as best JD "
                    f"(summary={len(jd.get('position_summary', ''))}chars, "
                    f"responsibilities={len(jd.get('responsibilities', []))}items)"
                )
                return jd
        
        # Fallback: return any non-None JD
        for name, jd in candidates:
            if jd and isinstance(jd, dict):
                logger.warning(f"⚠️ Using {name} as fallback (no JD with content found)")
                return jd
        
        return None

    def _add_thought(self, state: JDGenerationState, agent: str, thought: str, action: str = None, reasoning: dict = None):
        """Add agent thought to state for visibility with autonomous reasoning."""
        # Ensure agent_thoughts list exists
        if "agent_thoughts" not in state:
            state["agent_thoughts"] = []
        
        thought_entry = {
            "agent": agent,
            "thought": thought,
            "action": action,
            "state": state.get("current_state", "unknown"),
            "reasoning": reasoning,  # Add autonomous reasoning
            "autonomous": True,  # Mark as autonomous
        }
        state["agent_thoughts"].append(thought_entry)
        logger.info(f"🤔 [{agent}] {thought}")
        if action:
            logger.info(f"   → Action: {action}")
        if reasoning:
            logger.info(f"   → Reasoning: {reasoning.get('thinking', '')[:100]}...")
    
    @traceable(name="initialize_state")
    def initialize_state(self, state: JDGenerationState) -> JDGenerationState:
        """Initialize workflow state."""
        # Initialize state fields FIRST before adding thoughts
        state["current_state"] = "INITIALIZE"
        state["agent_thoughts"] = []
        state["errors"] = []
        state["workflow_complete"] = False
        
        # Now add the initialization thought
        self._add_thought(
            state,
            "Orchestrator",
            f"Initializing JD generation for: {state.get('job_title', 'Unknown')} ({state.get('job_level', 'Unknown')}) in {state.get('department', 'Unknown')}",
            "Setting up workflow state"
        )
        
        return state
    
    @traceable(name="gather_context")
    def gather_context(self, state: JDGenerationState) -> JDGenerationState:
        """
        Gather context from RAG agent.
        
        Fast mode (default): Uses direct method for instant retrieval.
        Uses OTPAR cycle: OBSERVE → THINK → PLAN → ACT → REFLECT.
        """
        self._add_thought(
            state,
            "RAG Agent",
            f"OTPAR: Gathering context for: {state['job_title']}",
            "Starting OTPAR context retrieval cycle"
        )
        
        try:
            from agents.jd_generation.autonomous_agent import Environment
            
            # Create environment for RAG agent OTPAR cycle
            environment = Environment({
                "state": {"search": True},
                "data": {
                    "job_title": state["job_title"],
                    "department": state["department"],
                },
                "constraints": {"limit": self.config.rag_similar_jobs_limit},
                "tools": ["retrieve_similar_jobs", "vector_search"],
                "agents": [],
            })
            
            # Execute OTPAR autonomous cycle
            cycle_result = self.rag_agent.execute_autonomous_cycle(
                environment=environment,
                goal=f"Retrieve similar jobs for {state['job_title']} in {state['department']}"
            )
            
            # Extract similar jobs from result
            final_result = cycle_result.get("final_result", {})
            similar_jobs = final_result.get("similar_jobs", [])
            
            # If OTPAR returned empty, use direct retrieval as ACT phase
            if not similar_jobs:
                similar_jobs = self.rag_agent.retrieve_similar_jobs(
                    job_title=state["job_title"],
                    department=state["department"],
                    limit=self.config.rag_similar_jobs_limit
                )
            
            state["similar_jobs"] = similar_jobs
            
            self._add_thought(
                state,
                "RAG Agent",
                f"OTPAR cycle complete. Found {len(similar_jobs)} similar jobs",
                "Context gathered successfully"
            )
            
        except Exception as e:
            error_msg = f"Failed to gather context: {str(e)}"
            state["errors"].append(error_msg)
            self._add_thought(
                state,
                "RAG Agent",
                f"Error gathering context: {str(e)}",
                "Continuing without context"
            )
            state["similar_jobs"] = []
            logger.error(
                f"Context gathering failed: {e}",
                exc_info=True,
                extra={"job_title": state["job_title"]}
            )
        
        state["current_state"] = "GATHER_CONTEXT"
        return state
    
    @traceable(name="generate_jd")
    def generate_jd(self, state: JDGenerationState) -> JDGenerationState:
        """
        Generate initial JD using Generator Agent.
        
        Uses OTPAR cycle: OBSERVE → THINK → PLAN → ACT → REFLECT.
        """
        self._add_thought(
            state,
            "Generator Agent",
            f"OTPAR: Generating JD for {state['job_title']}",
            f"Starting JD generation with OTPAR cycle"
        )
        
        try:
            # Prepare context
            context = {
                "job_title": state["job_title"],
                "job_level": state["job_level"],
                "department": state["department"],
                "location": state.get("location"),
                "remote_allowed": state.get("remote_allowed", False),
                "user_requirements": state.get("user_requirements"),
                "similar_jobs": state.get("similar_jobs", []),
            }
            
            # Pass state to agent so thoughts can be captured
            # Generate JD using OTPAR cycle
            jd = self.generator_agent.generate_jd(context, state=state)
            
            # Validate that we got actual content
            if jd and isinstance(jd, dict):
                position_summary = jd.get('position_summary', '')
                responsibilities = jd.get('responsibilities', [])
                logger.info(f"📋 Generated JD content check:")
                logger.info(f"   - job_title: {jd.get('job_title', 'MISSING')}")
                logger.info(f"   - position_summary: {len(position_summary)} chars")
                logger.info(f"   - responsibilities: {len(responsibilities)} items")
                
                if len(position_summary) < 50 or len(responsibilities) < 3:
                    logger.warning(f"⚠️ Generated JD appears to have insufficient content!")
            
            state["initial_jd"] = jd
            
            self._add_thought(
                state,
                "Generator Agent",
                f"JD generation complete. Position summary: {len(jd.get('position_summary', ''))} chars, Responsibilities: {len(jd.get('responsibilities', []))} items.",
                "Initial JD complete"
            )
            
        except Exception as e:
            error_msg = f"Failed to generate JD: {str(e)}"
            state["errors"].append(error_msg)
            self._add_thought(
                state,
                "Generator Agent",
                f"Error during generation: {str(e)}",
                "Generation failed"
            )
            logger.error(
                f"JD generation failed: {e}",
                exc_info=True,
                extra={"job_title": state["job_title"]}
            )
            raise
        
        state["current_state"] = "GENERATE_JD"
        return state
    
    @traceable(name="refine_jd")
    def refine_jd(self, state: JDGenerationState) -> JDGenerationState:
        """
        Refine JD using Refiner Agent.
        
        Uses CrewAI to improve the initial JD for clarity, completeness, and professionalism.
        """
        if not state.get("initial_jd"):
            self._add_thought(
                state,
                "Refiner Agent",
                "No initial JD to refine. Skipping refinement.",
                "Skipping step"
            )
            state["refined_jd"] = state.get("initial_jd")
            state["current_state"] = "REFINE_JD"
            return state
        
        self._add_thought(
            state,
            "Refiner Agent",
            "Starting autonomous refinement cycle",
            "Initiating full autonomous cycle"
        )
        
        try:
            # Parse user requirements for the refiner to use
            from agents.jd_generation.crew_agents import parse_user_requirements
            user_requirements = state.get("user_requirements", "")
            parsed_requirements = parse_user_requirements(user_requirements) if user_requirements else {}
            
            # Refine using autonomous cycle (implemented in refine_jd method)
            refined = self.refiner_agent.refine_jd(
                initial_jd=state["initial_jd"],
                context={
                    "job_level": state.get("job_level"),  # CRITICAL: Pass job_level for experience enforcement
                    "job_title": state.get("job_title"),
                    "department": state.get("department"),
                    "location": state.get("location"),
                    "remote_allowed": state.get("remote_allowed", False),
                    "similar_jobs": state.get("similar_jobs", []),
                    "user_requirements": state.get("user_requirements"),
                    "parsed_requirements": parsed_requirements,  # Pre-parsed for efficiency
                },
                state=state
            )
            
            state["refined_jd"] = refined
            
            self._add_thought(
                state,
                "Refiner Agent",
                "JD refinement complete. Content improved successfully.",
                "Refinement complete"
            )
            
        except Exception as e:
            error_msg = f"Failed to refine JD: {str(e)}"
            state["errors"].append(error_msg)
            self._add_thought(
                state,
                "Refiner Agent",
                f"Error during refinement: {str(e)}. Using initial JD.",
                "Refinement failed, using initial"
            )
            state["refined_jd"] = state.get("initial_jd")
            logger.error(
                f"JD refinement failed: {e}",
                exc_info=True,
                extra={"job_title": state["job_title"]}
            )
        
        state["current_state"] = "REFINE_JD"
        return state
    
    @traceable(name="validate_jd")
    def validate_jd(self, state: JDGenerationState) -> JDGenerationState:
        """Validate JD using Validator Agent."""
        jd_to_validate = state.get("refined_jd") or state.get("initial_jd")
        
        if not jd_to_validate:
            error_msg = "No JD to validate"
            state["errors"].append(error_msg)
            state["current_state"] = "VALIDATE_JD"
            return state
        
        self._add_thought(
            state,
            "Validator Agent",
            "Validating JD completeness. Checking all required sections, clarity, and professional standards.",
            "Starting validation"
        )
        
        try:
            validation_result = self.validator_agent.validate_jd(jd_to_validate, state=state)
            
            if validation_result.get("is_valid"):
                state["validated_jd"] = jd_to_validate
                self._add_thought(
                    state,
                    "Validator Agent",
                    f"JD validation passed. All checks: {', '.join(validation_result.get('checks_passed', []))}",
                    "Validation successful"
                )
            else:
                issues = validation_result.get("issues", [])
                self._add_thought(
                    state,
                    "Validator Agent",
                    f"JD validation found issues: {', '.join(issues)}. Attempting auto-fix.",
                    "Issues detected, fixing"
                )
                
                # Try to fix issues
                fixed_jd = self.validator_agent.fix_jd(jd_to_validate, issues)
                state["validated_jd"] = fixed_jd
                
                self._add_thought(
                    state,
                    "Validator Agent",
                    "Issues fixed. JD is now valid.",
                    "Auto-fix complete"
                )
            
        except Exception as e:
            error_msg = f"Failed to validate JD: {str(e)}"
            state["errors"].append(error_msg)
            self._add_thought(
                state,
                "Validator Agent",
                f"Error during validation: {str(e)}. Using refined JD.",
                "Validation failed, using refined"
            )
            state["validated_jd"] = jd_to_validate
        
        state["current_state"] = "VALIDATE_JD"
        return state
    
    def should_customize(self, state: JDGenerationState) -> Literal["customize", "prepare"]:
        """Decide if customization is needed."""
        if state.get("user_edits"):
            self._add_thought(
                state,
                "Orchestrator",
                "User edits detected. Proceeding to customization step.",
                "Customization needed"
            )
            return "customize"
        
        self._add_thought(
            state,
            "Orchestrator",
            "No user edits. Proceeding directly to preparation.",
            "Skipping customization"
        )
        return "prepare"
    
    @traceable(name="customize_jd")
    def customize_jd(self, state: JDGenerationState) -> JDGenerationState:
        """Apply user customizations."""
        if not state.get("user_edits"):
            state["final_jd"] = state.get("validated_jd")
            state["current_state"] = "CUSTOMIZE_JD"
            return state
        
        self._add_thought(
            state,
            "Orchestrator",
            f"Applying user customizations: {list(state['user_edits'].keys())}",
            "Applying edits"
        )
        
        try:
            validated_jd = state.get("validated_jd", {})
            user_edits = state.get("user_edits", {})
            
            # Apply edits
            final_jd = {**validated_jd, **user_edits}
            state["final_jd"] = final_jd
            
            self._add_thought(
                state,
                "Orchestrator",
                "User customizations applied successfully.",
                "Customization complete"
            )
            
        except Exception as e:
            error_msg = f"Failed to customize JD: {str(e)}"
            state["errors"].append(error_msg)
            state["final_jd"] = state.get("validated_jd")
        
        state["current_state"] = "CUSTOMIZE_JD"
        return state
    
    @traceable(name="prepare_jd")
    def prepare_jd(self, state: JDGenerationState) -> JDGenerationState:
        """Prepare JD for storage in Milvus (generate job_id)."""
        self._add_thought(
            state,
            "Storage Agent",
            "Preparing JD for storage in Milvus vector database.",
            "Generating job ID"
        )
        
        try:
            # Generate unique job ID for Milvus storage
            import uuid
            if not state.get("job_id"):
                state["job_id"] = str(uuid.uuid4())
            
            self._add_thought(
                state,
                "Storage Agent",
                f"JD prepared with ID: {state['job_id']} for Milvus storage",
                "Job ID generated"
            )
            
        except Exception as e:
            error_msg = f"Failed to prepare JD: {str(e)}"
            state["errors"].append(error_msg)
        
        state["current_state"] = "PREPARE_JD"
        return state
    
    @traceable(name="generate_embeddings")
    def generate_embeddings(self, state: JDGenerationState) -> JDGenerationState:
        """Generate embeddings for JD."""
        self._add_thought(
            state,
            "Storage Agent",
            "Generating embeddings for JD to enable semantic search.",
            "Creating embeddings"
        )
        
        try:
            # Get the best available JD with actual content
            final_jd = self._get_best_jd(state)
            if not final_jd:
                raise ValueError("No JD with content to generate embeddings for")
            
            # Update state with the selected JD for consistency
            if not state.get("final_jd"):
                state["final_jd"] = final_jd
            
            # Generate embedding (simplified - would use actual embedding model)
            # In production, use sentence transformers or OpenAI embeddings
            embedding = self.storage_agent.generate_embedding(final_jd)
            state["embedding"] = embedding
            
            self._add_thought(
                state,
                "Storage Agent",
                f"Embeddings generated. Vector dimension: {len(embedding)}",
                "Embeddings ready"
            )
            
            logger.info(
                f"✅ Embeddings generated successfully: dimension={len(embedding)}",
                extra={
                    "embedding_dimension": len(embedding),
                    "job_title": final_jd.get("job_title", "N/A")
                }
            )
            
        except Exception as e:
            error_msg = f"Failed to generate embeddings: {str(e)}"
            logger.error(
                f"❌ Embedding generation failed: {error_msg}",
                exc_info=True,
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "has_jd": bool(state.get("final_jd") or state.get("validated_jd"))
                }
            )
            state["errors"].append(error_msg)
            
            # CRITICAL: Generate fallback embedding to allow storage to proceed
            # This ensures the JD can still be stored in Milvus even if embedding fails
            try:
                from agents.jd_generation.config import get_config
                config = get_config()
                fallback_embedding = [0.0] * config.embedding_dimension
                state["embedding"] = fallback_embedding
                logger.warning(
                    f"⚠️ Using fallback zero embedding (dimension={config.embedding_dimension}) "
                    f"to allow Milvus storage. JD will be stored but semantic search may be limited.",
                    extra={"embedding_dimension": config.embedding_dimension}
                )
                self._add_thought(
                    state,
                    "Storage Agent",
                    f"Using fallback embedding due to generation failure. Storage will proceed.",
                    "Fallback embedding"
                )
            except Exception as fallback_error:
                logger.error(
                    f"❌ Failed to generate fallback embedding: {fallback_error}",
                    exc_info=True
                )
                # If even fallback fails, embedding will be None and storage will be skipped
                state["embedding"] = None
        
        state["current_state"] = "GENERATE_EMBEDDINGS"
        return state
    
    @traceable(name="store_in_milvus")
    def store_in_milvus(self, state: JDGenerationState) -> JDGenerationState:
        """Store JD in Milvus vector database.
        
        NOTE: Milvus storage is skipped during generation because the frontend
        always calls the /save endpoint immediately after, which stores the JD
        reliably. Attempting storage here is redundant and can cause long delays
        (up to 3 minutes of retries) if Milvus has transient channel issues.
        """
        logger.info(
            "🔄 ===== MILVUS STORAGE STEP (DEFERRED TO SAVE ENDPOINT) =====",
            extra={
                "job_id": state.get("job_id"),
                "has_final_jd": bool(state.get("final_jd")),
                "has_validated_jd": bool(state.get("validated_jd")),
                "has_embedding": bool(state.get("embedding")),
                "current_state": state.get("current_state")
            }
        )
        
        # Ensure job_id is set (needed by downstream save endpoint)
        job_id = state.get("job_id")
        if not job_id:
            import uuid
            job_id = str(uuid.uuid4())
            state["job_id"] = job_id
            logger.info(f"Generated job_id: {job_id}")
        
        self._add_thought(
            state,
            "Milvus Storage Agent",
            "Milvus storage will be handled by the save endpoint for reliability. "
            "Skipping redundant storage during generation to avoid delays.",
            "Storage deferred to save"
        )
        
        logger.info(
            f"✅ Milvus storage deferred to save endpoint for job_id={job_id}. "
            f"This avoids redundant storage and potential timeout delays."
        )
        
        state["milvus_id"] = None
        state["current_state"] = "STORE_IN_MILVUS"
        return state
    
    @traceable(name="complete_workflow")
    def complete_workflow(self, state: JDGenerationState) -> JDGenerationState:
        """Complete workflow."""
        self._add_thought(
            state,
            "Orchestrator",
            "JD generation workflow completed successfully!",
            "Workflow complete"
        )
        
        state["workflow_complete"] = True
        state["current_state"] = "COMPLETE"
        
        return state
    
    def _build_graph(self) -> StateGraph:
        """Build LangGraph state machine."""
        workflow = StateGraph(JDGenerationState)
        
        # Add nodes
        workflow.add_node("initialize", self.initialize_state)
        workflow.add_node("gather_context", self.gather_context)
        workflow.add_node("generate_jd", self.generate_jd)
        workflow.add_node("refine_jd", self.refine_jd)
        workflow.add_node("validate_jd", self.validate_jd)
        workflow.add_node("customize_jd", self.customize_jd)
        workflow.add_node("prepare_jd", self.prepare_jd)
        workflow.add_node("generate_embeddings", self.generate_embeddings)
        workflow.add_node("store_in_milvus", self.store_in_milvus)
        workflow.add_node("complete", self.complete_workflow)
        
        # Define edges
        workflow.set_entry_point("initialize")
        workflow.add_edge("initialize", "gather_context")
        workflow.add_edge("gather_context", "generate_jd")
        workflow.add_edge("generate_jd", "refine_jd")
        workflow.add_edge("refine_jd", "validate_jd")
        workflow.add_conditional_edges(
            "validate_jd",
            self.should_customize,
            {
                "customize": "customize_jd",
                "prepare": "prepare_jd",
            }
        )
        workflow.add_edge("customize_jd", "prepare_jd")
        workflow.add_conditional_edges(
            "prepare_jd",
            self._route_after_prepare,
            {
                "complete": "complete",
                "embed": "generate_embeddings",
            },
        )
        workflow.add_edge("generate_embeddings", "store_in_milvus")
        workflow.add_edge("store_in_milvus", "complete")
        workflow.add_edge("complete", END)
        
        return workflow

    def _route_after_prepare(self, state: JDGenerationState) -> Literal["complete", "embed"]:
        """Skip local embedding/Milvus when Azure pgvector pipeline handles storage."""
        from agents.deployment_env import should_skip_local_vector_storage

        if should_skip_local_vector_storage():
            logger.info(
                "Skipping in-workflow embeddings/Milvus — storage handled by API pgvector pipeline"
            )
            return "complete"
        return "embed"
    
    def run(self, input_data: dict) -> JDGenerationState:
        """Run the workflow."""
        initial_state: JDGenerationState = {
            "job_title": input_data.get("job_title", ""),
            "job_level": input_data.get("job_level", ""),
            "department": input_data.get("department", ""),
            "location": input_data.get("location"),
            "remote_allowed": input_data.get("remote_allowed", False),
            "user_requirements": input_data.get("user_requirements"),
            "similar_jobs": None,
            "market_context": None,
            "initial_jd": None,
            "refined_jd": None,
            "validated_jd": None,
            "user_edits": input_data.get("user_edits"),
            "final_jd": None,
            "job_id": None,
            "embedding": None,
            "milvus_id": None,
            "current_state": "INITIAL",
            "errors": [],
            "agent_thoughts": [],
            "workflow_complete": False,
        }
        
        # A checkpointer is compiled into the graph, so LangGraph requires a
        # thread_id; one id per generation run keeps runs isolated.
        import uuid as _uuid

        run_config = {"configurable": {"thread_id": str(_uuid.uuid4())}}
        result = self.compiled_graph.invoke(initial_state, config=run_config)
        return result


# ============================================================================
# Export for LangGraph Studio
# ============================================================================
# LangGraph Studio expects a CompiledStateGraph object exported as 'graph'

# LangGraph Studio export (optional — avoids double-init on every API import)
import os as _os

graph = None
if _os.getenv("LANGGRAPH_STUDIO", "").strip().lower() in ("1", "true", "yes"):
    print("Initializing JD Generation Workflow for LangGraph Studio...")
    _workflow_instance = JDGenerationWorkflow()
    graph = _workflow_instance.compiled_graph
    print(f"✅ Workflow initialized. Graph type: {type(graph).__name__}")

# Also export the workflow class and helper function
__all__ = ['JDGenerationWorkflow', 'JDGenerationState', 'graph']
