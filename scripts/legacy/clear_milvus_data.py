"""
Clear all data from Milvus collections while preserving schema.
"""
from pymilvus import connections, Collection, utility

def main():
    # Connect to Milvus
    connections.connect(host='localhost', port='19530')
    print('✅ Connected to Milvus')
    
    collections_to_clear = ['quanthire_resumes', 'quanthire_job_descriptions']
    
    for name in collections_to_clear:
        if not utility.has_collection(name):
            print(f'⚠️ Collection {name} does not exist')
            continue
        
        col = Collection(name)
        col.load()
        before = col.num_entities
        print(f'\n📊 {name}: {before} entities')
        
        if before == 0:
            print('  Already empty, skipping...')
            continue
        
        try:
            results = col.query(
                expr='document_type != ""',
                output_fields=['id'],
                limit=50000
            )
            ids = [r['id'] for r in results]
            print(f'  Found {len(ids)} entities to delete')
            
            if ids:
                batch_size = 1000
                for i in range(0, len(ids), batch_size):
                    batch_ids = ids[i:i+batch_size]
                    expr = f'id in {batch_ids}'
                    col.delete(expr=expr)
                    print(f'  Deleted batch {i//batch_size + 1}')
                
                col.flush()
                
                col.release()
                col.load()
                after = col.num_entities
                print(f'  ✅ After deletion: {after} entities')
        
        except Exception as e:
            print(f'  ❌ Error: {e}')
            print('  Trying alternative method...')
            try:
                schema = col.schema
                col.release()
                utility.drop_collection(name)
                print(f'  Dropped collection {name}')
                new_col = Collection(name=name, schema=schema)
                print(f'  ✅ Recreated collection {name} with same schema')
            except Exception as e2:
                print(f'  ❌ Alternative also failed: {e2}')
    
    print('\n✅ Data clearing complete!')
    
    print('\n📊 Final status:')
    for name in collections_to_clear:
        if utility.has_collection(name):
            col = Collection(name)
            col.load()
            print(f'  {name}: {col.num_entities} entities')
        else:
            print(f'  {name}: Collection does not exist')

if __name__ == '__main__':
    main()
