import numpy as np
import math
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass

@dataclass
class OcclusionResult:
    """Results from occlusion detection analysis."""
    occluded_drones: List[int]
    total_occlusions: int
    geometric_errors: List[float]
    intersection_count: int
    max_possible_intersections: int
    rover_position_estimate: Optional[Tuple[float, float]]
    detection_confidence: float

class OcclusionDetector:
    """
    Implements geometric occlusion detection based on circle intersection analysis.
    """
    
    def __init__(self, geometric_tolerance: float = 0.5):
        """
        Initialize occlusion detector.
        
        Args:
            geometric_tolerance: Maximum allowable geometric error in meters
        """
        self.geometric_tolerance = geometric_tolerance
        self.min_intersection_confidence = 0.6
        
    def detect_occlusion(self, drones: List, rover_true_pos: Tuple[float, float] = None) -> OcclusionResult:
        """
        Detect occlusion using geometric circle intersection analysis.
        
        Args:
            drones: List of drone objects with measured distances
            rover_true_pos: True rover position for validation (optional)
            
        Returns:
            OcclusionResult containing detection results
        """
        if len(drones) < 3:
            return OcclusionResult(
                occluded_drones=list(range(len(drones))),
                total_occlusions=len(drones),
                geometric_errors=[],
                intersection_count=0,
                max_possible_intersections=0,
                rover_position_estimate=None,
                detection_confidence=0.0
            )
        
        # Extract valid drone data
        valid_drones = [d for d in drones if d.measured_distance is not None]
        
        if len(valid_drones) < 3:
            return OcclusionResult(
                occluded_drones=list(range(len(drones))),
                total_occlusions=len(drones),
                geometric_errors=[],
                intersection_count=0,
                max_possible_intersections=0,
                rover_position_estimate=None,
                detection_confidence=0.0
            )
        
        # Perform geometric occlusion detection
        return self._geometric_occlusion_detection(valid_drones, rover_true_pos)
    
    def _geometric_occlusion_detection(self, drones: List, rover_true_pos: Tuple[float, float] = None) -> OcclusionResult:
        """
        Perform geometric occlusion detection using circle intersections.
        
        Args:
            drones: List of valid drone objects
            rover_true_pos: True rover position for validation
            
        Returns:
            OcclusionResult with detection analysis
        """
        n_drones = len(drones)
        
        # Step 1: Generate all pairwise circle intersections
        intersection_points = []
        
        for i in range(n_drones):
            for j in range(i + 1, n_drones):
                points = self._calculate_circle_intersection(
                    (drones[i].x, drones[i].y), drones[i].measured_distance,
                    (drones[j].x, drones[j].y), drones[j].measured_distance
                )
                intersection_points.extend(points)
        
        if not intersection_points:
            # No intersections found - all drones likely occluded
            return OcclusionResult(
                occluded_drones=[d.drone_id for d in drones],
                total_occlusions=n_drones,
                geometric_errors=[float('inf')] * n_drones,
                intersection_count=0,
                max_possible_intersections=n_drones,
                rover_position_estimate=None,
                detection_confidence=0.0
            )
        
        # Step 2: Find point with maximum circle intersections
        best_point = None
        max_intersections = 0
        intersection_counts = []
        
        for point in intersection_points:
            count = self._count_intersecting_circles(point, drones)
            intersection_counts.append(count)
            
            if count > max_intersections:
                max_intersections = count
                best_point = point
        
        # Step 3: Analyze occlusion based on intersection count
        rover_estimate = best_point
        geometric_errors = []
        occluded_drone_ids = []
        
        if rover_estimate is not None:
            # Calculate errors for each drone
            for drone in drones:
                error = self._calculate_geometric_error(rover_estimate, drone)
                geometric_errors.append(error)
                
                # Mark drone as occluded if error exceeds tolerance
                if error > self.geometric_tolerance:
                    occluded_drone_ids.append(drone.drone_id)
        
        # Step 4: Determine detection confidence
        detection_confidence = self._calculate_detection_confidence(
            max_intersections, n_drones, geometric_errors
        )
        
        return OcclusionResult(
            occluded_drones=occluded_drone_ids,
            total_occlusions=len(occluded_drone_ids),
            geometric_errors=geometric_errors,
            intersection_count=max_intersections,
            max_possible_intersections=n_drones,
            rover_position_estimate=rover_estimate,
            detection_confidence=detection_confidence
        )
    
    def _calculate_circle_intersection(self, center1: Tuple[float, float], radius1: float,
                                     center2: Tuple[float, float], radius2: float) -> List[Tuple[float, float]]:
        """
        Calculate intersection points between two circles.
        
        Args:
            center1: Center of first circle (x, y)
            radius1: Radius of first circle
            center2: Center of second circle (x, y)
            radius2: Radius of second circle
            
        Returns:
            List of intersection points
        """
        x1, y1 = center1
        x2, y2 = center2
        
        # Calculate distance between centers
        d = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        
        # Check for intersection feasibility
        if d > radius1 + radius2 + self.geometric_tolerance:
            return []  # Circles too far apart
        
        if d < abs(radius1 - radius2) - self.geometric_tolerance:
            return []  # One circle inside the other
        
        if d == 0 and radius1 == radius2:
            return []  # Identical circles (infinite intersections)
        
        if d == 0:
            return []  # Concentric circles
        
        # Calculate intersection points
        try:
            a = (radius1**2 - radius2**2 + d**2) / (2 * d)
            h_squared = radius1**2 - a**2
            
            if h_squared < 0:
                return []
            
            h = math.sqrt(h_squared)
            
            # Midpoint calculation
            x_m = x1 + a * (x2 - x1) / d
            y_m = y1 + a * (y2 - y1) / d
            
            if h < 1e-10:  # Tangent circles
                return [(x_m, y_m)]
            
            # Two intersection points
            x_int1 = x_m + h * (y2 - y1) / d
            y_int1 = y_m - h * (x2 - x1) / d
            
            x_int2 = x_m - h * (y2 - y1) / d
            y_int2 = y_m + h * (x2 - x1) / d
            
            return [(x_int1, y_int1), (x_int2, y_int2)]
            
        except (ZeroDivisionError, ValueError, OverflowError):
            return []
    
    def _count_intersecting_circles(self, point: Tuple[float, float], drones: List) -> int:
        """
        Count how many drone circles intersect at a given point.
        
        Args:
            point: Point to check (x, y)
            drones: List of drone objects
            
        Returns:
            Number of circles intersecting at the point
        """
        x, y = point
        count = 0
        
        for drone in drones:
            distance_to_point = math.sqrt((x - drone.x)**2 + (y - drone.y)**2)
            error = abs(distance_to_point - drone.measured_distance)
            
            if error <= self.geometric_tolerance:
                count += 1
        
        return count
    
    def _calculate_geometric_error(self, rover_position: Tuple[float, float], drone) -> float:
        """
        Calculate geometric error between rover position and drone measurement.
        
        Args:
            rover_position: Estimated rover position (x, y)
            drone: Drone object with measured distance
            
        Returns:
            Geometric error in meters
        """
        x_rover, y_rover = rover_position
        calculated_distance = math.sqrt((x_rover - drone.x)**2 + (y_rover - drone.y)**2)
        
        return abs(calculated_distance - drone.measured_distance)
    
    def _calculate_detection_confidence(self, max_intersections: int, total_drones: int,
                                      geometric_errors: List[float]) -> float:
        """
        Calculate confidence level for occlusion detection.
        
        Args:
            max_intersections: Maximum number of intersecting circles
            total_drones: Total number of drones
            geometric_errors: List of geometric errors
            
        Returns:
            Confidence level (0.0 to 1.0)
        """
        if not geometric_errors:
            return 0.0
        
        # Base confidence from intersection ratio
        intersection_ratio = max_intersections / total_drones
        
        # Penalize high geometric errors
        avg_error = np.mean(geometric_errors)
        error_penalty = min(avg_error / self.geometric_tolerance, 1.0)
        
        # Combined confidence
        confidence = intersection_ratio * (1.0 - error_penalty * 0.5)
        
        return max(0.0, min(1.0, confidence))
    
    def validate_triangle_inequality(self, drones: List) -> Dict[int, bool]:
        """
        Validate triangle inequality constraint for each drone pair.
        
        Args:
            drones: List of drone objects
            
        Returns:
            Dictionary mapping drone_id to violation status
        """
        violations = {}
        
        for i, drone_i in enumerate(drones):
            violations[drone_i.drone_id] = False
            
            for j, drone_j in enumerate(drones):
                if i >= j:
                    continue
                
                # Distance between drones
                d_ij = math.sqrt((drone_j.x - drone_i.x)**2 + (drone_j.y - drone_i.y)**2)
                
                # Measured distances to rover
                r_i = drone_i.measured_distance
                r_j = drone_j.measured_distance
                
                if r_i is None or r_j is None:
                    continue
                
                # Check triangle inequality: |r_i - r_j| <= d_ij <= r_i + r_j
                if not (abs(r_i - r_j) <= d_ij <= r_i + r_j + self.geometric_tolerance):
                    violations[drone_i.drone_id] = True
                    violations[drone_j.drone_id] = True
        
        return violations
    
    def print_occlusion_report(self, result: OcclusionResult, drones: List):
        """
        Print detailed occlusion detection report.
        
        Args:
            result: OcclusionResult from detection
            drones: List of drone objects
        """
        print("\n" + "="*50)
        print("OCCLUSION DETECTION REPORT")
        print("="*50)
        
        print(f"Total Drones: {len(drones)}")
        print(f"Occluded Drones: {result.total_occlusions}")
        print(f"Circle Intersections: {result.intersection_count}/{result.max_possible_intersections}")
        print(f"Detection Confidence: {result.detection_confidence:.2f}")
        
        if result.rover_position_estimate:
            x_est, y_est = result.rover_position_estimate
            print(f"Estimated Rover Position: ({x_est:.2f}, {y_est:.2f})")
        else:
            print("Rover Position: Unable to estimate")
        
        print("\nDrone Status:")
        for i, drone in enumerate(drones):
            status = "OCCLUDED" if drone.drone_id in result.occluded_drones else "CLEAR"
            error = result.geometric_errors[i] if i < len(result.geometric_errors) else "N/A"
            print(f"  Drone {drone.drone_id}: {status} (Error: {error:.3f}m)")
        
        if result.total_occlusions > 0:
            print(f"\nOccluded Drone IDs: {result.occluded_drones}")
        else:
            print("\nNo occlusions detected - all drones have clear line of sight")
        
        print("="*50)