
from pymilvus import connections, Collection, utility
import os

MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = int(os.getenv("MILVUS_PORT", "19530"))

def inspect_data():
    try:
        connections.connect(host=MILVUS_HOST, port=MILVUS_PORT)
        print(f"Connected to Milvus at {MILVUS_HOST}:{MILVUS_PORT}")
        
        if not utility.has_collection("quanthire_resumes"):
            print("Collection quanthire_resumes does not exist.")
            return
            
        col = Collection("quanthire_resumes")
        col.load()
        
        print("\n--- Sample Data from quanthire_resumes ---")
        results = col.query(expr="", output_fields=["id", "entity_name", "document_type"], limit=5)
        for res in results:
            print(res)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_data()
