#!/usr/bin/env python3
"""Remove root-level script clutter: no wrapper .bat files at repo root."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
STARTUP = SCRIPTS / "startup"
MANUAL_TESTS = SCRIPTS / "manual-tests"
UTILITIES = SCRIPTS / "utilities"
LEGACY = SCRIPTS / "legacy"

SKIP_PY = {
    "organize_root_scripts.py",
    "organize_root_structure.py",
    "relocate_markdown.py",
    "clean_root.py",
    "_migration_executor.py",
    "_root_inventory_probe.py",
}

KEEP_ROOT_CMD = {
    "ORGANIZE-ROOT-SCRIPTS.cmd",  # optional one-shot; can live in scripts only
}


def is_wrapper(text: str) -> bool:
    return "scripts\\startup\\" in text or "scripts/startup/" in text


def find_script_copy(name: str) -> Path | None:
    for folder in (MANUAL_TESTS, UTILITIES, LEGACY):
        candidate = folder / name
        if candidate.is_file():
            return candidate
    return None


def categorize_py(name: str) -> Path:
    lower = name.lower()
    if any(x in lower for x in ("agent", "hybrid", "backend", "main_api")):
        return LEGACY
    if lower.startswith("test_") or lower.startswith("e2e_") or lower.endswith("_test.py"):
        return MANUAL_TESTS
    if lower.startswith("test") or (lower.startswith("quick_") and "test" in lower):
        return MANUAL_TESTS
    if lower.startswith(("verify_", "check_", "fix_", "rebuild_", "diagnose_", "quick_verify")):
        return UTILITIES
    if lower.startswith("fix_") or name.startswith("FIX_") or name.startswith("VERIFY_"):
        return UTILITIES
    if lower.startswith("quick_"):
        return MANUAL_TESTS
    return LEGACY


def clean_python() -> tuple[int, int, int]:
    moved = deleted = failed = 0
    for src in sorted(ROOT.glob("*.py")):
        if src.name in SKIP_PY:
            continue
        existing = find_script_copy(src.name)
        if existing:
            try:
                src.unlink()
                deleted += 1
            except OSError:
                failed += 1
            continue
        dest_dir = categorize_py(src.name)
        dest = dest_dir / src.name
        dest_dir.mkdir(parents=True, exist_ok=True)
        try:
            if dest.exists():
                dest.unlink()
            shutil.move(str(src), str(dest))
            moved += 1
        except OSError:
            failed += 1
    return moved, deleted, failed


def clean_batches() -> tuple[int, int, int, int]:
    moved = deleted = wrappers_removed = failed = 0
    for src in sorted(ROOT.glob("*.bat")):
        dest = STARTUP / src.name
        try:
            text = src.read_text(encoding="utf-8", errors="replace")
        except OSError:
            failed += 1
            continue

        if dest.is_file():
            if is_wrapper(text):
                try:
                    src.unlink()
                    wrappers_removed += 1
                except OSError:
                    failed += 1
            else:
                # duplicate full implementation at root — drop root copy
                try:
                    src.unlink()
                    deleted += 1
                except OSError:
                    failed += 1
            continue

        STARTUP.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(src), str(dest))
            moved += 1
        except OSError:
            failed += 1

    return moved, wrappers_removed, deleted, failed


def patch_startup_paths() -> int:
    """Fix paths in startup bats after files moved off root."""
    replacements = [
        ("python main_api_hybrid.py", "python scripts\\legacy\\main_api_hybrid.py"),
        ("py main_api_hybrid.py", "py scripts\\legacy\\main_api_hybrid.py"),
        ('if not exist "main_api_hybrid.py"', 'if not exist "scripts\\legacy\\main_api_hybrid.py"'),
        ('copy "main_api_hybrid.py"', 'copy "scripts\\legacy\\main_api_hybrid.py"'),
        ("python E2E_RESUME_TO_QUANTCHAT_TEST.py", "python scripts\\manual-tests\\E2E_RESUME_TO_QUANTCHAT_TEST.py"),
        ("python fix_milvus_loading.py", "python scripts\\utilities\\fix_milvus_loading.py"),
        ("python fix_milvus_timestamp.py", "python scripts\\utilities\\fix_milvus_timestamp.py"),
        ("call START_MILVUS.bat", "call scripts\\startup\\START_MILVUS.bat"),
        ("call START_BACKEND.bat", "call scripts\\startup\\START_BACKEND.bat"),
        ('cmd /k "START_MILVUS.bat"', 'cmd /k "scripts\\startup\\START_MILVUS.bat"'),
        ('cmd /k "START_BACKEND.bat"', 'cmd /k "scripts\\startup\\START_BACKEND.bat"'),
        ("call load_api_keys.bat", "call scripts\\startup\\load_api_keys.bat"),
    ]
    patched = 0
    header = 'set "REPO_ROOT=%~dp0..\\.."\r\ncd /d "%REPO_ROOT%"\r\n'
    for bat in STARTUP.glob("*.bat"):
        try:
            content = bat.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        original = content
        if "REPO_ROOT=%~dp0" not in content:
            lines = content.splitlines(keepends=True)
            insert_at = 0
            for i, line in enumerate(lines):
                stripped = line.strip().lower()
                if stripped in {"@echo off", "setlocal"}:
                    insert_at = i + 1
                    if stripped == "setlocal":
                        break
                elif stripped and not stripped.startswith("rem "):
                    break
            lines.insert(insert_at, header)
            content = "".join(lines)
        content = content.replace("%~dp0", "%REPO_ROOT%\\")
        for old, new in replacements:
            content = content.replace(old, new)
        if content != original:
            bat.write_text(content, encoding="utf-8")
            patched += 1
    return patched


def main() -> int:
    py_moved, py_deleted, py_failed = clean_python()
    bat_moved, wrappers, bat_deleted, bat_failed = clean_batches()
    patched = patch_startup_paths()

    print("Root cleanup complete.")
    print(f"  Python moved: {py_moved}")
    print(f"  Python duplicates removed: {py_deleted}")
    print(f"  Batch moved to scripts/startup: {bat_moved}")
    print(f"  Root wrapper .bat removed: {wrappers}")
    print(f"  Root duplicate .bat removed: {bat_deleted}")
    print(f"  Startup bats patched: {patched}")
    remaining_py = [p.name for p in ROOT.glob("*.py")]
    remaining_bat = [p.name for p in ROOT.glob("*.bat")]
    if remaining_py:
        print(f"  Remaining root .py: {remaining_py}")
    if remaining_bat:
        print(f"  Remaining root .bat: {remaining_bat}")
    if py_failed or bat_failed:
        print(f"  Failures: py={py_failed} bat={bat_failed}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
