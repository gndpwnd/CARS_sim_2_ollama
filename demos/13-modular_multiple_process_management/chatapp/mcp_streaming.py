"""
Streaming endpoints for real-time log updates.
"""
import json
import asyncio
from datetime import datetime
from fastapi.responses import StreamingResponse

# Import storage functions
try:
    import psycopg2
    from core.config import DB_CONFIG
    PG_AVAILABLE = True
except ImportError:
    PG_AVAILABLE = False
    print("[STREAMING] PostgreSQL not available")

try:
    from qdrant_client import QdrantClient
    from core.config import QDRANT_HOST, QDRANT_PORT, TELEMETRY_COLLECTION
    QDRANT_AVAILABLE = True
    qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
except:
    QDRANT_AVAILABLE = False
    qdrant_client = None
    print("[STREAMING] Qdrant not available")

def fetch_logs_from_db(limit=None):
    """Fetch logs from PostgreSQL"""
    if not PG_AVAILABLE:
        return []
    
    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                query = "SELECT id, text, metadata, created_at FROM logs"
                if limit:
                    query += f" ORDER BY created_at DESC LIMIT {limit}"
                else:
                    query += " ORDER BY created_at DESC"
                cur.execute(query)
                rows = cur.fetchall()
                
                logs = []
                for row in rows:
                    log_id, content, metadata_json, created_at = row
                    metadata = json.loads(metadata_json) if isinstance(metadata_json, str) else metadata_json
                    logs.append({
                        "log_id": str(log_id),
                        "text": content,
                        "metadata": metadata,
                        "created_at": created_at.isoformat(),
                        "source": "postgresql"
                    })
                return logs
    except Exception as e:
        print(f"Error fetching logs from DB: {e}")
        return []

def fetch_logs_from_qdrant(limit=50, offset=None):
    """Fetch logs from Qdrant vector database"""
    if not qdrant_client:
        return []
    
    try:
        results = qdrant_client.scroll(
            collection_name=TELEMETRY_COLLECTION,
            limit=limit,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )[0]
        
        logs = []
        for point in results:
            payload = point.payload
            
            # Ensure timestamp is current if not provided
            current_time = datetime.now().isoformat()
            timestamp = payload.get('timestamp', current_time)
            if not isinstance(timestamp, str):
                timestamp = current_time
            
            metadata = {
                'agent_id': payload.get('agent_id'),
                'position': (payload.get('position_x', 0), payload.get('position_y', 0)),
                'jammed': payload.get('jammed', False),
                'communication_quality': payload.get('communication_quality', 0),
                'timestamp': timestamp,
                'iteration': payload.get('iteration'),
                'gps_satellites': payload.get('gps_satellites'),
                'gps_signal_quality': payload.get('gps_signal_quality'),
                'gps_fix_quality': payload.get('gps_fix_quality')
            }
            
            # Build descriptive text
            position_x = payload.get('position_x', 0)
            position_y = payload.get('position_y', 0)
            jammed = payload.get('jammed', False)
            comm_quality = payload.get('communication_quality', 0)
            
            text = (
                f"Agent {payload.get('agent_id', 'unknown')} at position ({position_x:.2f}, {position_y:.2f}) "
                f"{'JAMMED' if jammed else 'CLEAR'} comm_quality={comm_quality:.2f}"
            )
            
            logs.append({
                "log_id": str(point.id),
                "text": text,
                "metadata": metadata,
                "created_at": metadata['timestamp'],  # Use the normalized timestamp from metadata
                "source": "qdrant",
                "vector_score": None
            })
        
        # Sort logs by timestamp descending
        logs.sort(key=lambda x: x['created_at'], reverse=True)
        
        return logs
    except Exception as e:
        print(f"Error fetching from Qdrant: {e}")
        return []

async def stream_postgresql():
    """Stream PostgreSQL logs in real-time"""
    async def event_generator():
        last_check_time = datetime.now()
        
        while True:
            try:
                logs = fetch_logs_from_db(limit=10)
                
                for log in logs:
                    log_time = datetime.fromisoformat(log.get("created_at", datetime.now().isoformat()))
                    if log_time > last_check_time:
                        yield f"data: {json.dumps(log)}\n\n"
                
                last_check_time = datetime.now()
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"Error in PostgreSQL stream: {e}")
                await asyncio.sleep(1)
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")

async def stream_qdrant():
    """Stream Qdrant logs in real-time"""
    async def event_generator():
        seen_ids = set()  # Track which logs we've already sent
        
        while True:
            try:
                if qdrant_client:
                    # Get latest logs
                    logs = fetch_logs_from_qdrant(limit=50)
                    
                    # Filter and send only unseen logs
                    new_logs = []
                    for log in logs:
                        log_id = log.get('log_id')
                        if log_id and log_id not in seen_ids:
                            new_logs.append(log)
                            seen_ids.add(log_id)
                    
                    # Send new logs
                    for log in new_logs:
                        yield f"data: {json.dumps(log)}\n\n"
                        
                    # Prevent set from growing too large
                    if len(seen_ids) > 1000:
                        seen_ids.clear()
                        seen_ids.update(log.get('log_id') for log in logs)
                else:
                    yield f"data: {json.dumps({'error': 'Qdrant not available'})}\n\n"
                
                await asyncio.sleep(0.5)  # Check more frequently
                
            except Exception as e:
                print(f"Error in Qdrant stream: {e}")
                await asyncio.sleep(1)  # Wait longer on error
                
            except Exception as e:
                print(f"Error in Qdrant stream: {e}")
                await asyncio.sleep(2)
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")

async def get_postgresql_data():
    """Get PostgreSQL logs"""
    try:
        logs = fetch_logs_from_db(limit=50)
        return {"logs": logs, "source": "postgresql"}
    except Exception as e:
        return {"error": str(e)}

async def get_qdrant_data():
    """Get Qdrant logs"""
    try:
        logs = fetch_logs_from_qdrant(limit=50)
        return {"logs": logs, "source": "qdrant", "enabled": QDRANT_AVAILABLE}
    except Exception as e:
        return {"error": str(e)}