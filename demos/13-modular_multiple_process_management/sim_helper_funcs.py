"""
Compatibility layer for sim_helper_funcs.py
This file maintains backward compatibility by importing from the new modular structure.

DEPRECATED: This file is maintained for backward compatibility only.
New code should import directly from the simulation/ and integrations/ modules.
"""
import warnings

warnings.warn(
    "sim_helper_funcs.py is deprecated. Import from 'simulation' and 'integrations' modules instead.",
    DeprecationWarning,
    stacklevel=2
)

# Import from new modules
from simulation.sim_movement import (
    convert_numpy_coords,
    round_coord,
    linear_path,
    limit_movement
)

from simulation.sim_jamming import (
    is_jammed
)

from simulation.sim_recovery import (
    algorithm_make_move,
    get_last_safe_position
)

from integrations.storage_integration import (
    log_batch_of_data
)

# Export all for backward compatibility
__all__ = [
    'convert_numpy_coords',
    'round_coord',
    'linear_path',
    'limit_movement',
    'is_jammed',
    'algorithm_make_move',
    'get_last_safe_position',
    'log_batch_of_data'
]