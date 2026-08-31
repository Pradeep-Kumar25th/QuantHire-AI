"""
Enterprise-Level Autonomous AI Resume Parsing Agent
===================================================

Main agent implementation with enterprise best practices:
- Proper error handling and logging
- Type safety with Pydantic models
- Dependency injection
- Configuration management
- Performance optimizations
- Security best practices
"""

import json
import re
import time
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional

from quantire_agents.config.settings import AgentSettings, get_settings
from quantire_agents.config.constants import (
    ParsingMethod,
    SecurityStatus,
    ToolName,
    AGENT_VERSION,
    DEFAULT_MATCH_PERCENTAGE,
    DEFAULT_FALLBACK_MATCH_PERCENTAGE,
)
from quantire_agents.config.logging_config import AgentLogger
from quantire_agents.resume_parser.models import (
    ParsedResumeData,
    ResumeParsingResult,
    PersonalInfo,
    Experience,
    Education,
    Skills,
    EnhancedData,
)
from quantire_agents.resume_parser.exceptions import (
    ResumeParsingError,
    AgentInitializationError,
    ToolExecutionError,
)
from quantire_agents.resume_parser.extractors import LocalExtractor
from quantire_agents.resume_parser.services import EmbeddingService, LLMService

logger = AgentLogger.get_logger(__name__)


class ResumeParsingAgent:
    """
    Enterprise-Level Autonomous AI Resume Parsing Agent.
    
    Features:
    - Autonomous decision-making with LangChain AgentExecutor
    - Conversational memory across parsing steps
    - Multiple specialized tools for extraction
    - RAG integration with Milvus vector database
    - Hybrid architecture security
    - Comprehensive error handling and logging
    """
    
    def __init__(self, settings: Optional[AgentSettings] = None):
        """Initialize the resume parsing agent.
        
        Args:
            settings: Optional agent settings (uses global settings if not provided)
            
        Raises:
            AgentInitializationError: If agent initialization fails
        """
        try:
            self.settings = settings or get_settings()
            self.logger = AgentLogger.get_logger(self.__class__.__name__)
            
            # Services
            self.embedding_service: Optional[EmbeddingService] = None
            self.llm_service: Optional[LLMService] = None
            
            # Agent components
            self.agent_executor = None
            self.memory = None
            self.tools: List[Any] = []
            
            # Initialize services
            self._initialize_services()
            
            # Initialize agent if LangChain is available
            if self._is_langchain_available():
                self._initialize_agent()
            else:
                self.logger.warning("LangChain not available - using fallback parsing mode")
            
            # Log final initialization status
            self.logger.info("=" * 60)
            self.logger.info("Agent Initialization Status:")
            self.logger.info(f"  - Agent Executor: {'✅ Available' if self.agent_executor else '❌ Not Available'}")
            self.logger.info(f"  - LLM Service: {'✅ Available' if self.llm_service and self.llm_service.is_available() else '❌ Not Available'}")
            self.logger.info(f"  - Tools: {len(self.tools)} available")
            self.logger.info(f"  - Memory: {'✅ Enabled' if self.memory else '❌ Disabled'}")
            self.logger.info(f"  - Milvus RAG: ❌ Deprecated - Use QueryRouter for retrieval")
            self.logger.info("=" * 60)
                
        except Exception as e:
            self.logger.error(f"Agent initialization failed: {e}", exc_info=True)
            raise AgentInitializationError(
                f"Failed to initialize agent: {str(e)}",
                details={"error": str(e)}
            )
    
    def _is_langchain_available(self) -> bool:
        """Check if LangChain/LangGraph is available.
        
        Returns:
            True if LangChain/LangGraph is available, False otherwise
        """
        try:
            # Try LangGraph (modern approach) first
            try:
                from langgraph.prebuilt import create_react_agent
                from langgraph.checkpoint.memory import MemorySaver
                from langchain_core.tools import tool
                self.logger.info("LangGraph framework available - using modern agent architecture")
                return True
            except ImportError as e:
                self.logger.debug(f"LangGraph not available: {e}")
            
            # Try legacy LangChain imports
            try:
                from langchain.agents import AgentExecutor, create_structured_chat_agent
                self.logger.info("LangChain legacy agents module available (langchain.agents)")
                return True
            except ImportError as e:
                self.logger.debug(f"LangChain legacy agents not available: {e}")
            
            self.logger.warning("Neither LangGraph nor LangChain agents available - will use fallback parsing")
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking LangChain/LangGraph availability: {e}")
            return False
    
    def _initialize_services(self) -> None:
        """Initialize all services."""
        try:
            # MilvusService is deprecated - use QueryRouter for retrieval instead
            # RAG enhancement disabled - use QuantChat AI for queries
            
            # Initialize embedding service
            self.embedding_service = EmbeddingService(self.settings)
            
            # Initialize LLM service
            if self.settings.is_api_key_configured:
                self.llm_service = LLMService(self.settings)
            else:
                self.logger.warning("API key not configured - LLM features disabled")
                
        except Exception as e:
            self.logger.error(f"Service initialization failed: {e}", exc_info=True)
            # Continue with degraded functionality
    
    def _initialize_agent(self) -> None:
        """Initialize the LangChain/LangGraph agent."""
        try:
            self.logger.info("Initializing AI Agent...")
            
            # Initialize LLM if available (required for all agent types)
            if not self.llm_service or not self.llm_service.is_available():
                self.logger.warning("LLM service not available - agent initialization skipped")
                return
            
            # Create tools first (used by all agent types)
            self.tools = self._create_agent_tools()
            
            if not self.tools:
                self.logger.warning("No tools available - agent initialization skipped")
                return
            
            self.logger.info(f"  - Tools created: {len(self.tools)} tools")
            
            # ===== TRY LANGGRAPH FIRST (Modern Approach) =====
            try:
                from langgraph.prebuilt import create_react_agent
                from langgraph.checkpoint.memory import MemorySaver
                
                self.logger.info("Using LangGraph ReAct agent (modern approach)")
                
                # Create memory saver for LangGraph
                self.memory = MemorySaver()
                
                # Create the ReAct agent
                self.agent_executor = create_react_agent(
                    model=self.llm_service.llm,
                    tools=self.tools,
                    checkpointer=self.memory
                )
                
                self.logger.info("LangGraph ReAct agent initialized successfully")
                self.logger.info(f"  - LLM: {self.settings.llm_model_name}")
                self.logger.info(f"  - Memory: MemorySaver (LangGraph)")
                self.logger.info(f"  - Tools: {len(self.tools)}")
                self.logger.info(f"  - RAG: Disabled (use QueryRouter/QuantChat AI)")
                return
                
            except ImportError as e:
                self.logger.warning(f"LangGraph not available: {e}")
            except Exception as e:
                self.logger.warning(f"LangGraph agent creation failed: {e}")
                import traceback
                self.logger.debug(f"LangGraph error details: {traceback.format_exc()}")
            
            # ===== FALLBACK TO LEGACY LANGCHAIN =====
            self.logger.info("Trying legacy LangChain agent...")
            
            # Try to import legacy LangChain components
            AgentExecutor = None
            create_structured_chat_agent = None
            ConversationBufferMemory = None
            
            try:
                from langchain.agents import AgentExecutor as AE, create_structured_chat_agent as csca
                AgentExecutor = AE
                create_structured_chat_agent = csca
                self.logger.info("  - Legacy LangChain agents imported")
            except ImportError as e:
                self.logger.warning(f"  - Legacy LangChain agents not available: {e}")
            
            try:
                from langchain.memory import ConversationBufferMemory as CBM
                ConversationBufferMemory = CBM
            except ImportError:
                try:
                    from langchain_community.memory import ConversationBufferMemory as CBM
                    ConversationBufferMemory = CBM
                except ImportError:
                    pass
            
            if not AgentExecutor or not create_structured_chat_agent:
                self.logger.error("Neither LangGraph nor legacy LangChain available")
                self.logger.error("Agent initialization failed - no suitable agent framework available")
                return
            
            # Initialize memory for legacy agent
            if ConversationBufferMemory:
                self.memory = ConversationBufferMemory(
                    memory_key="chat_history",
                    return_messages=False,
                    output_key="output"
                )
                self.logger.info("Memory initialized - context will be maintained across parsing sessions")
            
            # Create prompt template
            prompt = self._create_agent_prompt()
            
            # Create agent
            agent = create_structured_chat_agent(
                llm=self.llm_service.llm,
                tools=self.tools,
                prompt=prompt
            )
            
            # Initialize agent executor
            self.agent_executor = AgentExecutor(
                agent=agent,
                tools=self.tools,
                memory=self.memory,
                verbose=self.settings.agent_verbose,
                return_intermediate_steps=self.settings.agent_return_intermediate_steps,
                handle_parsing_errors=True,
                max_iterations=self.settings.agent_max_iterations
            )
            
            self.logger.info("Legacy LangChain agent initialized successfully")
            self.logger.info(f"  - LLM: {self.settings.llm_model_name}")
            self.logger.info(f"  - Memory: Enabled")
            self.logger.info(f"  - Tools: {len(self.tools)}")
            self.logger.info(f"  - RAG: Disabled (use QueryRouter/QuantChat AI for RAG queries)")
            
        except Exception as e:
            self.logger.error(f"Agent initialization failed: {e}", exc_info=True)
            self.agent_executor = None
    
    def _create_agent_prompt(self) -> Any:
        """Create agent prompt template.
        
        Returns:
            ChatPromptTemplate instance
        """
        try:
            from langchain_core.prompts import ChatPromptTemplate
        except ImportError:
            try:
                from langchain.prompts import ChatPromptTemplate
            except ImportError:
                raise AgentInitializationError("ChatPromptTemplate not available")
        
        # Create prompt template with proper message structure for Gemini
        # Gemini requires at least one message with content
        return ChatPromptTemplate.from_messages([
            ("system", """You are a helpful assistant that can use tools to parse resumes.
You have access to the following tools:

{tools}

To use a tool, please use the following format:

```
Thought: Do I need to use a tool? Yes
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
```

When you have a response to say to the Human, or if you do not need to use a tool, you MUST use the format:

```
Thought: Do I need to use a tool? No
Final Answer: [your response here]
```

Begin!"""),
            ("human", """Previous conversation history:
{chat_history}

New question: {input}

{agent_scratchpad}"""),
        ])
    
    def _create_agent_tools(self) -> List[Any]:
        """Create specialized tools for the agent.
        
        Returns:
            List of LangChain Tool instances (compatible with LangGraph and legacy agents)
        """
        # Try to import the @tool decorator for LangGraph compatibility
        tool_decorator = None
        Tool = None
        
        try:
            from langchain_core.tools import tool as tool_decorator_fn
            tool_decorator = tool_decorator_fn
            self.logger.info("Using @tool decorator from langchain_core.tools")
        except ImportError:
            try:
                from langchain.tools import tool as tool_decorator_fn
                tool_decorator = tool_decorator_fn
                self.logger.info("Using @tool decorator from langchain.tools")
            except ImportError:
                pass
        
        try:
            from langchain.tools import Tool as ToolClass
            Tool = ToolClass
            self.logger.info("Using Tool class from langchain.tools")
        except ImportError:
            try:
                from langchain_core.tools import Tool as ToolClass
                Tool = ToolClass
                self.logger.info("Using Tool class from langchain_core.tools")
            except ImportError:
                self.logger.error("Neither Tool class nor @tool decorator available")
                return []
        
        # Tool 1: Extract Personal Information
        def extract_personal_info(resume_text: str) -> str:
            """Extract personal information from resume. 
            IMPORTANT: Verify the name is the actual candidate name, not a section header.
            Look for name patterns (2-4 capitalized words) and avoid common headers like 'UI', 'UX', 'Summary', etc."""
            try:
                info = LocalExtractor.extract_personal_info(resume_text)
                # Post-process: if name looks like a section header, try to find real name
                if info.get("name") and len(info.get("name", "").split()) <= 1:
                    # Single word name might be a header - look for better candidate
                    lines = [line.strip() for line in resume_text.splitlines() if line.strip()]
                    for line in lines[:5]:
                        words = line.split()
                        if (len(words) >= 2 and len(words) <= 4 and 
                            all(word[0].isupper() if word else False for word in words) and
                            line.lower() not in ['ui', 'ux', 'summary', 'objective', 'profile', 'experience', 'education', 'skills']):
                            info["name"] = line
                            break
                return json.dumps(info, indent=2)
            except Exception as e:
                self.logger.error(f"Error in extract_personal_info tool: {e}")
                raise ToolExecutionError(
                    ToolName.EXTRACT_PERSONAL_INFO,
                    str(e)
                )
        
        # Tool 2: Extract Skills
        def extract_skills(resume_text: str) -> str:
            """Extract skills from resume. 
            IMPORTANT: Extract ALL skills mentioned, including:
            - Skills explicitly listed in a 'Skills' section
            - Technologies mentioned in job descriptions
            - Tools and frameworks used in projects
            - Programming languages mentioned anywhere
            - Certifications and qualifications
            Be thorough and comprehensive."""
            try:
                skills = LocalExtractor.extract_skills(resume_text)
                # The LocalExtractor uses keyword matching, but the LLM agent should
                # also analyze the text to find additional skills mentioned in context
                return json.dumps(skills, indent=2)
            except Exception as e:
                self.logger.error(f"Error in extract_skills tool: {e}")
                raise ToolExecutionError(
                    ToolName.EXTRACT_SKILLS,
                    str(e)
                )
        
        # Tool 3: Extract Experience
        def extract_experience(resume_text: str) -> str:
            """Extract work experience from resume."""
            try:
                experience = LocalExtractor.extract_experience(resume_text)
                return json.dumps(experience, indent=2)
            except Exception as e:
                self.logger.error(f"Error in extract_experience tool: {e}")
                raise ToolExecutionError(
                    ToolName.EXTRACT_EXPERIENCE,
                    str(e)
                )
        
        # Tool 4: Extract Education
        def extract_education(resume_text: str) -> str:
            """Extract education information from resume."""
            try:
                education = LocalExtractor.extract_education(resume_text)
                return json.dumps(education, indent=2)
            except Exception as e:
                self.logger.error(f"Error in extract_education tool: {e}")
                raise ToolExecutionError(
                    ToolName.EXTRACT_EDUCATION,
                    str(e)
                )
        
        # Tool 5: Enhance with RAG
        def enhance_with_rag(data_json: str) -> str:
            """Enhance extracted data using RAG."""
            try:
                data = json.loads(data_json)
                enhanced = self._enhance_with_rag_ai(data)
                return json.dumps(enhanced, indent=2)
            except Exception as e:
                self.logger.error(f"Error in enhance_with_rag tool: {e}")
                raise ToolExecutionError(
                    ToolName.ENHANCE_WITH_RAG_AI,
                    str(e)
                )
        
        # Create tools using @tool decorator for LangGraph compatibility
        if tool_decorator:
            self.logger.info("Creating tools with @tool decorator for LangGraph compatibility")

            @tool_decorator(name=ToolName.EXTRACT_PERSONAL_INFO.value)
            def extract_personal_info_tool(resume_text: str) -> str:
                """Extract personal information (name, email, phone, location, LinkedIn, GitHub) from resume text. Use this first."""
                return extract_personal_info(resume_text)

            @tool_decorator(name=ToolName.EXTRACT_SKILLS.value)
            def extract_skills_tool(resume_text: str) -> str:
                """Extract technical skills, programming languages, soft skills, tools, frameworks, and certifications from resume text."""
                return extract_skills(resume_text)

            @tool_decorator(name=ToolName.EXTRACT_EXPERIENCE.value)
            def extract_experience_tool(resume_text: str) -> str:
                """Extract work experience including job titles, companies, duration, and achievements from resume text."""
                return extract_experience(resume_text)

            @tool_decorator(name=ToolName.EXTRACT_EDUCATION.value)
            def extract_education_tool(resume_text: str) -> str:
                """Extract education information including degrees, institutions, graduation years, and GPA from resume text."""
                return extract_education(resume_text)

            @tool_decorator(name=ToolName.ENHANCE_WITH_RAG_AI.value)
            def enhance_with_rag_tool(data_json: str) -> str:
                """Enhance extracted data using RAG (retrieval from Milvus vector database) and AI insights. Use this last."""
                return enhance_with_rag(data_json)
            
            return [
                extract_personal_info_tool,
                extract_skills_tool,
                extract_experience_tool,
                extract_education_tool,
                enhance_with_rag_tool
            ]
        
        # Fallback to Tool class for legacy LangChain
        self.logger.info("Creating tools with Tool class for legacy LangChain")
        return [
            Tool(
                name=ToolName.EXTRACT_PERSONAL_INFO,
                func=extract_personal_info,
                description="Extract personal information (name, email, phone, location, LinkedIn, GitHub) from resume text. Use this first."
            ),
            Tool(
                name=ToolName.EXTRACT_SKILLS,
                func=extract_skills,
                description="Extract technical skills, programming languages, soft skills, tools, frameworks, and certifications from resume text."
            ),
            Tool(
                name=ToolName.EXTRACT_EXPERIENCE,
                func=extract_experience,
                description="Extract work experience including job titles, companies, duration, and achievements from resume text."
            ),
            Tool(
                name=ToolName.EXTRACT_EDUCATION,
                func=extract_education,
                description="Extract education information including degrees, institutions, graduation years, and GPA from resume text."
            ),
            Tool(
                name=ToolName.ENHANCE_WITH_RAG_AI,
                func=enhance_with_rag,
                description="Enhance extracted data using RAG (retrieval from Milvus vector database) and AI insights. Use this last."
            )
        ]
    
    def _enhance_with_rag_ai(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance data using RAG and AI.
        
        Args:
            data: Extracted resume data
            
        Returns:
            Enhanced data dictionary
        """
        if not self.settings.enable_rag_enhancement:
            return data
        
        if not self.llm_service or not self.llm_service.is_available():
            self.logger.warning("LLM service not available for enhancement")
            return data
        
        if not self.embedding_service or not self.embedding_service.is_available():
            self.logger.warning("Embedding service not available for RAG")
            return data
        
        try:
            # Generate embedding for skills
            skills_text = " ".join(data.get("skills", {}).get("technical_skills", []))
            if not skills_text:
                return data
            
            candidate_embedding = self.embedding_service.generate_embedding(skills_text)
            
            # MilvusService is deprecated - use QueryRouter/QuantChat AI for similarity search
            similar_candidates = []
            
            # Prepare minimal context for LLM
            minimal_context = {
                "skills": data.get("skills", {}).get("technical_skills", [])[:10],
                "experience_years": data.get("experience", {}).get("total_years", 0),
                "similar_candidates_summary": f"Found {len(similar_candidates)} similar candidates" if similar_candidates else "No similar candidates found"
            }
            
            # Create enhancement prompt
            enhancement_prompt = f"""Enhance the following resume data with professional insights.

Minimal Context:
{json.dumps(minimal_context, indent=2)}

Instructions:
1. Generate a professional summary (2-3 sentences)
2. Suggest 3-5 additional relevant skills based on experience
3. Identify strengths and career progression
4. Highlight any certifications that would enhance their profile

Return ONLY valid JSON with:
- summary: string
- additional_skills: array
- strengths: array
- career_insights: array

DO NOT hallucinate information - only enhance what's reasonable.
"""
            
            # Invoke LLM
            try:
                from langchain_core.messages import SystemMessage, HumanMessage
            except ImportError:
                from langchain.schema import SystemMessage, HumanMessage
            
            messages = [
                SystemMessage(content="You are an expert resume analysis AI. Enhance data accurately."),
                HumanMessage(content=enhancement_prompt)
            ]
            
            response_content = self.llm_service.invoke(messages)
            enhancements = json.loads(response_content)
            
            # Merge enhancements
            data["summary"] = enhancements.get("summary", "")
            data["strengths"] = enhancements.get("strengths", [])
            data["career_insights"] = enhancements.get("career_insights", [])
            
            if "additional_skills" in enhancements:
                if "skills" not in data:
                    data["skills"] = {}
                if "technical_skills" not in data["skills"]:
                    data["skills"]["technical_skills"] = []
                data["skills"]["technical_skills"].extend(enhancements["additional_skills"])
            
            self.logger.info("RAG + AI enhancement completed")
            
        except Exception as e:
            self.logger.error(f"RAG enhancement failed: {e}", exc_info=True)
            # Return original data if enhancement fails
        
        return data
    
    def get_memory_context(self) -> str:
        """Get current memory context for continuous flow.
        
        Returns:
            String containing current conversation history from memory
        """
        if not self.memory:
            return ""
        
        try:
            memory_vars = self.memory.load_memory_variables({})
            chat_history = memory_vars.get("chat_history", "")
            return chat_history
        except Exception as e:
            self.logger.warning(f"Failed to retrieve memory context: {e}")
            return ""
    
    def clear_memory(self) -> bool:
        """Clear agent memory explicitly.
        
        Returns:
            True if memory was cleared successfully, False otherwise
        """
        if not self.memory:
            return False
        
        try:
            self.memory.clear()
            self.logger.info("✅ Agent memory cleared successfully")
            return True
        except Exception as e:
            self.logger.warning(f"Failed to clear memory: {e}")
            return False
    
    def parse_resume(
        self,
        resume_text: str,
        resume_id: str,
        clear_memory: bool = False,
        conversation_context: Optional[str] = None
    ) -> ResumeParsingResult:
        """
        Parse resume using autonomous AI agent with context memory.
        
        Args:
            resume_text: Resume text content
            resume_id: Unique resume identifier
            clear_memory: If True, clear memory before parsing (default: False for continuous flow)
            conversation_context: Optional context from previous conversations to maintain flow
            
        Returns:
            ResumeParsingResult with parsed data or error information
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"Starting resume parsing for resume_id: {resume_id}")
            self.logger.debug(f"Resume text length: {len(resume_text)} characters")
            self.logger.debug(f"Clear memory: {clear_memory}")
            self.logger.debug(f"Conversation context provided: {conversation_context is not None}")
            
            # Validate input
            if not resume_text or not resume_text.strip():
                raise ResumeParsingError("Empty resume text provided")
            
            if not resume_id:
                raise ResumeParsingError("Resume ID is required")
            
            # Use agent if available, otherwise raise exception (NO SILENT FALLBACK)
            if self.agent_executor:
                parsed_data = self._parse_with_agent(resume_text, resume_id, clear_memory, conversation_context)
            else:
                # CRITICAL: Do NOT silently fallback - agent executor should be available
                self.logger.error("CRITICAL: Agent executor is None - agent initialization failed")
                raise ResumeParsingError(
                    "Agent executor not available - agent initialization failed. Check logs for initialization errors.",
                    error_code="AGENT_EXECUTOR_NOT_AVAILABLE",
                    details={"resume_id": resume_id}
                )
            
            processing_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            self.logger.info(f"Resume parsing completed successfully in {processing_time:.2f}ms")
            
            return ResumeParsingResult(
                success=True,
                data=parsed_data,
                processing_time_ms=processing_time,
                metadata={
                    "resume_id": resume_id,
                    "text_length": len(resume_text),
                    "parsing_method": parsed_data.parsing_method
                }
            )
            
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            self.logger.error(f"Resume parsing failed: {e}", exc_info=True)
            
            return ResumeParsingResult(
                success=False,
                error=str(e),
                error_code=getattr(e, 'error_code', 'PARSING_ERROR'),
                processing_time_ms=processing_time,
                metadata={
                    "resume_id": resume_id,
                    "error_type": type(e).__name__
                }
            )
    
    def _parse_with_agent(
        self, 
        resume_text: str, 
        resume_id: str,
        clear_memory: bool = False,
        conversation_context: Optional[str] = None
    ) -> ParsedResumeData:
        """Parse resume using autonomous AI agent with context memory.
        
        Args:
            resume_text: Resume text content
            resume_id: Unique resume identifier
            clear_memory: If True, clear memory before parsing (default: False for continuous flow)
            conversation_context: Optional context from previous conversations to maintain flow
            
        Returns:
            ParsedResumeData instance
        """
        # Only clear memory if explicitly requested (for continuous flow, keep memory)
        if clear_memory and self.memory:
            try:
                self.logger.info("Clearing agent memory for fresh session...")
                self.memory.clear()
                self.logger.info("✅ Memory cleared")
            except Exception as e:
                self.logger.warning(f"Failed to clear memory: {e}")
        elif self.memory:
            # Check if memory has content
            try:
                memory_vars = self.memory.load_memory_variables({})
                chat_history = memory_vars.get("chat_history", "")
                if chat_history:
                    self.logger.info(f"📝 Maintaining context memory ({len(chat_history)} chars of history)")
                else:
                    self.logger.info("📝 Starting with fresh memory (no previous context)")
            except:
                self.logger.info("📝 Memory available but unable to check history")
        
        # Truncate resume text if needed
        truncated_text = resume_text[:self.settings.resume_text_truncate_length]
        
        # Build context-aware prompt
        context_section = ""
        if conversation_context:
            context_section = f"""
PREVIOUS CONVERSATION CONTEXT:
{conversation_context}

Use this context to maintain continuity and provide relevant answers that build upon previous interactions.
"""
        
        # Check memory for previous context
        memory_context = ""
        if self.memory:
            try:
                memory_vars = self.memory.load_memory_variables({})
                chat_history = memory_vars.get("chat_history", "")
                if chat_history and len(chat_history) > 50:  # Only use if substantial
                    memory_context = f"""
PREVIOUS PARSING SESSION CONTEXT (from memory):
{chat_history[:500]}... [truncated for efficiency]

Use this context to maintain continuity with previous resume parsing sessions and provide consistent, relevant answers.
"""
            except Exception as e:
                self.logger.debug(f"Could not load memory context: {e}")
        
        # Create agent prompt with context memory
        agent_prompt = f"""You are an expert resume parsing AI agent with access to multiple tools and a vector database.
You maintain context memory across parsing sessions to provide continuous, relevant answers.

Your task is to parse the following resume and extract ALL information:

RESUME TEXT:
{truncated_text}... [truncated for efficiency]
{context_section}
{memory_context}
AVAILABLE TOOLS:
1. {ToolName.EXTRACT_PERSONAL_INFO} - Extract name, email, phone, location, LinkedIn, GitHub
2. {ToolName.EXTRACT_SKILLS} - Extract technical skills, soft skills, tools, certifications
3. {ToolName.EXTRACT_EXPERIENCE} - Extract work experience, positions, companies, years
4. {ToolName.EXTRACT_EDUCATION} - Extract degrees, institutions, graduation years, GPA
5. {ToolName.ENHANCE_WITH_RAG_AI} - Enhance data using RAG (Milvus) and AI insights

INSTRUCTIONS:
1. Start by using {ToolName.EXTRACT_PERSONAL_INFO} to get basic information
2. Then use {ToolName.EXTRACT_SKILLS} to identify all technical and soft skills
3. Next use {ToolName.EXTRACT_EXPERIENCE} to extract work history
4. Then use {ToolName.EXTRACT_EDUCATION} to get education details
5. Finally, use {ToolName.ENHANCE_WITH_RAG_AI} to enrich the data with RAG and AI insights

CRITICAL ACCURACY REQUIREMENTS:
- VERIFY the extracted name is the ACTUAL candidate name, not a section header (like "UI", "UX", "Summary", "Professional Summary", etc.)
- Look for explicit "Name:" labels in the resume - if you see "Name: [Candidate Name]", use that exact name
- If the name looks incorrect (too short, is a common word, or matches a section header), analyze the resume text to find the REAL candidate name
- Extract ALL skills mentioned in the resume, including:
  * Skills listed in the "Skills" section (all bullet points)
  * Technologies mentioned in job descriptions
  * Tools and frameworks used in projects
  * Programming languages mentioned anywhere
  * Certifications listed in "Certifications" section (include certification names as skills)
  * Don't miss any skills - be comprehensive and thorough
- Calculate experience years ACCURATELY by analyzing job dates and durations
- Ensure email addresses are correctly extracted and validated
- Double-check all extracted data against the original resume text for accuracy
- If tool outputs seem incorrect, use your reasoning to correct them based on the resume text

IMPORTANT:
- Use ALL tools in sequence
- VALIDATE and CORRECT tool outputs using your reasoning - tools may make mistakes
- Save intermediate results
- Combine all extractions into final structured result
- Return comprehensive, well-structured data with ACCURATE information
- Ensure all fields are populated correctly
- Maintain context from previous sessions for continuous flow
- Provide relevant answers that build upon previous interactions

Begin parsing now. Be thorough and accurate.
"""
        
        self.logger.info("Agent reasoning and using tools autonomously...")
        self.logger.info(f"Agent executor available: {self.agent_executor is not None}")
        self.logger.info(f"LLM service available: {self.llm_service is not None and self.llm_service.is_available()}")
        self.logger.info(f"Tools count: {len(self.tools)}")
        self.logger.info(f"Memory available: {self.memory is not None}")
        
        # Execute agent with error handling and timeout
        try:
            self.logger.info("Invoking agent executor...")
            self.logger.debug(f"Agent prompt length: {len(agent_prompt)} characters")
            
            # Ensure input is not empty
            if not agent_prompt or not agent_prompt.strip():
                raise ResumeParsingError(
                    "Agent prompt is empty",
                    error_code="EMPTY_PROMPT",
                    details={"resume_id": resume_id}
                )
            
            # Check if this is a LangGraph agent or legacy LangChain agent
            is_langgraph = hasattr(self.agent_executor, 'get_state')
            self.logger.info(f"Agent type: {'LangGraph' if is_langgraph else 'Legacy LangChain'}")
            
            if is_langgraph:
                # LangGraph ReAct agent invocation
                try:
                    from langchain_core.messages import HumanMessage
                except ImportError:
                    from langchain.schema import HumanMessage
                
                import uuid
                thread_id = str(uuid.uuid4())
                config = {"configurable": {"thread_id": thread_id}}
                
                self.logger.info("Executing LangGraph ReAct agent...")
                result = self.agent_executor.invoke(
                    {"messages": [HumanMessage(content=agent_prompt.strip())]},
                    config=config
                )
                self.logger.info("LangGraph agent completed parsing")
            else:
                # Legacy LangChain agent invocation
                self.logger.info("Executing legacy LangChain agent...")
                result = self.agent_executor.invoke({
                    "input": agent_prompt.strip()
                })
                self.logger.info("Legacy agent completed parsing")
            
            self.logger.debug(f"Agent result type: {type(result)}")
            self.logger.debug(f"Agent result keys: {result.keys() if isinstance(result, dict) else 'Not a dict'}")
        except Exception as agent_error:
            self.logger.error(f"Agent executor invoke failed: {agent_error}", exc_info=True)
            self.logger.error(f"Error type: {type(agent_error).__name__}")
            self.logger.error(f"Error details: {str(agent_error)}")
            # Print full traceback for debugging
            import traceback
            self.logger.error(f"Full traceback:\n{traceback.format_exc()}")
            # Re-raise to be caught by outer try-except in parse_resume
            raise ResumeParsingError(
                f"Agent execution failed: {str(agent_error)}",
                error_code="AGENT_EXECUTION_ERROR",
                details={"error_type": type(agent_error).__name__, "error": str(agent_error)}
            )
        
        # Extract structured data from agent's tool executions
        extracted_data = self._extract_data_from_agent_result(result)
        
        # Merge with local extraction if needed
        # Always supplement with local extraction for experience if agent didn't extract it properly
        local_data = LocalExtractor.extract_all(resume_text)
        
        # Log local extraction results for debugging
        local_exp = local_data.get("experience", {})
        local_years = local_exp.get("total_years", 0) if isinstance(local_exp, dict) else 0
        self.logger.info(f"Local extraction experience: {local_years} years")
        
        # Merge missing or incomplete data
        for key in ["personal_info", "skills", "experience", "education"]:
            if not extracted_data.get(key):
                extracted_data[key] = local_data.get(key, {})
                self.logger.info(f"Using local extraction for {key} (agent had none)")
            elif key == "experience":
                # For experience, ALWAYS prefer local extraction if it has > 0 years
                agent_exp = extracted_data.get("experience", {})
                if isinstance(agent_exp, dict) and isinstance(local_exp, dict):
                    agent_years = agent_exp.get("total_years", 0)
                    local_years = local_exp.get("total_years", 0)
                    
                    # CRITICAL: Use local extraction if it has better experience data
                    if agent_years == 0 and local_years > 0:
                        self.logger.info(f"✅ Using local extraction for experience: {local_years} years (agent had {agent_years})")
                        extracted_data["experience"] = local_exp
                    elif agent_years > 0 and local_years > agent_years:
                        # Local extraction found more years - use it
                        self.logger.info(f"✅ Using local extraction for experience: {local_years} years (agent had {agent_years})")
                        extracted_data["experience"] = local_exp
                    elif agent_years > 0:
                        # Agent has valid years, but merge positions if needed
                        self.logger.info(f"Using agent extraction: {agent_years} years")
                        if not agent_exp.get("positions") and local_exp.get("positions"):
                            extracted_data["experience"]["positions"] = local_exp.get("positions", [])
                    else:
                        # Both are 0, but try local extraction anyway (it might have better logic)
                        if local_years == 0:
                            self.logger.warning("Both agent and local extraction returned 0 years")
                        else:
                            extracted_data["experience"] = local_exp
        
        # Enhance with RAG if not already done
        if not extracted_data.get("enhanced"):
            self.logger.info("Enhancing with RAG and AI...")
            combined_data = {
                "personal_info": extracted_data.get("personal_info", {}),
                "skills": extracted_data.get("skills", {}),
                "experience": extracted_data.get("experience", {}),
                "education": extracted_data.get("education", {})
            }
            enhanced_data = self._enhance_with_rag_ai(combined_data)
            extracted_data["enhanced"] = enhanced_data
        
        # Build parsed data model
        return self._build_parsed_data(resume_text, resume_id, extracted_data, ParsingMethod.TRUE_AI_AGENT_LANGCHAIN)

    @staticmethod
    def _normalize_tool_name(name: str) -> str:
        """Map LangGraph/LangChain tool names to ToolName enum values."""
        if not name:
            return ""
        normalized = name.strip().removesuffix("_tool")
        aliases = {
            "enhance_with_rag": ToolName.ENHANCE_WITH_RAG_AI.value,
        }
        return aliases.get(normalized, normalized)

    def _parse_tool_payload(self, payload: Any) -> Any:
        """Parse JSON tool output when possible."""
        if isinstance(payload, dict):
            return payload
        if isinstance(payload, str) and payload.strip().startswith("{"):
            try:
                return json.loads(payload)
            except json.JSONDecodeError:
                return payload
        return payload

    def _apply_tool_result(self, extracted_data: Dict[str, Any], tool_name: str, payload: Any) -> None:
        """Merge a single tool result into extracted_data."""
        normalized = self._normalize_tool_name(tool_name)
        tool_result = self._parse_tool_payload(payload)
        if not isinstance(tool_result, dict):
            return

        if normalized == ToolName.EXTRACT_PERSONAL_INFO:
            extracted_data["personal_info"] = tool_result
        elif normalized == ToolName.EXTRACT_SKILLS:
            extracted_data["skills"] = tool_result
        elif normalized == ToolName.EXTRACT_EXPERIENCE:
            total_years = tool_result.get("total_years", 0)
            self.logger.info("Extracted experience: %s years from tool", total_years)
            extracted_data["experience"] = tool_result
        elif normalized == ToolName.EXTRACT_EDUCATION:
            extracted_data["education"] = tool_result
        elif normalized == ToolName.ENHANCE_WITH_RAG_AI:
            extracted_data["enhanced"] = tool_result
    
    def _extract_data_from_agent_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract structured data from agent execution result.
        
        Args:
            result: Agent execution result (supports both LangGraph and legacy formats)
            
        Returns:
            Dictionary with extracted data
        """
        extracted_data = {
            "personal_info": {},
            "skills": {},
            "experience": {},
            "education": {},
            "enhanced": {}
        }
        
        # Handle LangGraph result format (messages with tool_calls)
        if "messages" in result:
            self.logger.info("Processing LangGraph agent result...")
            messages = result.get("messages", [])

            for msg in messages:
                if hasattr(msg, "tool_calls"):
                    for tc in msg.tool_calls or []:
                        tool_name = tc.get("name", "")
                        tool_result = tc.get("output", tc.get("args", {}))
                        self._apply_tool_result(extracted_data, tool_name, tool_result)

                tool_name = getattr(msg, "name", "") or ""
                tool_content = getattr(msg, "content", "")
                if tool_name:
                    self._apply_tool_result(extracted_data, tool_name, tool_content)

            return extracted_data
        
        # Handle legacy LangChain result format (intermediate_steps)
        if "intermediate_steps" in result:
            for step in result.get("intermediate_steps", []):
                action = step[0] if len(step) > 0 else None
                observation = step[1] if len(step) > 1 else ""
                
                if action and hasattr(action, 'tool'):
                    tool_name = action.tool
                    try:
                        # Parse JSON responses from tools
                        if isinstance(observation, str) and observation.strip().startswith('{'):
                            tool_result = json.loads(observation)
                        else:
                            tool_result = observation
                        
                        if tool_name == ToolName.EXTRACT_PERSONAL_INFO:
                            extracted_data["personal_info"] = tool_result if isinstance(tool_result, dict) else {}
                        elif tool_name == ToolName.EXTRACT_SKILLS:
                            extracted_data["skills"] = tool_result if isinstance(tool_result, dict) else {}
                        elif tool_name == ToolName.EXTRACT_EXPERIENCE:
                            if isinstance(tool_result, dict):
                                # Log the extracted experience for debugging
                                total_years = tool_result.get("total_years", 0)
                                self.logger.info(f"Extracted experience: {total_years} years from tool")
                                
                                # Validate positions structure - ensure they are dicts, not strings
                                positions = tool_result.get("positions", [])
                                if positions and isinstance(positions, list):
                                    fixed_positions = []
                                    for pos in positions:
                                        if isinstance(pos, str):
                                            # Convert string to dict
                                            fixed_positions.append({
                                                "title": pos.strip(),
                                                "company": "",
                                                "duration": "",
                                                "description": ""
                                            })
                                        elif isinstance(pos, dict):
                                            fixed_positions.append(pos)
                                    tool_result["positions"] = fixed_positions
                                
                                # Ensure total_years is preserved
                                if total_years == 0:
                                    self.logger.warning("Tool returned 0 years - this might be incorrect")
                                
                                extracted_data["experience"] = tool_result
                            else:
                                self.logger.warning(f"Tool result is not a dict: {type(tool_result)}")
                                extracted_data["experience"] = {}
                        elif tool_name == ToolName.EXTRACT_EDUCATION:
                            extracted_data["education"] = tool_result if isinstance(tool_result, dict) else {}
                        elif tool_name == ToolName.ENHANCE_WITH_RAG_AI:
                            extracted_data["enhanced"] = tool_result if isinstance(tool_result, dict) else {}
                    except (json.JSONDecodeError, AttributeError) as e:
                        self.logger.warning(f"Failed to parse tool result for {tool_name}: {e}")
        
        return extracted_data
    
    def _parse_with_fallback(self, resume_text: str, resume_id: str) -> ParsedResumeData:
        """Parse resume using fallback regex extraction.
        
        Args:
            resume_text: Resume text content
            resume_id: Unique resume identifier
            
        Returns:
            ParsedResumeData instance
        """
        self.logger.info("Using fallback parsing method")
        
        # Extract all data locally
        local_data = LocalExtractor.extract_all(resume_text)
        
        # Build parsed data model
        return self._build_parsed_data(
            resume_text,
            resume_id,
            local_data,
            ParsingMethod.BASIC_REGEX_FALLBACK
        )
    
    def _build_parsed_data(
        self,
        resume_text: str,
        resume_id: str,
        extracted_data: Dict[str, Any],
        parsing_method: ParsingMethod
    ) -> ParsedResumeData:
        """Build ParsedResumeData model from extracted data.
        
        Args:
            resume_text: Original resume text
            resume_id: Resume identifier
            extracted_data: Extracted data dictionary
            parsing_method: Parsing method used
            
        Returns:
            ParsedResumeData instance
        """
        # Get enhanced data
        enhanced = extracted_data.get("enhanced", {})
        
        # Validate and correct personal info (especially name)
        personal_info = extracted_data.get("personal_info", {})
        if personal_info:
            name = personal_info.get("name", "").strip()
            
            # Validate name - check if it looks like a section header
            invalid_name_patterns = [
                'professional summary', 'executive summary', 'summary', 'objective', 'profile',
                'experience', 'work experience', 'education', 'skills', 'technical skills',
                'contact', 'contact information', 'projects', 'certifications', 'resume', 'cv',
                'ui', 'ux', 'data scientist', 'software engineer', 'developer'
            ]
            
            # Clean up name: Remove dashes between single characters (PDF extraction artifact)
            # Pattern: "-K-A-R-A-N- -K-U-M-A-R-" -> "KARAN KUMAR"
            if name and '-' in name:
                name_parts = name.split()
                cleaned_parts = []
                for part in name_parts:
                    # If part looks like "-K-A-R-A-N-", clean it
                    if part.startswith('-') and part.endswith('-') and len(part) > 2:
                        # Remove leading and trailing dashes, then remove dashes between single chars
                        cleaned = part.strip('-')
                        # If pattern is like "K-A-R-A-N", join without dashes
                        if '-' in cleaned and all(len(c) == 1 for c in cleaned.split('-')):
                            cleaned = cleaned.replace('-', '')
                        cleaned_parts.append(cleaned)
                    else:
                        cleaned_parts.append(part)
                name = ' '.join(cleaned_parts)
                personal_info["name"] = name
                if name != personal_info.get("name", ""):
                    self.logger.info(f"Cleaned name from PDF extraction artifact: '{personal_info.get('name', '')}' -> '{name}'")
            
            if name.lower() in invalid_name_patterns or len(name.split()) == 1:
                # Try to find the actual name in the resume text
                self.logger.warning(f"Invalid name detected: '{name}', attempting to find correct name")
                
                # Look for "Name:" label
                name_label_match = re.search(r'name\s*:?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})', resume_text, re.IGNORECASE)
                if name_label_match:
                    corrected_name = name_label_match.group(1).strip()
                    personal_info["name"] = corrected_name
                    self.logger.info(f"Corrected name from '{name}' to '{corrected_name}'")
                else:
                    # Try to find name pattern in first few lines
                    lines = [line.strip() for line in resume_text.splitlines() if line.strip()]
                    for line in lines[:10]:
                        if re.match(r'^[A-Z][a-z]+\s+[A-Z][a-z]+', line) and len(line.split()) <= 4:
                            if line.lower() not in invalid_name_patterns:
                                personal_info["name"] = line
                                self.logger.info(f"Corrected name from '{name}' to '{line}'")
                                break
        
        # Validate and fix experience data structure
        experience_data = extracted_data.get("experience", {})
        if isinstance(experience_data, dict):
            positions = experience_data.get("positions", [])
            # Convert string positions to dictionaries if needed
            if positions and isinstance(positions, list):
                fixed_positions = []
                for pos in positions:
                    if isinstance(pos, str):
                        # Convert string to dict
                        fixed_positions.append({
                            "title": pos.strip(),
                            "company": "",
                            "duration": "",
                            "description": ""
                        })
                    elif isinstance(pos, dict):
                        # Already a dict, use as is
                        fixed_positions.append(pos)
                    else:
                        # Invalid type, skip
                        self.logger.warning(f"Invalid position type: {type(pos)}, skipping")
                experience_data["positions"] = fixed_positions
        
        # Validate and deduplicate skills
        skills_data = extracted_data.get("skills", {})
        if isinstance(skills_data, dict):
            # Common invalid skill patterns
            invalid_patterns = [
                'skills', 'skill', 'ed in', 'in designing', 'and', 'the', 'a', 'an',
                'secure', 'scalable', 'cost', 'optimized', 'designing', 'skilled',
                'architect', 'architectural', 'led', 'built', 'ensured'
            ]
            
            for skill_type in ["technical_skills", "soft_skills", "tools", "certifications"]:
                if skill_type in skills_data and isinstance(skills_data[skill_type], list):
                    # Remove duplicates and invalid entries (case-insensitive)
                    seen = set()
                    unique_skills = []
                    for skill in skills_data[skill_type]:
                        if not isinstance(skill, str):
                            skill = str(skill)
                        
                        skill = skill.strip()
                        skill_lower = skill.lower()
                        
                        # Skip empty or very short skills
                        if not skill or len(skill) < 2:
                            continue
                        
                        # Skip invalid patterns
                        if skill_lower in invalid_patterns:
                            continue
                        
                        # Skip if it contains common sentence fragments
                        if any(pattern in skill_lower for pattern in ['ed in', 'ing ', ' the ', ' a ', ' an ', 'and ', ' or ']):
                            # But allow common technical terms even if they contain these patterns
                            common_tech_terms = ['aws', 'azure', 'gcp', 'terraform', 'kubernetes', 'docker', 
                                                'python', 'java', 'javascript', 'react', 'angular', 'vue',
                                                'node.js', 'django', 'flask', 'spring', 'express']
                            if not any(term in skill_lower for term in common_tech_terms):
                                continue
                        
                        # Skip if it's just a single common word (unless it's a known skill)
                        if len(skill.split()) == 1 and skill_lower in ['secure', 'scalable', 'cost', 'designing', 'skilled']:
                            continue
                        
                        # Final validation: should be 2-50 chars, mostly alphanumeric
                        if not (2 <= len(skill) <= 50 and re.match(r'^[A-Za-z][A-Za-z0-9\s\-&.]+$', skill)):
                            continue
                        
                        # Check for duplicates (case-insensitive, also check if one is substring of another)
                        is_duplicate = False
                        for seen_skill in seen:
                            if skill_lower == seen_skill.lower() or skill_lower in seen_skill.lower() or seen_skill.lower() in skill_lower:
                                # Keep the longer/more complete version
                                if len(skill) > len(seen_skill):
                                    # Remove the shorter one and add the longer one
                                    if seen_skill.lower() in unique_skills:
                                        unique_skills = [s for s in unique_skills if s.lower() != seen_skill.lower()]
                                        seen.remove(seen_skill.lower())
                                else:
                                    is_duplicate = True
                                break
                        
                        if not is_duplicate:
                            unique_skills.append(skill)
                            seen.add(skill_lower)
                    
                    skills_data[skill_type] = unique_skills
        
        # Build model
        return ParsedResumeData(
            id=resume_id,
            raw_text=resume_text,
            content=resume_text,
            upload_date=datetime.now().isoformat(),
            parsing_method=parsing_method.value,
            match_percentage=DEFAULT_MATCH_PERCENTAGE if parsing_method == ParsingMethod.TRUE_AI_AGENT_LANGCHAIN else DEFAULT_FALLBACK_MATCH_PERCENTAGE,
            active_applications=1,
            security_status=SecurityStatus.HYBRID_SECURE.value,
            agent_version=AGENT_VERSION,
            tools_used=[tool.name for tool in self.tools] if self.tools else [],
            memory_enabled=self.memory is not None,
            rag_enabled=False,  # Deprecated - use QueryRouter/QuantChat AI
            personal_info=PersonalInfo(**extracted_data.get("personal_info", {})),
            skills=Skills(**extracted_data.get("skills", {})),
            experience=Experience(**experience_data),
            education=Education(**extracted_data.get("education", {})),
            summary=enhanced.get("summary", ""),
            strengths=enhanced.get("strengths", []),
            career_insights=enhanced.get("career_insights", [])
        )







