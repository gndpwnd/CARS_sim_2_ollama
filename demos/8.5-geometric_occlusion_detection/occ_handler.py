"""
Occlusion Handler for managing occlusion detection and mitigation strategies

This module provides high-level control for handling occlusions in multilateration systems,
including suggesting drone movements and managing the overall occlusion detection process.
"""

import numpy as np
from typing import List, Tuple, Dict, Set, Union
import math

class OcclusionHandler:
    def __init__(self, tolerance: float = 0.05, mode_3d: bool = False):
        """
        Initialize occlusion handler for managing occlusion detection and mitigation.
        
        Args:
            tolerance: Distance tolerance in meters for occlusion detection
            mode_3d: Whether to use 3D analysis
        """
        self.tolerance = tolerance
        self.mode_3d = mode_3d
        
    def get_occlusion_summary(self, results: Dict) -> str:
        """
        Generate a human-readable summary of occlusion detection results.
        """
        if not results['is_occluded']:
            return "No occlusion detected - all measurements are geometrically consistent"
        
        summary_lines = []
        summary_lines.append(f"OCCLUSION DETECTED (Confidence: {results['confidence_score']:.2f})")
        summary_lines.append(f"Occluded anchors: {sorted(list(results['occluded_anchors']))}")
        
        if results['line_of_sight_blocked']:
            summary_lines.append(f"Line-of-sight blocked: {len(results['line_of_sight_blocked'])}")
        
        if results['triangle_violations']:
            summary_lines.append(f"Triangle inequality violations: {len(results['triangle_violations'])}")
        
        if results['circle_intersection_issues']:
            summary_lines.append(f"Circle intersection issues: {len(results['circle_intersection_issues'])}")
        
        if results['distance_outliers']:
            summary_lines.append(f"Statistical outliers: {len(results['distance_outliers'])}")
        
        return "\n".join(summary_lines)
    
    def suggest_drone_movement(self, results: Dict, anchor_positions: List[Union[Tuple[float, float], Tuple[float, float, float]]], 
                             simulation_bounds: Tuple[float, float, float, float],
                             obstacle_areas: List[Tuple[float, float, float]] = None) -> Dict[int, Union[Tuple[float, float], Tuple[float, float, float]]]:
        """
        Suggest movement for occluded drones to improve positioning.
        
        Args:
            results: Occlusion detection results
            anchor_positions: Current anchor positions
            simulation_bounds: Boundary limits (min_x, max_x, min_y, max_y)
            obstacle_areas: Known obstacle areas to avoid
            
        Returns:
            Dictionary mapping anchor indices to suggested new positions
        """
        suggestions = {}
        
        if not results['is_occluded']:
            return suggestions
        
        min_x, max_x, min_y, max_y = simulation_bounds
        obstacle_areas = obstacle_areas or []
        
        # Estimate target position for better movement suggestions
        anchors = np.array(anchor_positions)
        if self.mode_3d and len(anchor_positions[0]) == 2:
            anchors = np.array([(x, y, 0) for x, y in anchor_positions])
        elif not self.mode_3d and len(anchor_positions[0]) == 3:
            anchors = np.array([(x, y) for x, y, z in anchor_positions])
        
        target_pos = self._estimate_target_position(anchors, results['distances'])
        
        for anchor_idx in results['occluded_anchors']:
            current_pos = anchor_positions[anchor_idx]
            
            if target_pos is not None:
                # Move to improve line-of-sight to estimated target
                new_pos = self._find_clear_position(current_pos, target_pos, obstacle_areas, simulation_bounds)
            else:
                # Fallback: move away from other anchors
                new_pos = self._move_away_from_others(anchor_idx, anchor_positions, simulation_bounds)
            
            if new_pos:
                suggestions[anchor_idx] = new_pos
        
        return suggestions
    
    def _find_clear_position(self, current_pos: Union[Tuple[float, float], Tuple[float, float, float]], 
                           target_pos: np.ndarray, obstacle_areas: List[Tuple[float, float, float]], 
                           bounds: Tuple[float, float, float, float]) -> Union[Tuple[float, float], Tuple[float, float, float]]:
        """
        Find a new position that provides clear line-of-sight to the target.
        """
        min_x, max_x, min_y, max_y = bounds
        is_3d = len(current_pos) == 3
        
        # Try positions in a circle around current position
        for radius in [5, 10, 15]:
            for angle in np.linspace(0, 2*np.pi, 16):
                new_x = current_pos[0] + radius * np.cos(angle)
                new_y = current_pos[1] + radius * np.sin(angle)
                
                # Keep within bounds
                if new_x < min_x + 5 or new_x > max_x - 5:
                    continue
                if new_y < min_y + 5 or new_y > max_y - 5:
                    continue
                
                if is_3d:
                    new_pos = (new_x, new_y, current_pos[2])
                    test_pos_2d = (new_x, new_y)
                else:
                    new_pos = (new_x, new_y)
                    test_pos_2d = new_pos
                
                # Check if this position has clear line-of-sight
                target_2d = target_pos[:2] if len(target_pos) > 2 else target_pos
                has_clear_los = True
                
                for obs_x, obs_y, obs_radius in obstacle_areas:
                    if self._line_intersects_circle(test_pos_2d, target_2d, (obs_x, obs_y), obs_radius):
                        has_clear_los = False
                        break
                
                if has_clear_los:
                    return new_pos
        
        return None
    
    def _move_away_from_others(self, anchor_idx: int, anchor_positions: List[Union[Tuple[float, float], Tuple[float, float, float]]], 
                             bounds: Tuple[float, float, float, float]) -> Union[Tuple[float, float], Tuple[float, float, float]]:
        """
        Move anchor away from other anchors (fallback strategy).
        """
        min_x, max_x, min_y, max_y = bounds
        current_pos = anchor_positions[anchor_idx]
        other_anchors = [pos for i, pos in enumerate(anchor_positions) if i != anchor_idx]
        is_3d = len(current_pos) == 3
        
        if other_anchors:
            # Calculate centroid of other anchors
            centroid_x = sum(pos[0] for pos in other_anchors) / len(other_anchors)
            centroid_y = sum(pos[1] for pos in other_anchors) / len(other_anchors)
            
            # Move away from centroid
            dx = current_pos[0] - centroid_x
            dy = current_pos[1] - centroid_y
            
            # Normalize and scale movement
            distance = math.sqrt(dx*dx + dy*dy)
            if distance > 0:
                move_distance = 8.0  # Move 8 meters
                new_x = current_pos[0] + (dx / distance) * move_distance
                new_y = current_pos[1] + (dy / distance) * move_distance
                
                # Keep within bounds
                new_x = max(min_x + 5, min(max_x - 5, new_x))
                new_y = max(min_y + 5, min(max_y - 5, new_y))
                
                if is_3d:
                    return (new_x, new_y, current_pos[2])
                else:
                    return (new_x, new_y)
        
        return None
    
    def _estimate_target_position(self, anchors: np.ndarray, distances: List[float]) -> np.ndarray:
        """
        Simple target position estimation using weighted centroid.
        """
        if len(anchors) < 3 or len(distances) < 3:
            return None
        
        total_weight = 0
        weighted_pos = np.zeros(len(anchors[0]))
        
        for anchor, distance in zip(anchors, distances):
            if distance > 0.1:  # Avoid division by very small numbers
                weight = 1.0 / (distance + 0.1)
                weighted_pos += anchor * weight
                total_weight += weight
        
        if total_weight > 0:
            return weighted_pos / total_weight
        return None
    
    def _line_intersects_circle(self, p1: Tuple[float, float], p2: Tuple[float, float], 
                              center: Tuple[float, float], radius: float) -> bool:
        """
        Check if a line segment intersects with a circle.
        """
        # Vector from p1 to p2
        d = np.array(p2) - np.array(p1)
        # Vector from p1 to circle center
        f = np.array(p1) - np.array(center)
        
        # Quadratic equation coefficients for line-circle intersection
        a = np.dot(d, d)
        b = 2 * np.dot(f, d)
        c = np.dot(f, f) - radius * radius
        
        discriminant = b * b - 4 * a * c
        
        if discriminant < 0:
            return False  # No intersection
        
        # Check if intersection points are within the line segment
        sqrt_discriminant = math.sqrt(discriminant)
        t1 = (-b - sqrt_discriminant) / (2 * a)
        t2 = (-b + sqrt_discriminant) / (2 * a)
        
        # Intersection occurs if either t1 or t2 is between 0 and 1
        return (0 <= t1 <= 1) or (0 <= t2 <= 1) or (t1 < 0 and t2 > 1)