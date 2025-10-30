"""
Core module - shared configuration and types
"""
from .config import *
from .types import *

__all__ = [
    # Config
    'UPDATE_FREQ',
    'MAX_MOVEMENT_PER_STEP',
    'NUM_HISTORY_SEGMENTS',
    'X_RANGE',
    'Y_RANGE',
    'MISSION_END',
    'DEFAULT_JAMMING_CENTER',
    'DEFAULT_JAMMING_RADIUS',
    'NUM_AGENTS',
    'get_agent_ids',
    'HIGH_COMM_QUAL',
    'LOW_COMM_QUAL',
    'DB_CONFIG',
    'QDRANT_HOST',
    'QDRANT_PORT',
    'NMEA_COLLECTION',
    'TELEMETRY_COLLECTION',
    'SIMULATION_API_URL',
    'MCP_API_URL',
    'GPS_CONSTELLATION_HOST',
    'GPS_CONSTELLATION_PORT',
    'GPS_BASE_LATITUDE',
    'GPS_BASE_LONGITUDE',
    # Types
    'Position',
    'PositionWithQuality',
    'JammingZone',
    'Bounds',
    'AgentState',
    'SimulationState',
]