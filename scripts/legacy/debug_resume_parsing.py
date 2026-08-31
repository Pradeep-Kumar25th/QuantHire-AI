"""
Debug Resume Parsing Output
============================

Check what data the AI agent is actually returning and why only 1 chunk is created.
"""

import sys
import json
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from pymilvus import connections, Collection, utility

def check_stored_resume():
    """Check what data is actually stored in Milvus."""
    
    print("="*60)
    print("Debug: Resume Data in Milvus")
    print("="*60)
    
    try:
        connections.connect(host="localhost", port="19530")
        print("✅ Connected to Milvus\n")
        
        collection = Collection("quanthire_resumes")
        collection.load()
        
        print(f"📊 Collection Stats:")
        print(f"   Total entities: {collection.num_entities}")
        
        if collection.num_entities == 0:
            print("\n❌ No data in collection!")
            return
        
        # Query all data
        results = collection.query(
            expr="",
            output_fields=["document_id", "document_type", "entity_name", "section_type", "chunk_text_reference", "created_at"],
            limit=20
        )
        
        print(f"\n📋 Stored Chunks ({len(results)} found):")
        print("="*60)
        
        for i, result in enumerate(results, 1):
            print(f"\nChunk {i}:")
            print(f"   Document ID: {result.get('document_id')}")
            print(f"   Entity Name: {result.get('entity_name')}")  # ← Check if proper name
            print(f"   Section: {result.get('section_type')}")
            print(f"   Content Length: {len(result.get('chunk_text_reference', ''))} chars")
            print(f"   Content Preview: {result.get('chunk_text_reference', '')[:200]}...")
        
        # Check if we have all expected sections
        sections = [r.get('section_type') for r in results]
        expected_sections = ['Personal Info', 'Skills', 'Experience', 'Education']
        
        print(f"\n📊 Section Analysis:")
        print(f"   Found sections: {sections}")
        print(f"   Expected sections: {expected_sections}")
        
        missing = [s for s in expected_sections if s not in sections]
        if missing:
            print(f"\n❌ MISSING SECTIONS: {missing}")
            print(f"\n⚠️  This means the resume is NOT fully chunked!")
            print(f"   Reason: AI agent is not returning complete parsed data structure")
        else:
            print(f"\n✅ All expected sections present")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


def check_candidate_name():
    """Specifically check if entity_name is being stored correctly."""
    
    print("\n" + "="*60)
    print("Debug: entity_name Field")
    print("="*60)
    
    try:
        connections.connect(alias="check_name", host="localhost", port="19530")
        
        collection = Collection("quanthire_resumes")
        collection.load()
        
        results = collection.query(
            expr="",
            output_fields=["entity_name", "section_type"],
            limit=10
        )
        
        print(f"\n📋 Entity Names Stored:")
        unique_names = set()
        for r in results:
            name = r.get('entity_name')
            section = r.get('section_type')
            print(f"   • {name} (section: {section})")
            unique_names.add(name)
        
        print(f"\n📊 Summary:")
        print(f"   Total chunks: {len(results)}")
        print(f"   Unique entity names: {len(unique_names)}")
        print(f"   Names: {list(unique_names)}")
        
        if None in unique_names or 'Unknown' in unique_names:
            print(f"\n⚠️  WARNING: entity_name is None or 'Unknown'!")
            print(f"   This means candidate name extraction failed")
        
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    print("\n🔍 DEBUGGING RESUME PARSING & STORAGE")
    print("="*60)
    
    check_stored_resume()
    check_candidate_name()
    
    print("\n" + "="*60)
    print("Debug Complete")
    print("="*60)
