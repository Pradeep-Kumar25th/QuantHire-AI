"""LangSmith integration for LLM tracing and prompt management."""

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class LangSmithIntegration:
    """
    LangSmith integration for LLM observability.
    
    Features:
    - Automatic tracing of LangChain calls
    - Prompt versioning
    - Evaluation datasets
    - Performance monitoring
    - Debugging and replay
    
    Setup:
    1. Sign up at https://smith.langchain.com
    2. Create API key
    3. Set environment variables:
       export LANGCHAIN_TRACING_V2=true
       export LANGCHAIN_API_KEY="your_api_key"
       export LANGCHAIN_PROJECT="quanthire-ai"
       export LANGCHAIN_ENDPOINT="https://api.smith.langchain.com"
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        project: str = "quanthire-ai",
        enabled: bool = True,
    ):
        """
        Initialize LangSmith integration.
        
        Args:
            api_key: LangSmith API key
            project: Project name
            enabled: Whether tracing is enabled
        """
        self.api_key = api_key or os.getenv("LANGCHAIN_API_KEY")
        self.project = project or os.getenv("LANGCHAIN_PROJECT", "quanthire-ai")
        self.enabled = enabled and bool(self.api_key)
        
        if self.enabled:
            # Configure LangSmith environment variables
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_API_KEY"] = self.api_key
            os.environ["LANGCHAIN_PROJECT"] = self.project
            os.environ["LANGCHAIN_ENDPOINT"] = os.getenv(
                "LANGCHAIN_ENDPOINT",
                "https://api.smith.langchain.com"
            )
            logger.info(f"LangSmith tracing enabled for project: {self.project}")
        else:
            logger.info("LangSmith tracing disabled")
    
    def create_run_context(
        self,
        run_name: str,
        run_type: str,
        tags: Optional[list] = None,
        metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Create context for a traced run.
        
        Args:
            run_name: Name for the run
            run_type: Type (e.g., "agent", "chain", "llm")
            tags: Tags for categorization
            metadata: Additional metadata
            
        Returns:
            Context dict for LangChain callbacks
        """
        if not self.enabled:
            return {}
        
        return {
            "run_name": run_name,
            "run_type": run_type,
            "tags": tags or [],
            "metadata": metadata or {},
        }
    
    def tag_run(self, run_id: str, tags: list) -> None:
        """Add tags to an existing run."""
        if not self.enabled:
            return
        
        # Tags are automatically captured by LangSmith when set in context
        logger.debug(f"Tagged run {run_id}: {tags}")
    
    def add_feedback(
        self,
        run_id: str,
        score: float,
        feedback_type: str = "human",
        comment: Optional[str] = None,
    ) -> None:
        """
        Add feedback to a run.
        
        Used for human-in-the-loop corrections.
        
        Args:
            run_id: LangSmith run ID
            score: Feedback score (0-1)
            feedback_type: Type of feedback
            comment: Optional comment
        """
        if not self.enabled:
            return
        
        try:
            from langsmith import Client
            
            client = Client(api_key=self.api_key)
            client.create_feedback(
                run_id=run_id,
                key="user_score",
                score=score,
                comment=comment,
            )
            logger.info(f"Feedback added to run {run_id}: score={score}")
        except Exception as e:
            logger.error(f"Failed to add feedback: {e}")
    
    @staticmethod
    def get_run_url(run_id: str, project: str = "quanthire-ai") -> str:
        """Get LangSmith UI URL for a run."""
        return f"https://smith.langchain.com/o/project/{project}/r/{run_id}"


# Global integration instance
_langsmith: Optional[LangSmithIntegration] = None


def init_langsmith(
    api_key: Optional[str] = None,
    project: str = "quanthire-ai",
) -> LangSmithIntegration:
    """Initialize global LangSmith integration."""
    global _langsmith
    
    enabled = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
    _langsmith = LangSmithIntegration(
        api_key=api_key,
        project=project,
        enabled=enabled,
    )
    return _langsmith


def get_langsmith() -> LangSmithIntegration:
    """Get global LangSmith integration."""
    if _langsmith is None:
        return init_langsmith()
    return _langsmith


# Setup instructions
SETUP_INSTRUCTIONS = """
LangSmith Integration Setup
===========================

1. Sign Up for LangSmith:
   - Visit: https://smith.langchain.com
   - Create account
   - Create new project: "quanthire-ai"

2. Generate API Key:
   - Go to Settings > API Keys
   - Create new API key
   - Copy key securely

3. Configure Environment:
   export LANGCHAIN_TRACING_V2=true
   export LANGCHAIN_API_KEY="your_langsmith_api_key"
   export LANGCHAIN_PROJECT="quanthire-ai"
   export LANGCHAIN_ENDPOINT="https://api.smith.langchain.com"

4. Verify Integration:
   - Run any agent
   - Check traces in LangSmith UI
   - View: https://smith.langchain.com/o/your-org/project/quanthire-ai

Features Enabled:
- ✅ Automatic tracing of all LangChain calls
- ✅ Token usage tracking
- ✅ Latency measurement
- ✅ Error tracking
- ✅ Prompt versioning
- ✅ Comparison and evaluation

Benefits:
- Debug agent behavior
- Compare prompt versions
- Monitor performance
- Track costs
- Identify bottlenecks
- Replay problematic runs

Documentation: https://docs.smith.langchain.com
"""


def print_setup_instructions():
    """Print LangSmith setup instructions."""
    print(SETUP_INSTRUCTIONS)












