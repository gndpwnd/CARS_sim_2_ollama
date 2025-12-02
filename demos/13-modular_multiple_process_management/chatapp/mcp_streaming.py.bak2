"""
Streaming endpoints for real-time log updates.
FIXED: Properly streams Qdrant telemetry with point ID-based deduplication
"""
import json
import asyncio
from datetime import datetime, timedelta
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
    from qdrant_store import TELEMETRY_COLLECTION
    from core.config import QDRANT_HOST, QDRANT_PORT
    QDRANT_AVAILABLE = True
    qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
except:
    QDRANT_AVAILABLE = False
    qdrant_client = None
    print("[STREAMING] Qdrant not available")


def normalize_timestamp_to_iso(timestamp) -> str:
    """
    Convert any timestamp format to ISO string for frontend.
    Handles: Unix timestamps (float/int), ISO strings, datetime objects
    
    Args:
        timestamp: Timestamp in any format
        
    Returns:
        ISO format string (e.g., "2025-01-15T10:30:45.123456")
    """
    if timestamp is None:
        return datetime.now().isoformat()
    
    # Already an ISO string
    if isinstance(timestamp, str):
        # If it looks like ISO format, return as-is
        if 'T' in timestamp or '-' in timestamp:
            return timestamp
        # Otherwise try to parse as Unix timestamp string
        try:
            return datetime.fromtimestamp(float(timestamp)).isoformat()
        except:
            return datetime.now().isoformat()
    
    # Unix timestamp (float or int)
    if isinstance(timestamp, (int, float)):
        try:
            return datetime.fromtimestamp(timestamp).isoformat()
        except:
            return datetime.now().isoformat()
    
    # Datetime object
    if isinstance(timestamp, datetime):
        return timestamp.isoformat()
    
    # Unknown format - use current time
    return datetime.now().isoformat()


def fetch_logs_from_db(limit=None):
    """Fetch logs from PostgreSQL - INCREASED DEFAULT LIMIT"""
    if not PG_AVAILABLE:
        return []
    
    # FIXED: Default to 200 logs instead of 50
    if limit is None:
        limit = 200
    
    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                query = f"""
                    SELECT id, text, metadata, created_at 
                    FROM logs
                    ORDER BY created_at DESC
                    LIMIT {limit}
                """
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
        print(f"[STREAMING] Error fetching logs from DB: {e}")
        return []


def fetch_logs_from_qdrant(limit=200, since_timestamp=None):
    """
    Fetch logs from Qdrant vector database - FIXED to handle mixed old/new data
    
    Args:
        limit: Maximum number of logs to fetch
        since_timestamp: Unused (kept for compatibility)
    
    Returns:
        List of log dictionaries with ISO format timestamps
    """
    if not qdrant_client:
        return []
    
    try:
        # Get all recent points (no offset - just get latest batch)
        results = qdrant_client.scroll(
            collection_name=TELEMETRY_COLLECTION,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )[0]
        
        logs = []
        
        for point in results:
            payload = point.payload
            
            # Get timestamp (may be Unix float or ISO string)
            raw_timestamp = payload.get('timestamp')
            
            # Convert to Unix timestamp for comparison
            try:
                if isinstance(raw_timestamp, (int, float)):
                    unix_timestamp = float(raw_timestamp)
                    # Silently use current time if timestamp seems off (no warning spam)
                    current_time = datetime.now().timestamp()
                    if unix_timestamp > current_time + 86400:  # More than 1 day in future
                        unix_timestamp = current_time
                elif isinstance(raw_timestamp, str):
                    # Try to parse as Unix timestamp string first
                    try:
                        unix_timestamp = float(raw_timestamp)
                        current_time = datetime.now().timestamp()
                        if unix_timestamp > current_time + 86400:
                            unix_timestamp = current_time
                    except:
                        # Parse as ISO string
                        try:
                            unix_timestamp = datetime.fromisoformat(raw_timestamp.replace('Z', '+00:00')).timestamp()
                        except:
                            unix_timestamp = datetime.now().timestamp()
                else:
                    unix_timestamp = datetime.now().timestamp()
            except:
                unix_timestamp = datetime.now().timestamp()
            
            # CRITICAL: Convert to ISO format for frontend display
            iso_timestamp = normalize_timestamp_to_iso(raw_timestamp)
            
            metadata = {
                'agent_id': payload.get('agent_id'),
                'position': (payload.get('position_x', 0), payload.get('position_y', 0)),
                'jammed': payload.get('jammed', False),
                'communication_quality': payload.get('communication_quality', 0),
                'timestamp': iso_timestamp,  # <-- ISO format for frontend!
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
                "created_at": iso_timestamp,  # <-- ISO format!
                "source": "qdrant",
                "vector_score": None,
                "_unix_timestamp": unix_timestamp,  # Keep for filtering
                "_point_id": str(point.id)  # Keep point ID for deduplication
            })
        
        # Sort logs by iteration number (more reliable than timestamp)
        # Handle None iterations by treating them as 0
        logs.sort(key=lambda x: x['metadata'].get('iteration') or 0, reverse=True)
        
        return logs
    except Exception as e:
        print(f"[STREAMING] Error fetching from Qdrant: {e}")
        import traceback
        traceback.print_exc()
        return []


async def stream_postgresql():
    """Stream PostgreSQL logs in real-time"""
    async def event_generator():
        last_check_time = datetime.now()
        
        while True:
            try:
                # Fetch recent logs (last 20 to avoid overwhelming)
                logs = fetch_logs_from_db(limit=20)
                
                for log in logs:
                    log_time = datetime.fromisoformat(log.get("created_at", datetime.now().isoformat()))
                    if log_time > last_check_time:
                        yield f"data: {json.dumps(log)}\n\n"
                
                last_check_time = datetime.now()
                await asyncio.sleep(1)  # Check every second
                
            except Exception as e:
                print(f"[STREAMING] Error in PostgreSQL stream: {e}")
                await asyncio.sleep(1)
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


async def stream_qdrant():
    """
    Stream Qdrant logs in real-time - FIXED to handle mixed old/new data
    """
    async def event_generator():
        # Track by point IDs only (don't rely on iterations due to mixed data)
        seen_point_ids = set()
        check_count = 0
        initial_load = True
        
        print("[STREAMING] Qdrant stream generator started")
        
        while True:
            try:
                if qdrant_client:
                    # Fetch logs (no timestamp filtering)
                    try:
                        logs = fetch_logs_from_qdrant(
                            limit=100,
                            since_timestamp=None  # Don't filter by timestamp
                        )
                    except Exception as fetch_error:
                        print(f"[STREAMING] Error fetching from Qdrant: {fetch_error}")
                        await asyncio.sleep(2)
                        continue
                    
                    # DEBUG: Log what we got
                    check_count += 1
                    if check_count == 1 or check_count % 20 == 0:
                        # Show first few iterations to debug
                        sample_iterations = [log.get('metadata', {}).get('iteration') for log in logs[:5]]
                        print(f"[STREAMING] Qdrant check #{check_count}: "
                              f"fetched {len(logs)} logs, "
                              f"seen_ids={len(seen_point_ids)}, "
                              f"sample iterations={sample_iterations}")
                    
                    # SIMPLIFIED: Just filter by point ID (ignore iteration confusion)
                    new_logs = []
                    for log in logs:
                        point_id = log.get('_point_id')
                        
                        # Skip if we've already sent this point
                        if point_id and point_id in seen_point_ids:
                            continue
                        
                        new_logs.append(log)
                        if point_id:
                            seen_point_ids.add(point_id)
                    
                    # Send new logs
                    sent_count = 0
                    for log in new_logs:
                        try:
                            # Remove internal fields before sending
                            log.pop('_unix_timestamp', None)
                            log.pop('_point_id', None)
                            
                            # JSON serialize with error handling
                            try:
                                log_json = json.dumps(log)
                            except (TypeError, ValueError) as json_error:
                                print(f"[STREAMING] JSON serialization error: {json_error}")
                                continue
                            
                            yield f"data: {log_json}\n\n"
                            sent_count += 1
                            
                        except Exception as log_error:
                            print(f"[STREAMING] Error processing individual log: {log_error}")
                            continue
                    
                    # Log when we send data
                    if sent_count > 0:
                        print(f"[STREAMING] Qdrant: SENT {sent_count} NEW logs to frontend")
                    
                    # After initial load, mark flag and trim seen_ids
                    if initial_load and sent_count > 0:
                        initial_load = False
                        print(f"[STREAMING] Qdrant: Initial load complete ({sent_count} logs)")
                    
                    # Keep seen_ids from growing too large
                    if len(seen_point_ids) > 1000:
                        # Keep only the most recent 500
                        seen_point_ids = set(list(seen_point_ids)[-500:])
                        print(f"[STREAMING] Qdrant: Trimmed seen_ids to {len(seen_point_ids)}")
                else:
                    yield f"data: {json.dumps({'error': 'Qdrant not available'})}\n\n"
                
                # Check for new data every 0.5 seconds (faster updates)
                await asyncio.sleep(0.5)
                
            except asyncio.CancelledError:
                print("[STREAMING] Qdrant stream cancelled by client")
                break
            except Exception as e:
                print(f"[STREAMING] CRITICAL ERROR in Qdrant stream: {e}")
                import traceback
                traceback.print_exc()
                # Try to send error to client
                try:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
                except:
                    pass
                await asyncio.sleep(2)  # Wait longer on error
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


async def get_postgresql_data():
    """Get PostgreSQL logs - RETURNS MORE LOGS"""
    try:
        logs = fetch_logs_from_db(limit=200)  # INCREASED from 50 to 200
        return {"logs": logs, "source": "postgresql"}
    except Exception as e:
        return {"error": str(e)}


async def get_qdrant_data():
    """Get Qdrant logs - RETURNS MORE LOGS with converted timestamps"""
    try:
        logs = fetch_logs_from_qdrant(limit=200)  # INCREASED from 50 to 200
        
        # Remove internal Unix timestamps before sending to frontend
        for log in logs:
            log.pop('_unix_timestamp', None)
            log.pop('_point_id', None)
        
        return {"logs": logs, "source": "qdrant", "enabled": QDRANT_AVAILABLE}
    except Exception as e:
        return {"error": str(e)}