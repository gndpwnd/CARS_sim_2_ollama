import numpy as np
import matplotlib.pyplot as plt
from typing import Tuple, Optional, List
import math

class Drone:
    """
    Represents a drone anchor for multilateration positioning.
    """
    
    def __init__(self, x: float, y: float, drone_id: int = 0):
        """
        Initialize a drone with position.
        
        Args:
            x: X coordinate
            y: Y coordinate
            drone_id: Unique identifier for the drone
        """
        self.x = x
        self.y = y
        self.drone_id = drone_id
        self.measured_distance = None
        self.true_distance = None
        self.is_occluded = False
        self.signal_strength = 100.0  # Percentage
        
    def get_position(self) -> Tuple[float, float]:
        """Get the current position of the drone."""
        return (self.x, self.y)
    
    def set_position(self, x: float, y: float):
        """Set the position of the drone."""
        self.x = x
        self.y = y
    
    def move_to(self, x: float, y: float):
        """Move the drone to a new position."""
        self.set_position(x, y)
    
    def calculate_distance_to_target(self, target_x: float, target_y: float) -> float:
        """
        Calculate the true geometric distance to a target.
        
        Args:
            target_x: Target X coordinate
            target_y: Target Y coordinate
            
        Returns:
            True geometric distance
        """
        distance = math.sqrt((target_x - self.x)**2 + (target_y - self.y)**2)
        self.true_distance = distance
        return distance
    
    def simulate_tof_measurement(self, target_x: float, target_y: float, 
                                obstacles: List = None, 
                                speed_of_light: float = 3e8,
                                noise_std: float = 0.1) -> float:
        """
        Simulate Time-of-Flight measurement including occlusion effects.
        
        Args:
            target_x: Target X coordinate
            target_y: Target Y coordinate
            obstacles: List of obstacle objects (with x, y, radius attributes)
            speed_of_light: Speed of light in m/s
            noise_std: Standard deviation of measurement noise
            
        Returns:
            Measured distance (may be corrupted by occlusion)
        """
        # Calculate true distance
        true_distance = self.calculate_distance_to_target(target_x, target_y)
        
        # Check for occlusion
        self.is_occluded = False
        if obstacles:
            self.is_occluded = self._check_line_of_sight_blocked(
                target_x, target_y, obstacles
            )
        
        # Simulate measurement
        if self.is_occluded:
            # Occluded measurement: add bias and increase noise
            occlusion_bias = np.random.uniform(0.5, 3.0)  # NLOS bias
            measured_distance = true_distance + occlusion_bias
            noise = np.random.normal(0, noise_std * 3)  # Higher noise when occluded
            self.signal_strength = np.random.uniform(10, 40)  # Weak signal
        else:
            # Clear LOS measurement
            measured_distance = true_distance
            noise = np.random.normal(0, noise_std)
            self.signal_strength = np.random.uniform(80, 100)  # Strong signal
        
        # Add measurement noise
        measured_distance += noise
        
        # Ensure positive distance
        measured_distance = max(0.1, measured_distance)
        
        self.measured_distance = measured_distance
        return measured_distance
    
    def _check_line_of_sight_blocked(self, target_x: float, target_y: float, 
                                   obstacles: List) -> bool:
        """
        Check if line of sight to target is blocked by obstacles.
        
        Args:
            target_x: Target X coordinate
            target_y: Target Y coordinate
            obstacles: List of obstacle objects
            
        Returns:
            True if line of sight is blocked
        """
        for obstacle in obstacles:
            if self._line_intersects_circle(
                self.x, self.y, target_x, target_y,
                obstacle.x, obstacle.y, obstacle.radius
            ):
                return True
        return False
    
    def _line_intersects_circle(self, x1: float, y1: float, x2: float, y2: float,
                               cx: float, cy: float, radius: float) -> bool:
        """
        Check if line segment intersects with circle.
        
        Args:
            x1, y1: Start point of line
            x2, y2: End point of line
            cx, cy: Circle center
            radius: Circle radius
            
        Returns:
            True if line intersects circle
        """
        # Vector from start to end
        dx = x2 - x1
        dy = y2 - y1
        
        # Vector from start to circle center
        fx = x1 - cx
        fy = y1 - cy
        
        # Quadratic equation coefficients
        a = dx*dx + dy*dy
        b = 2*(fx*dx + fy*dy)
        c = (fx*fx + fy*fy) - radius*radius
        
        discriminant = b*b - 4*a*c
        
        if discriminant < 0:
            return False
        
        # Check if intersection points are within line segment
        discriminant = math.sqrt(discriminant)
        
        t1 = (-b - discriminant) / (2*a)
        t2 = (-b + discriminant) / (2*a)
        
        # Check if either intersection point is within the line segment
        return (0 <= t1 <= 1) or (0 <= t2 <= 1) or (t1 < 0 and t2 > 1)
    
    def randomize_position(self, x_min: float = -50, x_max: float = 50,
                          y_min: float = -50, y_max: float = 50):
        """
        Randomize the drone position within specified bounds.
        
        Args:
            x_min, x_max: X coordinate bounds
            y_min, y_max: Y coordinate bounds
        """
        new_x = np.random.uniform(x_min, x_max)
        new_y = np.random.uniform(y_min, y_max)
        self.set_position(new_x, new_y)
    
    def plot_drone(self, ax, color='blue', size=100):
        """
        Plot the drone on the given axis.
        
        Args:
            ax: Matplotlib axis object
            color: Color of the drone marker
            size: Size of the drone marker
        """
        # Different color/style if occluded
        if self.is_occluded:
            edge_color = 'red'
            line_width = 3
        else:
            edge_color = 'black'
            line_width = 1
            
        ax.scatter(self.x, self.y, c=color, s=size, marker='^', 
                  edgecolors=edge_color, linewidth=line_width, 
                  label=f'Drone {self.drone_id}')
        
        # Add drone label
        ax.annotate(f'D{self.drone_id}', (self.x, self.y), 
                   xytext=(5, 5), textcoords='offset points', 
                   fontsize=8, fontweight='bold')
    
    def plot_range_circle(self, ax, color='lightblue', alpha=0.3, linestyle='-'):
        """
        Plot the range circle around the drone.
        
        Args:
            ax: Matplotlib axis object
            color: Color of the circle
            alpha: Transparency of the circle
            linestyle: Line style for the circle edge
        """
        if self.measured_distance is not None:
            # Different style if occluded
            if self.is_occluded:
                color = 'pink'
                linestyle = '--'
                alpha = 0.2
            
            circle = plt.Circle((self.x, self.y), self.measured_distance, 
                              color=color, alpha=alpha, fill=True)
            ax.add_patch(circle)
            
            # Add circle edge
            circle_edge = plt.Circle((self.x, self.y), self.measured_distance, 
                                   color=color, alpha=1.0, fill=False, 
                                   linestyle=linestyle, linewidth=1)
            ax.add_patch(circle_edge)
    
    def plot_line_to_target(self, ax, target_x: float, target_y: float, 
                           color='gray', alpha=0.6, linewidth=1):
        """
        Plot line from drone to target.
        
        Args:
            ax: Matplotlib axis object
            target_x: Target X coordinate
            target_y: Target Y coordinate
            color: Line color
            alpha: Line transparency
            linewidth: Line width
        """
        # Different style if occluded
        if self.is_occluded:
            color = 'red'
            linestyle = ':'
            alpha = 0.8
            linewidth = 2
        else:
            linestyle = '-'
        
        ax.plot([self.x, target_x], [self.y, target_y], 
               color=color, alpha=alpha, linewidth=linewidth, 
               linestyle=linestyle)
    
    def get_status_info(self) -> dict:
        """Get comprehensive status information about the drone."""
        return {
            'drone_id': self.drone_id,
            'position': self.get_position(),
            'measured_distance': self.measured_distance,
            'true_distance': self.true_distance,
            'is_occluded': self.is_occluded,
            'signal_strength': self.signal_strength
        }
    
    def __repr__(self):
        return f"Drone(id={self.drone_id}, pos=({self.x:.2f}, {self.y:.2f}), occluded={self.is_occluded})"