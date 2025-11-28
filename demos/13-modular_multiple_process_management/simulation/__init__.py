"""
Simulation module - exports all simulation components
"""

# Movement functions
from .sim_movement import (
    round_coord,
    convert_numpy_coords,
    linear_path,
    limit_movement
)

# Jamming functions
from .sim_jamming import (
    is_jammed,
    check_multiple_zones,
    get_nearest_jamming_zone,
    get_nearest_jamming_center,
    get_nearest_jamming_radius,
    calculate_jamming_level
)

# Recovery functions
from .sim_recovery import (
    algorithm_make_move,
    get_last_safe_position,
    is_at_target  # NEW: Helper to check if agent reached target
)

# Agent management
from .sim_agents import (
    initialize_agents,
    update_agent_position
)

__all__ = [
    # Movement
    'round_coord',
    'convert_numpy_coords',
    'linear_path',
    'limit_movement',
    
    # Jamming
    'is_jammed',
    'check_multiple_zones',
    'get_nearest_jamming_zone',
    'get_nearest_jamming_center',
    'get_nearest_jamming_radius',
    'calculate_jamming_level',
    
    # Recovery
    'algorithm_make_move',
    'get_last_safe_position',
    'is_at_target',
    
    # Agents
    'initialize_agents',
    'update_agent_position'
]