import numpy as np
import matplotlib.pyplot as plt
from typing import Tuple, Optional

class Rover:
    """
    Represents a rover target that needs to be localized using multilateration.
    """
    
    def __init__(self, x: float, y: float):
        """
        Initialize a rover with position.
        
        Args:
            x: X coordinate
            y: Y coordinate
        """
        self.x = x
        self.y = y
        self.estimated_x = None
        self.estimated_y = None
        self.position_history = []
        self.estimation_history = []
        
    def get_position(self) -> Tuple[float, float]:
        """Get the current true position of the rover."""
        return (self.x, self.y)
    
    def set_position(self, x: float, y: float):
        """Set the true position of the rover."""
        self.x = x
        self.y = y
        
        # Store position history
        self.position_history.append((self.x, self.y))
        
        # Keep only last 100 positions
        if len(self.position_history) > 100:
            self.position_history.pop(0)
    
    def move_to(self, x: float, y: float):
        """Move the rover to a new position."""
        self.set_position(x, y)
    
    def set_estimated_position(self, x: float, y: float):
        """
        Set the estimated position from multilateration.
        
        Args:
            x: Estimated X coordinate
            y: Estimated Y coordinate
        """
        self.estimated_x = x
        self.estimated_y = y
        
        # Store estimation history
        self.estimation_history.append((self.estimated_x, self.estimated_y))
        
        # Keep only last 100 estimations
        if len(self.estimation_history) > 100:
            self.estimation_history.pop(0)
    
    def get_estimated_position(self) -> Tuple[Optional[float], Optional[float]]:
        """Get the current estimated position."""
        return (self.estimated_x, self.estimated_y)
    
    def get_position_error(self) -> Optional[float]:
        """
        Calculate the error between true and estimated position.
        
        Returns:
            Distance error in meters, or None if no estimation exists
        """
        if self.estimated_x is None or self.estimated_y is None:
            return None
        
        dx = self.x - self.estimated_x
        dy = self.y - self.estimated_y
        
        return np.sqrt(dx**2 + dy**2)
    
    def randomize_position(self, x_min: float = -50, x_max: float = 50, 
                         y_min: float = -50, y_max: float = 50):
        """
        Randomize the rover position within specified bounds.
        
        Args:
            x_min, x_max: X coordinate bounds
            y_min, y_max: Y coordinate bounds
        """
        new_x = np.random.uniform(x_min, x_max)
        new_y = np.random.uniform(y_min, y_max)
        
        self.set_position(new_x, new_y)
    
    def get_status_info(self) -> dict:
        """Get comprehensive status information about the rover."""
        error = self.get_position_error()
        
        return {
            'true_position': self.get_position(),
            'estimated_position': self.get_estimated_position(),
            'position_error': error,
            'has_estimation': self.estimated_x is not None
        }
    
    def plot_true_position(self, ax, color='green', size=150):
        """
        Plot the true rover position.
        
        Args:
            ax: Matplotlib axis object
            color: Color of the rover marker
            size: Size of the rover marker
        """
        ax.scatter(self.x, self.y, c=color, s=size, marker='s', 
                  edgecolors='black', linewidth=2, label='True Rover')
        
        # Add rover label
        ax.annotate('Rover (True)', (self.x, self.y), 
                   xytext=(5, 5), textcoords='offset points', fontsize=9, fontweight='bold')
    
    def plot_estimated_position(self, ax, color='orange', size=120):
        """
        Plot the estimated rover position.
        
        Args:
            ax: Matplotlib axis object
            color: Color of the estimated position marker
            size: Size of the estimated position marker
        """
        if self.estimated_x is not None and self.estimated_y is not None:
            ax.scatter(self.estimated_x, self.estimated_y, c=color, s=size, marker='D', 
                      edgecolors='black', linewidth=2, label='Estimated Rover', alpha=0.8)
            
            # Add estimation label
            ax.annotate('Rover (Est)', (self.estimated_x, self.estimated_y), 
                       xytext=(5, -15), textcoords='offset points', fontsize=9, fontweight='bold')
    
    def plot_error_line(self, ax, color='purple', linewidth=2, alpha=0.7):
        """
        Plot a line showing the error between true and estimated position.
        
        Args:
            ax: Matplotlib axis object
            color: Color of the error line
            linewidth: Width of the error line
            alpha: Transparency of the error line
        """
        if self.estimated_x is not None and self.estimated_y is not None:
            ax.plot([self.x, self.estimated_x], [self.y, self.estimated_y], 
                   color=color, linewidth=linewidth, alpha=alpha, 
                   linestyle='--', label='Position Error')
    
    def plot_position_history(self, ax, color='lightgreen', alpha=0.5):
        """
        Plot the history of rover positions.
        
        Args:
            ax: Matplotlib axis object
            color: Color of the position history
            alpha: Transparency of the history markers
        """
        if len(self.position_history) > 1:
            x_hist = [pos[0] for pos in self.position_history[:-1]]  # Exclude current position
            y_hist = [pos[1] for pos in self.position_history[:-1]]
            
            ax.scatter(x_hist, y_hist, c=color, s=20, alpha=alpha, marker='o')
    
    def plot_estimation_history(self, ax, color='lightyellow', alpha=0.5):
        """
        Plot the history of rover position estimations.
        
        Args:
            ax: Matplotlib axis object
            color: Color of the estimation history
            alpha: Transparency of the history markers
        """
        if len(self.estimation_history) > 1:
            x_hist = [pos[0] for pos in self.estimation_history[:-1] if pos[0] is not None]
            y_hist = [pos[1] for pos in self.estimation_history[:-1] if pos[1] is not None]
            
            if x_hist and y_hist:
                ax.scatter(x_hist, y_hist, c=color, s=20, alpha=alpha, marker='D')
    
    def clear_history(self):
        """Clear position and estimation history."""
        self.position_history.clear()
        self.estimation_history.clear()
    
    def __repr__(self):
        return f"Rover(pos=({self.x:.2f}, {self.y:.2f}), est=({self.estimated_x}, {self.estimated_y}))"