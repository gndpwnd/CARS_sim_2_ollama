# constraints_mlat.py

"""
Multilateration constraints and geometric validation functions.
Based on the mathematical foundations described in multilateration.md
"""

import numpy as np
from typing import List, Tuple, Optional
import math

# ==============================================================================
# MULTILATERATION CONSTRAINTS
# ==============================================================================

# Dimension Configuration
DIMENSION_2D = True  # Set to True for 2D mode, False for 3D mode
DIMENSION_3D = not DIMENSION_2D

# Minimum anchor points required for each dimension
MIN_ANCHORS_2D = 3  # Minimum of 3 known locations for 2D positioning
MIN_ANCHORS_3D = 4  # Minimum of 4 known locations for 3D positioning

# Distance and positioning constraints
MULTILATERATION_TOLERANCE = 0.01  # Tolerance for intersection calculations (meters)
MAX_POSITION_ERROR = 0.5  # Maximum acceptable positioning error (meters)
MIN_DISTANCE_SEPARATION = 0.1  # Minimum distance difference between anchors to target (meters)

# Geometric constraints for 2D
MIN_TRIANGLE_AREA = 0.5  # Minimum triangle area to avoid collinearity (square meters)
MIN_ANGLE_SEPARATION_2D = 15.0  # Minimum angle separation between anchors (degrees)
MAX_COLLINEARITY_THRESHOLD = 0.1  # Maximum deviation from straight line for collinearity check

# Geometric constraints for 3D
MIN_TETRAHEDRON_VOLUME = 1.0  # Minimum tetrahedron volume to avoid coplanarity (cubic meters)
MIN_ANGLE_SEPARATION_3D = 10.0  # Minimum angle separation between anchors (degrees)
MAX_COPLANARITY_THRESHOLD = 0.1  # Maximum deviation from plane for coplanarity check

# Geometric Dilution of Precision (GDOP) constraints
GEOMETRIC_DILUTION_THRESHOLD = 10.0  # Maximum acceptable GDOP value
OPTIMAL_GDOP_THRESHOLD = 3.0  # Optimal GDOP threshold for good geometry

# Physical constraints for drone swarm applications
MIN_DRONE_SEPARATION = 1.5  # Minimum distance between drones (meters)
MAX_DRONE_RANGE = 100.0  # Maximum communication/measurement range (meters)
MIN_DRONE_ALTITUDE = 0.5  # Minimum drone altitude above ground (meters)
MAX_DRONE_ALTITUDE = 50.0  # Maximum drone altitude (meters)

# Signal processing constraints
SPEED_OF_SOUND = 343.0  # Speed of sound at 20°C (m/s)
MAX_SIGNAL_DELAY = 0.5  # Maximum acceptable signal delay (seconds)
MIN_SIGNAL_STRENGTH = -80.0  # Minimum signal strength (dBm)

# Convergence and optimization parameters
MAX_ITERATIONS = 100  # Maximum iterations for iterative solvers
CONVERGENCE_THRESHOLD = 1e-6  # Convergence threshold for optimization
LEAST_SQUARES_REGULARIZATION = 1e-6  # Regularization parameter for least squares

# ==============================================================================
# GEOMETRIC VALIDATION FUNCTIONS
# ==============================================================================

class GeometricConstraints:
    """Geometric constraint validation for multilateration."""
    
    @staticmethod
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
                    area = GeometricConstraints.calculate_triangle_area(
                        positions[i], positions[j], positions[k]
                    )
                    if area < MIN_TRIANGLE_AREA:
                        return True
        
        return False
    
    @staticmethod
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
                        volume = GeometricConstraints.calculate_tetrahedron_volume(
                            positions[i], positions[j], positions[k], positions[l]
                        )
                        if volume < MIN_TETRAHEDRON_VOLUME:
                            return True
        
        return False
    
    @staticmethod
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
    
    @staticmethod
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
    
    @staticmethod
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
                distance = np.linalg.norm(np.array(target_position) - np.array(anchor_pos))
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
    
    @staticmethod
    def validate_anchor_separation(anchor_positions: List[Tuple[float, ...]]) -> bool:
        """
        Validate that anchors are sufficiently separated.
        
        Args:
            anchor_positions: List of anchor positions
            
        Returns:
            True if anchors are properly separated, False otherwise
        """
        for i in range(len(anchor_positions)):
            for j in range(i + 1, len(anchor_positions)):
                distance = np.linalg.norm(
                    np.array(anchor_positions[i]) - np.array(anchor_positions[j])
                )
                if distance < MIN_DRONE_SEPARATION:
                    return False
        
        return True
    
    @staticmethod
    def validate_distance_separation(distances: List[float]) -> bool:
        """
        Validate that distance measurements are sufficiently different.
        
        Args:
            distances: List of measured distances
            
        Returns:
            True if distances are properly separated, False otherwise
        """
        for i in range(len(distances)):
            for j in range(i + 1, len(distances)):
                if abs(distances[i] - distances[j]) < MIN_DISTANCE_SEPARATION:
                    return False
        
        return True
    
    @staticmethod
    def validate_signal_constraints(distances: List[float], 
                                  signal_strengths: Optional[List[float]] = None) -> bool:
        """
        Validate signal-related constraints.
        
        Args:
            distances: List of measured distances
            signal_strengths: Optional list of signal strengths
            
        Returns:
            True if signal constraints are satisfied, False otherwise
        """
        # Check maximum range constraint
        for distance in distances:
            if distance > MAX_DRONE_RANGE:
                return False
        
        # Check signal strength if provided
        if signal_strengths:
            for strength in signal_strengths:
                if strength < MIN_SIGNAL_STRENGTH:
                    return False
        
        return True
    
    @staticmethod
    def calculate_optimal_anchor_positions_2d(center: Tuple[float, float],
                                            radius: float,
                                            num_anchors: int) -> List[Tuple[float, float]]:
        """
        Calculate optimal anchor positions for 2D multilateration.
        
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
    
    @staticmethod
    def calculate_optimal_anchor_positions_3d(center: Tuple[float, float, float],
                                            radius: float,
                                            num_anchors: int) -> List[Tuple[float, float, float]]:
        """
        Calculate optimal anchor positions for 3D multilateration.
        Uses spherical distribution for optimal geometry.
        
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
# VALIDATION FUNCTIONS
# ==============================================================================

def validate_multilateration_input(anchor_positions: List[Tuple[float, ...]],
                                 distances: List[float],
                                 dimension: str = "auto") -> Tuple[bool, str]:
    """
    Comprehensive validation of multilateration input parameters.
    
    Args:
        anchor_positions: List of anchor positions
        distances: List of measured distances
        dimension: "2d", "3d", or "auto" to determine from positions
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not anchor_positions or not distances:
        return False, "Empty anchor positions or distances"
    
    if len(anchor_positions) != len(distances):
        return False, "Mismatch between number of anchors and distances"
    
    # Determine dimension
    if dimension == "auto":
        if len(anchor_positions[0]) == 2:
            dimension = "2d"
        elif len(anchor_positions[0]) == 3:
            dimension = "3d"
        else:
            return False, "Invalid position dimension"
    
    # Check minimum anchors
    min_anchors = MIN_ANCHORS_2D if dimension == "2d" else MIN_ANCHORS_3D
    if len(anchor_positions) < min_anchors:
        return False, f"Insufficient anchors: need at least {min_anchors} for {dimension.upper()}"
    
    # Validate geometric constraints
    constraints = GeometricConstraints()
    
    if dimension == "2d":
        if constraints.check_collinearity_2d(anchor_positions):
            return False, "Anchor positions are collinear (bad geometry)"
    else:
        if constraints.check_coplanarity_3d(anchor_positions):
            return False, "Anchor positions are coplanar (bad geometry)"
    
    # Validate anchor separation
    if not constraints.validate_anchor_separation(anchor_positions):
        return False, f"Anchors too close together (minimum {MIN_DRONE_SEPARATION}m)"
    
    # Validate distance separation
    if not constraints.validate_distance_separation(distances):
        return False, f"Distance measurements too similar (minimum {MIN_DISTANCE_SEPARATION}m difference)"
    
    # Validate signal constraints
    if not constraints.validate_signal_constraints(distances):
        return False, f"Signal constraints violated (max range {MAX_DRONE_RANGE}m)"
    
    return True, "Input validation passed"

def get_dimension_config() -> dict:
    """
    Get current dimension configuration.
    
    Returns:
        Dictionary with dimension settings
    """
    return {
        "dimension_2d": DIMENSION_2D,
        "dimension_3d": DIMENSION_3D,
        "min_anchors_2d": MIN_ANCHORS_2D,
        "min_anchors_3d": MIN_ANCHORS_3D,
        "current_mode": "2D" if DIMENSION_2D else "3D"
    }

def set_dimension_mode(use_3d: bool) -> None:
    """
    Set the dimension mode for multilateration.
    
    Args:
        use_3d: True for 3D mode, False for 2D mode
    """
    global DIMENSION_2D, DIMENSION_3D
    DIMENSION_3D = use_3d
    DIMENSION_2D = not use_3d