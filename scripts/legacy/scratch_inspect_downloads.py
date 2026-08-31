from docx import Document
from pathlib import Path

p_leader = Path(r"c:\Users\prakumar\Downloads\JD Templates\JD Template_Leader position (1).docx")
p_non_leader = Path(r"c:\Users\prakumar\Downloads\JD Templates\JD Template_Non-Leader position (2).docx")

print("Leader exists:", p_leader.is_file())
print("Non-Leader exists:", p_non_leader.is_file())

if p_leader.is_file():
    doc_l = Document(str(p_leader))
    t = doc_l.tables[0]
    print(f"\nLeader table rows: {len(t.rows)}")
    for idx, r in enumerate(t.rows):
        txt = r.cells[0].text.strip().replace('\n', ' ')[:45]
        print(f"  Row {idx:2d}: {txt}")

if p_non_leader.is_file():
    doc_nl = Document(str(p_non_leader))
    t = doc_nl.tables[0]
    print(f"\nNon-Leader table rows: {len(t.rows)}")
    for idx, r in enumerate(t.rows):
        txt = r.cells[0].text.strip().replace('\n', ' ')[:45]
        print(f"  Row {idx:2d}: {txt}")
