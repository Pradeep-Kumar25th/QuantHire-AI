"""Frontend lib layer must be trackable in Git (audit Q2)."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "apps" / "web" / "src" / "lib"

REQUIRED_FILES = [
    "api.ts",
    "api-client.ts",
    "api-health.ts",
    "auth-storage.ts",
    "utils.ts",
    "enterprise-jd-print.ts",
    "test-connection.ts",
]


def test_frontend_lib_files_exist():
    assert LIB_DIR.is_dir(), f"Missing frontend lib directory: {LIB_DIR}"
    for name in REQUIRED_FILES:
        assert (LIB_DIR / name).is_file(), f"Missing required lib file: {name}"


def test_gitignore_does_not_ignore_frontend_lib():
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "\nlib/\n" not in gitignore
    assert "/lib/" in gitignore
