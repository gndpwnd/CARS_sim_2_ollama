"""
Enhanced Simulation Manager - Handles rover, child drones, and parent drone coordination.
Manages GPS-denied areas, vehicle interactions, and simulation timing.
"""

import time
import random
import numpy as np
from typing import List, Tuple, Dict, Optional

# Import vehicle classes
from vehicles.child_drone import ChildDrone
from vehicles.parent_drone import ParentDrone
from vehicles.rover import Rover

class SimulationManager:
    """Enhanced simulation manager for GPS-denied rover positioning system."""
    
    def __init__(self):
        # Simulation parameters
        self.bounds = (0, 100, 0, 100)  # (min_x, max_x, min_y, max_y)
        self.gps_denied_areas = []  # List of (center_x, center_y, radius)
        
        # Simulation state
        self.running = False
        self.paused = False
        self.simulation_time = 0.0
        self.dt = 0.1  # Time step in seconds
        
        # Initialize vehicles
        self.rover = None
        self.parent_drone = None
        self.child_drones = []
        
        self._initialize_vehicles()
        
    def _initialize_vehicles(self):
        """Initialize all vehicles for the simulation."""
        # Clear existing vehicles to avoid duplication on reset
        self.child_drones.clear()
        self.rover = None
        self.parent_drone = None

        # Create rover
        rover_start_pos = (10, 10)
        self.rover = Rover("ROVER_01", rover_start_pos, self.bounds)
        
        # Create survey waypoints for the rover
        survey_waypoints = [
            (20, 20), (40, 20), (60, 20), (80, 20),
            (80, 40), (60, 40), (40, 40), (20, 40),
            (20, 60), (40, 60), (60, 60), (80, 60),
            (80, 80), (60, 80), (40, 80), (20, 80)
        ]
        self.rover.load_survey_plan(survey_waypoints)
        
        # Create parent drone
        parent_pos = (50, 50)  # Central position
        self.parent_drone = ParentDrone("PARENT_01", parent_pos, self.bounds)
        
        # Create child drones
        child_positions = [
            (25, 25), (75, 25), (75, 75), (25, 75),  # Corner positions
            #(50, 15), (85, 50), (50, 85), (15, 50)   # Mid-edge positions
        ]
        
        for i, pos in enumerate(child_positions):
            drone_id = f"CHILD_{i+1:02d}"
            child_drone = ChildDrone(drone_id, pos, self.bounds)
            self.child_drones.append(child_drone)
            
            # Register child drone with parent
            self.parent_drone.register_child_drone(child_drone)
        
        # Register rover with parent drone
        self.parent_drone.register_rover(self.rover)
        
        print(f"Initialized simulation with {len(self.child_drones)} child drones, 1 parent drone, and 1 rover")
    
    def step(self):
        """Execute a single simulation step."""
        if not self.running or self.paused:
            return
        
        self.simulation_time += self.dt
        
        # Update all vehicles
        self._update_vehicles()
        
    def _update_vehicles(self):
        """Update all vehicles in the simulation."""
        # Update rover
        if self.rover:
            self.rover.update(self.dt, self.gps_denied_areas)
        
        # Update child drones
        for drone in self.child_drones:
            rover_pos = self.rover.position if self.rover else None
            drone.update(self.dt, self.gps_denied_areas, rover_pos)
        
        # Update parent drone
        if self.parent_drone:
            self.parent_drone.update(self.dt, self.gps_denied_areas)
    
    def add_gps_denied_area(self, center_x, center_y, radius):
        """Add a GPS-denied area to the simulation."""
        if radius >= 2.0:  # Minimum radius requirement
            self.gps_denied_areas.append((center_x, center_y, radius))
            print(f"Added GPS-denied area at ({center_x}, {center_y}) with radius {radius}")
    
    def clear_gps_denied_areas(self):
        """Remove all GPS-denied areas."""
        self.gps_denied_areas.clear()
        print("Cleared all GPS-denied areas")
    
    def start(self):
        """Start the simulation."""
        self.running = True
        self.paused = False
        
        # Start rover survey if not already started
        if self.rover and not self.rover.survey_active:
            self.rover.start_survey()
        
        print("Simulation started")
    
    def pause(self):
        """Pause the simulation."""
        self.paused = True
        print("Simulation paused")
    
    def reset(self):
        """Reset the simulation to initial state."""
        self.running = False
        self.paused = False
        self.simulation_time = 0.0
        
        # Clear GPS-denied areas
        self.clear_gps_denied_areas()
        
        # Reinitialize all vehicles
        self._initialize_vehicles()
        
        print("Simulation reset")
    
    def get_all_vehicles(self):
        """Get all vehicles for plotting and display."""
        vehicles = []
        
        if self.rover:
            vehicles.append({
                'type': 'rover',
                'id': self.rover.rover_id,
                'position': self.rover.position,
                'status': self.rover.get_status_dict(),
                'color': 'blue',
                'trajectory': getattr(self.rover, 'trajectory', []),
                'has_gps': self.rover.has_gps if hasattr(self.rover, 'has_gps') else True,
                'estimated_position': self.rover.get_status_dict().get('estimated_position'),
                'position_error': self.rover.get_status_dict().get('position_error', 0.0),
            })
        
        if self.parent_drone:
            vehicles.append({
                'type': 'parent_drone',
                'id': self.parent_drone.drone_id,
                'position': self.parent_drone.position,
                'status': self.parent_drone.get_status_dict(),
                'color': 'red',
                'trajectory': getattr(self.parent_drone, 'trajectory', []),
                'has_gps': True,
                'estimated_position': None,
                'position_error': 0.0,
            })
        
        for drone in self.child_drones:
            status = drone.get_status_dict()
            vehicles.append({
                'type': 'child_drone',
                'id': drone.drone_id,
                'position': drone.position,
                'status': status,
                'color': 'green' if drone.gps_available and not drone.jammed else 'orange',
                'trajectory': getattr(drone, 'trajectory', []),
                'has_gps': drone.gps_available,
                'estimated_position': status.get('estimated_position'),
                'position_error': status.get('position_error', 0.0),
            })
        
        return vehicles
    
    def get_simulation_status(self):
        """Get comprehensive simulation status."""
        return {
            'running': self.running,
            'paused': self.paused,
            'simulation_time': self.simulation_time,
            'total_vehicles': len(self.child_drones) + 2,  # children + parent + rover
            'gps_denied_areas': len(self.gps_denied_areas),
            'rover_status': self.rover.get_status_dict() if self.rover else None,
            'parent_drone_status': self.parent_drone.get_status_dict() if self.parent_drone else None,
            'operational_child_drones': sum(1 for d in self.child_drones if d.gps_available and not d.jammed),
            'jammed_child_drones': sum(1 for d in self.child_drones if d.jammed),
        }
    
    def set_rover_target(self, target_position: Tuple[float, float]):
        """Set a new target position for the rover."""
        if self.rover:
            # Add target to rover's survey plan
            current_waypoints = [wp.position for wp in self.rover.survey_waypoints]
            current_waypoints.append(target_position)
            self.rover.load_survey_plan(current_waypoints)
            print(f"Added target position {target_position} to rover survey plan")
    
    def get_rover_trajectory(self):
        """Get rover's planned trajectory for visualization."""
        if not self.rover or not self.rover.survey_waypoints:
            return []
        
        trajectory = [wp.position for wp in self.rover.survey_waypoints]
        return trajectory
    
    def emergency_stop_rover(self):
        """Emergency stop for the rover."""
        if self.rover:
            self.rover.stop_survey()
            print("Emergency stop activated for rover")
    
    def resume_rover_survey(self):
        """Resume rover survey operations."""
        if self.rover and not self.rover.survey_active:
            self.rover.start_survey()
            print("Rover survey resumed")
    
    def get_drone_telemetry(self):
        """Get telemetry data from all drones."""
        telemetry = {}
        
        if self.parent_drone:
            telemetry['parent'] = self.parent_drone.get_status_dict()
        
        telemetry['children'] = {}
        for drone in self.child_drones:
            telemetry['children'][drone.drone_id] = drone.get_status_dict()
        
        return telemetry
    
    def force_drone_repositioning(self, drone_id: str, target_position: Tuple[float, float]):
        """Force a specific drone to move to a target position."""
        for drone in self.child_drones:
            if drone.drone_id == drone_id:
                command = {
                    'type': 'move_to_position',
                    'target_position': target_position
                }
                drone.receive_command_from_parent(command)
                print(f"Forced repositioning of {drone_id} to {target_position}")
                return True
        return False
    
    def calibrate_all_distance_sensors(self):
        """Calibrate distance sensors on all child drones."""
        for drone in self.child_drones:
            command = {
                'type': 'calibrate_distance_sensor'
            }
            drone.receive_command_from_parent(command)
        print("Distance sensor calibration initiated for all child drones")