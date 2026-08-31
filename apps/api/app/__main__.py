"""
Uvicorn entry point for automatic reload support.
When you run: python -m app
This automatically configures reload directories.
"""

import sys
from pathlib import Path

# Get project root for reload directories
project_root = Path(__file__).resolve().parent.parent.parent.parent
api_dir = Path(__file__).resolve().parent.parent.parent

if __name__ == "__main__":
    import uvicorn
    from app.config import settings
    
    # Automatically configure reload directories
    reload_dirs = None
    if settings.debug:
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
