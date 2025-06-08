"""
Rover utilities - Supporting functions and classes for rover operations.
"""

import time
import numpy as np
from typing import Tuple, List, Optional, Dict
from dataclasses import dataclass
from enum import Enum

# Constants
COMM_RANGE = 50.0  # meters - communication range
SURVEY_SPEED = 2.0  # m/s - rover movement speed
POSITION_TOLERANCE = 1.0  # meters - acceptable position accuracy
WAYPOINT_TOLERANCE = 1.0  # meters - distance to consider waypoint reached
MAX_WAIT_TIME = 30.0  # seconds - maximum time to wait for position update
TRAJECTORY_HISTORY_SIZE = 100  # number of positions to store in history


class RoverStatus(Enum):
    IDLE = "idle"
    SURVEYING = "surveying"
    MOVING_TO_WAYPOINT = "moving_to_waypoint"
    WAITING_FOR_POSITION = "waiting_for_position"
    GPS_DENIED = "gps_denied"
    ERROR = "error"


@dataclass
class SurveyWaypoint:
    """Survey waypoint data structure"""
    position: Tuple[float, float]
    waypoint_id: str
    survey_type: str = "standard"
    completed: bool = False
    timestamp_reached: Optional[float] = None


@dataclass
class PositionUpdate:
    """Position update from parent drone"""
    position: Tuple[float, float]
    accuracy: float
    confidence: float
    timestamp: float
    source: str = "parent_drone"


def check_gps_status(position: Tuple[float, float], 
                    gps_denied_areas: List[Tuple[float, float, float]],
                    current_time: float,
                    current_gps_status: bool,
                    gps_lost_time: Optional[float]) -> Tuple[bool, Optional[float]]:
    """
    Check if rover position is in GPS-denied area.
    
    Returns:
        Tuple of (has_gps, gps_lost_time)
    """
    from utils.utils_MLAT import is_point_in_circle
    
    # Check if in any GPS-denied area
    in_denied_area = any(
        is_point_in_circle(position, (center_x, center_y), radius)
        for center_x, center_y, radius in gps_denied_areas
    )
    
    if in_denied_area and current_gps_status:
        # Just lost GPS
        return False, current_time
    elif not in_denied_area and not current_gps_status:
        # Regained GPS
        return True, None
    else:
        # No change in GPS status
        return current_gps_status, gps_lost_time


def calculate_movement(current_pos: Tuple[float, float],
                      target_pos: Tuple[float, float],
                      speed: float,
                      dt: float,
                      bounds: Tuple[float, float, float, float]) -> Tuple[Tuple[float, float], float]:
    """
    Calculate new position after movement towards target.
    
    Returns:
        Tuple of (new_position, distance_traveled)
    """
    # Calculate direction to target
    dx = target_pos[0] - current_pos[0]
    dy = target_pos[1] - current_pos[1]
    distance_to_target = np.sqrt(dx**2 + dy**2)
    
    if distance_to_target == 0:
        return current_pos, 0.0
    
    # Calculate movement distance
    movement_distance = speed * dt
    
    # Don't overshoot target
    if movement_distance >= distance_to_target:
        return target_pos, distance_to_target
    
    # Calculate new position
    direction_x = dx / distance_to_target
    direction_y = dy / distance_to_target
    
    new_x = current_pos[0] + direction_x * movement_distance
    new_y = current_pos[1] + direction_y * movement_distance
    
    # Keep within bounds
    new_x = max(bounds[0], min(bounds[1], new_x))
    new_y = max(bounds[2], min(bounds[3], new_y))
    
    return (new_x, new_y), movement_distance


def check_waypoint_reached(current_pos: Tuple[float, float],
                          waypoint_pos: Tuple[float, float]) -> bool:
    """Check if rover has reached a waypoint."""
    from utils.utils_MLAT import euclidean_distance
    
    distance = euclidean_distance(current_pos, waypoint_pos)
    return distance <= WAYPOINT_TOLERANCE


def can_communicate(rover_pos: Tuple[float, float],
                   drone_pos: Tuple[float, float]) -> bool:
    """Check if rover can communicate with drone."""
    from utils.utils_MLAT import euclidean_distance
    
    distance = euclidean_distance(rover_pos, drone_pos)
    return distance <= COMM_RANGE


def generate_telemetry(rover_id: str,
                      position: Tuple[float, float],
                      has_gps: bool,
                      status: RoverStatus,
                      survey_active: bool,
                      current_waypoint_index: int,
                      survey_progress: float,
                      waiting_for_position: bool,
                      comm_status: bool,
                      timestamp: float) -> Dict:
    """Generate telemetry data for transmission to parent drone."""
    return {
        'rover_id': rover_id,
        'position': position,
        'has_gps': has_gps,
        'status': status.value,
        'survey_active': survey_active,
        'current_waypoint': current_waypoint_index,
        'survey_progress': survey_progress,
        'waiting_for_position': waiting_for_position,
        'can_communicate': comm_status,
        'timestamp': timestamp
    }