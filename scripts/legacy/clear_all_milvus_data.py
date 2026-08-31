from pymilvus import connections, Collection, utility
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clear_collections():
    try:
        connections.connect("default", host="localhost", port="19530")
        logger.info("Connected to Milvus.")
    except Exception as e:
        logger.error(f"Connection failed: {e}")
        return

    collections_to_clear = ["quanthire_resumes", "quanthire_job_descriptions"]
    
    for collection_name in collections_to_clear:
        if not utility.has_collection(collection_name):
            logger.warning(f"Collection {collection_name} does not exist. Skipping.")
            continue
            
        try:
            collection = Collection(collection_name)
            collection.load()
            
            num_entities = collection.num_entities
            logger.info(f"Collection {collection_name} has {num_entities} entities.")
            
            if num_entities > 0:
                logger.info(f"Clearing all data from {collection_name}...")
                pk_field = None
                for field in collection.schema.fields:
                    if field.is_primary:
                        pk_field = field.name
                        break
                
                if pk_field:
                    logger.info(f"Deleting using primary key: {pk_field}")
                    collection.delete(expr=f"{pk_field} >= 0")
                    collection.flush()
                    collection.load()
                    logger.info(f"✅ Collection {collection_name} cleared. Now has {collection.num_entities} entities.")
                else:
                    logger.error(f"Could not find primary key for {collection_name}")
            else:
                logger.info(f"Collection {collection_name} is already empty.")
                
        except Exception as e:
            logger.error(f"Failed to clear {collection_name}: {e}")

if __name__ == "__main__":
    clear_collections()
