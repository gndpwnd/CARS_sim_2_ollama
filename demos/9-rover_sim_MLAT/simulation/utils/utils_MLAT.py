# utils_MLAT.py

"""
Mathematical utility functions for multilateration calculations.
Centralizes all geometric computations, intersection algorithms, and optimization routines.
"""

import numpy as np
import math
from typing import List, Tuple, Optional, Union
from scipy.optimize import least_squares
from constraints_MLAT import (
    MULTILATERATION_TOLERANCE,
    MAX_ITERATIONS,
    CONVERGENCE_THRESHOLD,
    LEAST_SQUARES_REGULARIZATION,
    MIN_TRIANGLE_AREA,
    MIN_TETRAHEDRON_VOLUME
)

# ==============================================================================
# BASIC MATHEMATICAL UTILITIES
# ==============================================================================

def euclidean_distance(point1: Union[Tuple[float, ...], np.ndarray], 
                      point2: Union[Tuple[float, ...], np.ndarray]) -> float:
    """
    Calculate Euclidean distance between two points.
    
    Args:
        point1: First point coordinates
        point2: Second point coordinates
        
    Returns:
        Euclidean distance between points
    """
    if isinstance(point1, tuple):
        point1 = np.array(point1)
    if isinstance(point2, tuple):
        point2 = np.array(point2)
    return np.linalg.norm(point1 - point2)


def calculate_centroid(positions: List[Tuple[float, ...]]) -> Tuple[float, ...]:
    """
    Calculate the centroid (geometric center) of a set of points.
    
    Args:
        positions: List of point coordinates
        
    Returns:
        Centroid coordinates
    """
    if not positions:
        return tuple()
    
    dimensions = len(positions[0])
    centroid = tuple(
        sum(pos[i] for pos in positions) / len(positions)
        for i in range(dimensions)
    )
    return centroid


def calculate_rms_error(errors: List[float]) -> float:
    """
    Calculate Root Mean Square (RMS) error.
    
    Args:
        errors: List of error values
        
    Returns:
        RMS error value
    """
    if not errors:
        return 0.0
    return math.sqrt(sum(e**2 for e in errors) / len(errors))


# ==============================================================================
# 2D GEOMETRIC CALCULATIONS
# ==============================================================================

def calculate_triangle_area(p1: Tuple[float, float], 
                           p2: Tuple[float, float], 
                           p3: Tuple[float, float]) -> float:
    """
    Calculate the area of a triangle formed by three 2D points.
    
    Args:
        p1, p2, p3: Triangle vertices (x, y)
        
    Returns:
        Area of the triangle
    """
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    
    area = abs((x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2)) / 2.0)
    return area


def check_collinearity_2d(positions: List[Tuple[float, float]]) -> bool:
    """
    Check if three or more 2D points are collinear.
    
    Args:
        positions: List of 2D positions (x, y)
        
    Returns:
        True if points are collinear (bad geometry), False otherwise
    """
    if len(positions) < 3:
        return False
    
    # Check all combinations of three points
    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            for k in range(j + 1, len(positions)):
                area = calculate_triangle_area(positions[i], positions[j], positions[k])
                if area < MIN_TRIANGLE_AREA:
                    return True
    
    return False


def circle_circle_intersection(center1: Tuple[float, float], 
                              radius1: float,
                              center2: Tuple[float, float], 
                              radius2: float) -> List[Tuple[float, float]]:
    """
    Calculate intersection points between two circles.
    
    Args:
        center1: Center of first circle (x, y)
        radius1: Radius of first circle
        center2: Center of second circle (x, y)
        radius2: Radius of second circle
        
    Returns:
        List of intersection points (0, 1, or 2 points)
    """
    x0, y0 = center1
    x1, y1 = center2
    dx, dy = x1 - x0, y1 - y0
    d = math.hypot(dx, dy)
    
    # Check intersection conditions
    if d > radius1 + radius2 or d < abs(radius1 - radius2) or d == 0:
        return []  # No intersections
    
    # Calculate intersection points
    a = (radius1**2 - radius2**2 + d**2) / (2 * d)
    h = math.sqrt(radius1**2 - a**2)
    
    # Midpoint between intersections
    xm = x0 + a * dx / d
    ym = y0 + a * dy / d
    
    # Perpendicular offset
    rx = -dy * (h / d)
    ry = dx * (h / d)
    
    # Two intersection points
    p1 = (xm + rx, ym + ry)
    p2 = (xm - rx, ym - ry)
    
    return [p1, p2]


def generate_optimal_2d_positions(center: Tuple[float, float],
                                 radius: float,
                                 num_anchors: int) -> List[Tuple[float, float]]:
    """
    Generate optimal anchor positions for 2D multilateration using circular distribution.
    
    Args:
        center: Center point for anchor distribution
        radius: Radius for circular distribution
        num_anchors: Number of anchors to position
        
    Returns:
        List of optimal anchor positions
    """
    positions = []
    angle_step = 2 * math.pi / num_anchors
    
    for i in range(num_anchors):
        angle = i * angle_step
        x = center[0] + radius * math.cos(angle)
        y = center[1] + radius * math.sin(angle)
        positions.append((x, y))
    
    return positions


# ==============================================================================
# 3D GEOMETRIC CALCULATIONS
# ==============================================================================

def calculate_tetrahedron_volume(p1: Tuple[float, float, float],
                                p2: Tuple[float, float, float],
                                p3: Tuple[float, float, float],
                                p4: Tuple[float, float, float]) -> float:
    """
    Calculate the volume of a tetrahedron formed by four 3D points.
    
    Args:
        p1, p2, p3, p4: Tetrahedron vertices (x, y, z)
        
    Returns:
        Volume of the tetrahedron
    """
    # Convert to numpy arrays for easier calculation
    p1 = np.array(p1)
    p2 = np.array(p2)
    p3 = np.array(p3)
    p4 = np.array(p4)
    
    # Calculate vectors from p1 to other points
    v1 = p2 - p1
    v2 = p3 - p1
    v3 = p4 - p1
    
    # Volume = |det(v1, v2, v3)| / 6
    matrix = np.column_stack([v1, v2, v3])
    volume = abs(np.linalg.det(matrix)) / 6.0
    
    return volume


def check_coplanarity_3d(positions: List[Tuple[float, float, float]]) -> bool:
    """
    Check if four or more 3D points are coplanar.
    
    Args:
        positions: List of 3D positions (x, y, z)
        
    Returns:
        True if points are coplanar (bad geometry), False otherwise
    """
    if len(positions) < 4:
        return False
    
    # Check all combinations of four points
    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            for k in range(j + 1, len(positions)):
                for l in range(k + 1, len(positions)):
                    volume = calculate_tetrahedron_volume(
                        positions[i], positions[j], positions[k], positions[l]
                    )
                    if volume < MIN_TETRAHEDRON_VOLUME:
                        return True
    
    return False


def sphere_sphere_intersection(center1: Tuple[float, float, float], 
                              radius1: float,
                              center2: Tuple[float, float, float], 
                              radius2: float) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], float, float]:
    """
    Calculate intersection circle between two spheres.
    
    Args:
        center1: Center of first sphere (x, y, z)
        radius1: Radius of first sphere
        center2: Center of second sphere (x, y, z)
        radius2: Radius of second sphere
        
    Returns:
        Tuple of (circle_center, normal_vector, circle_radius, sphere_distance)
    """
    center1 = np.array(center1)
    center2 = np.array(center2)
    d = np.linalg.norm(center2 - center1)
    
    # Check intersection conditions
    if d > radius1 + radius2 or d < abs(radius1 - radius2) or d == 0:
        return None, None, 0, 0
    
    # Calculate intersection circle parameters
    a = (radius1**2 - radius2**2 + d**2) / (2 * d)
    h = math.sqrt(radius1**2 - a**2)
    
    # Circle center and normal vector
    circle_center = center1 + a * (center2 - center1) / d
    normal = (center2 - center1) / d
    
    return circle_center, normal, h, d


def generate_optimal_3d_positions(center: Tuple[float, float, float],
                                 radius: float,
                                 num_anchors: int) -> List[Tuple[float, float, float]]:
    """
    Generate optimal anchor positions for 3D multilateration using spherical distribution.
    Uses golden spiral algorithm for optimal sphere distribution.
    
    Args:
        center: Center point for anchor distribution
        radius: Radius for spherical distribution
        num_anchors: Number of anchors to position
        
    Returns:
        List of optimal anchor positions
    """
    positions = []
    
    # Use golden spiral for optimal sphere distribution
    golden_ratio = (1 + math.sqrt(5)) / 2
    
    for i in range(num_anchors):
        # Golden spiral algorithm
        theta = 2 * math.pi * i / golden_ratio
        phi = math.acos(1 - 2 * i / num_anchors)
        
        x = center[0] + radius * math.sin(phi) * math.cos(theta)
        y = center[1] + radius * math.sin(phi) * math.sin(theta)
        z = center[2] + radius * math.cos(phi)
        
        positions.append((x, y, z))
    
    return positions


# ==============================================================================
# GEOMETRIC DILUTION OF PRECISION (GDOP) CALCULATIONS
# ==============================================================================

def calculate_geometric_dilution(anchor_positions: List[Tuple[float, ...]],
                                target_position: Tuple[float, ...]) -> float:
    """
    Calculate Geometric Dilution of Precision (GDOP).
    
    Args:
        anchor_positions: List of anchor positions
        target_position: Target position for GDOP calculation
        
    Returns:
        GDOP value (lower is better)
    """
    n = len(anchor_positions)
    dim = len(target_position)
    
    if n < dim + 1:
        return float('inf')
    
    try:
        # Build geometry matrix
        G = np.zeros((n, dim))
        
        for i, anchor_pos in enumerate(anchor_positions):
            distance = euclidean_distance(target_position, anchor_pos)
            if distance == 0:
                return float('inf')
            
            for j in range(dim):
                G[i, j] = (target_position[j] - anchor_pos[j]) / distance
        
        # Calculate GDOP = sqrt(trace((G^T * G)^-1))
        GTG = np.dot(G.T, G)
        GTG_inv = np.linalg.inv(GTG + LEAST_SQUARES_REGULARIZATION * np.eye(dim))
        gdop = np.sqrt(np.trace(GTG_inv))
        
        return gdop
    
    except (np.linalg.LinAlgError, ZeroDivisionError):
        return float('inf')


# ==============================================================================
# MULTILATERATION SOLVERS
# ==============================================================================

def solve_2d_geometric_intersection(positions: List[Tuple[float, float]], 
                                   distances: List[float]) -> Optional[Tuple[float, float]]:
    """
    Solve 2D multilateration using geometric circle intersection method.
    
    Args:
        positions: List of 2D anchor positions
        distances: List of distances from anchors to target
        
    Returns:
        Estimated target position or None if no solution found
    """
    intersections = []
    
    # Generate all pairwise circle intersections
    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            points = circle_circle_intersection(
                positions[i], distances[i],
                positions[j], distances[j]
            )
            intersections.extend(points)
    
    if not intersections:
        return None
    
    # Find point with maximum circle intersections
    best_point = None
    max_count = 0
    
    for point in intersections:
        count = sum(
            abs(euclidean_distance(point, positions[k]) - distances[k]) 
            <= MULTILATERATION_TOLERANCE
            for k in range(len(positions))
        )
        if count > max_count:
            max_count = count
            best_point = point
    
    if best_point is not None and max_count >= 3:
        return best_point
    else:
        return None


def solve_3d_geometric_intersection(positions: List[Tuple[float, float, float]], 
                                   distances: List[float]) -> Optional[Tuple[float, float, float]]:
    """
    Solve 3D multilateration using geometric sphere intersection method.
    
    Args:
        positions: List of 3D anchor positions
        distances: List of distances from anchors to target
        
    Returns:
        Estimated target position or None if no solution found
    """
    # Generate sphere-sphere intersection circles
    intersection_planes = []
    
    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            circle_center, normal, radius, d = sphere_sphere_intersection(
                positions[i], distances[i],
                positions[j], distances[j]
            )
            if circle_center is not None:
                intersection_planes.append((circle_center, normal, radius))
    
    if len(intersection_planes) < 3:
        return None
    
    # Solve system of plane equations
    return solve_plane_intersection_system(intersection_planes)


def solve_plane_intersection_system(intersection_planes: List[Tuple[np.ndarray, np.ndarray, float]]) -> Optional[Tuple[float, float, float]]:
    """
    Solve system of plane equations from sphere intersections.
    
    Args:
        intersection_planes: List of (circle_center, normal_vector, radius) tuples
        
    Returns:
        Intersection point or None if no solution
    """
    A = []
    b = []
    
    for circle_center, normal, radius in intersection_planes:
        # Plane equation: normal · (x - circle_center) = 0
        # Rearranged: normal · x = normal · circle_center
        A.append(normal.tolist())
        b.append(np.dot(normal, circle_center))
    
    if len(A) < 3:
        return None
    
    try:
        A_np = np.array(A)
        b_np = np.array(b)
        
        # Solve using least squares: x = (A^T A)^-1 A^T b
        ATA = np.dot(A_np.T, A_np)
        ATb = np.dot(A_np.T, b_np)
        
        # Add regularization for numerical stability
        ATA += LEAST_SQUARES_REGULARIZATION * np.eye(ATA.shape[0])
        
        result = np.linalg.solve(ATA, ATb)
        return tuple(result)
        
    except np.linalg.LinAlgError:
        return None


def solve_least_squares_optimization(positions: List[Tuple[float, ...]], 
                                    distances: List[float]) -> Optional[Tuple[float, ...]]:
    """
    Solve multilateration using least squares optimization.
    
    Args:
        positions: List of anchor positions
        distances: List of distances from anchors to target
        
    Returns:
        Estimated target position or None if optimization fails
    """
    # Initial guess: centroid of anchor positions
    initial_guess = calculate_centroid(positions)
    
    # Define objective function
    def objective(point):
        return [
            euclidean_distance(point, positions[i]) - distances[i]
            for i in range(len(positions))
        ]
    
    # Solve using least squares
    try:
        result = least_squares(
            objective,
            initial_guess,
            method='lm',
            max_nfev=MAX_ITERATIONS,
            ftol=CONVERGENCE_THRESHOLD,
            xtol=CONVERGENCE_THRESHOLD
        )
        
        if result.success:
            return tuple(result.x)
        else:
            return None
            
    except Exception:
        return None


# ==============================================================================
# ERROR CALCULATION UTILITIES
# ==============================================================================

def calculate_positioning_error(positions: List[Tuple[float, ...]], 
                               distances: List[float], 
                               estimated_pos: Tuple[float, ...]) -> float:
    """
    Calculate RMS positioning error for multilateration result.
    
    Args:
        positions: List of anchor positions
        distances: List of measured distances
        estimated_pos: Estimated target position
        
    Returns:
        RMS positioning error
    """
    errors = []
    for i, (pos, dist) in enumerate(zip(positions, distances)):
        calculated_dist = euclidean_distance(estimated_pos, pos)
        error = abs(calculated_dist - dist)
        errors.append(error)
    
    return calculate_rms_error(errors)


def calculate_residuals(positions: List[Tuple[float, ...]], 
                       distances: List[float], 
                       estimated_pos: Tuple[float, ...]) -> List[float]:
    """
    Calculate residuals for each anchor-target distance.
    
    Args:
        positions: List of anchor positions
        distances: List of measured distances
        estimated_pos: Estimated target position
        
    Returns:
        List of residual errors for each anchor
    """
    residuals = []
    for i, (pos, dist) in enumerate(zip(positions, distances)):
        calculated_dist = euclidean_distance(estimated_pos, pos)
        residual = calculated_dist - dist
        residuals.append(residual)
    
    return residuals


# ==============================================================================
# VALIDATION UTILITIES
# ==============================================================================

def validate_anchor_separation(anchor_positions: List[Tuple[float, ...]], 
                              min_separation: float) -> bool:
    """
    Validate that anchors are sufficiently separated.
    
    Args:
        anchor_positions: List of anchor positions
        min_separation: Minimum required separation distance
        
    Returns:
        True if anchors are properly separated, False otherwise
    """
    for i in range(len(anchor_positions)):
        for j in range(i + 1, len(anchor_positions)):
            distance = euclidean_distance(anchor_positions[i], anchor_positions[j])
            if distance < min_separation:
                return False
    
    return True


def validate_distance_separation(distances: List[float], 
                                min_separation: float) -> bool:
    """
    Validate that distance measurements are sufficiently different.
    
    Args:
        distances: List of measured distances
        min_separation: Minimum required difference between distances
        
    Returns:
        True if distances are properly separated, False otherwise
    """
    for i in range(len(distances)):
        for j in range(i + 1, len(distances)):
            if abs(distances[i] - distances[j]) < min_separation:
                return False
    
    return True


def check_solution_validity(positions: List[Tuple[float, ...]], 
                           distances: List[float], 
                           solution: Tuple[float, ...],
                           tolerance: float = MULTILATERATION_TOLERANCE) -> bool:
    """
    Check if a multilateration solution is valid within tolerance.
    
    Args:
        positions: List of anchor positions
        distances: List of measured distances
        solution: Proposed solution position
        tolerance: Acceptable error tolerance
        
    Returns:
        True if solution is valid, False otherwise
    """
    for i, (pos, expected_dist) in enumerate(zip(positions, distances)):
        calculated_dist = euclidean_distance(solution, pos)
        if abs(calculated_dist - expected_dist) > tolerance:
            return False
    
    return True


# ==============================================================================
# COORDINATE TRANSFORMATION UTILITIES
# ==============================================================================

def transform_to_local_coordinates(positions: List[Tuple[float, ...]], 
                                  origin: Tuple[float, ...]) -> List[Tuple[float, ...]]:
    """
    Transform positions to local coordinate system with given origin.
    
    Args:
        positions: List of positions to transform
        origin: New origin point
        
    Returns:
        List of transformed positions
    """
    transformed = []
    for pos in positions:
        local_pos = tuple(pos[i] - origin[i] for i in range(len(pos)))
        transformed.append(local_pos)
    
    return transformed


def rotate_2d_coordinates(positions: List[Tuple[float, float]], 
                         angle: float) -> List[Tuple[float, float]]:
    """
    Rotate 2D coordinates by given angle (in radians).
    
    Args:
        positions: List of 2D positions to rotate
        angle: Rotation angle in radians
        
    Returns:
        List of rotated positions
    """
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    
    rotated = []
    for x, y in positions:
        new_x = x * cos_a - y * sin_a
        new_y = x * sin_a + y * cos_a
        rotated.append((new_x, new_y))
    
    return rotated


def scale_coordinates(positions: List[Tuple[float, ...]], 
                     scale_factor: float) -> List[Tuple[float, ...]]:
    """
    Scale coordinates by given factor.
    
    Args:
        positions: List of positions to scale
        scale_factor: Scaling factor
        
    Returns:
        List of scaled positions
    """
    scaled = []
    for pos in positions:
        scaled_pos = tuple(coord * scale_factor for coord in pos)
        scaled.append(scaled_pos)
    
    return scaled