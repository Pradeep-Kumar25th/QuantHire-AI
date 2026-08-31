"""Ingestion modules for QuantChat AI."""

from typing import Optional

_ingestion_instance: Optional['DocumentIngestion'] = None

def get_document_ingestion():
    """Get DocumentIngestion singleton instance."""
    from .document_ingestion import DocumentIngestion
    global _ingestion_instance
    if _ingestion_instance is None:
        _ingestion_instance = DocumentIngestion()
        _ingestion_instance.connect()
        _ingestion_instance.load_embedding_model()
    return _ingestion_instance
