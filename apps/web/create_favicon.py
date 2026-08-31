"""
Legacy entry point — use scripts/setup-brand-assets.py with the approved logo PNG.
"""

from pathlib import Path
import runpy

if __name__ == "__main__":
    script = Path(__file__).resolve().parent / "scripts" / "setup-brand-assets.py"
    runpy.run_path(str(script), run_name="__main__")
