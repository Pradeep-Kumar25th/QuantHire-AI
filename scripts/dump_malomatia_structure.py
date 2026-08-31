"""Dump Malomatia JD docx structure for template filling."""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.table import Table

TEMPLATES = Path(__file__).resolve().parents[1] / "apps" / "api" / "app" / "templates" / "malomatia"
FILES = [
    "leader_template.docx",
    "non_leader_template.docx",
    "data_center_manager_reference.docx",
]


def snippet(text: str, limit: int = 200) -> str:
    normalized = " ".join(text.split())
    return normalized if len(normalized) <= limit else normalized[: limit - 3] + "..."


def count_paragraphs_in_table(table: Table) -> int:
    total = 0
    for row in table.rows:
        for cell in row.cells:
            total += len(cell.paragraphs)
            for nested in cell.tables:
                total += count_paragraphs_in_table(nested)
    return total


def dump_table(table: Table, label: str, depth: int = 0) -> None:
    indent = "  " * depth
    print(f"{indent}TABLE {label}: {len(table.rows)} rows x {len(table.columns)} cols")
    for row_index, row in enumerate(table.rows):
        for col_index, cell in enumerate(row.cells):
            print(
                f"{indent}  [{row_index},{col_index}] "
                f"({len(cell.paragraphs)} para): {snippet(cell.text)!r}"
            )
            for nested_index, nested in enumerate(cell.tables):
                dump_table(nested, f"{label}.{row_index}.{col_index}.nested{nested_index}", depth + 1)


def analyze(path: Path) -> None:
    doc = Document(path)
    table_paragraphs = sum(count_paragraphs_in_table(table) for table in doc.tables)
    print("=" * 80)
    print(f"FILE: {path.name}")
    print(f"Body paragraphs: {len(doc.paragraphs)}")
    print(f"Paragraphs inside tables: {table_paragraphs}")
    print(f"Top-level tables: {len(doc.tables)}")
    for table_index, table in enumerate(doc.tables):
        dump_table(table, str(table_index))
    print("\nBody paragraphs:")
    for index, paragraph in enumerate(doc.paragraphs):
        text = snippet(paragraph.text)
        if text:
            print(f"  P{index}: {text!r}")


def main() -> None:
    for name in FILES:
        path = TEMPLATES / name
        if not path.is_file():
            print(f"MISSING: {path}")
            continue
        analyze(path)


if __name__ == "__main__":
    main()
