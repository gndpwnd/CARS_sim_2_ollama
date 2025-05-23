# Newest sim_helpers.py

import numpy as np
import math
from scipy.optimize import least_squares

def convert_numpy_coords(obj):
    """
    Recursively convert numpy data types to native Python types for JSON serialization.
    """
    if isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        return float(obj)
    elif isinstance(obj, (np.complexfloating,)):
        return complex(obj)
    elif isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (list, tuple)):
        converted = [convert_numpy_coords(item) for item in obj]
        return tuple(converted) if isinstance(obj, tuple) else converted
    elif isinstance(obj, dict):
        return {key: convert_numpy_coords(value) for key, value in obj.items()}
    return obj  # Unchanged types

def round_coord(value):
    """Round coordinates to 3 decimal places"""
    return round(value, 3)

def is_jammed(pos, jamming_center, jamming_radius):
    """Check if a position is inside the jamming zone"""
    if isinstance(pos, tuple) or isinstance(pos, list):
        pos_x, pos_y = pos[0], pos[1]
    else:  # Assume numpy array
        pos_x, pos_y = pos[0], pos[1]
    
    distance = math.sqrt((pos_x - jamming_center[0])**2 + (pos_y - jamming_center[1])**2)
    return distance <= jamming_radius

def calculate_distance(pos1, pos2):
    """Calculate Euclidean distance between two points"""
    return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)

def circle_circle_intersections(c1, r1, c2, r2):
    """Return intersection points between two circles (if they exist)"""
    x0, y0 = c1
    x1, y1 = c2
    dx, dy = x1 - x0, y1 - y0
    d = math.hypot(dx, dy)

    if d > r1 + r2 or d < abs(r1 - r2) or d == 0:
        return []  # No intersections

    a = (r1**2 - r2**2 + d**2) / (2 * d)
    h = math.sqrt(r1**2 - a**2)
    xm = x0 + a * dx / d
    ym = y0 + a * dy / d
    rx = -dy * (h / d)
    ry = dx * (h / d)

    p1 = (xm + rx, ym + ry)
    p2 = (xm - rx, ym - ry)
    return [p1, p2]

def objective_function(point, agent_positions, distances):
    """Objective function for multilateration optimization"""
    x, y = point
    return [calculate_distance((x, y), agent_positions[i]) - distances[i] for i in range(len(agent_positions))]

def localize_rover_multilateration(agent_positions, distances):
    """Localize rover using multilateration with least squares optimization"""
    if len(agent_positions) < 3:
        print("Warning: Need at least 3 agents for multilateration")
        return None
        
    # Use average position as initial guess
    x_avg = sum(pos[0] for pos in agent_positions) / len(agent_positions)
    y_avg = sum(pos[1] for pos in agent_positions) / len(agent_positions)
    initial_guess = [x_avg, y_avg]

    try:
        result = least_squares(
            objective_function,
            initial_guess,
            args=(agent_positions, distances),
            method='lm'
        )

        if result.success:
            return (round_coord(result.x[0]), round_coord(result.x[1]))
        else:
            print("Multilateration failed to converge")
            return None
    except Exception as e:
        print(f"Multilateration error: {e}")
        return None

def exact_intersection(agent_positions, distances, tolerance=1e-2):
    """
    Return the point where the most circles intersect (within tolerance).
    Falls back to multilateration if no good intersection found.
    """
    if len(agent_positions) < 3:
        return None
        
    intersections = []

    # Generate all pairwise circle intersections
    for i in range(len(agent_positions)):
        for j in range(i + 1, len(agent_positions)):
            points = circle_circle_intersections(
                agent_positions[i], distances[i],
                agent_positions[j], distances[j]
            )
            intersections.extend(points)

    if not intersections:
        print("No intersections found, falling back to multilateration.")
        return localize_rover_multilateration(agent_positions, distances)

    # Count how many circles each intersection point lies on
    best_point = None
    max_count = 0

    for point in intersections:
        count = sum(
            abs(calculate_distance(point, agent_positions[k]) - distances[k]) <= tolerance
            for k in range(len(agent_positions))
        )
        if count > max_count:
            max_count = count
            best_point = point

    if best_point is not None and max_count >= 3:
        return (round_coord(best_point[0]), round_coord(best_point[1]))
    else:
        print("Could not find a point on 3+ circles. Falling back to multilateration.")
        return localize_rover_multilateration(agent_positions, distances)