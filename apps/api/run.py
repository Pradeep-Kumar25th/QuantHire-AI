"""
QuantHire AI API Server - Automatic Startup
===========================================
This is the recommended way to start the API server.
It automatically configures reload directories to watch:
- apps/api (for API code changes)
- Project root (for real_hybrid_architecture_complete.py changes)

Usage (from apps/api directory):
    python run.py
    OR
    python -m app
    
Both methods automatically watch project directories for changes.
"""

import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import uvicorn
from app.config import settings

if __name__ == "__main__":
    # Automatically configure reload directories
    # This ensures changes to real_hybrid_architecture_complete.py trigger reload
    reload_dirs = None
    if settings.debug:
        api_dir = Path(__file__).resolve().parent
        reload_dirs = [
            str(api_dir),  # Watch apps/api
            str(project_root),  # Watch project root (real_hybrid_architecture_complete.py, etc.)
        ]
        print(f"🔄 Auto-reload enabled: watching project directories")
        print(f"   📁 {api_dir}")
        print(f"   📁 {project_root}")

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        reload_dirs=reload_dirs if settings.debug else None,
        log_level=settings.log_level.lower(),
    )
