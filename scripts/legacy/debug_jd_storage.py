"""Debug script to check JD storage in Milvus"""
from pymilvus import connections, Collection

connections.connect('default', host='localhost', port='19530')

from pymilvus import utility
collections = utility.list_collections()
print(f"Collections: {collections}")

jd_collection = None
for col_name in collections:
    if 'jd' in col_name.lower() or 'job_description' in col_name.lower():
        jd_collection = col_name
        print(f"Found JD collection: {jd_collection}")

if jd_collection:
    col = Collection(jd_collection)
    col.load()
    
    results = col.query(
        expr='entity_name != ""',
        output_fields=['document_id', 'entity_name', 'section_type', 'chunk_text'],
        limit=50
    )
    
    print(f"\nFound {len(results)} JD chunks in {jd_collection}")
    print("="*60)
    
    jds = {}
    for r in results:
        name = r['entity_name']
        if name not in jds:
            jds[name] = []
        jds[name].append(r)
    
    print(f"\nUnique JDs: {len(jds)}")
    for name, chunks in jds.items():
        print(f"  - {name}: {len(chunks)} chunks")
        
    print("\n" + "="*60)
    print("Looking for 'Data Analyst' JDs:")
    for name in jds:
        if 'data analyst' in name.lower():
            print(f"  Found: {name}")
            for chunk in jds[name][:2]:
                print(f"    Section: {chunk['section_type']}")
                print(f"    Content preview: {chunk['chunk_text'][:200]}...")
else:
    print("No JD collection found!")
    
    if 'quanthire_resumes' in collections:
        col = Collection('quanthire_resumes')
        col.load()
        print("\nChecking quanthire_resumes for JD documents...")
