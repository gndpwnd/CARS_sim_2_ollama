"""
Storage integration helpers - PostgreSQL and Qdrant logging.
"""
import datetime
from typing import Dict, Any, Optional
from simulation.sim_movement import convert_numpy_coords

# Import storage modules with fallbacks
try:
    from postgresql_store import add_log as _pg_add_log
    PG_ENABLED = True
except ImportError:
    PG_ENABLED = False
    print("[STORAGE] PostgreSQL logging disabled")

try:
    from qdrant_store import add_nmea_message, add_telemetry
    QDRANT_ENABLED = True
except ImportError:
    QDRANT_ENABLED = False
    print("[STORAGE] Qdrant logging disabled")
    def add_nmea_message(*args, **kwargs):
        pass
    def add_telemetry(*args, **kwargs):
        pass

def add_log(log_text: str, metadata: Dict[str, Any], log_id: Optional[str] = None):
    """
    Add log to PostgreSQL (wrapper with fallback).
    
    Args:
        log_text: Log message text
        metadata: Metadata dictionary
        log_id: Optional log ID
    """
    if PG_ENABLED:
        _pg_add_log(log_text, metadata, log_id)

def log_batch_of_data(agent_histories: Dict, add_log_func, prefix: str = "batch"):
    """
    Log a batch of data from all agents to PostgreSQL.
    This logs agent telemetry as 'telemetry' or 'error' messages.
    
    NOTE: Position/GPS data should primarily go to Qdrant.
    This function logs summaries/notifications to PostgreSQL.
    
    Args:
        agent_histories: Mapping of agent_id to list of data points
        add_log_func: Function to add logs to PostgreSQL
        prefix: Prefix used to construct a unique log ID
    """
    print(f"[LOGGING] Logging batch of data with prefix: {prefix}")
    
    for agent_id, history in agent_histories.items():
        prev_entry = None
        
        for i, data in enumerate(history):
            if data == prev_entry:
                continue
            prev_entry = data

            position = convert_numpy_coords(data['position'])
            comm_quality = convert_numpy_coords(data['communication_quality'])
            jammed = data['jammed']
            timestamp = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')

            # Determine message type based on status
            message_type = "error" if jammed else "telemetry"

            log_text = (
                f"Agent {agent_id} is at position {position}. "
                f"Communication quality: {comm_quality}. "
                f"Status: {'Jammed' if jammed else 'Clear'}."
            )

            metadata = {
                'timestamp': timestamp,
                'source': agent_id,
                'message_type': message_type,
                'comm_quality': comm_quality,
                'position': position,
                'jammed': jammed,
                'role': 'agent'
            }

            add_log_func(log_text=log_text, metadata=metadata)

def log_gps_to_qdrant(agent_id: str, gps_data, position: tuple, is_jammed: bool):
    """
    Log GPS data to Qdrant.
    
    Args:
        agent_id: Agent identifier
        gps_data: GPS data object with NMEA sentences
        position: Agent position (x, y)
        is_jammed: Whether agent is jammed
    """
    if not QDRANT_ENABLED or not gps_data:
        return
    
    # Log NMEA messages
    for nmea_sentence in gps_data.nmea_sentences:
        add_nmea_message(
            agent_id=agent_id,
            nmea_sentence=nmea_sentence,
            metadata={
                'position': position,
                'jammed': is_jammed,
                'fix_quality': gps_data.fix_quality,
                'satellites': gps_data.satellite_count,
                'signal_quality': gps_data.signal_quality
            }
        )

def log_telemetry_to_qdrant(agent_id: str, position: tuple, 
                            is_jammed: bool, comm_quality: float,
                            gps_data=None, iteration: int = 0):
    """
    Log telemetry to Qdrant.
    
    Args:
        agent_id: Agent identifier
        position: Agent position (x, y)
        is_jammed: Whether agent is jammed
        comm_quality: Communication quality
        gps_data: Optional GPS data
        iteration: Simulation iteration number
    """
    if not QDRANT_ENABLED:
        return
    
    metadata = {
        'jammed': is_jammed,
        'communication_quality': comm_quality,
        'iteration': iteration,
        'timestamp': datetime.datetime.now().timestamp()
    }
    
    if gps_data:
        metadata.update({
            'gps_satellites': gps_data.satellite_count,
            'gps_signal_quality': gps_data.signal_quality,
            'gps_fix_quality': gps_data.fix_quality
        })
    
    add_telemetry(
        agent_id=agent_id,
        position=position,
        metadata=metadata
    )

def log_event(event_type: str, agent_id: str, position: tuple, 
              message: str, additional_metadata: Optional[Dict] = None):
    """
    Log a specific event to PostgreSQL.
    
    Args:
        event_type: Type of event ('error', 'notification', 'telemetry', 'command')
        agent_id: Agent identifier
        position: Agent position
        message: Event message
        additional_metadata: Additional metadata to include
    """
    if not PG_ENABLED:
        return
    
    metadata = {
        'timestamp': datetime.datetime.now().isoformat(),
        'source': agent_id,
        'message_type': event_type,
        'position': position,
        'role': 'agent'
    }
    
    if additional_metadata:
        metadata.update(additional_metadata)
    
    add_log(message, metadata)