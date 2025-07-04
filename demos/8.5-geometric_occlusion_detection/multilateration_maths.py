import numpy as np
import math
from typing import List, Tuple, Optional
from scipy.optimize import least_squares

class MultilaterationSolver:
    """
    Solves 2D multilateration using distance measurements from multiple drones.
    """
    
    def __init__(self):
        """Initialize the multilateration solver."""
        pass
    
    def solve(self, drones: List, method: str = 'hybrid') -> Optional[Tuple[float, float]]:
        """
        Solve multilateration using drone distance measurements.
        
        Args:
            drones: List of drone objects with measured distances
            method: 'least_squares', 'geometric', or 'hybrid'
            
        Returns:
            Estimated position (x, y) or None if failed
        """
        if len(drones) < 3:
            return None
        
        # Extract positions and distances
        positions = [(drone.x, drone.y) for drone in drones]
        distances = [drone.measured_distance for drone in drones if drone.measured_distance is not None]
        
        if len(distances) < 3:
            return None
        
        if method == 'least_squares':
            return self._solve_least_squares(positions, distances)
        elif method == 'geometric':
            return self._solve_geometric(positions, distances)
        elif method == 'hybrid':
            # Try geometric first, fall back to least squares
            result = self._solve_geometric(positions, distances)
            if result is None:
                result = self._solve_least_squares(positions, distances)
            return result
        else:
            raise ValueError(f"Unknown method: {method}")
    
    def _solve_least_squares(self, positions: List[Tuple[float, float]], 
                           distances: List[float]) -> Optional[Tuple[float, float]]:
        """
        Solve multilateration using least squares optimization.
        
        Args:
            positions: List of drone positions [(x, y), ...]
            distances: List of measured distances
            
        Returns:
            Estimated position (x, y) or None if failed
        """
        # Initial guess - centroid of drone positions
        x_avg = sum(pos[0] for pos in positions) / len(positions)
        y_avg = sum(pos[1] for pos in positions) / len(positions)
        initial_guess = [x_avg, y_avg]
        
        def objective_function(point):
            x, y = point
            errors = []
            for i, (px, py) in enumerate(positions):
                if i < len(distances):
                    calculated_distance = np.sqrt((x - px)**2 + (y - py)**2)
                    error = calculated_distance - distances[i]
                    errors.append(error)
            return errors
        
        try:
            result = least_squares(objective_function, initial_guess, method='lm')
            if result.success:
                return tuple(result.x)
            else:
                return None
        except Exception:
            return None
    
    def _solve_geometric(self, positions: List[Tuple[float, float]], 
                        distances: List[float], tolerance: float = 0.5) -> Optional[Tuple[float, float]]:
        """
        Solve multilateration using geometric circle intersections.
        
        Args:
            positions: List of drone positions [(x, y), ...]
            distances: List of measured distances
            tolerance: Tolerance for intersection matching
            
        Returns:
            Estimated position (x, y) or None if failed
        """
        # Generate all pairwise circle intersections
        intersections = []
        
        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                if i < len(distances) and j < len(distances):
                    points = self._circle_intersection(
                        positions[i], distances[i],
                        positions[j], distances[j]
                    )
                    intersections.extend(points)
        
        if not intersections:
            return None
        
        # Find the point where the most circles intersect
        best_point = None
        max_count = 0
        
        for point in intersections:
            count = 0
            for k in range(len(positions)):
                if k < len(distances):
                    calculated_distance = np.sqrt((point[0] - positions[k][0])**2 + 
                                               (point[1] - positions[k][1])**2)
                    if abs(calculated_distance - distances[k]) <= tolerance:
                        count += 1
            
            if count > max_count:
                max_count = count
                best_point = point
        
        # Require at least 3 circles to intersect at the point
        if best_point is not None and max_count >= 3:
            return best_point
        else:
            return None
    
    def _circle_intersection(self, center1: Tuple[float, float], radius1: float,
                           center2: Tuple[float, float], radius2: float) -> List[Tuple[float, float]]:
        """
        Find intersection points between two circles.
        
        Args:
            center1: Center of first circle (x, y)
            radius1: Radius of first circle
            center2: Center of second circle (x, y)
            radius2: Radius of second circle
            
        Returns:
            List of intersection points (empty if no intersection)
        """
        x1, y1 = center1
        x2, y2 = center2
        
        # Distance between centers
        d = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        
        # Check if circles intersect
        if d > radius1 + radius2 or d < abs(radius1 - radius2) or d == 0:
            return []
        
        # Calculate intersection points
        try:
            a = (radius1**2 - radius2**2 + d**2) / (2 * d)
            h_squared = radius1**2 - a**2
            
            if h_squared < 0:
                return []
            
            h = math.sqrt(h_squared)
            
            # Midpoint between intersections
            x_mid = x1 + a * (x2 - x1) / d
            y_mid = y1 + a * (y2 - y1) / d
            
            if h < 1e-10:  # Circles are tangent
                return [(x_mid, y_mid)]
            
            # The two intersection points
            x_int1 = x_mid + h * (y2 - y1) / d
            y_int1 = y_mid - h * (x2 - x1) / d
            
            x_int2 = x_mid - h * (y2 - y1) / d
            y_int2 = y_mid + h * (x2 - x1) / d
            
            return [(x_int1, y_int1), (x_int2, y_int2)]
            
        except (ZeroDivisionError, ValueError):
            return []
    
    def calculate_position_error(self, estimated_pos: Tuple[float, float], 
                               positions: List[Tuple[float, float]],
                               distances: List[float]) -> float:
        """
        Calculate the RMS error between estimated position and measured distances.
        
        Args:
            estimated_pos: Estimated position (x, y)
            positions: List of drone positions
            distances: List of measured distances
            
        Returns:
            RMS error in meters
        """
        if not estimated_pos:
            return float('inf')
        
        x_est, y_est = estimated_pos
        errors = []
        
        for i, (px, py) in enumerate(positions):
            if i < len(distances):
                calculated_distance = np.sqrt((x_est - px)**2 + (y_est - py)**2)
                error = abs(calculated_distance - distances[i])
                errors.append(error)
        
        if not errors:
            return float('inf')
        
        return np.sqrt(np.mean(np.array(errors)**2))
    
    def get_residuals(self, estimated_pos: Tuple[float, float], 
                     positions: List[Tuple[float, float]],
                     distances: List[float]) -> List[float]:
        """
        Get residuals for each drone measurement.
        
        Args:
            estimated_pos: Estimated position (x, y)
            positions: List of drone positions
            distances: List of measured distances
            
        Returns:
            List of residuals (calculated - measured distance)
        """
        if not estimated_pos:
            return []
        
        x_est, y_est = estimated_pos
        residuals = []
        
        for i, (px, py) in enumerate(positions):
            if i < len(distances):
                calculated_distance = np.sqrt((x_est - px)**2 + (y_est - py)**2)
                residual = calculated_distance - distances[i]
                residuals.append(residual)
        
        return residuals