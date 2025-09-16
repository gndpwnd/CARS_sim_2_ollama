import math
import random
from typing import List, Tuple

import numpy as np
import utils_gps_sim as utils


class Vehicle:
    """Represents a vehicle/agent in the simulation."""

    def __init__(self, agent_id: str, position: Tuple[float, float], color: str):
        self.id = agent_id
        self.position = position
        self.previous_position = position
        self.color = color
        self.has_gps = True
        self.estimated_position = None
        self.position_error = 0.0
        self.trajectory = [position]
        self.velocity = (0.0, 0.0)

        # Movement parameters
        self.speed = 1.0
        self.trajectory_angle = random.uniform(0, 2 * math.pi)
        self.trajectory_center = (50, 50)
        self.trajectory_radius = 30

    def update_position(self, bounds: Tuple[float, float, float, float]):
        """Update vehicle position with circular movement pattern."""
        self.previous_position = self.position

        # Generate circular trajectory with some randomness
        new_pos, self.trajectory_angle = utils.generate_circular_trajectory(
            self.trajectory_center,
            self.trajectory_radius,
            self.trajectory_angle,
            angular_speed=0.02 + random.uniform(-0.01, 0.01),
        )

        # Add some random noise to make movement more realistic
        noise_x = random.gauss(0, 0.3)
        noise_y = random.gauss(0, 0.3)
        new_pos = (new_pos[0] + noise_x, new_pos[1] + noise_y)

        # Keep within bounds
        self.position = utils.bound_position(new_pos, bounds)

        # Calculate velocity
        dt = 0.1  # Simulation time step
        self.velocity = utils.estimate_velocity(
            self.previous_position, self.position, dt
        )

        # Store trajectory
        self.trajectory.append(self.position)
        if len(self.trajectory) > 500:  # Limit trajectory length
            self.trajectory.pop(0)

    def lose_gps(self):
        """Simulate losing GPS signal."""
        self.has_gps = False
        self.estimated_position = None
        self.position_error = float("inf")

    def regain_gps(self):
        """Simulate regaining GPS signal."""
        self.has_gps = True
        self.estimated_position = None
        self.position_error = 0.0

    def estimate_position_via_trilateration(self, anchor_vehicles: List["Vehicle"]):
        """Estimate position using trilateration from anchor vehicles."""
        if len(anchor_vehicles) < 3:
            self.estimated_position = None
            self.position_error = float("inf")
            return

        # Get positions and distances from anchors
        anchors = []
        distances = []

        for anchor in anchor_vehicles:
            if anchor.has_gps and anchor.id != self.id:
                anchors.append(anchor.position)
                # Simulate distance measurement with noise
                measured_distance = utils.simulate_distance_measurement(
                    self.position, anchor.position, noise_std=0.2
                )
                distances.append(measured_distance)

        if len(anchors) >= 3:
            try:
                # Use multilateration for robust estimation
                self.estimated_position = utils.multilaterate_2d(anchors, distances)
                self.position_error = utils.calculate_position_error(
                    self.position, self.estimated_position
                )
            except (ValueError, np.linalg.LinAlgError):
                self.estimated_position = None
                self.position_error = float("inf")
        else:
            self.estimated_position = None
            self.position_error = float("inf")