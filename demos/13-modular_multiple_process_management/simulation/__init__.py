"""
Simulation module - core simulation logic
"""
from .sim_movement import (
    round_coord,
    convert_numpy_coords,
    linear_path,
    limit_movement
)

from .sim_jamming import (
    is_jammed,
    check_multiple_zones,
    get_nearest_jamming_zone,
    get_nearest_jamming_center,
    get_nearest_jamming_radius,
    calculate_jamming_level
)

from .sim_recovery import (
    algorithm_make_move,
    get_last_safe_position
)

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
    # Agents
    'initialize_agents',
    'update_agent_position',
]