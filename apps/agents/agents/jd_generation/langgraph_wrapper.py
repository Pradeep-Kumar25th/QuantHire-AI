"""
LangGraph Studio Wrapper
Adds parent directories to Python path so imports work correctly
"""
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Add the apps directory to Python path
apps_dir = Path(__file__).parent.parent.parent
if str(apps_dir) not in sys.path:
    sys.path.insert(0, str(apps_dir))

# Now import the actual workflow
from agents.jd_generation.state_machine import JDGenerationWorkflow

# Export for LangGraph Studio
__all__ = ['JDGenerationWorkflow']
