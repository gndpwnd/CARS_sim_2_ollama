"""
Child drone class for GPS-denied rover positioning system.
Handles GPS tracking, jam recovery, distance measurements, and communication with parent drone.
"""

import time
import random
import numpy as np
from typing import Tuple, List, Optional, Dict
from dataclasses import dataclass
from enum import Enum
from collections import deque

# Import existing modules
from simulation.distance_measurement import ToFDistanceMeasurement, HardwareConfig
from simulation.utils.utils_MLAT import euclidean_distance, is_point_in_circle

# Constants
COMM_RANGE = 50.0  # meters - communication range
NUM_DRONE_POS_ONBOARD = 5  # number of positions to store for recovery
GPS_UPDATE_RATE = 1.0  # Hz
POSITION_NOISE_STD = 0.1  # meters
MOVEMENT_SPEED = 2.0  # m/s


class DroneStatus(Enum):
    OPERATIONAL = "operational"
    GPS_DENIED = "gps_denied"
    JAMMED = "jammed"
    RECOVERING = "recovering"
    MOVING_TO_POSITION = "moving_to_position"


@dataclass
class TelemetryData:
    """Telemetry data structure for drone communication"""
    drone_id: str
    timestamp: float
    position: Tuple[float, float]
    gps_available: bool
    status: DroneStatus
    distance_to_rover: Optional[float] = None
    measurement_quality: Optional[float] = None
    battery_level: float = 100.0
    signal_strength: float = 100.0
    jammed: bool = False


class ChildDrone:
    """
    Child drone that performs distance measurements and communicates with parent drone.
    Handles GPS jamming recovery and maintains position history.
    """
    
    def __init__(self, drone_id: str, initial_position: Tuple[float, float], 
                 bounds: Tuple[float, float, float, float]):
        self.drone_id = drone_id
        self.position = initial_position
        self.bounds = bounds  # (min_x, max_x, min_y, max_y)
        
        # Position tracking and recovery
        self.position_history = deque(maxlen=NUM_DRONE_POS_ONBOARD)
        self.position_history.append(initial_position)
        self.last_good_gps_position = initial_position
        
        # Status tracking
        self.status = DroneStatus.OPERATIONAL
        self.gps_available = True
        self.jammed = False
        self.last_gps_update = time.time()
        
        # Communication
        self.parent_drone = None
        self.last_communication_time = 0.0
        self.communication_active = False
        
        # Distance measurement system
        self.distance_measurement = ToFDistanceMeasurement(HardwareConfig())
        self.distance_measurement.calibrate_system()
        
        # Movement and navigation
        self.target_position = initial_position
        self.moving_to_target = False
        self.trajectory_angle = random.uniform(0, 2 * np.pi)
        self.movement_speed = MOVEMENT_SPEED
        
        # Performance metrics
        self.battery_level = 100.0
        self.signal_strength = 100.0
        self.measurement_count = 0
        self.successful_measurements = 0
        
        print(f"Child drone {self.drone_id} initialized at position {initial_position}")
    
    def set_parent_drone(self, parent_drone):
        """Set reference to parent drone for communication"""
        self.parent_drone = parent_drone
        print(f"Child drone {self.drone_id} connected to parent drone")
    
    def update(self, dt: float, gps_denied_areas: List[Tuple[float, float, float]], 
               rover_position: Optional[Tuple[float, float]] = None):
        """
        Update drone state, check for GPS jamming, and perform measurements.
        
        Args:
            dt: Time step in seconds
            gps_denied_areas: List of (center_x, center_y, radius) GPS-denied areas
            rover_position: Current rover position if known
        """
        # Update position if moving to target
        if self.moving_to_target:
            self._move_towards_target(dt)
        else:
            self._autonomous_movement(dt)
        
        # Check GPS availability
        self._check_gps_status(gps_denied_areas)
        
        # Update position history if GPS is available
        if self.gps_available:
            self.position_history.append(self.position)
            self.last_good_gps_position = self.position
        
        # Handle jam recovery
        if self.jammed or self.status == DroneStatus.GPS_DENIED:
            self._handle_jam_recovery()
        
        # Perform distance measurement to rover if conditions are met
        if rover_position and self._can_measure_distance(rover_position):
            distance_data = self._measure_distance_to_rover(rover_position)
            if distance_data:
                self._send_telemetry_to_parent(distance_data)
        
        # Send regular telemetry
        self._send_regular_telemetry()
        
        # Update battery and signal strength
        self._update_system_status(dt)
    
    def _check_gps_status(self, gps_denied_areas: List[Tuple[float, float, float]]):
        """Check if drone is in GPS-denied area"""
        was_gps_available = self.gps_available
        self.gps_available = True
        
        for area_center_x, area_center_y, radius in gps_denied_areas:
            if is_point_in_circle(self.position, (area_center_x, area_center_y), radius):
                self.gps_available = False
                break
        
        # Update status based on GPS availability
        if not self.gps_available and was_gps_available:
            self.status = DroneStatus.GPS_DENIED
            self.jammed = True
            print(f"Drone {self.drone_id} entered GPS-denied area")
        elif self.gps_available and not was_gps_available:
            self.status = DroneStatus.OPERATIONAL
            self.jammed = False
            print(f"Drone {self.drone_id} recovered GPS signal")
    
    def _handle_jam_recovery(self):
        """Handle recovery from GPS jamming by returning to last good position"""
        if self.status != DroneStatus.RECOVERING and len(self.position_history) > 1:
            # Find the most recent good GPS position
            recovery_position = self.last_good_gps_position
            
            # If we have position history, use the last good position
            if len(self.position_history) >= 2:
                recovery_position = self.position_history[-2]  # Previous position
            
            self.status = DroneStatus.RECOVERING
            self.target_position = recovery_position
            self.moving_to_target = True
            
            print(f"Drone {self.drone_id} initiating jam recovery to position {recovery_position}")
    
    def _can_measure_distance(self, rover_position: Tuple[float, float]) -> bool:
        """Check if drone can measure distance to rover"""
        if not self.gps_available or self.jammed:
            return False
        
        # Check if within communication range
        distance_to_rover = euclidean_distance(self.position, rover_position)
        if distance_to_rover > COMM_RANGE:
            return False
        
        # Check if distance measurement system is ready
        if not self.distance_measurement.is_calibrated:
            return False
        
        return True
    
    def _measure_distance_to_rover(self, rover_position: Tuple[float, float]) -> Optional[Dict]:
        """Perform ToF distance measurement to rover"""
        try:
            self.measurement_count += 1
            
            # Use ToF distance measurement system
            measured_distance = self.distance_measurement.measure_distance(
                self.position, rover_position, use_precision_timing=True
            )
            
            if measured_distance is not None:
                self.successful_measurements += 1
                
                # Get measurement quality
                comm_quality = self.distance_measurement.get_communication_quality(
                    self.position, rover_position
                )
                
                measurement_data = {
                    'drone_id': self.drone_id,
                    'drone_position': self.position,
                    'rover_position': rover_position,
                    'measured_distance': measured_distance,
                    'measurement_quality': comm_quality,
                    'timestamp': time.time()
                }
                
                return measurement_data
            
        except Exception as e:
            print(f"Distance measurement error for drone {self.drone_id}: {e}")
        
        return None
    
    def _send_telemetry_to_parent(self, measurement_data: Dict):
        """Send measurement data to parent drone"""
        if self.parent_drone and self._can_communicate_with_parent():
            telemetry = TelemetryData(
                drone_id=self.drone_id,
                timestamp=time.time(),
                position=self.position,
                gps_available=self.gps_available,
                status=self.status,
                distance_to_rover=measurement_data.get('measured_distance'),
                measurement_quality=measurement_data.get('measurement_quality'),
                battery_level=self.battery_level,
                signal_strength=self.signal_strength,
                jammed=self.jammed
            )
            
            self.parent_drone.receive_telemetry(telemetry, measurement_data)
            self.last_communication_time = time.time()
    
    def _send_regular_telemetry(self):
        """Send regular status telemetry to parent drone"""
        current_time = time.time()
        
        # Send telemetry every second
        if current_time - self.last_communication_time >= 1.0:
            if self.parent_drone and self._can_communicate_with_parent():
                telemetry = TelemetryData(
                    drone_id=self.drone_id,
                    timestamp=current_time,
                    position=self.position,
                    gps_available=self.gps_available,
                    status=self.status,
                    battery_level=self.battery_level,
                    signal_strength=self.signal_strength,
                    jammed=self.jammed,
                )
                
                self.parent_drone.receive_telemetry(telemetry)
                self.last_communication_time = current_time
    
    def _can_communicate_with_parent(self) -> bool:
        """Check if drone can communicate with parent drone"""
        if not self.parent_drone:
            return False
        
        # Check communication range to parent
        distance_to_parent = euclidean_distance(self.position, self.parent_drone.position)
        return distance_to_parent <= COMM_RANGE
    
    def _move_towards_target(self, dt: float):
        """Move drone towards target position"""
        if not self.moving_to_target:
            return
        
        # Calculate direction to target
        dx = self.target_position[0] - self.position[0]
        dy = self.target_position[1] - self.position[1]
        distance_to_target = np.sqrt(dx**2 + dy**2)
        
        # Check if we've reached the target
        if distance_to_target < 0.5:  # Within 0.5 meters
            self.position = self.target_position
            self.moving_to_target = False
            
            if self.status == DroneStatus.RECOVERING:
                self.status = DroneStatus.OPERATIONAL
                print(f"Drone {self.drone_id} completed jam recovery")
            elif self.status == DroneStatus.MOVING_TO_POSITION:
                self.status = DroneStatus.OPERATIONAL
                print(f"Drone {self.drone_id} reached commanded position")
            
            return
        
        # Move towards target
        movement_distance = self.movement_speed * dt
        if movement_distance >= distance_to_target:
            self.position = self.target_position
        else:
            direction_x = dx / distance_to_target
            direction_y = dy / distance_to_target
            
            new_x = self.position[0] + direction_x * movement_distance
            new_y = self.position[1] + direction_y * movement_distance
            
            # Keep within bounds
            new_x = max(self.bounds[0], min(self.bounds[1], new_x))
            new_y = max(self.bounds[2], min(self.bounds[3], new_y))
            
            self.position = (new_x, new_y)
    
    def _autonomous_movement(self, dt: float):
        """Autonomous movement when not moving to specific target"""
        if self.moving_to_target or self.status != DroneStatus.OPERATIONAL:
            return
        
        # Simple autonomous patrol movement
        movement_distance = self.movement_speed * dt * 0.5  # Slower autonomous movement
        
        # Update position based on trajectory angle
        new_x = self.position[0] + np.cos(self.trajectory_angle) * movement_distance
        new_y = self.position[1] + np.sin(self.trajectory_angle) * movement_distance
        
        # Bounce off boundaries
        if new_x <= self.bounds[0] or new_x >= self.bounds[1]:
            self.trajectory_angle = np.pi - self.trajectory_angle
            new_x = max(self.bounds[0], min(self.bounds[1], new_x))
        
        if new_y <= self.bounds[2] or new_y >= self.bounds[3]:
            self.trajectory_angle = -self.trajectory_angle
            new_y = max(self.bounds[2], min(self.bounds[3], new_y))
        
        # Add some randomness to trajectory
        if random.random() < 0.1:  # 10% chance to change direction
            self.trajectory_angle += random.uniform(-0.5, 0.5)
        
        self.position = (new_x, new_y)
    
    def _update_system_status(self, dt: float):
        """Update battery level and signal strength"""
        # Simulate battery drain
        battery_drain_rate = 0.1  # %/hour
        self.battery_level -= battery_drain_rate * (dt / 3600.0)
        self.battery_level = max(0.0, self.battery_level)
        
        # Simulate signal strength based on position and interference
        base_signal = 100.0
        if self.jammed:
            self.signal_strength = max(0.0, base_signal * 0.1)
        else:
            self.signal_strength = base_signal * (0.8 + 0.2 * random.random())
    
    def receive_command_from_parent(self, command: Dict):
        """Receive and execute command from parent drone"""
        command_type = command.get('type')
        
        if command_type == 'move_to_position':
            target_pos = command.get('target_position')
            if target_pos:
                self.target_position = target_pos
                self.moving_to_target = True
                self.status = DroneStatus.MOVING_TO_POSITION
                print(f"Drone {self.drone_id} received move command to {target_pos}")
        
        elif command_type == 'return_to_base':
            self.target_position = self.last_good_gps_position
            self.moving_to_target = True
            self.status = DroneStatus.MOVING_TO_POSITION
            print(f"Drone {self.drone_id} returning to base position")
        
        elif command_type == 'calibrate_distance_sensor':
            success = self.distance_measurement.calibrate_system()
            print(f"Drone {self.drone_id} distance sensor calibration: {'Success' if success else 'Failed'}")
    
    def get_status_dict(self) -> Dict:
        """Get comprehensive status dictionary"""
        return {
            'drone_id': self.drone_id,
            'position': self.position,
            'status': self.status.value,
            'gps_available': self.gps_available,
            'jammed': self.jammed,
            'battery_level': self.battery_level,
            'signal_strength': self.signal_strength,
            'measurement_success_rate': (
                self.successful_measurements / max(1, self.measurement_count) * 100.0
            ),
            'position_history_size': len(self.position_history),
            'can_communicate_with_parent': self._can_communicate_with_parent(),
            'target_position': self.target_position if self.moving_to_target else None,
            'distance_sensor_calibrated': self.distance_measurement.is_calibrated
        }