"""
Milvus Maintenance Operations
=============================

Provides maintenance and health monitoring for Milvus collections.
Addresses gaps in:
- Index maintenance
- Collection health monitoring
- Cleanup operations
- Statistics gathering
"""

import time
import logging
from typing import Dict, List, Optional, Any
from pymilvus import Collection, utility, connections

from ..config.logging_config import setup_logger
from ..config.settings import RESUME_COLLECTION, JD_COLLECTION

logger = setup_logger("milvus_maintenance")


class MilvusMaintenanceOps:
    """
    Maintenance operations for Milvus collections.
    
    Features:
    - Collection statistics
    - Index health checks
    - Compaction scheduling
    - Storage analysis
    """
    
    def __init__(self):
        self.collections = [RESUME_COLLECTION, JD_COLLECTION]
    
    def get_collection_stats(self, collection_name: str = None) -> Dict[str, Any]:
        """
        Get detailed statistics for a collection.
        
        Args:
            collection_name: Specific collection or None for all
            
        Returns:
            Dictionary with collection statistics
        """
        collections = [collection_name] if collection_name else self.collections
        stats = {}
        
        for col_name in collections:
            if not utility.has_collection(col_name):
                stats[col_name] = {"exists": False}
                continue
            
            try:
                collection = Collection(col_name)
                collection.load()
                
                # Get entity count
                num_entities = collection.num_entities
                
                # Get index info
                indexes = collection.indexes
                index_info = []
                for idx in indexes:
                    index_info.append({
                        "field": idx.field_name,
                        "type": str(idx.params.get("index_type", "unknown")),
                        "params": idx.params
                    })
                
                # Get schema info
                schema = collection.schema
                fields = [{"name": f.name, "dtype": str(f.dtype)} for f in schema.fields]
                
                stats[col_name] = {
                    "exists": True,
                    "num_entities": num_entities,
                    "indexes": index_info,
                    "fields": fields,
                    "loaded": True
                }
                
            except Exception as e:
                stats[col_name] = {"exists": True, "error": str(e)}
        
        return stats
    
    def check_index_health(self, collection_name: str) -> Dict[str, Any]:
        """
        Check health of indexes on a collection.
        
        Args:
            collection_name: Collection to check
            
        Returns:
            Health report dictionary
        """
        if not utility.has_collection(collection_name):
            return {"healthy": False, "reason": "Collection not found"}
        
        try:
            collection = Collection(collection_name)
            indexes = collection.indexes
            
            required_indexes = {
                "embedding": "HNSW",
                "document_type": "Trie",
                "entity_name": "Trie",
                "section_type": "Trie"
            }
            
            found_indexes = {idx.field_name: idx.params.get("index_type") for idx in indexes}
            
            missing = []
            wrong_type = []
            
            for field, expected_type in required_indexes.items():
                if field not in found_indexes:
                    missing.append(field)
                elif found_indexes[field] != expected_type:
                    wrong_type.append({
                        "field": field,
                        "expected": expected_type,
                        "actual": found_indexes[field]
                    })
            
            healthy = len(missing) == 0 and len(wrong_type) == 0
            
            return {
                "healthy": healthy,
                "missing_indexes": missing,
                "wrong_type_indexes": wrong_type,
                "found_indexes": found_indexes
            }
            
        except Exception as e:
            return {"healthy": False, "error": str(e)}
    
    def compact_collection(self, collection_name: str) -> Dict[str, Any]:
        """
        Trigger compaction on a collection.
        
        Compaction merges small segments and removes deleted entities.
        Should be run periodically for optimal performance.
        
        Args:
            collection_name: Collection to compact
            
        Returns:
            Compaction result
        """
        if not utility.has_collection(collection_name):
            return {"success": False, "reason": "Collection not found"}
        
        try:
            collection = Collection(collection_name)
            
            # Trigger compaction
            collection.compact()
            
            # Wait for completion (with timeout)
            start_time = time.time()
            max_wait = 60  # 60 seconds timeout
            
            while time.time() - start_time < max_wait:
                state = collection.get_compaction_state()
                if state.state == 2:  # Completed
                    break
                time.sleep(1)
            
            logger.info(f"Compaction completed for {collection_name}")
            return {"success": True, "collection": collection_name}
            
        except Exception as e:
            logger.error(f"Compaction failed: {e}")
            return {"success": False, "error": str(e)}
    
    def analyze_storage_waste(self, collection_name: str) -> Dict[str, Any]:
        """
        Analyze potential storage waste in a collection.
        
        Checks for:
        - Duplicated full_content across chunks
        - Oversized chunks
        - Empty fields
        
        Args:
            collection_name: Collection to analyze
            
        Returns:
            Analysis report
        """
        if not utility.has_collection(collection_name):
            return {"error": "Collection not found"}
        
        try:
            collection = Collection(collection_name)
            collection.load()
            
            # Sample some entities
            sample_size = min(100, collection.num_entities)
            if sample_size == 0:
                return {"message": "Collection is empty"}
            
            results = collection.query(
                expr="id >= 0",
                output_fields=["document_id", "full_content", "chunk_text"],
                limit=sample_size
            )
            
            # Analyze
            doc_full_content_count = {}
            total_full_content_size = 0
            empty_full_content = 0
            
            for entity in results:
                doc_id = entity.get("document_id", "unknown")
                full_content = entity.get("full_content", "")
                
                if not full_content:
                    empty_full_content += 1
                else:
                    total_full_content_size += len(full_content)
                    doc_full_content_count[doc_id] = doc_full_content_count.get(doc_id, 0) + 1
            
            # Check for duplicates
            duplicated_docs = {k: v for k, v in doc_full_content_count.items() if v > 1}
            
            return {
                "sample_size": sample_size,
                "empty_full_content": empty_full_content,
                "total_full_content_size_bytes": total_full_content_size,
                "avg_full_content_size": total_full_content_size // max(sample_size - empty_full_content, 1),
                "documents_with_duplicated_full_content": len(duplicated_docs),
                "optimized": empty_full_content > sample_size * 0.5  # More than 50% empty = optimized
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def get_entity_counts_by_type(self, collection_name: str) -> Dict[str, int]:
        """
        Get entity counts grouped by document_type and entity_name.
        
        Args:
            collection_name: Collection to query
            
        Returns:
            Dictionary with counts by type
        """
        if not utility.has_collection(collection_name):
            return {}
        
        try:
            collection = Collection(collection_name)
            collection.load()
            
            # Query all unique entity names
            results = collection.query(
                expr="id >= 0",
                output_fields=["document_type", "entity_name"],
                limit=10000
            )
            
            # Count
            type_counts = {}
            entity_counts = {}
            
            for entity in results:
                doc_type = entity.get("document_type", "unknown")
                entity_name = entity.get("entity_name", "unknown")
                
                type_counts[doc_type] = type_counts.get(doc_type, 0) + 1
                entity_counts[entity_name] = entity_counts.get(entity_name, 0) + 1
            
            return {
                "by_document_type": type_counts,
                "by_entity_name": entity_counts,
                "total": len(results)
            }
            
        except Exception as e:
            return {"error": str(e)}


# Convenience functions
def get_all_collection_stats() -> Dict[str, Any]:
    """Get stats for all collections."""
    return MilvusMaintenanceOps().get_collection_stats()


def compact_all_collections() -> Dict[str, Any]:
    """Compact all collections."""
    ops = MilvusMaintenanceOps()
    results = {}
    for col in ops.collections:
        results[col] = ops.compact_collection(col)
    return results


def health_check() -> Dict[str, Any]:
    """Perform health check on all collections."""
    ops = MilvusMaintenanceOps()
    results = {}
    for col in ops.collections:
        results[col] = ops.check_index_health(col)
    results["all_healthy"] = all(r.get("healthy", False) for r in results.values())
    return results
