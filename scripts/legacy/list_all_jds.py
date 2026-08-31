"""List all unique JD names in Milvus."""
from pymilvus import connections, Collection

connections.connect('default', host='localhost', port='19530')
col = Collection('quanthire_job_descriptions')
col.load()

# Get all unique entity names for JDs
results = col.query(
    expr='document_type == "jd"', 
    output_fields=['entity_name', 'document_id'], 
    limit=200
)

# Group by entity_name
from collections import Counter
names = Counter(r.get('entity_name') for r in results)

print(f"Total JD chunks: {len(results)}")
print(f"\nUnique JD names ({len(names)}):")
for n, count in sorted(names.items(), key=lambda x: x[0]):
    print(f"  {count} chunks: {n}")

# Search for UI/UX
print("\n--- UI/UX related JDs ---")
ux_names = [n for n in names.keys() if 'UX' in n.upper() or 'UI' in n.upper()]
for n in ux_names:
    print(f"  - {n} ({names[n]} chunks)")
