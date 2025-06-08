import math
import random
import numpy as np

def euclidean_distance(p1, p2):
    """Compute Euclidean distance between two points (2D or 3D)."""
    if len(p1) != len(p2):
        raise ValueError("Points must have the same dimension")
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(p1, p2)))

def calculate_circular_position(center, radius, angle, movement_scale=1.0):
    """
    Calculate position on a circular trajectory with noise.
    
    Args:
        center: Center point of the circle (x, y)
        radius: Radius of the circle
        angle: Current angle in radians
        movement_scale: Scale factor for movement noise
        
    Returns:
        Tuple of (new_x, new_y) position
    """
    # Calculate base position
    new_x = center[0] + radius * math.cos(angle)
    new_y = center[1] + radius * math.sin(angle)
    
    # Add noise
    noise_x = random.gauss(0, 0.3 * movement_scale)
    noise_y = random.gauss(0, 0.3 * movement_scale)
    
    return (new_x + noise_x, new_y + noise_y)

def calculate_velocity(prev_pos, current_pos, dt=0.1):
    """
    Calculate velocity between two positions.
    
    Args:
        prev_pos: Previous position (x, y)
        current_pos: Current position (x, y)
        dt: Time delta
        
    Returns:
        Tuple of (velocity_x, velocity_y)
    """
    vel_x = (current_pos[0] - prev_pos[0]) / dt
    vel_y = (current_pos[1] - prev_pos[1]) / dt
    return (vel_x, vel_y)

def simulate_distance_measurement(pos1, pos2, noise_std=0.1):
    """
    Simulate distance measurement with realistic noise.
    
    Args:
        pos1: First position
        pos2: Second position
        noise_std: Standard deviation of measurement noise
        
    Returns:
        Measured distance with noise
    """
    true_distance = euclidean_distance(pos1, pos2)
    noise = random.gauss(0, noise_std)
    return max(0.1, true_distance + noise)  # Ensure positive distance

def estimate_position_simple(anchors, distances):
    """
    Simple position estimation using weighted centroid.
    
    Args:
        anchors: List of anchor positions
        distances: List of distances to anchors
        
    Returns:
        Estimated position (x, y)
    """
    total_weight = 0
    weighted_x = 0
    weighted_y = 0
    
    for (anchor_x, anchor_y), distance in zip(anchors, distances):
        if distance > 0:
            weight = 1.0 / (distance + 0.1)  # Inverse distance weighting
            weighted_x += anchor_x * weight
            weighted_y += anchor_y * weight
            total_weight += weight
    
    if total_weight > 0:
        return (weighted_x / total_weight, weighted_y / total_weight)
    return anchors[0]  # Fallback to first anchor position