"""
Recreate Milvus Collections with Optimized Schema
==================================================

This script:
1. Drops old collections (if they exist)
2. Creates new collections with optimized schema
3. Sets up HNSW indices for better performance

Run this before re-uploading resumes/JDs.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from pymilvus import connections, Collection, CollectionSchema, utility
from milvus_schema import (
    UNIFIED_FIELDS,
    INDEX_PARAMS,
    RESUME_COLLECTION,
    JD_COLLECTION,
    UNIFIED_COLLECTION_SCHEMA,
)

def recreate_collections():
    """Drop old collections and create new ones with optimized schema."""
    
    print("🔌 Connecting to Milvus...")
    try:
        connections.connect(
            alias="default",
            host="localhost",
            port="19530"
        )
        print("✅ Connected to Milvus")
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        return False
    
    # Drop old collections
    print("\n🗑️  Dropping old collections...")
    for col_name in [RESUME_COLLECTION, JD_COLLECTION]:
        if utility.has_collection(col_name):
            utility.drop_collection(col_name)
            print(f"   ✅ Dropped: {col_name}")
        else:
            print(f"   ⚠️  Not found: {col_name}")
    
    # Create new collections
    print("\n📦 Creating new collections with optimized schema...")
    
    # Resume Collection
    print(f"\n1️⃣  Creating {RESUME_COLLECTION}...")
    resume_collection = Collection(
        name=RESUME_COLLECTION,
        schema=UNIFIED_COLLECTION_SCHEMA
    )
    print(f"   ✅ Collection created")
    
    print(f"   🔍 Creating HNSW index on embedding field...")
    resume_collection.create_index(
        field_name="embedding",
        index_params=INDEX_PARAMS
    )
    print(f"   ✅ HNSW index created")
    
    # JD Collection
    print(f"\n2️⃣  Creating {JD_COLLECTION}...")
    jd_collection = Collection(
        name=JD_COLLECTION,
        schema=UNIFIED_COLLECTION_SCHEMA
    )
    print(f"   ✅ Collection created")
    
    print(f"   🔍 Creating HNSW index on embedding field...")
    jd_collection.create_index(
        field_name="embedding",
        index_params=INDEX_PARAMS
    )
    print(f"   ✅ HNSW index created")
    
    # Verify
    print("\n📊 Verification:")
    print(f"   Resume collection exists: {utility.has_collection(RESUME_COLLECTION)}")
    print(f"   JD collection exists: {utility.has_collection(JD_COLLECTION)}")
    
    # Show schema
    print(f"\n📋 Schema fields:")
    for field in UNIFIED_FIELDS:
        field_type = str(field.dtype).split(".")[-1]
        if field.dtype.name == "FLOAT_VECTOR":
            print(f"   • {field.name}: {field_type} (dim={field.params.get('dim', 'N/A')})")
        elif field.dtype.name in ["VARCHAR", "STRING"]:
            print(f"   • {field.name}: {field_type} (max_length={field.params.get('max_length', 'N/A')})")
        else:
            print(f"   • {field.name}: {field_type}")
    
    print(f"\n🎯 Index type: {INDEX_PARAMS['index_type']}")
    print(f"   Parameters: {INDEX_PARAMS['params']}")
    
    print("\n✅ Collections recreated successfully!")
    print("\n📝 Next steps:")
    print("   1. Restart your API server")
    print("   2. Re-upload Rahul's resume")
    print("   3. Test queries with entity_name support")
    
    return True


if __name__ == "__main__":
    print("="*60)
    print("Recreate Milvus Collections - Optimized Schema")
    print("="*60)
    
    success = recreate_collections()
    
    if success:
        print("\n" + "="*60)
        print("✅ SUCCESS - Collections ready for data!")
        print("="*60)
    else:
        print("\n" + "="*60)
        print("❌ FAILED - Check errors above")
        print("="*60)
        sys.exit(1)
