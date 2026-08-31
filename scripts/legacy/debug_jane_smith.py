import os
import sys
import logging
import json
from enterprise_rag_integration import get_enterprise_rag

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_full_doc():
    rag = get_enterprise_rag()
    query = "Show me the full resume of JANE SMITH"
    
    try:
        print(f"DEBUG: Processing query: {query}")
        result = rag.process_query_hybrid(query)
        print(f"RESULT: {result}")
    except Exception as e:
        import traceback
        print(f"ERROR: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    debug_full_doc()
