"""
JD Generation Orchestrator
===========================
Main orchestrator that coordinates LangGraph workflow and CrewAI agents.
"""

import logging
import os
import warnings
from typing import Any, Dict, Optional

# Suppress LangChain deprecation warning for ChatVertexAI
warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain_google_vertexai")

# LangSmith is optional - make imports conditional
try:
    from langsmith import Client, traceable
    LANGSMITH_AVAILABLE = True
except ImportError:
    LANGSMITH_AVAILABLE = False
    # Create a no-op decorator if langsmith is not available
    def traceable(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    Client = None

from agents.jd_generation.state_machine import JDGenerationWorkflow
from agents.jd_generation.exceptions import (
    JDGenerationError,
    WorkflowError,
    AgentError,
)
from agents.jd_generation.retry import retry_with_backoff, RetryConfig

logger = logging.getLogger(__name__)


class JDGenerationOrchestrator:
    """
    Main orchestrator for JD generation.
    
    Coordinates:
    - LangGraph state machine for workflow orchestration
    - CrewAI multi-agent collaboration
    - LangSmith observability
    """
    
    def __init__(self, config=None):
        """
        Initialize orchestrator with configuration.
        
        Args:
            config: JDGenerationConfig instance (uses global config if not provided)
        """
        from agents.jd_generation.config import JDGenerationConfig, get_config
        from agents.jd_generation.exceptions import ConfigurationError
        
        self.config: JDGenerationConfig = config or get_config()

        try:
            from agents.llm.chat_factory import llm_status

            logger.info("JD generation LLM ready: %s", llm_status())
        except Exception as exc:
            logger.warning("JD generation LLM status log failed: %s", exc)
        
        # Validate configuration
        try:
            self.config.validate()
        except ValueError as e:
            raise ConfigurationError(
                message=str(e),
                details={"config_errors": [str(e)]}
            )
        
        # Initialize LangSmith client for observability (if configured and available)
        if self.config.is_langsmith_configured and LANGSMITH_AVAILABLE and Client is not None:
            langsmith_config = self.config.get_langsmith_config()
            try:
                self.langsmith_client = Client(api_key=langsmith_config["api_key"])
                logger.info(
                    "LangSmith client initialized for observability",
                    extra={"project": langsmith_config["project"]}
                )
                # Set environment variables for LangChain tracing
                import os
                os.environ["LANGCHAIN_TRACING_V2"] = "true"
                os.environ["LANGCHAIN_API_KEY"] = langsmith_config["api_key"]
                os.environ["LANGCHAIN_PROJECT"] = langsmith_config["project"]
            except Exception as e:
                logger.warning(f"Failed to initialize LangSmith client: {e}")
                self.langsmith_client = None
        else:
            self.langsmith_client = None
            if not LANGSMITH_AVAILABLE:
                logger.info("LangSmith package not installed - observability limited")
            else:
                logger.info("LangSmith not configured - observability limited")
        
        # Initialize workflow with configuration (dependency injection)
        self.workflow = JDGenerationWorkflow(config=self.config)
        
        logger.info(
            "JD Generation Orchestrator initialized",
            extra={
                "langsmith_enabled": self.config.is_langsmith_configured,
                "autonomous_features": {
                    "reasoning": self.config.enable_autonomous_reasoning,
                    "reflection": self.config.enable_self_reflection,
                    "planning": self.config.enable_adaptive_planning,
                    "recovery": self.config.enable_error_recovery,
                }
            }
        )
    
    @traceable(name="generate_jd", run_type="chain")
    def generate_job_description(
        self,
        job_title: str,
        job_level: str,
        department: str,
        location: Optional[str] = None,
        remote_allowed: bool = False,
        user_requirements: Optional[str] = None,
        user_edits: Optional[Dict[str, Any]] = None,
        preserve_hr_inputs: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate Job Description using multi-agent system.
        
        Args:
            job_title: Job title
            job_level: Job level (e.g., "Senior", "Mid-level")
            department: Department name
            location: Job location
            remote_allowed: Whether remote work is allowed
            user_requirements: Additional user requirements
            user_edits: User customizations to apply
            
        Returns:
            Generated JD with metadata
            
        Raises:
            ValidationError: If input validation fails
            WorkflowError: If workflow execution fails
        """
        from agents.jd_generation.exceptions import ValidationError
        
        # Input validation
        if not job_title or not job_title.strip():
            raise ValidationError(
                message="Job title is required",
                field="job_title"
            )
        
        # Job level is optional, default to "Mid-level" if not provided
        if not job_level or not job_level.strip():
            job_level = "Mid-level"
        
        if not department or not department.strip():
            raise ValidationError(
                message="Department is required",
                field="department"
            )
        
        # Validate input length
        if len(job_title) > self.config.max_input_length:
            raise ValidationError(
                message=f"Job title exceeds maximum length of {self.config.max_input_length}",
                field="job_title"
            )
        
        logger.info(
            "Starting JD generation",
            extra={
                "job_title": job_title,
                "job_level": job_level,
                "department": department,
                "location": location,
            }
        )
        
        # Prepare input
        input_data = {
            "job_title": job_title.strip(),
            "job_level": job_level.strip(),
            "department": department.strip(),
            "location": location.strip() if location else None,
            "remote_allowed": remote_allowed,
            "user_requirements": user_requirements.strip() if user_requirements else None,
            "user_edits": user_edits,
        }
        
        # Execute workflow with retry logic
        retry_config = RetryConfig(
            max_retries=self.config.max_retries,
            initial_delay=self.config.retry_delay,
        )
        
        @retry_with_backoff(
            retry_config=retry_config,
            retryable_exceptions=(WorkflowError, AgentError),
        )
        def _execute_workflow() -> Dict[str, Any]:
            """Execute workflow with retry logic."""
            try:
                result = self.workflow.run(input_data)
                
                # Extract final JD - check each stage for content
                final_jd = result.get("final_jd")
                validated_jd = result.get("validated_jd")
                refined_jd = result.get("refined_jd")
                initial_jd = result.get("initial_jd")
                
                # Log what we have at each stage
                logger.info("📊 JD Pipeline Results:")
                logger.info(f"   - initial_jd: {self._describe_jd(initial_jd)}")
                logger.info(f"   - refined_jd: {self._describe_jd(refined_jd)}")
                logger.info(f"   - validated_jd: {self._describe_jd(validated_jd)}")
                logger.info(f"   - final_jd: {self._describe_jd(final_jd)}")
                
                # Use the best available JD (prefer later stages, but check for content)
                final_jd = self._select_best_jd(final_jd, validated_jd, refined_jd, initial_jd)
                
                # ALWAYS enforce Malomatia company defaults AND preserve original job title
                if final_jd and isinstance(final_jd, dict):
                    original_title = input_data["job_title"]
                    user_reqs = input_data.get("user_requirements")
                    
                    if not preserve_hr_inputs:
                        logger.info(
                            "AI Agent validating JD relevance for '%s'...",
                            original_title,
                        )
                        final_jd = self._validate_and_fix_jd_relevance(
                            final_jd, original_title, user_reqs
                        )
                    else:
                        logger.info(
                            "Skipping extra relevance LLM pass — API will enforce HR matrix inputs"
                        )
                    
                    # Enforce Malomatia defaults while preserving user's location, department, and remote preference
                    user_location = input_data.get("location")
                    user_department = input_data.get("department")
                    remote_allowed = input_data.get("remote_allowed", False)
                    final_jd = self._enforce_malomatia_defaults(
                        final_jd, 
                        user_location=user_location,
                        user_department=user_department,
                        remote_allowed=remote_allowed
                    )
                    
                    # CRITICAL: Preserve the EXACT job title and department user entered
                    final_jd["job_title"] = original_title
                    if user_department:
                        final_jd["department"] = user_department
                    logger.info(f"✅ Enforced original job title: {original_title}")
                    if user_department:
                        logger.info(f"✅ Enforced original department: {user_department}")
                    
                    # CRITICAL: Deduplicate and fix repetitive responsibilities
                    # This is the FINAL cleanup step to ensure no repetitive patterns like
                    # "Apply X expertise to deliver project objectives" remain in the output
                    from agents.jd_generation.crew_agents import deduplicate_responsibilities
                    if 'responsibilities' in final_jd and isinstance(final_jd['responsibilities'], list):
                        job_level = input_data.get("job_level", final_jd.get("job_level", ""))
                        original_count = len(final_jd['responsibilities'])
                        final_jd['responsibilities'] = deduplicate_responsibilities(
                            final_jd['responsibilities'], 
                            job_level
                        )
                        new_count = len(final_jd['responsibilities'])
                        if new_count != original_count:
                            logger.info(f"🔄 Deduplicated responsibilities: {original_count} → {new_count}")
                    
                    job_level = input_data.get("job_level", final_jd.get("job_level", "")).lower()
                    if not preserve_hr_inputs and 'required_qualifications' in final_jd and isinstance(final_jd['required_qualifications'], dict):
                        rq = final_jd['required_qualifications']
                        current_exp = rq.get('experience', '')
                        if current_exp:
                            import re
                            years_match = re.search(r'(\d+)\+?\s*(?:years?|yrs?)', current_exp.lower())
                            
                            if 'junior' in job_level or 'entry' in job_level:
                                if years_match and int(years_match.group(1)) >= 3:
                                    logger.warning(
                                        "Fixing experience '%s' for %s level",
                                        years_match.group(0),
                                        job_level,
                                    )
                                    rq['experience'] = "0-2 years of relevant experience. Internships and academic projects count towards experience. Recent graduates are welcome to apply."
                            elif 'mid' in job_level or 'intermediate' in job_level:
                                if years_match and (int(years_match.group(1)) < 3 or int(years_match.group(1)) > 5):
                                    logger.warning(
                                        "Fixing experience '%s' for %s level",
                                        years_match.group(0),
                                        job_level,
                                    )
                                    rq['experience'] = "3-5 years of professional experience in the field."
                            elif 'senior' in job_level:
                                if years_match and int(years_match.group(1)) < 5:
                                    logger.warning(
                                        "Fixing experience '%s' for %s level",
                                        years_match.group(0),
                                        job_level,
                                    )
                                    rq['experience'] = "5-8 years of extensive professional experience. Demonstrated expertise in leading technical initiatives and mentoring team members."
                            elif 'lead' in job_level or 'principal' in job_level:
                                if years_match and int(years_match.group(1)) < 8:
                                    logger.warning(
                                        "Fixing experience '%s' for %s level",
                                        years_match.group(0),
                                        job_level,
                                    )
                                    rq['experience'] = "8+ years of progressive professional experience with proven leadership and technical expertise."
                    
                    if not preserve_hr_inputs and 'position_summary' in final_jd and ('junior' in job_level or 'entry' in job_level):
                        summary = final_jd.get('position_summary', '')
                        # Check for senior-sounding language and add junior-appropriate framing
                        senior_phrases = ['lead', 'mentor', 'oversee', 'strategic', 'autonomous', 'independently manage']
                        needs_junior_update = any(phrase in summary.lower() for phrase in senior_phrases)
                        if needs_junior_update or 'under guidance' not in summary.lower():
                            
                            final_jd['position_summary'] = f"We are seeking an enthusiastic and motivated {job_level} {original_title} to join our team. This is an excellent opportunity to begin or advance your career in a supportive and growth-oriented environment. The ideal candidate will work under the guidance of senior team members, learning and contributing to projects while developing foundational skills. This role is perfect for recent graduates or early-career professionals eager to apply their knowledge to real-world challenges."
                            logger.info(f"✅ Updated position summary to be Junior-appropriate")
                    
                    if not preserve_hr_inputs and 'reports_to' in final_jd:
                        current_reports = final_jd.get('reports_to', '').lower()
                        if 'junior' in job_level or 'entry' in job_level:
                            if 'manager' in current_reports or 'director' in current_reports:
                                final_jd['reports_to'] = 'Team Lead or Senior Engineer'
                                logger.info(f"✅ Updated reports_to to be Junior-appropriate: Team Lead or Senior Engineer")
                        elif 'mid' in job_level or 'intermediate' in job_level:
                            if 'director' in current_reports or 'senior' in current_reports:
                                final_jd['reports_to'] = 'Team Lead or Engineering Manager'
                                logger.info(f"✅ Updated reports_to to be Mid-appropriate: Team Lead or Engineering Manager")
                    
                    if not preserve_hr_inputs and 'responsibilities' in final_jd and ('junior' in job_level or 'entry' in job_level):
                        fixed_responsibilities = []
                        for resp in final_jd['responsibilities']:
                            resp_lower = resp.lower()
                            # Remove senior-level responsibilities completely
                            if any(x in resp_lower for x in ['conduct code reviews', 'mentor', 'lead team', 'manage team', 'strategic planning', 'architecture decisions']):
                                logger.info(f"🔄 Removing senior responsibility from Junior JD: {resp[:50]}...")
                                continue
                            # Transform senior verbs to junior verbs
                            if resp.startswith('Lead '):
                                resp = resp.replace('Lead ', 'Assist with ', 1)
                            elif resp.startswith('Manage '):
                                resp = resp.replace('Manage ', 'Support ', 1)
                            elif resp.startswith('Oversee '):
                                resp = resp.replace('Oversee ', 'Participate in ', 1)
                            elif resp.startswith('Architect '):
                                resp = resp.replace('Architect ', 'Learn about ', 1)
                            fixed_responsibilities.append(resp)
                        if len(fixed_responsibilities) < len(final_jd['responsibilities']):
                            logger.info(f"🔄 Removed {len(final_jd['responsibilities']) - len(fixed_responsibilities)} senior responsibilities from Junior JD")
                        final_jd['responsibilities'] = fixed_responsibilities
                    
                    # CRITICAL: Ensure success_metrics are present and not empty
                    success_metrics = final_jd.get('success_metrics', [])
                    if not success_metrics or len(success_metrics) == 0:
                        logger.warning(f"⚠️ success_metrics is empty for {original_title}. Generating fallback metrics.")
                        fallback_metrics = self._generate_fallback_success_metrics(original_title)
                        final_jd['success_metrics'] = fallback_metrics
                        logger.info(f"✅ Added {len(fallback_metrics)} fallback success metrics for {original_title}")
                
                # Prepare response
                response = {
                    "success": result.get("workflow_complete", False),
                    "job_id": result.get("job_id"),
                    "milvus_id": result.get("milvus_id"),
                    "jd": final_jd,
                    "agent_thoughts": result.get("agent_thoughts", []),
                    "workflow_states": self._extract_workflow_states(result),
                    "errors": result.get("errors", []),
                    "metadata": {
                        "similar_jobs_found": len(result.get("similar_jobs", [])),
                        "states_visited": len(result.get("agent_thoughts", [])),
                    },
                }
                
                if result.get("workflow_complete"):
                    logger.info(
                        "JD generation completed successfully",
                        extra={"job_title": job_title}
                    )
                else:
                    logger.warning(
                        "JD generation completed with errors",
                        extra={
                            "job_title": job_title,
                            "errors": result.get("errors", []),
                        }
                    )
                
                return response
                
            except Exception as e:
                logger.error(
                    "JD generation failed",
                    exc_info=True,
                    extra={
                        "job_title": job_title,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    }
                )
                raise WorkflowError(
                    message=f"JD generation failed: {str(e)}",
                    details={"original_error": str(e), "job_title": job_title}
                )
        
        try:
            return _execute_workflow()
        except JDGenerationError:
            raise
        except AttributeError as e:
            # Handle compatibility errors (like GenerationConfig.MediaResolution)
            error_msg = str(e)
            if "MediaResolution" in error_msg or "GenerationConfig" in error_msg:
                logger.warning(
                    f"Compatibility error detected: {error_msg}. "
                    "This is likely a version mismatch. The system should fallback automatically."
                )
                # Try to continue - the fallback should have been applied
                raise WorkflowError(
                    message=f"LLM compatibility error: {error_msg}. Please check google-generativeai and crewai versions.",
                    details={"original_error": str(e), "error_type": "compatibility"}
                )
            else:
                raise WorkflowError(
                    message=f"Unexpected attribute error during JD generation: {str(e)}",
                    details={"original_error": str(e), "error_type": "attribute"}
                )
        except Exception as e:
            logger.error(
                f"Unexpected error during JD generation: {e}",
                exc_info=True,
                extra={"error_type": type(e).__name__, "error": str(e)}
            )
            raise WorkflowError(
                message=f"Unexpected error during JD generation: {str(e)}",
                details={"original_error": str(e), "error_type": type(e).__name__}
            )
    
    def _describe_jd(self, jd: Optional[Dict[str, Any]]) -> str:
        """Describe a JD for logging purposes."""
        if not jd:
            return "None"
        if not isinstance(jd, dict):
            return f"Invalid type: {type(jd)}"
        
        position_summary = jd.get('position_summary', '')
        responsibilities = jd.get('responsibilities', [])
        return f"summary={len(position_summary)}chars, resp={len(responsibilities)}items"
    
    def _select_best_jd(self, final_jd, validated_jd, refined_jd, initial_jd) -> Optional[Dict[str, Any]]:
        """Select the best JD from the pipeline stages, preferring ones with actual content."""
        def has_content(jd):
            if not jd or not isinstance(jd, dict):
                return False
            position_summary = jd.get('position_summary', '')
            responsibilities = jd.get('responsibilities', [])
            # Consider it has content if position_summary > 50 chars OR has at least 3 responsibilities
            return len(position_summary) > 50 or len(responsibilities) >= 3
        
        # Prefer later stages, but only if they have content
        if has_content(final_jd):
            logger.info("✅ Using final_jd (has content)")
            return final_jd
        if has_content(validated_jd):
            logger.info("✅ Using validated_jd (has content)")
            return validated_jd
        if has_content(refined_jd):
            logger.info("✅ Using refined_jd (has content)")
            return refined_jd
        if has_content(initial_jd):
            logger.info("✅ Using initial_jd (has content)")
            return initial_jd
        
        # Fallback: return whatever we have, even if empty
        logger.warning("⚠️ No JD stage has sufficient content, using best available")
        return final_jd or validated_jd or refined_jd or initial_jd
    
    def _extract_workflow_states(self, result: Dict[str, Any]) -> list:
        """Extract workflow states from result."""
        states = []
        thoughts = result.get("agent_thoughts", [])
        
        for thought in thoughts:
            state = thought.get("state", "unknown")
            if state not in states:
                states.append(state)
        
        return states
    
    def get_agent_thoughts(self, result: Dict[str, Any]) -> list:
        """Get agent thoughts for visibility."""
        return result.get("agent_thoughts", [])
    
    def _enforce_malomatia_defaults(self, jd: Dict[str, Any], user_location: str = None, user_department: str = None, remote_allowed: bool = False) -> Dict[str, Any]:
        """
        Enforce Malomatia company information in the final JD while PRESERVING user's location, department, and remote preference.
        
        Args:
            jd: The job description dictionary
            user_location: The original location string from user input (e.g., "Pune, Maharashtra")
            user_department: The original department string from user input (e.g., "Research and Development / AI Innovation")
            remote_allowed: Whether the user selected remote work (True = Remote, False = Hybrid)
        """
        # Malomatia company info - MUST be used for all JDs
        MALOMATIA_ABOUT = "Malomatia is a leading provider of Information Technology services and solutions in Qatar, focusing on enhancing operational efficiency and enabling digital transformation across various sectors. Founded in 2008 and headquartered at Manarat Lusail Tower in Doha, Qatar, Malomatia supports Qatar's National Vision 2030 by contributing to the development of a knowledge-based society through innovative IT solutions."
        MALOMATIA_EEO = "Malomatia is an Equal Opportunity Employer. We celebrate diversity and are committed to creating an inclusive environment for all employees regardless of race, religion, gender, age, nationality, disability, or any other protected status. We welcome applications from all qualified candidates."
        
        # Section 4: About the Company - ALWAYS use Malomatia info
        jd["about_company"] = MALOMATIA_ABOUT
        
        # Section 14: Equal Opportunity Statement - ALWAYS use Malomatia statement
        jd["equal_opportunity_statement"] = MALOMATIA_EEO
        
        # Section 2: Department - PRESERVE user's department input if provided
        if user_department and user_department.strip():
            jd["department"] = user_department.strip()
            logger.info(f"✅ Preserved user's department: {user_department.strip()}")
        
        # Section 3: Location - PRESERVE user's location input if provided
        if "location" not in jd or not isinstance(jd["location"], dict):
            jd["location"] = {}
        
        location = jd["location"]
        
        # Parse user_location if provided (format: "City, State/Country" or just "City")
        if user_location and user_location.strip():
            parsed_location = self._parse_location_string(user_location)
            # Only use parsed values if they're valid
            if parsed_location.get("city"):
                location["city"] = parsed_location["city"]
                logger.info(f"✅ Preserved user's location city: {parsed_location['city']}")
            if parsed_location.get("country"):
                location["country"] = parsed_location["country"]
                logger.info(f"✅ Preserved user's location country/state: {parsed_location['country']}")
        
        # Only use defaults if location city is truly empty or placeholder
        city = location.get("city", "")
        generic_placeholders = ["city", "not specified", "tbd", "", "location"]
        if not city or city.lower().strip() in generic_placeholders:
            location["city"] = "Doha"
            location["country"] = "Qatar"
            logger.info("📍 Using default location: Doha, Qatar (no user location provided)")
        
        # Ensure country has a value (but don't override if user provided)
        if not location.get("country"):
            location["country"] = "India" if "india" in (user_location or "").lower() else "Qatar"
        
        # Ensure work_model has a value - use Remote if user selected remote_allowed
        # CRITICAL: If user selected remote_allowed, always set work_model to Remote
        if remote_allowed:
            location["work_model"] = "Remote"
            logger.info(f"✅ Set work_model to Remote (user selected remote_allowed)")
        elif not location.get("work_model"):
            location["work_model"] = "Hybrid"
        # Ensure travel_required is set
        if "travel_required" not in location:
            location["travel_required"] = False
        
        jd["location"] = location
        
        # Section 15: Application Instructions - ALWAYS use Malomatia URLs
        if "application_instructions" not in jd or not isinstance(jd["application_instructions"], dict):
            jd["application_instructions"] = {}
        
        jd["application_instructions"]["apply_url"] = "https://careers.malomatia.com/apply"
        jd["application_instructions"]["email"] = "careers@malomatia.com"
        if not jd["application_instructions"].get("required_materials"):
            jd["application_instructions"]["required_materials"] = ["Resume", "Cover Letter"]
        
        logger.info(f"✅ Enforced Malomatia company defaults. Location: {location.get('city')}, {location.get('country')}")
        if user_department:
            logger.info(f"✅ Preserved user department: {user_department}")
        return jd
    
    def _generate_fallback_success_metrics(self, job_title: str) -> list:
        """Generate fallback success metrics based on job title keywords."""
        job_title_lower = job_title.lower()
        
        # Governance/Compliance roles
        if any(keyword in job_title_lower for keyword in ['governance', 'compliance', 'risk', 'audit', 'regulatory']):
            return [
                "Achievement and maintenance of high compliance audit scores (target: >95%)",
                "Reduction in identified compliance gaps and audit findings",
                "Timely completion of compliance reviews and assessments",
                "Effective implementation and adherence to governance policies and frameworks",
                "Positive feedback from stakeholders on governance effectiveness",
                "Successful completion of regulatory audits with minimal findings"
            ]
        
        # Security roles
        elif any(keyword in job_title_lower for keyword in ['security', 'cybersecurity', 'vulnerability', 'threat']):
            return [
                "Reduction in security incidents and vulnerabilities",
                "Improved security posture as measured by security assessments",
                "Timely and effective response to security incidents",
                "Successful completion of security audits and penetration tests",
                "Implementation and maintenance of effective security controls"
            ]
        
        # Engineering/Development roles
        elif any(keyword in job_title_lower for keyword in ['engineer', 'developer', 'programmer', 'software']):
            return [
                "Delivery of high-quality, well-tested code that meets project specifications",
                "Successful implementation of features and enhancements on schedule",
                "Reduction in production incidents and bug reports",
                "Measurable improvement in application performance and scalability",
                "Effective collaboration with cross-functional teams"
            ]
        
        # Management/Leadership roles
        elif any(keyword in job_title_lower for keyword in ['manager', 'director', 'lead', 'head', 'chief']):
            return [
                "Successful on-time delivery of projects and initiatives",
                "Achievement of team performance and productivity targets",
                "Positive stakeholder feedback and satisfaction scores",
                "Effective budget management and resource utilization",
                "Successful team development and talent retention"
            ]
        
        # Data/AI roles
        elif any(keyword in job_title_lower for keyword in ['data', 'analyst', 'scientist', 'ai', 'ml', 'machine learning']):
            return [
                "Accuracy and performance of data models and analyses",
                "Timely delivery of data insights and reports",
                "Improvement in data quality and reliability metrics",
                "Successful implementation of data-driven solutions",
                "Positive impact of data insights on business decisions"
            ]
        
        # Default/generic metrics
        else:
            return [
                "Successful completion of assigned tasks and projects within defined timelines",
                "Achievement of quality standards and performance targets",
                "Positive feedback from stakeholders and team members",
                "Effective collaboration and contribution to team objectives",
                "Continuous improvement in role-specific skills and competencies"
            ]
    
    def _parse_location_string(self, location_str: str) -> Dict[str, str]:
        """
        Parse a location string like 'Pune, Maharashtra' into city and country/state.
        
        Args:
            location_str: Location string from user input
            
        Returns:
            Dict with 'city' and 'country' keys
        """
        result = {"city": "", "country": ""}
        
        if not location_str:
            return result
        
        location_str = location_str.strip()
        
        # Handle comma-separated format: "City, State" or "City, Country"
        if "," in location_str:
            parts = [p.strip() for p in location_str.split(",")]
            if len(parts) >= 2:
                result["city"] = parts[0]
                result["country"] = parts[1]
            elif len(parts) == 1:
                result["city"] = parts[0]
        else:
            # Single value - treat as city
            result["city"] = location_str
        
        return result


    def _validate_and_fix_jd_relevance(self, jd: Dict[str, Any], job_title: str, user_requirements: str = None) -> Dict[str, Any]:
        """
        Use the LLM autonomously to validate and fix JD content relevance.
        The AI agent will analyze if the content matches the job title and fix it if needed.
        
        This is a CRITICAL validation step that ensures the generated JD is truly relevant
        to the specific job title, not generic content.
        """
        import json
        import re
        try:
            # Get LLM config
            llm_config = self.config.get_llm_config()
            model = llm_config["model"]
            provider = llm_config.get("provider", "google")
            
            # Create LLM for validation - use lower temperature for precise corrections
            from langchain_core.language_models.chat_models import BaseChatModel
            
            from agents.llm.chat_factory import create_chat_llm

            llm: BaseChatModel = create_chat_llm(
                model=model,
                temperature=0.2,
                max_tokens=llm_config.get("max_tokens", 4096),
                provider=llm_config.get("provider"),
            )
            logger.info("Using LLM for JD validation: %s (provider=%s)", model, llm_config.get("provider"))
            
            # Analyze the job title to understand what kind of role it is
            title_lower = job_title.lower()
            
            # Determine role category for validation
            role_category = self._determine_role_category(title_lower)
            
            # Create comprehensive validation prompt
            validation_prompt = f"""You are an EXPERT JD Quality Validator Agent. Your CRITICAL task is to ensure this Job Description is 100% RELEVANT to the job title "{job_title}".

=== JOB TITLE TO VALIDATE AGAINST ===
"{job_title}" (Role Category: {role_category})

=== CURRENT JD CONTENT ===
{json.dumps(jd, indent=2)}

=== USER'S ADDITIONAL REQUIREMENTS ===
{user_requirements if user_requirements else "None specified - generate based on job title only"}

=== STRICT VALIDATION RULES ===

1. **POSITION SUMMARY**: Must specifically describe what a "{job_title}" does.
   - WRONG: Generic "software engineer" or "developer" description
   - RIGHT: Specific description of "{job_title}" responsibilities

2. **RESPONSIBILITIES**: Every single responsibility must be something a "{job_title}" would ACTUALLY do.
   - Check each bullet point: "Would a {job_title} do this?"
   - If NO, replace it with a relevant responsibility

3. **TECHNICAL SKILLS**: Must be skills a "{job_title}" would ACTUALLY use.
   - {self._get_skill_validation_guidance(role_category, job_title)}

4. **TOOLS & TECHNOLOGIES**: Must be tools a "{job_title}" would ACTUALLY use daily.
   - {self._get_tools_validation_guidance(role_category, job_title)}

5. **SUCCESS METRICS**: Must be KPIs relevant to "{job_title}" work.

6. **LEVEL ENFORCEMENT (CRITICAL)**:
   - Check the `job_level` in the input JD.
   - If LEVEL is JUNIOR: Ensure NO senior responsibilities (Lead, Mentor, Manage, Architect). Experience must be 0-2 years.
   - If LEVEL is SENIOR: Ensure responsibilities reflect leadership, mentoring, and system design. Experience must be 5-8 years.
   - If LEVEL is MID: Ensure execution focus with some independence. Experience must be 3-5 years.

=== COMMON MISTAKES TO FIX ===
- Frontend role with backend skills (Java, Python, C++, Spring, Django) → Fix to frontend skills
- Backend role with frontend skills (React, Vue, CSS, Figma) → Fix to backend skills
- Data role with web development skills → Fix to data/ML skills
- DevOps role with application development skills → Fix to infrastructure skills
- Generic "Software Engineer" content for specialized roles → Make it specific
- JUNIOR roles with SENIOR responsibilities (e.g. "Manage team") -> REMOVE or DOWNGRADE them

=== YOUR TASK ===
1. Review EVERY section of the JD
2. For EACH item, ask: "Is this relevant to a {job_title}?"
3. If ANY content is NOT relevant, REPLACE it with relevant content
4. Ensure the JD reads as if it was written specifically for a "{job_title}" position
5. VALIDATE that all content matches the user requirements: "{user_requirements}"
6. VALIDATE that all content matches the job level (Years of experience, verbs used)

=== OUTPUT ===
Return the CORRECTED JD as a valid JSON object with the EXACT same structure.
- Keep all 15 sections
- Fix ANY irrelevant content
- The job_title MUST be exactly "{job_title}"
- DO NOT include any explanation, ONLY the JSON object

JSON:"""

            # Call LLM to validate and fix
            logger.info(f"🔍 Validating JD relevance for '{job_title}' (category: {role_category})...")
            response = llm.invoke(validation_prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Extract JSON from response - handle various formats
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                try:
                    fixed_jd = json.loads(json_match.group(0))
                    # Ensure job_title is preserved exactly
                    fixed_jd["job_title"] = job_title
                    logger.info(f"✅ AI Agent validated and corrected JD for '{job_title}'")
                    return fixed_jd
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse AI validation response: {e}")
                    # Try to clean up the JSON and parse again
                    try:
                        cleaned_json = self._clean_json_string(json_match.group(0))
                        fixed_jd = json.loads(cleaned_json)
                        fixed_jd["job_title"] = job_title
                        logger.info(f"✅ AI Agent validated JD after JSON cleanup for '{job_title}'")
                        return fixed_jd
                    except:
                        logger.warning("JSON cleanup also failed, returning original JD")
                        return jd
            else:
                logger.warning("No JSON found in AI validation response, returning original JD")
                return jd
                
        except Exception as e:
            logger.warning(f"AI validation failed: {e}, returning original JD")
            return jd
    
    def _determine_role_category(self, title_lower: str) -> str:
        """Determine the role category based on job title for validation."""
        if any(kw in title_lower for kw in ["frontend", "front-end", "front end", "ui developer", "ui engineer", "react", "angular", "vue"]):
            return "FRONTEND"
        elif any(kw in title_lower for kw in ["backend", "back-end", "back end", "server", "api developer", "java developer", "python developer", "node"]):
            return "BACKEND"
        elif any(kw in title_lower for kw in ["full stack", "fullstack", "full-stack"]):
            return "FULLSTACK"
        elif any(kw in title_lower for kw in ["data scientist", "data science", "data analyst", "analytics", "business intelligence", "bi developer"]):
            return "DATA_ANALYTICS"
        elif any(kw in title_lower for kw in ["ai", "ml", "machine learning", "artificial intelligence", "deep learning", "nlp", "computer vision"]):
            return "AI_ML"
        elif any(kw in title_lower for kw in ["devops", "dev ops", "sre", "site reliability", "platform engineer", "infrastructure", "cloud"]):
            return "DEVOPS"
        elif any(kw in title_lower for kw in ["mobile", "ios", "android", "react native", "flutter"]):
            return "MOBILE"
        elif any(kw in title_lower for kw in ["qa", "quality", "test", "sdet", "automation"]):
            return "QA_TESTING"
        elif any(kw in title_lower for kw in ["product manager", "product owner", "pm"]):
            return "PRODUCT"
        elif any(kw in title_lower for kw in ["designer", "ux", "ui/ux", "product design", "visual design"]):
            return "DESIGN"
        elif any(kw in title_lower for kw in ["marketing", "growth", "seo", "content", "social media"]):
            return "MARKETING"
        elif any(kw in title_lower for kw in ["security", "cybersecurity", "infosec", "penetration"]):
            return "SECURITY"
        else:
            return "GENERAL"
    
    def _get_skill_validation_guidance(self, role_category: str, job_title: str) -> str:
        """Get skill validation guidance based on role category."""
        guidance = {
            "FRONTEND": "MUST include: HTML, CSS, JavaScript, TypeScript, React/Vue/Angular. MUST NOT include: Java, Python, C++, Spring, Django, PostgreSQL",
            "BACKEND": "MUST include: Python/Java/Node.js, SQL, REST APIs, databases. MUST NOT include: React, Vue, Angular, CSS, Figma",
            "FULLSTACK": "MUST include both frontend (React/Vue) AND backend (Node.js/Python) skills",
            "DATA_ANALYTICS": "MUST include: Python, SQL, Pandas, data visualization, statistics. MUST NOT include: React, Angular, frontend frameworks",
            "AI_ML": "MUST include: Python, TensorFlow/PyTorch, ML algorithms, data processing. MUST NOT include: frontend frameworks, CSS",
            "DEVOPS": "MUST include: Docker, Kubernetes, CI/CD, cloud platforms, IaC. MUST NOT include: React, frontend development",
            "MOBILE": "MUST include: Swift/Kotlin or React Native/Flutter, mobile SDKs. MUST NOT include: backend frameworks like Django/Spring",
            "QA_TESTING": "MUST include: Testing frameworks, automation tools, test planning. Focus on quality assurance skills",
            "PRODUCT": "MUST include: Product strategy, roadmapping, stakeholder management, analytics. NOT coding skills",
            "DESIGN": "MUST include: Figma, design systems, user research, prototyping. NOT coding skills",
            "MARKETING": "MUST include: Marketing tools, analytics, campaign management. NOT technical coding skills",
            "SECURITY": "MUST include: Security tools, penetration testing, compliance, threat analysis",
        }
        return guidance.get(role_category, f"Skills must be directly relevant to what a {job_title} does")
    
    def _get_tools_validation_guidance(self, role_category: str, job_title: str) -> str:
        """Get tools validation guidance based on role category."""
        guidance = {
            "FRONTEND": "Tools like: VS Code, Chrome DevTools, Webpack, npm, Figma, Jest, Cypress, Storybook",
            "BACKEND": "Tools like: IDEs, Postman, Docker, databases (PostgreSQL, MongoDB), Redis, message queues",
            "FULLSTACK": "Mix of frontend tools (VS Code, npm) AND backend tools (Docker, databases)",
            "DATA_ANALYTICS": "Tools like: Jupyter, Tableau, Power BI, SQL clients, Excel, Python IDEs",
            "AI_ML": "Tools like: Jupyter, TensorBoard, MLflow, cloud ML platforms, GPU computing",
            "DEVOPS": "Tools like: Docker, Kubernetes, Terraform, Jenkins, GitHub Actions, Prometheus, Grafana",
            "MOBILE": "Tools like: Xcode, Android Studio, mobile testing tools, app store consoles",
            "QA_TESTING": "Tools like: Selenium, Cypress, Postman, JIRA, TestRail, load testing tools",
            "PRODUCT": "Tools like: JIRA, Confluence, Figma, analytics platforms, roadmapping tools",
            "DESIGN": "Tools like: Figma, Sketch, Adobe Creative Suite, prototyping tools, Miro",
            "MARKETING": "Tools like: HubSpot, Google Analytics, social media platforms, email marketing tools",
            "SECURITY": "Tools like: Burp Suite, Nessus, SIEM tools, vulnerability scanners",
        }
        return guidance.get(role_category, f"Tools must be what a {job_title} would actually use daily")
    
    def _clean_json_string(self, json_str: str) -> str:
        """Clean up a JSON string that might have formatting issues."""
        import re
        # Remove any leading/trailing whitespace
        json_str = json_str.strip()
        # Remove any markdown code block markers
        json_str = re.sub(r'^```json\s*', '', json_str)
        json_str = re.sub(r'^```\s*', '', json_str)
        json_str = re.sub(r'\s*```$', '', json_str)
        # Fix common JSON issues
        json_str = re.sub(r',\s*}', '}', json_str)  # Remove trailing commas before }
        json_str = re.sub(r',\s*]', ']', json_str)  # Remove trailing commas before ]
        return json_str
