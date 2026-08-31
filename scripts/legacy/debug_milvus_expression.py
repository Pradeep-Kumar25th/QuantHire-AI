"""Debug the Milvus expression for Aditya Rao query"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

# Test the metadata filter directly
from apps.quantchat.retrieval.metadata_filter import MetadataFilter

mf = MetadataFilter()

# Simulate filters for "Aditya Rao"
filters1 = {"document_type": "resume", "entity_names": ["Karan Kumar"]}
filters2 = {"document_type": "resume", "entity_names": ["Aditya Rao"]}

expr1 = mf.build_milvus_expression(filters1)
expr2 = mf.build_milvus_expression(filters2)

print("=" * 70)
print("Metadata Filter Expression Debug")
print("=" * 70)

print(f"\nQuery: 'Karan Kumar'")
print(f"Expression: {expr1}")

print(f"\nQuery: 'Aditya Rao'")
print(f"Expression: {expr2}")

# Now test the expressions directly in Milvus
from pymilvus import connections, Collection

connections.connect("default", host="localhost", port="19530")
c = Collection("quanthire_resumes")
c.load()

print("\n" + "=" * 70)
print("Testing expressions in Milvus")
print("=" * 70)

# Test expression 1
print(f"\nTesting: {expr1}")
try:
    results = c.query(expr=expr1, output_fields=["entity_name"], limit=10)
    print(f"✅ Success! Found {len(results)} results")
    for r in results:
        print(f"   - {r.get('entity_name')}")
except Exception as e:
    print(f"❌ Failed: {e}")

# Test expression 2
print(f"\nTesting: {expr2}")
try:
    results = c.query(expr=expr2, output_fields=["entity_name"], limit=10)
    print(f"✅ Success! Found {len(results)} results")
    for r in results:
        print(f"   - {r.get('entity_name')}")
except Exception as e:
    print(f"❌ Failed: {e}")

# Test without the entity filter
print(f"\nTesting without entity filter:")
try:
    results = c.query(expr='document_type == "resume"', output_fields=["entity_name"], limit=10)
    print(f"✅ Success! Found {len(results)} results")
    for r in results:
        print(f"   - {r.get('entity_name')}")
except Exception as e:
    print(f"❌ Failed: {e}")
