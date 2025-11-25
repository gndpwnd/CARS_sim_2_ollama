#!/usr/bin/env python3
"""
Qdrant Store - NMEA Messages and Agent Telemetry
Handles all non-relational time-series data (NMEA, positions, GPS metrics)

FIXED: Timestamp sorting to handle mixed string/float types
"""

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
import time
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional

# Configuration
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
NMEA_COLLECTION = "nmea_messages"
TELEMETRY_COLLECTION = "agent_telemetry"
VECTOR_DIM = 384  # MiniLM embedding size

# Initialize
model = SentenceTransformer("all-MiniLM-L6-v2")
qdrant_client = None


def init_qdrant(retries=5, delay=2):
    """Initialize Qdrant client and collections"""
    global qdrant_client
    
    for attempt in range(retries):
        try:
            qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
            
            # Create NMEA collection if not exists
            try:
                qdrant_client.get_collection(NMEA_COLLECTION)
                print(f"✅ Connected to Qdrant collection '{NMEA_COLLECTION}'")
            except:
                qdrant_client.create_collection(
                    collection_name=NMEA_COLLECTION,
                    vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE)
                )
                print(f"✅ Created Qdrant collection '{NMEA_COLLECTION}'")
            
            # Create Telemetry collection if not exists
            try:
                qdrant_client.get_collection(TELEMETRY_COLLECTION)
                print(f"✅ Connected to Qdrant collection '{TELEMETRY_COLLECTION}'")
            except:
                qdrant_client.create_collection(
                    collection_name=TELEMETRY_COLLECTION,
                    vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE)
                )
                print(f"✅ Created Qdrant collection '{TELEMETRY_COLLECTION}'")
            
            return True
            
        except Exception as e:
            print(f"🔁 Waiting for Qdrant... ({attempt + 1}/{retries}): {e}")
            time.sleep(delay)
    
    print("❌ Failed to connect to Qdrant after multiple attempts")
    return False


def _normalize_timestamp(ts: Any) -> str:
    """
    Normalize timestamp to ISO format string.
    Handles mixed types (str, float, int, datetime).
    
    Args:
        ts: Timestamp in any format
    
    Returns:
        ISO format string
    """
    if isinstance(ts, str):
        # Already a string, ensure it's not empty
        return ts if ts else datetime.now().isoformat()
    elif isinstance(ts, (int, float)):
        # Unix timestamp
        try:
            return datetime.fromtimestamp(ts).isoformat()
        except:
            return datetime.now().isoformat()
    elif isinstance(ts, datetime):
        return ts.isoformat()
    else:
        # Unknown type, use current time
        return datetime.now().isoformat()


def add_nmea_message(agent_id: str, nmea_sentence: str, metadata: Dict[str, Any]) -> Optional[str]:
    """
    Add a single NMEA message to Qdrant
    
    Args:
        agent_id: Agent identifier
        nmea_sentence: Raw NMEA sentence (e.g., "$GPGGA,...")
        metadata: Additional context (position, jamming, etc.)
    
    Returns:
        Point ID if successful, None otherwise
    """
    if not qdrant_client:
        print("[QDRANT] Client not initialized")
        return None
    
    try:
        # Create searchable text
        text = f"Agent {agent_id} NMEA: {nmea_sentence}"
        
        # Generate embedding
        embedding = model.encode([text])[0].tolist()
        
        # Create point ID
        point_id = str(uuid.uuid4())
        
        # Normalize timestamp
        timestamp = _normalize_timestamp(metadata.get('timestamp', datetime.now()))
        
        # Prepare payload
        payload = {
            "agent_id": agent_id,
            "nmea_sentence": nmea_sentence,
            "timestamp": timestamp,  # Always string
            "text": text,
            **{k: v for k, v in metadata.items() if k != 'timestamp'}  # Exclude old timestamp
        }
        
        # Insert into Qdrant
        qdrant_client.upsert(
            collection_name=NMEA_COLLECTION,
            points=[PointStruct(
                id=point_id,
                vector=embedding,
                payload=payload
            )]
        )
        
        return point_id
        
    except Exception as e:
        print(f"[QDRANT] Error adding NMEA message: {e}")
        return None


def add_telemetry(agent_id: str, position: tuple, metadata: Dict[str, Any]) -> Optional[str]:
    """
    Add agent telemetry (position, jamming status, GPS metrics)
    
    Args:
        agent_id: Agent identifier
        position: (x, y) coordinates
        metadata: GPS metrics, jamming status, etc.
    
    Returns:
        Point ID if successful, None otherwise
    """
    if not qdrant_client:
        print("[QDRANT] Client not initialized")
        return None
    
    try:
        # Create searchable text
        jammed = metadata.get('jammed', False)
        comm_quality = metadata.get('communication_quality', 0)
        
        text = (f"Agent {agent_id} at position ({position[0]:.2f}, {position[1]:.2f}) "
                f"{'JAMMED' if jammed else 'CLEAR'} "
                f"comm_quality={comm_quality:.2f}")
        
        # Generate embedding
        embedding = model.encode([text])[0].tolist()
        
        # Create point ID
        point_id = str(uuid.uuid4())
        
        # Normalize timestamp
        timestamp = _normalize_timestamp(metadata.get('timestamp', datetime.now()))
        
        # Prepare payload
        payload = {
            "agent_id": agent_id,
            "position_x": float(position[0]),
            "position_y": float(position[1]),
            "timestamp": timestamp,  # Always string
            "text": text,
            **{k: v for k, v in metadata.items() if k != 'timestamp'}  # Exclude old timestamp
        }
        
        # Insert into Qdrant
        qdrant_client.upsert(
            collection_name=TELEMETRY_COLLECTION,
            points=[PointStruct(
                id=point_id,
                vector=embedding,
                payload=payload
            )]
        )
        
        return point_id
        
    except Exception as e:
        print(f"[QDRANT] Error adding telemetry: {e}")
        return None


def get_agent_position_history(agent_id: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Get last N positions for an agent (for backtracking)
    
    Args:
        agent_id: Agent identifier
        limit: Number of recent positions to retrieve
    
    Returns:
        List of position records, newest first
    """
    if not qdrant_client:
        print("[QDRANT] Client not initialized")
        return []
    
    try:
        # Scroll through collection filtering by agent_id
        results = qdrant_client.scroll(
            collection_name=TELEMETRY_COLLECTION,
            scroll_filter={
                "must": [
                    {
                        "key": "agent_id",
                        "match": {"value": agent_id}
                    }
                ]
            },
            limit=limit * 3,  # Get more to ensure we have enough after sorting
            with_payload=True,
            with_vectors=False
        )[0]
        
        # FIXED: Normalize all timestamps before sorting
        for point in results:
            if 'timestamp' in point.payload:
                point.payload['timestamp'] = _normalize_timestamp(point.payload['timestamp'])
        
        # Sort by timestamp (newest first) - now all strings
        try:
            sorted_results = sorted(
                results,
                key=lambda x: x.payload.get('timestamp', ''),
                reverse=True
            )[:limit]
        except Exception as sort_error:
            print(f"[QDRANT] Warning: Could not sort by timestamp: {sort_error}")
            # Fallback: just take first N results
            sorted_results = results[:limit]
        
        # Extract position data
        positions = []
        for point in sorted_results:
            payload = point.payload
            # Convert position coordinates to float
            try:
                x = float(payload.get('position_x', 0))
                y = float(payload.get('position_y', 0))
                positions.append({
                    'position': (x, y),
                    'jammed': bool(payload.get('jammed', False)),
                    'communication_quality': float(payload.get('communication_quality', 0)),
                    'timestamp': str(payload.get('timestamp', ''))
                })
            except (ValueError, TypeError) as e:
                print(f"[QDRANT] Warning: Could not parse position data: {e}")
                continue
        
        return positions
        
    except Exception as e:
        print(f"[QDRANT] Error retrieving position history: {e}")
        import traceback
        traceback.print_exc()
        return []


def get_nmea_messages(agent_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get recent NMEA messages, optionally filtered by agent
    
    Args:
        agent_id: Optional agent filter
        limit: Number of messages to retrieve
    
    Returns:
        List of NMEA message records
    """
    if not qdrant_client:
        print("[QDRANT] Client not initialized")
        return []
    
    try:
        scroll_filter = None
        if agent_id:
            scroll_filter = {
                "must": [
                    {
                        "key": "agent_id",
                        "match": {"value": agent_id}
                    }
                ]
            }
        
        results = qdrant_client.scroll(
            collection_name=NMEA_COLLECTION,
            scroll_filter=scroll_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False
        )[0]
        
        # Normalize timestamps
        for point in results:
            if 'timestamp' in point.payload:
                point.payload['timestamp'] = _normalize_timestamp(point.payload['timestamp'])
        
        # Sort by timestamp
        try:
            sorted_results = sorted(
                results,
                key=lambda x: x.payload.get('timestamp', ''),
                reverse=True
            )
        except:
            sorted_results = results
        
        return [point.payload for point in sorted_results]
        
    except Exception as e:
        print(f"[QDRANT] Error retrieving NMEA messages: {e}")
        return []


def search_telemetry(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Semantic search through telemetry data
    
    Args:
        query: Search query (e.g., "jammed agents near origin")
        limit: Number of results
    
    Returns:
        List of matching telemetry records with scores
    """
    if not qdrant_client:
        print("[QDRANT] Client not initialized")
        return []
    
    try:
        # Generate query embedding
        query_vector = model.encode([query])[0].tolist()
        
        # Search
        results = qdrant_client.search(
            collection_name=TELEMETRY_COLLECTION,
            query_vector=query_vector,
            limit=limit,
            with_payload=True
        )
        
        return [
            {
                **hit.payload,
                'score': hit.score
            }
            for hit in results
        ]
        
    except Exception as e:
        print(f"[QDRANT] Error searching telemetry: {e}")
        return []


def clear_collections():
    """Clear all data from Qdrant collections"""
    if not qdrant_client:
        print("[QDRANT] Client not initialized")
        return
    
    try:
        qdrant_client.delete_collection(NMEA_COLLECTION)
        qdrant_client.delete_collection(TELEMETRY_COLLECTION)
        print("[QDRANT] Collections cleared")
        
        # Recreate
        init_qdrant()
        
    except Exception as e:
        print(f"[QDRANT] Error clearing collections: {e}")


# Initialize on import
init_qdrant()


# Export key functions
__all__ = [
    'add_nmea_message',
    'add_telemetry',
    'get_agent_position_history',
    'get_nmea_messages',
    'search_telemetry',
    'clear_collections'
]


if __name__ == "__main__":
    print("Testing Qdrant Store...")
    
    # Test NMEA message
    nmea_id = add_nmea_message(
        agent_id="test_agent1",
        nmea_sentence="$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47",
        metadata={
            'position': (5.0, 5.0),
            'fix_quality': 1,
            'satellites': 8,
            'jammed': False
        }
    )
    print(f"Added NMEA message: {nmea_id}")
    
    # Test telemetry
    telem_id = add_telemetry(
        agent_id="test_agent1",
        position=(5.0, 5.0),
        metadata={
            'jammed': False,
            'communication_quality': 1.0,
            'gps_satellites': 8,
            'gps_signal_quality': 45.0
        }
    )
    print(f"Added telemetry: {telem_id}")
    
    # Retrieve history
    history = get_agent_position_history("test_agent1", limit=5)
    print(f"Position history: {len(history)} entries")
    
    print("✅ Qdrant store test complete")