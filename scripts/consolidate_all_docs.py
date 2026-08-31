#!/usr/bin/env python3
"""
Move every .md file in the repo into docs/ (single deletable documentation folder).

Layout:
  docs/
    README.md              - master index
    INDEX.md               - full file listing
    azure-deployment/      - Azure / Hazim handoff docs
    interview-prep/        - output/interview_prep docs
    archive/               - former _documentation-archive/
    project/               - former root README.md
    scripts/               - former scripts/README.md
    misc/                  - any other stray markdown
"""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
EXCLUDE_DIRS = {
    "node_modules",
    "venv",
    ".venv",
    ".git",
    ".next",
    "__pycache__",
    "htmlcov",
    ".pytest_cache",
}


def should_skip(path: Path) -> bool:
    return any(part in EXCLUDE_DIRS for part in path.parts)


def safe_move(src: Path, dest: Path, moved: list[str]) -> None:
    if not src.is_file():
        return
    if dest.exists():
        stem = dest.stem
        suffix = dest.suffix
        parent = dest.parent
        n = 2
        while dest.exists():
            dest = parent / f"{stem}__{n}{suffix}"
            n += 1
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))
    moved.append(f"{src.relative_to(ROOT)} -> {dest.relative_to(ROOT)}")


def main() -> int:
    moved: list[str] = []

    # Fresh docs layout (preserve azure-deployment if re-run)
    DOCS.mkdir(exist_ok=True)

    # 1) Merge _documentation-archive -> docs/archive/
    archive_src = ROOT / "_documentation-archive"
    archive_dest = DOCS / "archive"
    if archive_src.is_dir():
        if archive_dest.exists():
            for item in archive_src.rglob("*"):
                if item.is_file() and item.suffix.lower() == ".md":
                    rel = item.relative_to(archive_src)
                    safe_move(item, archive_dest / rel, moved)
            shutil.rmtree(archive_src, ignore_errors=True)
        else:
            shutil.move(str(archive_src), str(archive_dest))
            moved.append("_documentation-archive/ -> docs/archive/")

    # 2) Azure deployment markdown
    azure_src = ROOT / "output" / "azure_deployment"
    azure_dest = DOCS / "azure-deployment"
    azure_dest.mkdir(parents=True, exist_ok=True)
    if azure_src.is_dir():
        for md in azure_src.glob("*.md"):
            safe_move(md, azure_dest / md.name, moved)

    # 3) Interview prep markdown
    interview_src = ROOT / "output" / "interview_prep"
    interview_dest = DOCS / "interview-prep"
    interview_dest.mkdir(parents=True, exist_ok=True)
    if interview_src.is_dir():
        for md in interview_src.glob("*.md"):
            safe_move(md, interview_dest / md.name, moved)

    # 4) Known root-level markdown
    root_readme = ROOT / "README.md"
    if root_readme.is_file():
        safe_move(root_readme, DOCS / "project" / "README.md", moved)

    scripts_readme = ROOT / "scripts" / "README.md"
    if scripts_readme.is_file():
        safe_move(scripts_readme, DOCS / "scripts" / "README.md", moved)

    # 5) Collect any remaining .md outside docs/
    for path in sorted(ROOT.rglob("*.md")):
        if should_skip(path):
            continue
        if path.is_relative_to(DOCS):
            continue
        rel = path.relative_to(ROOT)
        if rel.parts[:2] == ("output", "azure_deployment"):
            continue  # already handled or env-only folder
        if rel.parts[:2] == ("output", "interview_prep"):
            continue
        dest = DOCS / "misc" / rel
        safe_move(path, dest, moved)

    # 6) Master index
    all_md = sorted(p.relative_to(DOCS) for p in DOCS.rglob("*.md"))
    index_lines = [
        "# Documentation Index",
        "",
        f"**Total markdown files:** {len(all_md)}",
        "",
        "Delete the entire `docs/` folder to remove all project documentation.",
        "",
        "## Folders",
        "",
        "| Folder | Purpose |",
        "|--------|---------|",
        "| [azure-deployment/](azure-deployment/) | Azure Non-Prod deploy, Hazim handoff, smoke tests |",
        "| [archive/](archive/) | Historical dev notes, RAG/Milvus fixes, demo kits |",
        "| [interview-prep/](interview-prep/) | Interview preparation notes |",
        "| [project/](project/) | Former repository README |",
        "| [scripts/](scripts/) | Scripts documentation |",
        "| [misc/](misc/) | Other relocated markdown |",
        "",
        "## All files",
        "",
    ]
    index_lines.extend(f"- `{p.as_posix()}`" for p in all_md)
    (DOCS / "INDEX.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")

    readme = DOCS / "README.md"
    readme.write_text(
        """# QuantHire — All Documentation

**This folder contains every markdown file in the project.**

To remove all documentation from the codebase, delete the entire `docs/` folder.

## Start here (Azure deploy / Hazim handoff)

1. [azure-deployment/QUANTHIRE_REPLATFORM_SUMMARY_FOR_HAZIM.md](azure-deployment/QUANTHIRE_REPLATFORM_SUMMARY_FOR_HAZIM.md)
2. [azure-deployment/COMPLETE_HAZIM_HANDOFF_CHECKLIST.md](azure-deployment/COMPLETE_HAZIM_HANDOFF_CHECKLIST.md)
3. [azure-deployment/NONPROD_SMOKE_TEST_CHECKLIST.md](azure-deployment/NONPROD_SMOKE_TEST_CHECKLIST.md)

## Layout

| Folder | Contents |
|--------|----------|
| `azure-deployment/` | Azure replatform, Helm, secrets, smoke tests |
| `archive/` | Legacy dev docs (Milvus, QuantChat, JD, demos, career) |
| `interview-prep/` | Interview notes |
| `project/` | Former root README (quick start, repo layout) |
| `scripts/` | Scripts folder documentation |
| `misc/` | Any other markdown relocated here |

Full listing: [INDEX.md](INDEX.md)

**Non-markdown config** (not in this folder): `output/azure_deployment/env/azure-nonprod.env`
""",
        encoding="utf-8",
    )

    # 7) Root pointer (not markdown — user requested no .md at repo root)
    (ROOT / "DOCS.txt").write_text(
        "All project documentation (.md) lives in the docs/ folder.\n"
        "Delete docs/ to remove every markdown file from this repository.\n"
        "Start: docs/azure-deployment/QUANTHIRE_REPLATFORM_SUMMARY_FOR_HAZIM.md\n",
        encoding="utf-8",
    )

    print(f"Documentation consolidated under {DOCS.relative_to(ROOT)}/")
    print(f"Total markdown files: {len(all_md)}")
    print(f"Moves this run: {len(moved)}")
    print("Root pointer: DOCS.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
