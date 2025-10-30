"""
Jamming detection and zone management.
"""
import math
from typing import List, Tuple, Optional
from core.types import Position, JammingZone

def is_jammed(pos: Position, jamming_center: Position, jamming_radius: float) -> bool:
    """
    Check if a position is inside the jamming zone.
    
    Args:
        pos: Position to check (x, y)
        jamming_center: Center of jamming zone (x, y)
        jamming_radius: Radius of jamming zone
        
    Returns:
        True if position is jammed, False otherwise
    """
    if isinstance(pos, tuple) or isinstance(pos, list):
        pos_x, pos_y = pos[0], pos[1]
    else:  # Assume numpy array
        pos_x, pos_y = pos[0], pos[1]
    
    distance = math.sqrt((pos_x - jamming_center[0])**2 + (pos_y - jamming_center[1])**2)
    return distance <= jamming_radius

def check_multiple_zones(pos: Position, zones: List[JammingZone]) -> bool:
    """
    Check if a position is in any jamming zone.
    
    Args:
        pos: Position to check
        zones: List of jamming zones (center_x, center_y, radius)
        
    Returns:
        True if position is in any zone
    """
    for cx, cy, radius in zones:
        if is_jammed(pos, (cx, cy), radius):
            return True
    return False

def get_nearest_jamming_zone(pos: Position, 
                             zones: List[JammingZone]) -> Optional[JammingZone]:
    """
    Find the nearest jamming zone to a position.
    
    Args:
        pos: Position to check
        zones: List of jamming zones
        
    Returns:
        Nearest jamming zone or None if no zones
    """
    if not zones:
        return None
    
    min_dist = float('inf')
    nearest_zone = None
    
    for zone in zones:
        cx, cy, radius = zone
        dist = math.sqrt((pos[0] - cx)**2 + (pos[1] - cy)**2)
        if dist < min_dist:
            min_dist = dist
            nearest_zone = zone
    
    return nearest_zone

def get_nearest_jamming_center(pos: Position, 
                               zones: List[JammingZone],
                               default_center: Position = (0, 0)) -> Position:
    """
    Get the center of the nearest jamming zone.
    
    Args:
        pos: Position to check from
        zones: List of jamming zones
        default_center: Default center if no zones
        
    Returns:
        Center position of nearest zone
    """
    zone = get_nearest_jamming_zone(pos, zones)
    if zone:
        return (zone[0], zone[1])
    return default_center

def get_nearest_jamming_radius(pos: Position, 
                               zones: List[JammingZone],
                               default_radius: float = 5.0) -> float:
    """
    Get the radius of the nearest jamming zone.
    
    Args:
        pos: Position to check from
        zones: List of jamming zones
        default_radius: Default radius if no zones
        
    Returns:
        Radius of nearest zone
    """
    zone = get_nearest_jamming_zone(pos, zones)
    if zone:
        return zone[2]
    return default_radius

def calculate_jamming_level(pos: Position, zones: List[JammingZone]) -> float:
    """
    Calculate jamming level at a position (0-100).
    
    Args:
        pos: Position to check
        zones: List of jamming zones
        
    Returns:
        Jamming level as percentage (0-100)
    """
    jamming_level = 0.0
    
    for cx, cy, radius in zones:
        dist = math.sqrt((pos[0] - cx)**2 + (pos[1] - cy)**2)
        if dist < radius:
            # Stronger jamming closer to center
            level = 100 * (1 - dist / radius)
            jamming_level = max(jamming_level, level)
    
    return jamming_level