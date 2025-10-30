"""
Movement logic for the simulation.
Handles path generation and movement limits.
"""
import math
import numpy as np
from typing import List, Tuple
from core.config import MAX_MOVEMENT_PER_STEP
from core.types import Position

def round_coord(value: float) -> float:
    """Round coordinates to 3 decimal places"""
    return round(value, 3)

def convert_numpy_coords(obj):
    """
    Recursively convert numpy data types to native Python types for JSON serialization.
    """
    if isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        return float(obj)
    elif isinstance(obj, (np.complexfloating,)):
        return complex(obj)
    elif isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (list, tuple)):
        converted = [convert_numpy_coords(item) for item in obj]
        return tuple(converted) if isinstance(obj, tuple) else converted
    elif isinstance(obj, dict):
        return {key: convert_numpy_coords(value) for key, value in obj.items()}
    return obj

def linear_path(start: Position, end: Position, 
                max_movement_per_step: float = MAX_MOVEMENT_PER_STEP) -> List[Position]:
    """
    Create a linear path between start and end points with max step distance constraint.
    
    Args:
        start: Starting position (x, y)
        end: Ending position (x, y)
        max_movement_per_step: Maximum distance per step
        
    Returns:
        List of positions forming the path
    """
    path = []
    
    # Convert to numpy arrays if they aren't already
    if isinstance(start, tuple) or isinstance(start, list):
        start_np = np.array([start[0], start[1]])
    else:
        start_np = start
        
    if isinstance(end, tuple) or isinstance(end, list):
        end_np = np.array([end[0], end[1]])
    else:
        end_np = end
    
    direction_x = end_np[0] - start_np[0]
    direction_y = end_np[1] - start_np[1]
    distance = math.sqrt(direction_x**2 + direction_y**2)
    
    if distance > 0:
        unit_x = direction_x / distance
        unit_y = direction_y / distance
    else:
        return [(round_coord(end_np[0]), round_coord(end_np[1]))]
    
    current_x = start_np[0]
    current_y = start_np[1]
    
    while math.sqrt((current_x - end_np[0])**2 + (current_y - end_np[1])**2) > max_movement_per_step:
        current_x += max_movement_per_step * unit_x
        current_y += max_movement_per_step * unit_y
        path.append((round_coord(current_x), round_coord(current_y)))
    
    path.append((round_coord(end_np[0]), round_coord(end_np[1])))
    return path

def limit_movement(current_pos: Position, target_pos: Position, 
                   max_movement_per_step: float = MAX_MOVEMENT_PER_STEP) -> Position:
    """
    Limit movement to max_movement_per_step.
    
    Args:
        current_pos: Current position
        target_pos: Desired target position
        max_movement_per_step: Maximum movement allowed
        
    Returns:
        Position limited by max movement
    """
    if isinstance(current_pos, tuple) or isinstance(current_pos, list):
        current_np = np.array([current_pos[0], current_pos[1]])
    else:
        current_np = current_pos
        
    if isinstance(target_pos, tuple) or isinstance(target_pos, list):
        target_np = np.array([target_pos[0], target_pos[1]])
    else:
        target_np = target_pos
    
    distance = np.linalg.norm(target_np - current_np)
    
    if distance <= max_movement_per_step:
        return target_np  # We can reach the target directly
    
    # Otherwise, move in the direction of the target, but only by max_movement_per_step
    direction = (target_np - current_np) / distance
    limited_pos = current_np + direction * max_movement_per_step
    
    return (round_coord(limited_pos[0]), round_coord(limited_pos[1]))