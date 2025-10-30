"""
Integrations module for cross-cutting concerns like logging and monitoring.
"""
from typing import Dict, Any, Optional
from datetime import datetime

try:
    from postgresql_store import log_message as db_log_message
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False
    print("[INTEGRATIONS] PostgreSQL store not available")

def add_log(message: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
    """
    Add a log message with metadata to the database
    
    Args:
        message: The message to log
        metadata: Optional metadata dictionary
    
    Returns:
        True if logging succeeded, False otherwise
    """
    if not metadata:
        metadata = {}
    
    # Ensure we have a timestamp
    if 'timestamp' not in metadata:
        metadata['timestamp'] = datetime.now().isoformat()
    
    try:
        if POSTGRESQL_AVAILABLE:
            db_log_message(message, metadata)
            return True
        else:
            # Fallback to console logging
            print(f"[LOG] {metadata.get('timestamp', '')} | {metadata.get('source', 'unknown')} | {message}")
            return True
            
    except Exception as e:
        print(f"[INTEGRATIONS] Error logging message: {e}")
        print(f"[INTEGRATIONS] Message: {message}")
        print(f"[INTEGRATIONS] Metadata: {metadata}")
        return False