"""Debug script to check Arjun Mehta's data in Milvus"""
from pymilvus import connections, Collection

connections.connect('default', host='localhost', port='19530')
col = Collection('quanthire_resumes')
col.load()

# Search for Arjun Mehta
results = col.query(
    expr='entity_name like "ARJUN%" or entity_name like "Arjun%"',
    output_fields=['document_id', 'entity_name', 'section_type', 'chunk_text', 'full_content'],
    limit=20
)

print(f'Found {len(results)} chunks for Arjun Mehta')
print('='*80)
for r in results:
    print(f"Section: {r['section_type']}")
    chunk = r['chunk_text'] if r['chunk_text'] else ''
    print(f"Chunk Text ({len(chunk)} chars):")
    print(chunk[:500] if len(chunk) > 500 else chunk)
    full = r.get('full_content', '') or ''
    print(f"Full Content: {len(full)} chars")
    print('-'*40)
