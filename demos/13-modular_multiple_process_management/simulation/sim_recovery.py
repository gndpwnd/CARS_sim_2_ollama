"""
Recovery algorithms for jammed agents.
"""
import random
import numpy as np
from typing import Tuple, Dict, List, Optional
from core.types import Position, Bounds
from core.config import MAX_MOVEMENT_PER_STEP, HIGH_COMM_QUAL
from .sim_jamming import is_jammed
from .sim_movement import round_coord

def algorithm_make_move(agent_id: str, 
                       current_pos: Position, 
                       jamming_center: Position, 
                       jamming_radius: float,
                       max_movement_per_step: float, 
                       x_range: Bounds, 
                       y_range: Bounds) -> Position:
    """
    Recovery algorithm for jammed agents:
    1. Try random moves within max_movement_per_step
    2. Prefer moves that exit jamming zone
    3. Fall back to moving away from jamming center
    
    Args:
        agent_id: Agent identifier
        current_pos: Current position
        jamming_center: Center of jamming zone
        jamming_radius: Radius of jamming zone
        max_movement_per_step: Maximum movement distance
        x_range: X boundaries (min, max)
        y_range: Y boundaries (min, max)
        
    Returns:
        Suggested recovery position
    """
    print(f"[Algorithm] Recovery for {agent_id} at {current_pos}")
    
    # Try random directions (prefer ones exiting jamming)
    for attempt in range(10):
        angle = random.uniform(0, 2 * np.pi)
        direction = np.array([np.cos(angle), np.sin(angle)])
        suggestion = np.array(current_pos) + direction * max_movement_per_step
        
        # Clamp to boundaries
        suggestion[0] = max(min(suggestion[0], x_range[1]), x_range[0])
        suggestion[1] = max(min(suggestion[1], y_range[1]), y_range[0])
        
        # Check if outside jamming
        if not is_jammed(suggestion, jamming_center, jamming_radius):
            print(f"[Algorithm] Found clear position: {suggestion}")
            return (round_coord(suggestion[0]), round_coord(suggestion[1]))
    
    # Fallback: move directly away from jamming center
    print(f"[Algorithm] Moving away from jamming center")
    direction = np.array(current_pos) - np.array(jamming_center)
    direction_norm = np.linalg.norm(direction)
    
    if direction_norm > 0:
        unit_direction = direction / direction_norm
    else:
        # At center - pick random direction
        angle = random.uniform(0, 2 * np.pi)
        unit_direction = np.array([np.cos(angle), np.sin(angle)])
    
    suggestion = np.array(current_pos) + unit_direction * max_movement_per_step
    suggestion[0] = max(min(suggestion[0], x_range[1]), x_range[0])
    suggestion[1] = max(min(suggestion[1], y_range[1]), y_range[0])
    
    return (round_coord(suggestion[0]), round_coord(suggestion[1]))

def get_last_safe_position(agent_id: str, 
                          last_safe_position: Dict[str, Position],
                          swarm_pos_dict: Dict[str, List], 
                          high_comm_qual: float = HIGH_COMM_QUAL) -> Position:
    """
    Retrieves the last known safe position for an agent, 
    defined as the most recent position with high communication quality.
    
    Args:
        agent_id: Agent identifier
        last_safe_position: Dictionary of last safe positions
        swarm_pos_dict: Dictionary of agent position histories
        high_comm_qual: Threshold for high communication quality
        
    Returns:
        Last safe position (x, y)
    """
    if agent_id in last_safe_position:
        safe_pos = last_safe_position[agent_id]
        print(f"Agent {agent_id}: Returning to stored safe position {safe_pos}")
        return safe_pos

    # If no stored safe position, find one from history
    for pos in reversed(swarm_pos_dict[agent_id]):
        if pos[2] >= high_comm_qual:  # Communication quality must be high
            print(f"Agent {agent_id}: Found historical safe position {pos[:2]}")
            return pos[:2]  # Return the coordinates
            
    # If no valid position found, return the current position
    current_pos = swarm_pos_dict[agent_id][-1][:2]
    print(f"Agent {agent_id}: No valid safe position found, using current position {current_pos}")
    return current_pos