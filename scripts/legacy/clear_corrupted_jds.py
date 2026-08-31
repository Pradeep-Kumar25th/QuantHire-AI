from pymilvus import connections, utility
import os

def clear_corrupted_collection():
    try:
        connections.connect("default", host="localhost", port="19530")
        print("Connected to Milvus.")
    except Exception as e:
        print(f"Connection failed: {e}")
        return

    collection_name = "quanthire_job_descriptions"
    if utility.has_collection(collection_name):
        print(f"Dropping corrupted collection: {collection_name}")
        utility.drop_collection(collection_name)
        print("✅ Collection dropped successfully.")
    else:
        print(f"Collection {collection_name} does not exist.")

if __name__ == "__main__":
    clear_corrupted_collection()
