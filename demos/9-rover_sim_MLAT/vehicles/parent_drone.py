"""
Parent drone class for GPS-denied rover positioning system.
Coordinates child drones, performs multilateration, and manages rover positioning.
"""

import time
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict, deque

# Import existing modules
from multilateration import MultilaterationSolver
from child_drone import TelemetryData, DroneStatus
from utils_parent_drone import (
    check_drone_connectivity,
    cleanup_old_commands,
    coordinate_rover_positioning,
    get_available_drones_for_positioning,
    send_position_to_rover,
    update_status,
    check_multilateration_constraints,
    fix_constraint_violations,
    calculate_rover_position
)

# Constants
COMM_RANGE = 50.0  # meters - communication range
MIN_DRONES_FOR_MULTILATERATION = 4  # minimum drones needed for positioning
POSITION_UPDATE_INTERVAL = 2.0  # seconds between position updates to rover
DRONE_REPOSITIONING_TIMEOUT = 10.0  # seconds to wait for drone repositioning
MAX_POSITIONING_ERROR = 2.0  # meters - maximum acceptable positioning error
TELEMETRY_TIMEOUT = 5.0  # seconds before considering drone offline


class ParentDroneStatus(Enum):
    IDLE = "idle"
    COLLECTING_MEASUREMENTS = "collecting_measurements"
    CALCULATING_POSITION = "calculating_position"
    REPOSITIONING_DRONES = "repositioning_drones"
    SENDING_POSITION = "sending_position"
    ERROR = "error"


@dataclass
class DroneCommand:
    """Command structure for drone communication"""
    command_id: str
    drone_id: str
    command_type: str
    target_position: Optional[Tuple[float, float]] = None
    parameters: Optional[Dict] = None
    timestamp: float = 0.0


@dataclass
class PositioningSolution:
    """Solution data structure for rover positioning"""
    rover_position: Tuple[float, float]
    error_estimate: float
    confidence: float
    participating_drones: List[str]
    gdop: float
    timestamp: float


class ParentDrone:
    """
    Parent drone that coordinates child drones and performs multilateration
    calculations for GPS-denied rover positioning.
    """
    
    def __init__(self, drone_id: str, initial_position: Tuple[float, float],
                 bounds: Tuple[float, float, float, float]):
        self.drone_id = drone_id
        self.position = initial_position
        self.bounds = bounds  # (min_x, max_x, min_y, max_y)
        
        # Child drone management
        self.child_drones = {}  # drone_id -> child_drone_reference
        self.drone_telemetry = {}  # drone_id -> latest_telemetry
        self.drone_distances = {}  # drone_id -> distance_to_rover
        self.last_telemetry_time = {}  # drone_id -> timestamp
        
        # Rover communication
        self.rover = None
        self.rover_position = None
        self.last_rover_position_update = 0.0
        
        # Multilateration system
        self.multilateration_solver = MultilaterationSolver(dimension="2d", method="geometric")
        self.positioning_history = deque(maxlen=100)
        self.current_solution = None
        
        # Status and control
        self.status = ParentDroneStatus.IDLE
        self.active_commands = {}  # command_id -> command
        self.repositioning_drones = set()
        self.operational_drones = set()
        
        # Performance tracking
        self.successful_positions = 0
        self.failed_positions = 0
        self.repositioning_commands = 0
        
        print(f"Parent drone {self.drone_id} initialized at position {initial_position}")
    
    def register_child_drone(self, child_drone):
        """Register a child drone with the parent"""
        self.child_drones[child_drone.drone_id] = child_drone
        child_drone.set_parent_drone(self)
        self.drone_telemetry[child_drone.drone_id] = None
        self.last_telemetry_time[child_drone.drone_id] = 0.0
        print(f"Child drone {child_drone.drone_id} registered with parent {self.drone_id}")
    
    def register_rover(self, rover):
        """Register the rover with the parent drone"""
        self.rover = rover
        rover.set_parent_drone(self)
        print(f"Rover {rover.rover_id} registered with parent drone {self.drone_id}")
    
    def receive_telemetry(self, telemetry: TelemetryData, measurement_data: Optional[Dict] = None):
        """Receive telemetry data from child drones"""
        drone_id = telemetry.drone_id
        current_time = time.time()
        
        # Store telemetry
        self.drone_telemetry[drone_id] = telemetry
        self.last_telemetry_time[drone_id] = current_time
        
        # Store distance measurement if provided
        if measurement_data and 'measured_distance' in measurement_data:
            self.drone_distances[drone_id] = {
                'distance': measurement_data['measured_distance'],
                'quality': measurement_data.get('measurement_quality', 1.0),
                'timestamp': current_time,
                'drone_position': telemetry.position
            }
        
        # Update operational drone status
        if telemetry.status == DroneStatus.OPERATIONAL and telemetry.gps_available:
            self.operational_drones.add(drone_id)
        else:
            self.operational_drones.discard(drone_id)
        
        # Check if drone needs jam recovery assistance
        if telemetry.status == DroneStatus.GPS_DENIED or telemetry.status == DroneStatus.JAMMED:
            self._assist_drone_recovery(drone_id, telemetry)
    
    def update(self, dt: float, gps_denied_areas: List[Tuple[float, float, float]]):
        """Update parent drone state and coordinate positioning system"""
        current_time = time.time()
        
        # Check for offline drones
        check_drone_connectivity(self, current_time)
        
        # Update rover position if available
        if self.rover and self.rover.has_gps:
            self.rover_position = self.rover.position
        
        # Main positioning logic
        if self.rover and not self.rover.has_gps and self.rover_position:
            coordinate_rover_positioning(self, current_time)
        
        # Clean up old commands
        cleanup_old_commands(self, current_time)
        
        # Update status
        update_status(self)
    
    def _assist_drone_recovery(self, drone_id: str, telemetry: TelemetryData):
        """Assist child drone with jam recovery"""
        if drone_id not in self.child_drones:
            return
        
        print(f"Parent drone {self.drone_id} monitoring recovery of {drone_id}")
    
    def _send_repositioning_command(self, drone_id: str, target_position: Tuple[float, float]):
        """Send repositioning command to a child drone"""
        if drone_id not in self.child_drones:
            return
        
        # Ensure target position is within bounds
        target_x = max(self.bounds[0], min(self.bounds[1], target_position[0]))
        target_y = max(self.bounds[2], min(self.bounds[3], target_position[1]))
        bounded_target = (target_x, target_y)
        
        command = {
            'type': 'move_to_position',
            'target_position': bounded_target,
            'command_id': f"reposition_{drone_id}_{time.time()}",
            'priority': 'high'
        }
        
        self.child_drones[drone_id].receive_command_from_parent(command)
        self.repositioning_drones.add(drone_id)
        self.repositioning_commands += 1
        
        print(f"Parent drone {self.drone_id} commanding {drone_id} to move to {bounded_target}")
    
    def get_status_dict(self) -> Dict:
        """Get comprehensive status dictionary"""
        return {
            'parent_drone_id': self.drone_id,
            'position': self.position,
            'status': self.status.value,
            'registered_child_drones': len(self.child_drones),
            'operational_drones': len(self.operational_drones),
            'repositioning_drones': len(self.repositioning_drones),
            'rover_registered': self.rover is not None,
            'current_solution': {
                'position': self.current_solution.rover_position if self.current_solution else None,
                'error': self.current_solution.error_estimate if self.current_solution else None,
                'confidence': self.current_solution.confidence if self.current_solution else None
            } if self.current_solution else None,
            'performance': {
                'successful_positions': self.successful_positions,
                'failed_positions': self.failed_positions,
                'repositioning_commands': self.repositioning_commands,
                'success_rate': self.successful_positions / max(1, self.successful_positions + self.failed_positions) * 100
            }
        }