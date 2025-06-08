"""
Occlusion Checker for Geometric Consistency Analysis

This module implements geometric occlusion detection for multilateration systems
by analyzing distance measurements and anchor positions for consistency.
"""

import numpy as np
from typing import List, Tuple, Dict, Set, Union
from itertools import combinations
import math
from occlusion_handler import OcclusionHandler

class OcclusionChecker(OcclusionHandler):
    def check_occlusion(self, anchor_positions: List[Union[Tuple[float, float], Tuple[float, float, float]]], 
                       distances: List[float], obstacle_areas: List[Tuple[float, float, float]] = None) -> Dict:
        """
        Check if distance measurements are geometrically consistent with anchor positions.
        
        Args:
            anchor_positions: List of (x, y) or (x, y, z) tuples representing drone/anchor positions
            distances: List of measured distances from target to each anchor
            obstacle_areas: List of (x, y, radius) obstacle areas that can cause occlusion
            
        Returns:
            Dictionary containing occlusion analysis results
        """
        if len(anchor_positions) != len(distances):
            raise ValueError("Number of anchors must match number of distances")
        
        if len(anchor_positions) < 3:
            raise ValueError("Need at least 3 anchors for occlusion detection")
        
        # Convert to numpy array and handle 2D/3D
        if self.mode_3d:
            if len(anchor_positions[0]) == 2:
                # Convert 2D to 3D with Z=0
                anchors = np.array([(x, y, 0) for x, y in anchor_positions])
            else:
                anchors = np.array(anchor_positions)
        else:
            if len(anchor_positions[0]) == 3:
                # Convert 3D to 2D by dropping Z
                anchors = np.array([(x, y) for x, y, z in anchor_positions])
            else:
                anchors = np.array(anchor_positions)
        
        num_anchors = len(anchor_positions)
        
        results = {
            'occluded_anchors': set(),
            'triangle_violations': [],
            'circle_intersection_issues': [],
            'distance_outliers': [],
            'line_of_sight_blocked': [],
            'is_occluded': False,
            'confidence_score': 1.0,
            'num_anchors': num_anchors,
            'anchor_positions': anchor_positions,
            'distances': distances,
            'analysis_mode': '3D' if self.mode_3d else '2D',
            'obstacle_areas': obstacle_areas or []
        }
        
        # Only perform geometric checks if we have realistic distance variations
        distance_variance = np.var(distances) if len(distances) > 1 else 0
        
        # Core geometric consistency checks
        if distance_variance > 0.01:  # Only check if distances vary meaningfully
            self._check_triangle_inequalities(anchors, distances, results)
            self._check_circle_intersections(anchors, distances, results)
            
        # Check for statistical outliers only if we have enough variance
        if distance_variance > 0.1:
            self._check_distance_outliers(distances, results)
        
        # Check line-of-sight occlusion from obstacles
        if obstacle_areas:
            self._check_line_of_sight_occlusion(anchors, distances, obstacle_areas, results)
        
        # Determine overall occlusion status
        results['is_occluded'] = len(results['occluded_anchors']) > 0
        results['confidence_score'] = self._calculate_confidence_score(results)
        
        return results
    
    def _check_triangle_inequalities(self, anchors: np.ndarray, 
                                   distances: List[float], results: Dict):
        """
        Check triangle inequality violations for geometric consistency.
        Uses more lenient thresholds to avoid false positives.
        """
        num_anchors = len(anchors)
        
        # Check all combinations of 3 anchors
        for i, j, k in combinations(range(num_anchors), 3):
            # Distances from target to each anchor
            d_target_i, d_target_j, d_target_k = distances[i], distances[j], distances[k]
            
            # Inter-anchor distances
            d_ij = np.linalg.norm(anchors[i] - anchors[j])
            d_ik = np.linalg.norm(anchors[i] - anchors[k])
            d_jk = np.linalg.norm(anchors[j] - anchors[k])
            
            # More lenient triangle inequality checks
            tolerance = max(self.tolerance, 0.5)  # At least 0.5m tolerance
            
            # Check if distances are impossibly short
            if d_target_i + d_target_j < d_ij - tolerance:
                results['triangle_violations'].append(
                    f"Distances to anchors {i},{j} impossibly short: {d_target_i:.2f} + {d_target_j:.2f} < {d_ij:.2f}"
                )
                # Flag the shorter distance as potentially occluded
                if d_target_i < d_target_j:
                    results['occluded_anchors'].add(i)
                else:
                    results['occluded_anchors'].add(j)
            
            if d_target_i + d_target_k < d_ik - tolerance:
                results['triangle_violations'].append(
                    f"Distances to anchors {i},{k} impossibly short: {d_target_i:.2f} + {d_target_k:.2f} < {d_ik:.2f}"
                )
                if d_target_i < d_target_k:
                    results['occluded_anchors'].add(i)
                else:
                    results['occluded_anchors'].add(k)
                
            if d_target_j + d_target_k < d_jk - tolerance:
                results['triangle_violations'].append(
                    f"Distances to anchors {j},{k} impossibly short: {d_target_j:.2f} + {d_target_k:.2f} < {d_jk:.2f}"
                )
                if d_target_j < d_target_k:
                    results['occluded_anchors'].add(j)
                else:
                    results['occluded_anchors'].add(k)
            
            # Check if distances are impossibly long (very lenient)
            long_tolerance = tolerance * 2
            if d_target_i > d_ij + max(d_target_j, d_target_k) + long_tolerance:
                results['triangle_violations'].append(
                    f"Distance to anchor {i} impossibly long: {d_target_i:.2f} > {d_ij:.2f} + max({d_target_j:.2f}, {d_target_k:.2f})"
                )
                results['occluded_anchors'].add(i)
    
    def _check_circle_intersections(self, anchors: np.ndarray, 
                                  distances: List[float], results: Dict):
        """
        Check if ranging circles can intersect properly.
        Uses more realistic thresholds.
        """
        num_anchors = len(anchors)
        
        for i, j in combinations(range(num_anchors), 2):
            anchor_i, anchor_j = anchors[i], anchors[j]
            r_i, r_j = distances[i], distances[j]  # Radii of ranging circles
            
            # Distance between anchor centers
            d_centers = np.linalg.norm(anchor_i - anchor_j)
            
            # More lenient circle intersection analysis
            tolerance = max(self.tolerance, 0.3)  # At least 0.3m tolerance
            
            # Circles completely separate (gap between them)
            if d_centers > r_i + r_j + tolerance:
                results['circle_intersection_issues'].append(
                    f"Ranging circles {i},{j} don't intersect: gap={d_centers - (r_i + r_j):.2f}m"
                )
                # Flag the anchor with the more suspicious measurement
                expected_distance = d_centers / 2  # Rough expected distance
                error_i = abs(r_i - expected_distance)
                error_j = abs(r_j - expected_distance)
                if error_i > error_j:
                    results['occluded_anchors'].add(i)
                else:
                    results['occluded_anchors'].add(j)
            
            # One circle completely inside the other with significant gap
            elif d_centers + tolerance < abs(r_i - r_j):
                gap = abs(r_i - r_j) - d_centers
                if gap > tolerance:
                    results['circle_intersection_issues'].append(
                        f"Circle {i if r_i > r_j else j} completely contains circle {j if r_i > r_j else i}: gap={gap:.2f}m"
                    )
                    # Flag the anchor with the much larger measurement
                    if r_i > r_j and r_i > d_centers + r_j + tolerance:
                        results['occluded_anchors'].add(i)
                    elif r_j > r_i and r_j > d_centers + r_i + tolerance:
                        results['occluded_anchors'].add(j)
    
    def _check_distance_outliers(self, distances: List[float], results: Dict):
        """
        Detect statistical outliers in distance measurements using robust statistics.
        More conservative approach to avoid false positives.
        """
        if len(distances) < 4:  # Need more points for reliable outlier detection
            return
        
        distances_array = np.array(distances)
        median_dist = np.median(distances_array)
        
        # Use Median Absolute Deviation (MAD) for robust outlier detection
        mad = np.median(np.abs(distances_array - median_dist))
        
        if mad < 0.1:  # Insufficient variation for outlier detection
            return
        
        # More conservative threshold for outlier detection
        modified_z_threshold = 5.0  # Increased from 3.5
        
        for i, dist in enumerate(distances):
            # Calculate modified Z-score using MAD
            modified_z_score = 0.6745 * (dist - median_dist) / mad
            if abs(modified_z_score) > modified_z_threshold:
                results['distance_outliers'].append(
                    f"Anchor {i}: distance={dist:.2f}m, modified_z_score={modified_z_score:.2f}"
                )
                results['occluded_anchors'].add(i)
    
    def _check_line_of_sight_occlusion(self, anchors: np.ndarray, distances: List[float], 
                                     obstacle_areas: List[Tuple[float, float, float]], results: Dict):
        """
        Check if line-of-sight is blocked by known obstacle areas.
        This simulates the primary cause of occlusion.
        """
        if not obstacle_areas:
            return
        
        # Estimate target position using simple weighted centroid
        target_pos = self._estimate_target_position(anchors, distances)
        if target_pos is None:
            return
        
        for i, anchor in enumerate(anchors):
            anchor_2d = anchor[:2] if len(anchor) > 2 else anchor
            target_2d = target_pos[:2] if len(target_pos) > 2 else target_pos
            
            # Check if line from target to anchor is blocked by any obstacle
            for obs_x, obs_y, obs_radius in obstacle_areas:
                if self._line_intersects_circle(target_2d, anchor_2d, (obs_x, obs_y), obs_radius):
                    results['line_of_sight_blocked'].append(
                        f"Anchor {i}: line of sight blocked by obstacle at ({obs_x:.1f}, {obs_y:.1f})"
                    )
                    results['occluded_anchors'].add(i)
                    break
    
    def _calculate_confidence_score(self, results: Dict) -> float:
        """
        Calculate confidence score for occlusion detection (0-1, where 1 is high confidence).
        """
        # Weight different types of evidence
        triangle_weight = 0.4
        circle_weight = 0.3
        outlier_weight = 0.1
        los_weight = 0.8  # Line-of-sight blocking is strong evidence
        
        total_evidence = 0
        max_evidence = 1.0
        
        # Triangle inequality violations
        if results['triangle_violations']:
            total_evidence += triangle_weight * min(1.0, len(results['triangle_violations']) / 3)
        
        # Circle intersection issues
        if results['circle_intersection_issues']:
            total_evidence += circle_weight * min(1.0, len(results['circle_intersection_issues']) / 2)
        
        # Distance outliers
        if results['distance_outliers']:
            total_evidence += outlier_weight * min(1.0, len(results['distance_outliers']) / 2)
        
        # Line-of-sight blocking (strongest evidence)
        if results['line_of_sight_blocked']:
            total_evidence += los_weight * min(1.0, len(results['line_of_sight_blocked']) / 3)
        
        # Base confidence decreases with evidence of occlusion
        base_confidence = max(0.0, 1.0 - total_evidence)
        
        # If no occlusion detected, return high confidence
        if not results['is_occluded']:
            return base_confidence
        
        # Adjust confidence based on strength of evidence
        if results['line_of_sight_blocked']:
            return min(0.95, 0.7 + 0.25 * len(results['line_of_sight_blocked']))
        elif results['triangle_violations'] or results['circle_intersection_issues']:
            return min(0.8, 0.5 + 0.1 * (len(results['triangle_violations']) + len(results['circle_intersection_issues'])))
        else:
            return 0.3  # Low confidence if only statistical evidence