# multilateration.py

"""
Comprehensive multilateration class for 2D and 3D positioning.
Handles geometric intersection methods and constraint validation.
Uses utility functions from utils_MLAT.py for calculations.
"""

import numpy as np
from typing import List, Tuple, Optional, Dict, Union
from scipy.optimize import least_squares
from simulation.utils.constraints_MLAT import (
    validate_multilateration_input, 
    GeometricConstraints,
    get_dimension_config,
    MULTILATERATION_TOLERANCE,
    MAX_ITERATIONS,
    CONVERGENCE_THRESHOLD,
    LEAST_SQUARES_REGULARIZATION
)
from simulation.utils.utils_MLAT import (
    euclidean_distance,
    calculate_centroid,
    calculate_rms_error,
    solve_2d_geometric_intersection,
    solve_3d_geometric_intersection,
    solve_least_squares_optimization,
    calculate_geometric_dilution,
    calculate_positioning_error
)

class MultilaterationSolver:
    """
    Comprehensive multilateration solver for 2D and 3D positioning.
    Uses utility functions from utils_MLAT.py for calculations.
    """
    
    def __init__(self, dimension: str = "2d", method: str = "geometric"):
        """
        Initialize the multilateration solver.
        
        Args:
            dimension: "2d" or "3d" for positioning dimension
            method: "geometric" for intersection method, "least_squares" for optimization
        """
        self.dimension = dimension.lower()
        self.method = method.lower()
        self.constraints = GeometricConstraints()
        
        # Validate dimension
        if self.dimension not in ["2d", "3d"]:
            raise ValueError("Dimension must be '2d' or '3d'")
        
        # Validate method
        if self.method not in ["geometric", "least_squares"]:
            raise ValueError("Method must be 'geometric' or 'least_squares'")
        
        # Initialize result storage
        self.last_result = None
        self.last_error = None
        self.last_gdop = None
    
    def solve(self, 
              drone_ids: List[Union[str, int]], 
              positions: List[Tuple[float, ...]], 
              distances: List[float]) -> Optional[Tuple[float, ...]]:
        """
        Solve multilateration problem for given drone positions and distances.
        
        Args:
            drone_ids: List of drone identifiers
            positions: List of drone positions [(x, y) for 2D, (x, y, z) for 3D]
            distances: List of measured distances from each drone to target
            
        Returns:
            Estimated target position or None if solution fails
        """
        # Validate input data
        is_valid, error_msg = self._validate_input(drone_ids, positions, distances)
        if not is_valid:
            print(f"Input validation failed: {error_msg}")
            return None
        
        # Validate constraints
        constraint_valid, constraint_msg = validate_multilateration_input(
            positions, distances, self.dimension
        )
        if not constraint_valid:
            print(f"Constraint validation failed: {constraint_msg}")
            return None
        
        # Solve based on method
        if self.method == "geometric":
            result = self._solve_geometric(positions, distances)
        else:
            result = self._solve_least_squares(positions, distances)
        
        if result is not None:
            self.last_result = result
            self.last_error = calculate_positioning_error(positions, distances, result)
            self.last_gdop = calculate_geometric_dilution(positions, result)
        
        return result
    
    def _validate_input(self, 
                       drone_ids: List[Union[str, int]], 
                       positions: List[Tuple[float, ...]], 
                       distances: List[float]) -> Tuple[bool, str]:
        """Validate input parameters."""
        if not drone_ids or not positions or not distances:
            return False, "Empty input data"
        
        if len(drone_ids) != len(positions) or len(positions) != len(distances):
            return False, "Mismatched input lengths"
        
        # Check dimension consistency
        expected_dims = 2 if self.dimension == "2d" else 3
        for i, pos in enumerate(positions):
            if len(pos) != expected_dims:
                return False, f"Position {i} has {len(pos)} dimensions, expected {expected_dims}"
        
        # Check for non-negative distances
        for i, dist in enumerate(distances):
            if dist < 0:
                return False, f"Distance {i} is negative: {dist}"
        
        return True, "Input validation passed"
    
    def _solve_geometric(self, 
                        positions: List[Tuple[float, ...]], 
                        distances: List[float]) -> Optional[Tuple[float, ...]]:
        """Solve using geometric intersection method."""
        if self.dimension == "2d":
            return solve_2d_geometric_intersection(positions, distances)
        else:
            return solve_3d_geometric_intersection(positions, distances)
    
    def _solve_least_squares(self, 
                            positions: List[Tuple[float, ...]], 
                            distances: List[float]) -> Optional[Tuple[float, ...]]:
        """Solve using least squares optimization."""
        return solve_least_squares_optimization(positions, distances)
    
    def get_last_result_info(self) -> Dict[str, any]:
        """Get information about the last solve operation."""
        return {
            "position": self.last_result,
            "error": self.last_error,
            "gdop": self.last_gdop,
            "dimension": self.dimension,
            "method": self.method
        }
    
    def optimize_anchor_positions(self, 
                                 center: Tuple[float, ...], 
                                 radius: float, 
                                 num_anchors: int) -> List[Tuple[float, ...]]:
        """
        Calculate optimal anchor positions for multilateration.
        
        Args:
            center: Center point for anchor distribution
            radius: Radius for anchor distribution
            num_anchors: Number of anchor positions to generate
            
        Returns:
            List of optimal anchor positions
        """
        if self.dimension == "2d":
            return self.constraints.calculate_optimal_anchor_positions_2d(
                center, radius, num_anchors
            )
        else:
            return self.constraints.calculate_optimal_anchor_positions_3d(
                center, radius, num_anchors
            )
    
    def validate_geometry(self, 
                         positions: List[Tuple[float, ...]], 
                         distances: List[float]) -> Tuple[bool, str, float]:
        """
        Validate the geometry of anchor positions for multilateration.
        
        Args:
            positions: List of anchor positions
            distances: List of measured distances
            
        Returns:
            Tuple of (is_valid, message, gdop_value)
        """
        # Basic constraint validation
        is_valid, msg = validate_multilateration_input(positions, distances, self.dimension)
        if not is_valid:
            return False, msg, float('inf')
        
        # Calculate GDOP for geometry quality assessment
        estimated_center = calculate_centroid(positions)
        gdop = calculate_geometric_dilution(positions, estimated_center)
        
        # Assess geometry quality
        if gdop > 10.0:
            return False, f"Poor geometry (GDOP: {gdop:.2f})", gdop
        elif gdop > 5.0:
            return True, f"Acceptable geometry (GDOP: {gdop:.2f})", gdop
        else:
            return True, f"Good geometry (GDOP: {gdop:.2f})", gdop


# Convenience functions for quick usage
def solve_2d_multilateration(drone_ids: List[Union[str, int]], 
                            positions: List[Tuple[float, float]], 
                            distances: List[float],
                            method: str = "geometric") -> Optional[Tuple[float, float]]:
    """
    Convenience function for 2D multilateration.
    
    Args:
        drone_ids: List of drone identifiers
        positions: List of 2D positions [(x, y), ...]
        distances: List of measured distances
        method: "geometric" or "least_squares"
        
    Returns:
        Estimated 2D position or None
    """
    solver = MultilaterationSolver(dimension="2d", method=method)
    return solver.solve(drone_ids, positions, distances)


def solve_3d_multilateration(drone_ids: List[Union[str, int]], 
                            positions: List[Tuple[float, float, float]], 
                            distances: List[float],
                            method: str = "geometric") -> Optional[Tuple[float, float, float]]:
    """
    Convenience function for 3D multilateration.
    
    Args:
        drone_ids: List of drone identifiers
        positions: List of 3D positions [(x, y, z), ...]
        distances: List of measured distances
        method: "geometric" or "least_squares"
        
    Returns:
        Estimated 3D position or None
    """
    solver = MultilaterationSolver(dimension="3d", method=method)
    return solver.solve(drone_ids, positions, distances)