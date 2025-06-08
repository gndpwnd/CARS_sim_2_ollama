"""
Rover class for GPS-denied land survey operations.
Handles autonomous navigation, GPS status management, and communication with parent drone.
"""

import time
from typing import Tuple, List, Optional, Dict
from dataclasses import dataclass
from collections import deque

from utils_rover import (
    RoverStatus,
    SurveyWaypoint,
    PositionUpdate,
    check_gps_status,
    calculate_movement,
    check_waypoint_reached,
    can_communicate,
    generate_telemetry,
    COMM_RANGE,
    SURVEY_SPEED,
    POSITION_TOLERANCE,
    WAYPOINT_TOLERANCE,
    MAX_WAIT_TIME,
    TRAJECTORY_HISTORY_SIZE
)


class Rover:
    """
    Autonomous rover for land survey operations in GPS-denied environments.
    Communicates with parent drone for positioning when GPS is unavailable.
    """
    
    def __init__(self, rover_id: str, initial_position: Tuple[float, float],
                 bounds: Tuple[float, float, float, float]):
        self.rover_id = rover_id
        self.position = initial_position
        self.bounds = bounds  # (min_x, max_x, min_y, max_y)
        
        # Navigation and survey
        self.survey_waypoints = []
        self.current_waypoint_index = 0
        self.target_position = initial_position
        self.trajectory_history = deque(maxlen=TRAJECTORY_HISTORY_SIZE)
        self.trajectory_history.append(initial_position)
        
        # GPS and positioning
        self.has_gps = True
        self.gps_lost_time = None
        self.last_gps_position = initial_position
        self.estimated_position = None
        self.position_accuracy = 0.0
        
        # Communication with parent drone
        self.parent_drone = None
        self.last_communication_time = 0.0
        self.waiting_for_position = False
        self.position_wait_start_time = None
        self.last_position_update = None
        
        # Status and control
        self.status = RoverStatus.IDLE
        self.survey_active = False
        self.movement_speed = SURVEY_SPEED
        self.total_distance_traveled = 0.0
        self.survey_progress = 0.0
        
        # Performance metrics
        self.waypoints_completed = 0
        self.gps_denied_episodes = 0
        self.total_gps_denied_time = 0.0
        self.position_updates_received = 0
        self.successful_communications = 0
        
        print(f"Rover {self.rover_id} initialized at position {initial_position}")
    
    def set_parent_drone(self, parent_drone):
        """Set reference to parent drone for communication"""
        self.parent_drone = parent_drone
        print(f"Rover {self.rover_id} connected to parent drone {parent_drone.drone_id}")
    
    def load_survey_plan(self, waypoints: List[Tuple[float, float]], survey_types: Optional[List[str]] = None):
        """Load survey waypoints for autonomous navigation"""
        self.survey_waypoints = []
        
        for i, waypoint in enumerate(waypoints):
            survey_type = survey_types[i] if survey_types and i < len(survey_types) else "standard"
            waypoint_obj = SurveyWaypoint(
                position=waypoint,
                waypoint_id=f"WP_{i+1:03d}",
                survey_type=survey_type
            )
            self.survey_waypoints.append(waypoint_obj)
        
        self.current_waypoint_index = 0
        if self.survey_waypoints:
            self.target_position = self.survey_waypoints[0].position
        
        print(f"Rover {self.rover_id} loaded {len(waypoints)} survey waypoints")
    
    def start_survey(self):
        """Start autonomous survey operations"""
        if not self.survey_waypoints:
            print(f"Rover {self.rover_id}: No survey waypoints loaded")
            return False
        
        self.survey_active = True
        self.status = RoverStatus.SURVEYING
        self.current_waypoint_index = 0
        self.target_position = self.survey_waypoints[0].position
        
        print(f"Rover {self.rover_id} starting survey with {len(self.survey_waypoints)} waypoints")
        return True
    
    def stop_survey(self):
        """Stop survey operations"""
        self.survey_active = False
        self.status = RoverStatus.IDLE
        print(f"Rover {self.rover_id} survey stopped")
    
    def update(self, dt: float, gps_denied_areas: List[Tuple[float, float, float]]):
        """
        Update rover state, check GPS status, and handle navigation.
        
        Args:
            dt: Time step in seconds
            gps_denied_areas: List of (center_x, center_y, radius) GPS-denied areas
        """
        current_time = time.time()
        
        # Check GPS availability
        self.has_gps, self.gps_lost_time = check_gps_status(
            self.position,
            gps_denied_areas,
            current_time,
            self.has_gps,
            self.gps_lost_time
        )
        
        # Update trajectory history
        self.trajectory_history.append(self.position)
        
        # Handle navigation based on GPS status and survey state
        if self.survey_active:
            if self.has_gps:
                self._handle_gps_navigation(dt, current_time)
            else:
                self._handle_gps_denied_navigation(dt, current_time)
        
        # Update performance metrics
        self._update_metrics(dt)
        
        # Send telemetry to parent drone if connected
        self._send_telemetry_to_parent(current_time)
    
    def _handle_gps_navigation(self, dt: float, current_time: float):
        """Handle navigation when GPS is available"""
        if not self.survey_waypoints or self.current_waypoint_index >= len(self.survey_waypoints):
            self._complete_survey()
            return
        
        current_waypoint = self.survey_waypoints[self.current_waypoint_index]
        
        # Move towards current waypoint
        if not current_waypoint.completed:
            new_position, distance = calculate_movement(
                self.position,
                current_waypoint.position,
                self.movement_speed,
                dt,
                self.bounds
            )
            self.position = new_position
            self.total_distance_traveled += distance
            
            # Check if waypoint reached
            if check_waypoint_reached(self.position, current_waypoint.position):
                self._reach_waypoint(current_waypoint, current_time)
        
        # Move to next waypoint if current is completed
        if current_waypoint.completed:
            self._advance_to_next_waypoint()
    
    def _handle_gps_denied_navigation(self, dt: float, current_time: float):
        """Handle navigation when GPS is denied"""
        # Stop movement and wait for position update from parent drone
        if self.waiting_for_position:
            # Check for timeout
            if (current_time - self.position_wait_start_time) > MAX_WAIT_TIME:
                print(f"Rover {self.rover_id}: Position update timeout, attempting emergency procedures")
                self._handle_position_timeout()
                return
            
            # Request position update from parent drone
            self._request_position_update()
        
        # If we have a recent position update, continue navigation
        elif self.last_position_update and (current_time - self.last_position_update.timestamp) < 5.0:
            # Use estimated position for navigation
            if self.survey_active and self.survey_waypoints:
                current_waypoint = self.survey_waypoints[self.current_waypoint_index]
                new_position, distance = calculate_movement(
                    self.position,
                    current_waypoint.position,
                    self.movement_speed,
                    dt,
                    self.bounds
                )
                self.position = new_position
                self.total_distance_traveled += distance
                
                # Check if waypoint reached using estimated position
                if check_waypoint_reached(self.position, current_waypoint.position):
                    self._reach_waypoint(current_waypoint, current_time)
                    self._advance_to_next_waypoint()
    
    def _reach_waypoint(self, waypoint: SurveyWaypoint, current_time: float):
        """Handle reaching a survey waypoint"""
        waypoint.completed = True
        waypoint.timestamp_reached = current_time
        self.waypoints_completed += 1
        
        print(f"Rover {self.rover_id} reached waypoint {waypoint.waypoint_id} at {waypoint.position}")
        
        # Perform survey operations at waypoint
        self._perform_survey_at_waypoint(waypoint)
    
    def _perform_survey_at_waypoint(self, waypoint: SurveyWaypoint):
        """Perform survey operations at reached waypoint"""
        pass
    
    def _advance_to_next_waypoint(self):
        """Advance to the next waypoint in the survey plan"""
        self.current_waypoint_index += 1
        
        if self.current_waypoint_index < len(self.survey_waypoints):
            next_waypoint = self.survey_waypoints[self.current_waypoint_index]
            self.target_position = next_waypoint.position
            self.survey_progress = (self.current_waypoint_index / len(self.survey_waypoints)) * 100.0
            print(f"Rover {self.rover_id} advancing to waypoint {next_waypoint.waypoint_id}")
        else:
            self._complete_survey()
    
    def _complete_survey(self):
        """Complete the survey operations"""
        self.survey_active = False
        self.status = RoverStatus.IDLE
        self.survey_progress = 100.0
        print(f"Rover {self.rover_id} completed survey: {self.waypoints_completed} waypoints")
    
    def _request_position_update(self):
        """Request position update from parent drone"""
        if self.parent_drone and self._can_communicate_with_parent():
            pass
    
    def _handle_position_timeout(self):
        """Handle timeout when waiting for position update"""
        if self.last_gps_position:
            print(f"Rover {self.rover_id}: Emergency return to last GPS position {self.last_gps_position}")
            self.target_position = self.last_gps_position
            self.status = RoverStatus.MOVING_TO_WAYPOINT
        else:
            self.status = RoverStatus.ERROR
            print(f"Rover {self.rover_id}: Critical error - no fallback position available")
    
    def receive_position_update(self, position_update: PositionUpdate):
        """Receive position update from parent drone"""
        self.last_position_update = position_update
        self.position_updates_received += 1
        self.waiting_for_position = False
        
        # Update estimated position if accuracy is acceptable
        if position_update.accuracy <= POSITION_TOLERANCE:
            self.estimated_position = position_update.position
            self.position = position_update.position
            self.position_accuracy = position_update.accuracy
            self.status = RoverStatus.SURVEYING if self.survey_active else RoverStatus.IDLE
            
            print(f"Rover {self.rover_id} received position update: {position_update.position} "
                  f"(accuracy: {position_update.accuracy:.2f}m)")
        else:
            print(f"Rover {self.rover_id}: Position update accuracy insufficient "
                  f"({position_update.accuracy:.2f}m > {POSITION_TOLERANCE}m)")
    
    def _can_communicate_with_parent(self) -> bool:
        """Check if rover can communicate with parent drone"""
        if not self.parent_drone:
            return False
        return can_communicate(self.position, self.parent_drone.position)
    
    def _send_telemetry_to_parent(self, current_time: float):
        """Send telemetry data to parent drone"""
        if current_time - self.last_communication_time >= 1.0:
            if self.parent_drone and self._can_communicate_with_parent():
                telemetry_data = generate_telemetry(
                    rover_id=self.rover_id,
                    position=self.position,
                    has_gps=self.has_gps,
                    status=self.status,
                    survey_active=self.survey_active,
                    current_waypoint_index=self.current_waypoint_index,
                    survey_progress=self.survey_progress,
                    waiting_for_position=self.waiting_for_position,
                    comm_status=self._can_communicate_with_parent(),
                    timestamp=current_time
                )
                
                self.successful_communications += 1
                self.last_communication_time = current_time
    
    def _update_metrics(self, dt: float):
        """Update performance metrics"""
        pass
    
    def get_status_dict(self) -> Dict:
        """Get comprehensive status dictionary"""
        current_time = time.time()
        
        return {
            'rover_id': self.rover_id,
            'position': self.position,
            'estimated_position': self.estimated_position,
            'status': self.status.value,
            'has_gps': self.has_gps,
            'survey_active': self.survey_active,
            'survey_progress': self.survey_progress,
            'current_waypoint': self.current_waypoint_index,
            'total_waypoints': len(self.survey_waypoints),
            'waypoints_completed': self.waypoints_completed,
            'waiting_for_position': self.waiting_for_position,
            'time_waiting': (current_time - self.position_wait_start_time) if self.position_wait_start_time else 0.0,
            'can_communicate_with_parent': self._can_communicate_with_parent(),
            'position_accuracy': self.position_accuracy,
            'total_distance_traveled': self.total_distance_traveled,
            'gps_denied_episodes': self.gps_denied_episodes,
            'total_gps_denied_time': self.total_gps_denied_time,
            'position_updates_received': self.position_updates_received,
            'successful_communications': self.successful_communications,
            'last_position_update': {
                'position': self.last_position_update.position,
                'accuracy': self.last_position_update.accuracy,
                'timestamp': self.last_position_update.timestamp
            } if self.last_position_update else None
        }
    
    def get_survey_status(self) -> Dict:
        """Get detailed survey status"""
        completed_waypoints = [wp for wp in self.survey_waypoints if wp.completed]
        pending_waypoints = [wp for wp in self.survey_waypoints if not wp.completed]
        
        return {
            'total_waypoints': len(self.survey_waypoints),
            'completed_waypoints': len(completed_waypoints),
            'pending_waypoints': len(pending_waypoints),
            'current_waypoint_id': (
                self.survey_waypoints[self.current_waypoint_index].waypoint_id 
                if self.current_waypoint_index < len(self.survey_waypoints) else None
            ),
            'progress_percentage': self.survey_progress,
            'survey_active': self.survey_active,
            'total_distance_traveled': self.total_distance_traveled
        }