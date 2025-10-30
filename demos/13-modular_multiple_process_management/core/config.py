"""
Shared configuration constants for the GPS simulation system.
Used by both GUI and MCP components.
"""

# =============================================================================
# SIMULATION PARAMETERS
# =============================================================================

# Update frequency (seconds)
UPDATE_FREQ = 2.5

# Maximum movement per simulation step
MAX_MOVEMENT_PER_STEP = 1.41

# Number of history segments to keep
NUM_HISTORY_SEGMENTS = 5

# =============================================================================
# ENVIRONMENT SETUP
# =============================================================================

# Simulation boundaries (x_min, x_max), (y_min, y_max)
X_RANGE = (-10, 10)
Y_RANGE = (-10, 10)

# Mission endpoint
MISSION_END = (10, 10)

# Default jamming configuration
DEFAULT_JAMMING_CENTER = (0, 0)
DEFAULT_JAMMING_RADIUS = 5

# =============================================================================
# AGENT CONFIGURATION
# =============================================================================

# Number of agents in simulation
NUM_AGENTS = 5

# Agent naming pattern
def get_agent_ids(num_agents=NUM_AGENTS):
    """Generate agent IDs"""
    return [f"agent{i+1}" for i in range(num_agents)]

# =============================================================================
# COMMUNICATION QUALITY
# =============================================================================

# Communication quality levels
HIGH_COMM_QUAL = 1.0
LOW_COMM_QUAL = 0.2

# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================

DB_CONFIG = {
    "dbname": "rag_db",
    "user": "postgres",
    "password": "password",
    "host": "localhost",
    "port": "5432"
}

# =============================================================================
# QDRANT CONFIGURATION
# =============================================================================

QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
NMEA_COLLECTION = "nmea_messages"
TELEMETRY_COLLECTION = "agent_telemetry"

# =============================================================================
# API ENDPOINTS
# =============================================================================

SIMULATION_API_URL = "http://localhost:5001"
MCP_API_URL = "http://localhost:5000"
GPS_CONSTELLATION_HOST = "localhost"
GPS_CONSTELLATION_PORT = 12345

# =============================================================================
# GPS CONFIGURATION
# =============================================================================

GPS_BASE_LATITUDE = 40.7128
GPS_BASE_LONGITUDE = -74.0060

# =============================================================================
# LLM CONFIGURATION
# =============================================================================

# Imported from llm_config.py - these are defaults if that module is unavailable
DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_LLM_MODEL = "llama3.2:latest"