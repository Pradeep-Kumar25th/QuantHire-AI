from pymilvus import connections, utility

try:
    connections.connect("default", host="localhost", port="19530")
    print("Connected to Milvus")
    collections = utility.list_collections()
    print("Collections found:", collections)
except Exception as e:
    print(f"Error: {e}")
