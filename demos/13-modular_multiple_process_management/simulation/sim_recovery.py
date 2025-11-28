"""
Recovery algorithms for jammed agents.
Updated to use random point strategy with return-to-safe logic.
"""
import random
import numpy as np
from typing import Tuple, Dict, List, Optional
from core.types import Position, Bounds
from core.config import MAX_MOVEMENT_PER_STEP, HIGH_COMM_QUAL
from .sim_jamming import is_jammed, check_multiple_zones
from .sim_movement import round_coord


def algorithm_make_move(agent_id: str, 
                       current_pos: Position, 
                       jamming_zones: List,
                       max_movement_per_step: float, 
                       x_range: Bounds, 
                       y_range: Bounds) -> Position:
    """
    Recovery algorithm for jammed agents using random point strategy:
    1. Agent returns to last safe position (handled by caller)
    2. Pick a random point within boundaries
    3. Move toward that random point
    4. If reached and not jammed, resume normal movement to mission end
    
    Args:
        agent_id: Agent identifier
        current_pos: Current position (should be at safe position)
        jamming_zones: List of jamming zones
        max_movement_per_step: Maximum movement distance
        x_range: X boundaries (min, max)
        y_range: Y boundaries (min, max)
        
    Returns:
        Random target position to move toward
    """
    print(f"[Algorithm] Generating random recovery point for {agent_id} from {current_pos}")
    
    # Generate multiple random points and pick one that's not jammed
    max_attempts = 20
    best_point = None
    
    for attempt in range(max_attempts):
        # Generate random point within boundaries
        random_x = random.uniform(x_range[0], x_range[1])
        random_y = random.uniform(y_range[0], y_range[1])
        random_point = (random_x, random_y)
        
        # Check if this point is not jammed
        if not check_multiple_zones(random_point, jamming_zones):
            # Found a clear point - calculate distance from current position
            distance = np.sqrt((random_x - current_pos[0])**2 + 
                             (random_y - current_pos[1])**2)
            
            # Prefer points that are further away (more exploration)
            # but not too far (within reasonable distance)
            if 2.0 < distance < 10.0:
                best_point = random_point
                print(f"[Algorithm] Found clear random point: ({random_x:.2f}, {random_y:.2f}) "
                      f"at distance {distance:.2f}")
                break
            elif best_point is None:
                # Keep this as backup even if distance isn't ideal
                best_point = random_point
    
    if best_point is None:
        # Fallback: if all random points are jammed, move away from nearest jamming center
        print(f"[Algorithm] All random points jammed, moving away from jamming zones")
        
        # Find nearest jamming zone
        nearest_zone = None
        min_dist = float('inf')
        for zone in jamming_zones:
            cx, cy, radius = zone
            dist = np.sqrt((current_pos[0] - cx)**2 + (current_pos[1] - cy)**2)
            if dist < min_dist:
                min_dist = dist
                nearest_zone = zone
        
        if nearest_zone:
            cx, cy, radius = nearest_zone
            # Move directly away from jamming center
            direction = np.array(current_pos) - np.array([cx, cy])
            direction_norm = np.linalg.norm(direction)
            
            if direction_norm > 0:
                unit_direction = direction / direction_norm
                # Move 2-3 steps away from jamming zone
                escape_distance = radius * 1.5
                suggestion = np.array(current_pos) + unit_direction * escape_distance
            else:
                # At center - pick random direction
                angle = random.uniform(0, 2 * np.pi)
                unit_direction = np.array([np.cos(angle), np.sin(angle)])
                suggestion = np.array(current_pos) + unit_direction * max_movement_per_step * 3
            
            # Clamp to boundaries
            suggestion[0] = max(min(suggestion[0], x_range[1]), x_range[0])
            suggestion[1] = max(min(suggestion[1], y_range[1]), y_range[0])
            
            best_point = (suggestion[0], suggestion[1])
        else:
            # No jamming zones? Just pick a random point
            best_point = (
                random.uniform(x_range[0], x_range[1]),
                random.uniform(y_range[0], y_range[1])
            )
    
    print(f"[Algorithm] Recovery target for {agent_id}: ({best_point[0]:.2f}, {best_point[1]:.2f})")
    return (round_coord(best_point[0]), round_coord(best_point[1]))


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
        print(f"[Recovery] {agent_id}: Returning to stored safe position {safe_pos}")
        return safe_pos

    # If no stored safe position, find one from history
    for pos in reversed(swarm_pos_dict[agent_id]):
        if pos[2] >= high_comm_qual:  # Communication quality must be high
            safe_pos = pos[:2]
            print(f"[Recovery] {agent_id}: Found historical safe position {safe_pos}")
            return safe_pos
            
    # If no valid position found, return the starting position or current position
    current_pos = swarm_pos_dict[agent_id][-1][:2]
    print(f"[Recovery] {agent_id}: No valid safe position found, using current position {current_pos}")
    return current_pos


def is_at_target(current_pos: Position, target_pos: Position, tolerance: float = 0.5) -> bool:
    """
    Check if agent has reached target position within tolerance
    
    Args:
        current_pos: Current position
        target_pos: Target position
        tolerance: Distance tolerance for "reached"
        
    Returns:
        True if at target, False otherwise
    """
    distance = np.sqrt((current_pos[0] - target_pos[0])**2 + 
                      (current_pos[1] - target_pos[1])**2)
    return distance <= tolerance