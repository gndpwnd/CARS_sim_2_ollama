"""
Vehicle Class for GPS Localization Simulation

This module contains the Vehicle class that represents agents/vehicles in the
GPS localization simulation with trilateration capabilities.
"""

import math
import random
from typing import List, Tuple
import numpy as np
import occlusion_utils as utils

class Vehicle:
    """Represents a vehicle/agent in the GPS localization simulation."""

    def __init__(self, agent_id: str, position: Tuple[float, float], color: str, is_anchor=False):
        """
        Initialize a vehicle with given parameters.
        
        Args:
            agent_id: Unique identifier for the vehicle
            position: Initial position (x, y)
            color: Color for visualization
            is_anchor: Whether this vehicle serves as an anchor point
        """
        self.id = agent_id
        self.position = position
        self.previous_position = position
        self.is_anchor = is_anchor
        self.color = color
        
        # GPS and positioning
        self.has_gps = True
        self.estimated_position = None
        self.position_error = 0.0
        self.occlusion_info = None  # Store occlusion detection results
        
        # Movement tracking
        self.trajectory = [position]
        self.velocity = (0.0, 0.0)

        # Movement parameters
        self.speed = 1.0
        self.trajectory_angle = random.uniform(0, 2 * math.pi)
        self.trajectory_center = (50, 50)
        self.trajectory_radius = 30

    def update_position(self, bounds: Tuple[float, float, float, float], movement_scale=1.0):
        """
        Update vehicle position with circular movement pattern.
        
        Args:
            bounds: Boundary limits (min_x, max_x, min_y, max_y)
            movement_scale: Scale factor for movement speed (default: 1.0)
        """
        self.previous_position = self.position

        # Generate circular trajectory with some randomness
        angular_speed = (0.02 + random.uniform(-0.01, 0.01)) * movement_scale
        
        # Update trajectory angle
        self.trajectory_angle += angular_speed
        
        # Calculate new position using utility function
        new_pos = utils.calculate_circular_position(
            self.trajectory_center,
            self.trajectory_radius,
            self.trajectory_angle,
            movement_scale
        )

        # Keep within bounds
        min_x, max_x, min_y, max_y = bounds
        new_x = max(min_x + 2, min(max_x - 2, new_pos[0]))
        new_y = max(min_y + 2, min(max_y - 2, new_pos[1]))
        self.position = (new_x, new_y)

        # Calculate velocity using utility function
        self.velocity = utils.calculate_velocity(self.previous_position, self.position)

        # Store trajectory
        self.trajectory.append(self.position)
        if len(self.trajectory) > 500:  # Limit trajectory length
            self.trajectory.pop(0)

    def lose_gps(self):
        """Simulate losing GPS signal."""
        self.has_gps = False
        self.estimated_position = None
        self.position_error = float("inf")
        self.occlusion_info = None

    def regain_gps(self):
        """Simulate regaining GPS signal."""
        self.has_gps = True
        self.estimated_position = None
        self.position_error = 0.0
        self.occlusion_info = None

    def estimate_position_via_trilateration(self, anchor_vehicles: List["Vehicle"], 
                                          occlusion_detector=None):
        """
        Estimate position using trilateration from anchor vehicles with occlusion detection.
        
        Args:
            anchor_vehicles: List of vehicles with GPS that can serve as anchors
            occlusion_detector: OcclusionDetector instance for checking signal integrity
        """
        if len(anchor_vehicles) < 3:
            self.estimated_position = None
            self.position_error = float("inf")
            self.occlusion_info = None
            return

        # Get positions and distances from anchors
        anchors = []
        distances = []
        valid_anchors = []

        for anchor in anchor_vehicles:
            if anchor.has_gps and anchor.id != self.id:
                anchors.append(anchor.position)
                distances.append(utils.simulate_distance_measurement(
                    self.position, anchor.position, noise_std=0.2
                ))
                valid_anchors.append(anchor)

        if len(anchors) >= 3:
            try:
                # Check for occlusion if detector is provided
                if occlusion_detector is not None:
                    self.occlusion_info = occlusion_detector.check_occlusion(anchors, distances)
                    
                    # If significant occlusion is detected, flag the estimate as unreliable
                    if (self.occlusion_info['is_occluded'] and 
                        self.occlusion_info['confidence_score'] < 0.5):
                        self.estimated_position = None
                        self.position_error = float("inf")
                        return
                    
                    # Filter out occluded anchors for better estimation
                    if self.occlusion_info['occluded_anchors']:
                        filtered_anchors = []
                        filtered_distances = []
                        for i, (anchor, distance) in enumerate(zip(anchors, distances)):
                            if i not in self.occlusion_info['occluded_anchors']:
                                filtered_anchors.append(anchor)
                                filtered_distances.append(distance)
                        
                        # Check if we still have enough anchors after filtering
                        if len(filtered_anchors) >= 3:
                            anchors = filtered_anchors
                            distances = filtered_distances

                # Use utility function for position estimation
                self.estimated_position = utils.estimate_position_simple(anchors, distances)
                self.position_error = utils.euclidean_distance(
                    self.position, self.estimated_position
                ) if self.estimated_position else float("inf")
                
            except (ValueError, np.linalg.LinAlgError):
                self.estimated_position = None
                self.position_error = float("inf")
                self.occlusion_info = None
        else:
            self.estimated_position = None
            self.position_error = float("inf")
            self.occlusion_info = None

    def get_anchor_distances(self, anchor_vehicles: List["Vehicle"]) -> Tuple[List[Tuple[float, float]], List[float]]:
        """
        Get current distances to anchor vehicles for occlusion analysis.
        
        Args:
            anchor_vehicles: List of vehicles with GPS
            
        Returns:
            Tuple of (anchor_positions, distances)
        """
        anchors = []
        distances = []

        for anchor in anchor_vehicles:
            if anchor.has_gps and anchor.id != self.id:
                anchors.append(anchor.position)
                distances.append(utils.simulate_distance_measurement(
                    self.position, anchor.position, noise_std=0.2
                ))

        return anchors, distances

    def reset_to_position(self, position: Tuple[float, float]):
        """
        Reset vehicle to a specific position.
        
        Args:
            position: New position (x, y)
        """
        self.position = position
        self.previous_position = position
        self.trajectory = [position]
        self.has_gps = True
        self.estimated_position = None
        self.position_error = 0.0
        self.occlusion_info = None
        self.trajectory_angle = random.uniform(0, 2 * math.pi)

    def get_status_summary(self) -> dict:
        """
        Get a summary of the vehicle's current status.
        
        Returns:
            Dictionary containing vehicle status information
        """
        return {
            'id': self.id,
            'position': self.position,
            'has_gps': self.has_gps,
            'estimated_position': self.estimated_position,
            'position_error': self.position_error,
            'velocity': self.velocity,
            'occlusion_detected': self.occlusion_info is not None and self.occlusion_info.get('is_occluded', False),
            'occluded_anchors': list(self.occlusion_info.get('occluded_anchors', [])) if self.occlusion_info else [],
            'occlusion_confidence': self.occlusion_info.get('confidence_score', 1.0) if self.occlusion_info else 1.0
        }

    def __str__(self) -> str:
        """String representation of the vehicle."""
        return f"Vehicle({self.id}, pos={self.position}, gps={self.has_gps}, error={self.position_error:.2f})"

    def __repr__(self) -> str:
        """Detailed string representation of the vehicle."""
        return (f"Vehicle(id='{self.id}', position={self.position}, color='{self.color}', "
                f"has_gps={self.has_gps}, estimated_pos={self.estimated_position}, "
                f"error={self.position_error:.3f})")