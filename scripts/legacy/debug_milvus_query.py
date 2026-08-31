"""Debug the full document retrieval query."""
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Add paths
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from pymilvus import connections, Collection

connections.connect('default', host='localhost', port='19530')
col = Collection('quanthire_job_descriptions')
col.load()

print("=" * 60)
print("DEBUGGING MILVUS QUERY FOR 'UI/UX Designer'")
print("=" * 60)

# Test 1: See what the current query looks like
entity_name = "UI/UX Designer"
words = [w.strip() for w in entity_name.replace('/', ' ').replace('-', ' ').split() if w.strip()]
common_words = {'a', 'an', 'the', 'for', 'and', 'or', 'of', 'to', 'in', 'on', 'at'}
words = [w for w in words if w.lower() not in common_words]

print(f"\nQuery: '{entity_name}'")
print(f"Extracted words: {words}")

# Build like conditions
like_conditions = []
for word in words:
    word_lower = word.lower()
    word_upper = word.upper()
    word_cap = word.capitalize()
    like_conditions.extend([
        f'entity_name like "{word}%"',
        f'entity_name like "{word_lower}%"',
        f'entity_name like "{word_upper}%"',
        f'entity_name like "{word_cap}%"',
    ])

print(f"\nLike conditions ({len(like_conditions)}):")
for c in like_conditions[:8]:  # Just show first 8
    print(f"  {c}")

# Test direct queries
print("\n--- Testing individual conditions ---")

test_conditions = [
    'entity_name like "UI%"',
    'entity_name like "UX%"',
    'entity_name like "Designer%"',
    'entity_name like "Junior%"',
]

for cond in test_conditions:
    expr = f'document_type == "jd" && {cond}'
    results = col.query(expr=expr, output_fields=['entity_name'], limit=10)
    names = set(r.get('entity_name') for r in results)
    print(f"  {cond} -> {len(results)} results: {names if names else 'None'}")

# Test the full query
print("\n--- Testing combined OR query ---")
combined_expr = f'document_type == "jd" && ({" || ".join(like_conditions)})'
print(f"Expression length: {len(combined_expr)} chars")
try:
    results = col.query(expr=combined_expr, output_fields=['entity_name'], limit=50)
    names = set(r.get('entity_name') for r in results)
    print(f"Results: {len(results)} chunks from {len(names)} unique JDs")
    for n in names:
        print(f"  - {n}")
except Exception as e:
    print(f"Error: {e}")
