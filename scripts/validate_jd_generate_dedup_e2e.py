#!/usr/bin/env python3
"""Validate JD generate dedup fixes (in-flight guard, session draft id, postgres job id).

Usage:
  python scripts\\validate_jd_generate_dedup_e2e.py
  python scripts\\validate_jd_generate_dedup_e2e.py --full
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

DEDUP_FIX_TESTS = REPO_ROOT / "tests" / "unit" / "test_jd_generate_dedup_fix.py"
NO_DUP_TESTS = REPO_ROOT / "tests" / "unit" / "test_jd_no_duplicate_jobs.py"


def run_pytest(paths: list[Path]) -> int:
    cmd = [sys.executable, "-m", "pytest", *[str(path) for path in paths], "-v", "--tb=short"]
    result = subprocess.run(cmd, cwd=REPO_ROOT, text=True)
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate JD generate dedup fixes")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Also run tests/unit/test_jd_no_duplicate_jobs.py",
    )
    args = parser.parse_args()

    test_paths = [DEDUP_FIX_TESTS]
    if args.full:
        test_paths.append(NO_DUP_TESTS)

    print()
    print("=" * 60)
    print("  QuantHire AI - JD Generate Dedup Fix Validation")
    print("  In-flight guard | session draft id | postgres job id")
    print("=" * 60)
    print()

    for path in test_paths:
        if not path.is_file():
            print(f"FAIL: missing {path}")
            return 1

    code = run_pytest(test_paths)
    print()
    if code != 0:
        print("=" * 60)
        print("  VALIDATION FAILED")
        print("=" * 60)
        return code

    print("=" * 60)
    print("  ALL JD GENERATE DEDUP CHECKS PASSED")
    print("=" * 60)
    print()
    print("Manual browser UAT (after redeploy):")
    print("  1. Click AI Generate JD once")
    print("  2. Click Generate JD once and wait (do NOT click again)")
    print("  3. Jobs list shows exactly 1 new card")
    print("  4. Regenerate -> Generate -> still 1 card")
    print("  5. Delete old duplicate cards manually")
    print()
    print("Re-run:")
    print("  scripts\\validate_jd_generate_dedup_e2e.cmd")
    print("  scripts\\validate_jd_generate_dedup_e2e.cmd --full")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
