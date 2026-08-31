"""Copy official Malomatia JD .docx templates into the API bundle."""

from __future__ import annotations

import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET_DIR = REPO_ROOT / "apps" / "api" / "app" / "templates" / "malomatia"

SOURCE_CANDIDATES = [
    Path(r"c:\Users\prakumar\Downloads\JD Templates"),
    Path(r"c:\Users\prakumar\Downloads"),
]

FILES = {
    "leader_template.docx": "JD Template_Leader position (1).docx",
    "non_leader_template.docx": "JD Template_Non-Leader position (2).docx",
    "data_center_manager_reference.docx": "Data Center Manager JD (1).docx",
}


def _resolve_source(name: str) -> Path | None:
    for folder in SOURCE_CANDIDATES:
        candidate = folder / name
        if candidate.is_file():
            return candidate
    return None


def main() -> None:
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    copied = 0
    for target_name, source_name in FILES.items():
        source = _resolve_source(source_name)
        target = TARGET_DIR / target_name
        if source is None:
            print(f"MISSING source: {source_name}")
            continue
        shutil.copy2(source, target)
        copied += 1
        print(f"Copied {source} -> {target}")

    if copied == 0:
        raise SystemExit(
            "No Malomatia templates copied. Place the official .docx files in "
            "Downloads or Downloads\\JD Templates, then rerun."
        )
    print(f"Done. Copied {copied} template(s).")


if __name__ == "__main__":
    main()
