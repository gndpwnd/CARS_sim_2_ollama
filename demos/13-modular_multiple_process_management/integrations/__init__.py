"""
Integrations module - external system integrations
"""
from .storage_integration import (
    add_log,
    log_batch_of_data,
    log_gps_to_qdrant,
    log_telemetry_to_qdrant,
    log_event,
    PG_ENABLED,
    QDRANT_ENABLED
)

from .llm_integration import (
    request_llm_recovery_position,
    parse_coordinates_from_text,
    ask_llm_general
)

from .gps_integration import (
    GPSManagerWrapper,
    create_gps_manager,
    GPS_AVAILABLE
)

__all__ = [
    # Storage
    'add_log',
    'log_batch_of_data',
    'log_gps_to_qdrant',
    'log_telemetry_to_qdrant',
    'log_event',
    'PG_ENABLED',
    'QDRANT_ENABLED',
    # LLM
    'request_llm_recovery_position',
    'parse_coordinates_from_text',
    'ask_llm_general',
    # GPS
    'GPSManagerWrapper',
    'create_gps_manager',
    'GPS_AVAILABLE',
]