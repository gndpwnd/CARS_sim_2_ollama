"""
Parent drone utilities - Supporting functions for parent drone operations.
"""

import time
import numpy as np
from typing import Dict, List, Tuple, Optional, Set
from vehicles.parent_drone_status import ParentDroneStatus

# Constants
TELEMETRY_TIMEOUT = 5.0  # seconds before considering drone offline
MIN_DRONES_FOR_POSITIONING = 4  # minimum drones needed for multilateration
POSITION_UPDATE_INTERVAL = 2.0  # seconds between position updates
DRONE_REPOSITIONING_TIMEOUT = 10.0  # seconds to wait for repositioning
MAX_POSITIONING_ERROR = 2.0  # meters - maximum acceptable positioning error


def check_drone_connectivity(parent_drone, current_time: float):
    """Check connectivity status of all child drones."""
    offline_drones = []
    
    for drone_id, last_time in parent_drone.last_telemetry_time.items():
        if current_time - last_time > TELEMETRY_TIMEOUT:
            offline_drones.append(drone_id)
            parent_drone.operational_drones.discard(drone_id)
    
    if offline_drones:
        print(f"Parent drone {parent_drone.drone_id}: Offline drones detected: {offline_drones}")


def cleanup_old_commands(parent_drone, current_time: float):
    """Clean up old commands that have timed out."""
    expired_commands = []
    
    for cmd_id, cmd in parent_drone.active_commands.items():
        if current_time - cmd.timestamp > DRONE_REPOSITIONING_TIMEOUT:
            expired_commands.append(cmd_id)
    
    for cmd_id in expired_commands:
        del parent_drone.active_commands[cmd_id]


def coordinate_rover_positioning(parent_drone, current_time: float):
    """Coordinate rover positioning using multilateration."""
    if current_time - parent_drone.last_rover_position_update < POSITION_UPDATE_INTERVAL:
        return
    
    # Get available drones for positioning
    available_drones = get_available_drones_for_positioning(parent_drone)
    
    if len(available_drones) < MIN_DRONES_FOR_POSITIONING:
        parent_drone.status = ParentDroneStatus.REPOSITIONING_DRONES
        _handle_insufficient_drones(parent_drone, available_drones)
        return
    
    # Check multilateration constraints
    if not check_multilateration_constraints(parent_drone, available_drones):
        parent_drone.status = ParentDroneStatus.REPOSITIONING_DRONES
        fix_constraint_violations(parent_drone, available_drones)
        return
    
    # Calculate rover position
    rover_position = calculate_rover_position(parent_drone, available_drones)
    
    if rover_position:
        send_position_to_rover(parent_drone, rover_position, current_time)
        parent_drone.last_rover_position_update = current_time
        parent_drone.successful_positions += 1
    else:
        parent_drone.failed_positions += 1


def get_available_drones_for_positioning(parent_drone) -> List[str]:
    """Get list of drones available for positioning calculations."""
    available_drones = []
    
    for drone_id in parent_drone.operational_drones:
        telemetry = parent_drone.drone_telemetry.get(drone_id)
        if telemetry and telemetry.gps_available and not telemetry.jammed:
            # Check if drone has recent distance measurement
            if drone_id in parent_drone.drone_distances:
                distance_data = parent_drone.drone_distances[drone_id]
                if time.time() - distance_data['timestamp'] < 5.0:  # Recent measurement
                    available_drones.append(drone_id)
    
    return available_drones


def check_multilateration_constraints(parent_drone, available_drones: List[str]) -> bool:
    """Check if multilateration constraints are satisfied."""
    if len(available_drones) < MIN_DRONES_FOR_POSITIONING:
        return False
    
    # Check geometric constraints (GDOP)
    drone_positions = []
    for drone_id in available_drones:
        telemetry = parent_drone.drone_telemetry.get(drone_id)
        if telemetry:
            drone_positions.append(telemetry.position)
    
    if len(drone_positions) < MIN_DRONES_FOR_POSITIONING:
        return False
    
    # Simple geometric diversity check
    return _check_geometric_diversity(drone_positions)


def _check_geometric_diversity(positions: List[Tuple[float, float]]) -> bool:
    """Check if drone positions provide good geometric diversity."""
    if len(positions) < 4:
        return False
    
    # Calculate center of mass
    center_x = sum(pos[0] for pos in positions) / len(positions)
    center_y = sum(pos[1] for pos in positions) / len(positions)
    
    # Check if drones are too clustered
    distances_from_center = []
    for pos in positions:
        dist = np.sqrt((pos[0] - center_x)**2 + (pos[1] - center_y)**2)
        distances_from_center.append(dist)
    
    # Require minimum spread
    return max(distances_from_center) > 10.0  # 10 meter minimum spread


def fix_constraint_violations(parent_drone, available_drones: List[str]):
    """Fix constraint violations by repositioning drones."""
    # Simple repositioning strategy: spread drones around rover
    if not parent_drone.rover_position:
        return
    
    rover_x, rover_y = parent_drone.rover_position
    
    # Target positions in a circle around rover
    target_positions = []
    for i in range(len(available_drones)):
        angle = (2 * np.pi * i) / len(available_drones)
        radius = 30.0  # 30 meter radius
        target_x = rover_x + radius * np.cos(angle)
        target_y = rover_y + radius * np.sin(angle)
        
        # Keep within bounds
        target_x = max(parent_drone.bounds[0], min(parent_drone.bounds[1], target_x))
        target_y = max(parent_drone.bounds[2], min(parent_drone.bounds[3], target_y))
        
        target_positions.append((target_x, target_y))
    
    # Send repositioning commands
    for drone_id, target_pos in zip(available_drones, target_positions):
        parent_drone._send_repositioning_command(drone_id, target_pos)


def calculate_rover_position(parent_drone, available_drones: List[str]) -> Optional[Tuple[float, float]]:
    """Calculate rover position using multilateration."""
    if len(available_drones) < MIN_DRONES_FOR_POSITIONING:
        return None
    
    # Prepare data for multilateration
    anchor_positions = []
    distances = []
    
    for drone_id in available_drones:
        telemetry = parent_drone.drone_telemetry.get(drone_id)
        distance_data = parent_drone.drone_distances.get(drone_id)
        
        if telemetry and distance_data:
            anchor_positions.append(telemetry.position)
            distances.append(distance_data['distance'])
    
    if len(anchor_positions) < MIN_DRONES_FOR_POSITIONING:
        return None
    
    try:
        # Use multilateration solver
        solution = parent_drone.multilateration_solver.solve(anchor_positions, distances)
        
        if solution and solution['success']:
            estimated_pos = solution['position']
            error_estimate = solution.get('error', 0.0)
            
            # Check if solution is reasonable
            if error_estimate <= MAX_POSITIONING_ERROR:
                # Store solution
                from parent_drone import PositioningSolution
                parent_drone.current_solution = PositioningSolution(
                    rover_position=estimated_pos,
                    error_estimate=error_estimate,
                    confidence=solution.get('confidence', 0.0),
                    participating_drones=available_drones,
                    gdop=solution.get('gdop', 0.0),
                    timestamp=time.time()
                )
                
                return estimated_pos
        
    except Exception as e:
        print(f"Multilateration calculation failed: {e}")
    
    return None


def send_position_to_rover(parent_drone, rover_position: Tuple[float, float], current_time: float):
    """Send calculated position to rover."""
    if not parent_drone.rover:
        return
    
    # Create position update
    from utils_rover import PositionUpdate
    position_update = PositionUpdate(
        position=rover_position,
        accuracy=parent_drone.current_solution.error_estimate if parent_drone.current_solution else 1.0,
        confidence=parent_drone.current_solution.confidence if parent_drone.current_solution else 0.8,
        timestamp=current_time
    )
    
    # Send to rover
    parent_drone.rover.receive_position_update(position_update)
    parent_drone.status = ParentDroneStatus.SENDING_POSITION
    
    print(f"Parent drone {parent_drone.drone_id} sent position {rover_position} to rover")


def update_status(parent_drone):
    """Update parent drone status based on current operations."""
    if parent_drone.status == ParentDroneStatus.REPOSITIONING_DRONES:
        # Check if repositioning is complete
        if not parent_drone.repositioning_drones:
            parent_drone.status = ParentDroneStatus.IDLE
    elif parent_drone.status == ParentDroneStatus.SENDING_POSITION:
        # Reset to collecting measurements
        parent_drone.status = ParentDroneStatus.COLLECTING_MEASUREMENTS


def _handle_insufficient_drones(parent_drone, available_drones: List[str]):
    """Handle case where insufficient drones are available for positioning."""
    print(f"Parent drone {parent_drone.drone_id}: Insufficient drones for positioning "
          f"({len(available_drones)}/{MIN_DRONES_FOR_POSITIONING})")
    
    # Try to bring more drones online by sending them to good positions
    offline_drones = set(parent_drone.child_drones.keys()) - parent_drone.operational_drones
    
    for drone_id in list(offline_drones)[:MIN_DRONES_FOR_POSITIONING - len(available_drones)]:
        # Send recovery command
        command = {
            'type': 'return_to_base'
        }
        if drone_id in parent_drone.child_drones:
            parent_drone.child_drones[drone_id].receive_command_from_parent(command)