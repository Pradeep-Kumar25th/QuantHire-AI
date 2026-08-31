"""
QuantHire AI - In-Memory Vector Database Implementation
======================================================

This implements a Milvus-compatible in-memory vector database
for when Docker/Milvus is not available
"""

import numpy as np
from typing import List, Dict, Any, Optional
import json
from datetime import datetime

class InMemoryVectorDatabase:
    """In-memory vector database that mimics Milvus functionality"""
    
    def __init__(self):
        self.collections = {}
        self.collection_schemas = {}
        self.indexes = {}
        print("✅ In-Memory Vector Database initialized")
    
    def create_collection(self, collection_name: str, schema: Any):
        """Create a collection in the in-memory database"""
        self.collections[collection_name] = {
            'data': [],
            'embeddings': [],
            'metadata': []
        }
        self.collection_schemas[collection_name] = schema
        print(f"✅ Created collection: {collection_name}")
        return True
    
    def insert(self, collection_name: str, data: List[List]):
        """Insert data into the collection"""
        if collection_name not in self.collections:
            self.create_collection(collection_name, None)
        
        # data format: [[resume_ids], [contents], [embeddings]]
        resume_ids, contents, embeddings = data
        
        for i in range(len(resume_ids)):
            self.collections[collection_name]['data'].append({
                'id': len(self.collections[collection_name]['data']),
                'resume_id': resume_ids[i],
                'content': contents[i],
                'embedding': embeddings[i]
            })
        
        print(f"✅ Inserted {len(resume_ids)} records into {collection_name}")
        return True
    
    def search(self, collection_name: str, query_embedding: List[float], 
               search_params: Dict, limit: int = 10, output_fields: List[str] = None):
        """Search for similar vectors using cosine similarity"""
        
        if collection_name not in self.collections:
            return []
        
        collection_data = self.collections[collection_name]['data']
        if not collection_data:
            return []
        
        # Calculate cosine similarities
        similarities = []
        query_vector = np.array(query_embedding)
        
        for item in collection_data:
            item_vector = np.array(item['embedding'])
            
            # Cosine similarity
            dot_product = np.dot(query_vector, item_vector)
            norm_query = np.linalg.norm(query_vector)
            norm_item = np.linalg.norm(item_vector)
            
            if norm_query > 0 and norm_item > 0:
                similarity = dot_product / (norm_query * norm_item)
            else:
                similarity = 0
            
            similarities.append({
                'entity': {
                    'resume_id': item['resume_id'],
                    'content': item['content']
                },
                'score': float(similarity)
            })
        
        # Sort by similarity and return top results
        similarities.sort(key=lambda x: x['score'], reverse=True)
        return [similarities[:limit]]
    
    def create_index(self, collection_name: str, field_name: str, index_params: Dict):
        """Create an index (for compatibility)"""
        self.indexes[collection_name] = {
            'field': field_name,
            'params': index_params
        }
        print(f"✅ Created index for {collection_name}.{field_name}")
        return True
    
    def load(self, collection_name: str):
        """Load collection (for compatibility)"""
        print(f"✅ Loaded collection: {collection_name}")
        return True
    
    def flush(self, collection_name: str = None):
        """Flush data (for compatibility)"""
        print(f"✅ Flushed collection: {collection_name or 'all'}")
        return True

# Global instance
in_memory_db = InMemoryVectorDatabase()

# Mock Milvus classes for compatibility
class Collection:
    def __init__(self, name: str, schema: Any = None):
        self.name = name
        self.schema = schema
        in_memory_db.create_collection(name, schema)
    
    def insert(self, data: List[List]):
        return in_memory_db.insert(self.name, data)
    
    def search(self, query_embedding: List[List], field_name: str, 
               search_params: Dict, limit: int = 10, output_fields: List[str] = None):
        return in_memory_db.search(self.name, query_embedding[0], search_params, limit, output_fields)
    
    def create_index(self, field_name: str, index_params: Dict):
        return in_memory_db.create_index(self.name, field_name, index_params)
    
    def load(self):
        return in_memory_db.load(self.name)
    
    def flush(self):
        return in_memory_db.flush(self.name)

class CollectionSchema:
    def __init__(self, fields: List, description: str = ""):
        self.fields = fields
        self.description = description

class FieldSchema:
    def __init__(self, name: str, dtype: Any, is_primary: bool = False, 
                 auto_id: bool = False, max_length: int = None):
        self.name = name
        self.dtype = dtype
        self.is_primary = is_primary
        self.auto_id = auto_id
        self.max_length = max_length

class DataType:
    INT64 = "INT64"
    VARCHAR = "VARCHAR"
    FLOAT_VECTOR = "FLOAT_VECTOR"

def connections():
    class Connection:
        @staticmethod
        def connect(alias: str, host: str, port: int):
            print(f"✅ Connected to in-memory database: {host}:{port}")
            return True
    return Connection()

def utility():
    class Utility:
        @staticmethod
        def has_collection(name: str):
            return name in in_memory_db.collections
    return Utility()

print("✅ In-Memory Vector Database (Milvus-compatible) ready!")

