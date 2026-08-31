#!/usr/bin/env python3
"""Validate JD generate/regenerate/HITL flows do not create duplicate job cards.

Simulates:
  - First AI Generate -> one new job card
  - Regenerate / re-generate with job_id -> same card updated
  - HITL Save to pgvector -> same card updated
  - Old bug: repeat generate without job_id -> duplicates

Usage:
  python scripts\\validate_jd_no_duplicates_e2e.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TEST_FILE = REPO_ROOT / "tests" / "unit" / "test_jd_no_duplicate_jobs.py"


def main() -> int:
    print()
    print("=" * 60)
    print("  QuantHire AI - JD No-Duplicate Jobs E2E Validation")
    print("=" * 60)
    print()

    if not TEST_FILE.is_file():
        print(f"FAIL: missing {TEST_FILE}")
        return 1

    cmd = [sys.executable, "-m", "pytest", str(TEST_FILE), "-v", "--tb=short"]
    result = subprocess.run(cmd, cwd=REPO_ROOT, text=True)
    print()
    if result.returncode != 0:
        print("=" * 60)
        print("  VALIDATION FAILED")
        print("=" * 60)
        return result.returncode

    print("=" * 60)
    print("  ALL NO-DUPLICATE JD CHECKS PASSED")
    print("=" * 60)
    print()
    print("Manual browser UAT (after deploy):")
    print("  1. AI Generate JD once -> exactly 1 new card appears")
    print("  2. Regenerate -> Generate again -> still 1 card (title updates)")
    print("  3. Open card -> HITL edit -> Save to pgvector -> still 1 card")
    print("  4. Close dialog, reopen -> same job ID and edits")
    print("  5. Delete any old duplicate cards created before this fix")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
