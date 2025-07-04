import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Button, Slider
import matplotlib.patches as patches
from typing import List, Tuple, Optional
import random

# Import our modules
from drone import Drone
from rover import Rover
# Note: You'll need to save these files as separate .py files:
# - drone.py (from document)
# - rover.py (from document)  
# - multilateration_maths.py (from document)
# - occlusion_maths.py (created above)

# For now, importing from the provided files
from multilateration_maths import MultilaterationSolver
from occlusion_maths import OcclusionDetector

class Obstacle:
    """Simple obstacle class for simulation."""
    def __init__(self, x: float, y: float, radius: float):
        self.x = x
        self.y = y
        self.radius = radius
        self.selected = False
    
    def contains_point(self, x: float, y: float) -> bool:
        """Check if point is inside obstacle."""
        return (x - self.x)**2 + (y - self.y)**2 <= self.radius**2
    
    def move_to(self, x: float, y: float):
        """Move obstacle to new position."""
        self.x = x
        self.y = y

class OcclusionSimulation:
    """Interactive simulation for target occlusion detection."""
    
    def __init__(self):
        """Initialize the simulation."""
        self.fig, self.ax = plt.subplots(figsize=(14, 10))
        self.fig.subplots_adjust(bottom=0.25, right=0.85)
        
        # Initialize components
        self.drones = []
        self.rover = Rover(0, 0)
        self.obstacles = []
        self.multilateration_solver = MultilaterationSolver()
        self.occlusion_detector = OcclusionDetector(geometric_tolerance=0.5)
        
        # Simulation state
        self.selected_obstacle = None
        self.dragging = False
        self.last_occlusion_result = None
        
        # Create initial setup
        self._create_initial_setup()
        self._create_ui_elements()
        self._connect_events()
        
        # Update display
        self._update_simulation()
    
    def _create_initial_setup(self):
        """Create initial drones, rover, and obstacles."""
        # Create 4 drones in a square pattern
        drone_positions = [(-30, -30), (30, -30), (30, 30), (-30, 30)]
        for i, (x, y) in enumerate(drone_positions):
            drone = Drone(x, y, drone_id=i)
            self.drones.append(drone)
        
        # Create some obstacles
        self.obstacles = [
            Obstacle(-10, 5, 3),
            Obstacle(15, -10, 4),
            Obstacle(-5, -20, 2.5)
        ]
        
        # Place rover at origin
        self.rover.set_position(0, 0)
    
    def _create_ui_elements(self):
        """Create UI buttons and sliders."""
        # Button positions
        button_width = 0.12
        button_height = 0.04
        button_spacing = 0.02
        
        # Randomize buttons
        ax_rand_rover = plt.axes([0.1, 0.15, button_width, button_height])
        self.btn_rand_rover = Button(ax_rand_rover, 'Random Rover')
        self.btn_rand_rover.on_clicked(self._randomize_rover)
        
        ax_rand_drones = plt.axes([0.1 + button_width + button_spacing, 0.15, button_width, button_height])
        self.btn_rand_drones = Button(ax_rand_drones, 'Random Drones')
        self.btn_rand_drones.on_clicked(self._randomize_drones)
        
        # Drone count slider
        ax_drone_count = plt.axes([0.1, 0.08, 0.25, 0.03])
        self.slider_drone_count = Slider(ax_drone_count, 'Drones', 3, 8, valinit=4, valfmt='%d')
        self.slider_drone_count.on_changed(self._update_drone_count)
        
        # Add/Remove obstacle buttons
        ax_add_obs = plt.axes([0.1, 0.02, button_width, button_height])
        self.btn_add_obs = Button(ax_add_obs, 'Add Obstacle')
        self.btn_add_obs.on_clicked(self._add_obstacle)
        
        ax_remove_obs = plt.axes([0.1 + button_width + button_spacing, 0.02, button_width, button_height])
        self.btn_remove_obs = Button(ax_remove_obs, 'Remove Obstacle')
        self.btn_remove_obs.on_clicked(self._remove_obstacle)
        
        # Clear obstacles button
        ax_clear_obs = plt.axes([0.1 + 2*(button_width + button_spacing), 0.02, button_width, button_height])
        self.btn_clear_obs = Button(ax_clear_obs, 'Clear Obstacles')
        self.btn_clear_obs.on_clicked(self._clear_obstacles)
        
        # Update button
        ax_update = plt.axes([0.7, 0.02, button_width, button_height])
        self.btn_update = Button(ax_update, 'Update Sim')
        self.btn_update.on_clicked(self._force_update)
    
    def _connect_events(self):
        """Connect mouse events for interaction."""
        self.fig.canvas.mpl_connect('button_press_event', self._on_click)
        self.fig.canvas.mpl_connect('button_release_event', self._on_release)
        self.fig.canvas.mpl_connect('motion_notify_event', self._on_motion)
    
    def _on_click(self, event):
        """Handle mouse click events."""
        if event.inaxes != self.ax:
            return
        
        x, y = event.xdata, event.ydata
        
        # Check if clicking on an obstacle
        for obstacle in self.obstacles:
            if obstacle.contains_point(x, y):
                self.selected_obstacle = obstacle
                obstacle.selected = True
                self.dragging = True
                break
        else:
            # Deselect all obstacles
            for obstacle in self.obstacles:
                obstacle.selected = False
            self.selected_obstacle = None
        
        self._update_display()
    
    def _on_release(self, event):
        """Handle mouse release events."""
        if self.selected_obstacle:
            self.selected_obstacle.selected = False
        self.selected_obstacle = None
        self.dragging = False
        
        # Update simulation after moving obstacle
        self._update_simulation()
    
    def _on_motion(self, event):
        """Handle mouse motion events."""
        if not self.dragging or not self.selected_obstacle or event.inaxes != self.ax:
            return
        
        x, y = event.xdata, event.ydata
        self.selected_obstacle.move_to(x, y)
        self._update_display()
    
    def _randomize_rover(self, event):
        """Randomize rover position."""
        self.rover.randomize_position(-40, 40, -40, 40)
        self._update_simulation()
    
    def _randomize_drones(self, event):
        """Randomize drone positions."""
        for drone in self.drones:
            drone.randomize_position(-50, 50, -50, 50)
        self._update_simulation()
    
    def _update_drone_count(self, val):
        """Update number of drones."""
        new_count = int(self.slider_drone_count.val)
        current_count = len(self.drones)
        
        if new_count > current_count:
            # Add drones
            for i in range(current_count, new_count):
                drone = Drone(0, 0, drone_id=i)
                drone.randomize_position(-50, 50, -50, 50)
                self.drones.append(drone)
        elif new_count < current_count:
            # Remove drones
            self.drones = self.drones[:new_count]
        
        self._update_simulation()
    
    def _add_obstacle(self, event):
        """Add a new obstacle at random position."""
        x = random.uniform(-30, 30)
        y = random.uniform(-30, 30)
        radius = random.uniform(2, 5)
        
        obstacle = Obstacle(x, y, radius)
        self.obstacles.append(obstacle)
        self._update_simulation()
    
    def _remove_obstacle(self, event):
        """Remove the last obstacle."""
        if self.obstacles:
            self.obstacles.pop()
            self._update_simulation()
    
    def _clear_obstacles(self, event):
        """Remove all obstacles."""
        self.obstacles.clear()
        self._update_simulation()
    
    def _force_update(self, event):
        """Force update of simulation."""
        self._update_simulation()
    
    def _update_simulation(self):
        """Update the entire simulation."""
        # Simulate ToF measurements
        rover_pos = self.rover.get_position()
        
        for drone in self.drones:
            drone.simulate_tof_measurement(
                rover_pos[0], rover_pos[1], 
                obstacles=self.obstacles,
                noise_std=0.1
            )
        
        # Perform multilateration
        estimated_pos = self.multilateration_solver.solve(self.drones, method='hybrid')
        if estimated_pos:
            self.rover.set_estimated_position(estimated_pos[0], estimated_pos[1])
        
        # Detect occlusion
        self.last_occlusion_result = self.occlusion_detector.detect_occlusion(self.drones, rover_pos)
        
        # Print results
        self._print_results()
        
        # Update display
        self._update_display()
    
    def _print_results(self):
        """Print simulation results to console."""
        print("\n" + "="*60)
        print("SIMULATION UPDATE")
        print("="*60)
        
        # Rover information
        rover_pos = self.rover.get_position()
        rover_est = self.rover.get_estimated_position()
        error = self.rover.get_position_error()
        
        print(f"Rover True Position: ({rover_pos[0]:.2f}, {rover_pos[1]:.2f})")
        if rover_est[0] is not None:
            print(f"Rover Estimated Position: ({rover_est[0]:.2f}, {rover_est[1]:.2f})")
            print(f"Position Error: {error:.3f}m")
        else:
            print("Rover Position: Unable to estimate")
        
        # Occlusion results
        if self.last_occlusion_result:
            self.occlusion_detector.print_occlusion_report(self.last_occlusion_result, self.drones)
        
        # Drone details
        print("\nDrone Details:")
        for drone in self.drones:
            status = "OCCLUDED" if drone.is_occluded else "CLEAR"
            print(f"  Drone {drone.drone_id}: Pos=({drone.x:.1f}, {drone.y:.1f}), "
                  f"Dist={drone.measured_distance:.2f}m, Status={status}")
    
    def _update_display(self):
        """Update the visual display."""
        self.ax.clear()
        
        # Set up the plot
        self.ax.set_xlim(-60, 60)
        self.ax.set_ylim(-60, 60)
        self.ax.set_aspect('equal')
        self.ax.grid(True, alpha=0.3)
        self.ax.set_title('Target Occlusion Detection Simulation', fontsize=14, fontweight='bold')
        self.ax.set_xlabel('X Position (meters)')
        self.ax.set_ylabel('Y Position (meters)')
        
        # Plot obstacles
        for obstacle in self.obstacles:
            color = 'darkred' if obstacle.selected else 'red'
            alpha = 0.8 if obstacle.selected else 0.6
            
            circle = plt.Circle((obstacle.x, obstacle.y), obstacle.radius, 
                              color=color, alpha=alpha, label='Obstacles' if obstacle == self.obstacles[0] else "")
            self.ax.add_patch(circle)
            
            # Add obstacle label
            self.ax.annotate(f'R={obstacle.radius:.1f}', 
                           (obstacle.x, obstacle.y), 
                           ha='center', va='center', fontsize=8, color='white', fontweight='bold')
        
        # Plot drones and their range circles
        for drone in self.drones:
            # Plot range circle first (behind drone)
            drone.plot_range_circle(self.ax)
            
            # Plot drone
            drone.plot_drone(self.ax)
            
            # Plot line to rover
            rover_pos = self.rover.get_position()
            drone.plot_line_to_target(self.ax, rover_pos[0], rover_pos[1])
        
        # Plot rover
        self.rover.plot_true_position(self.ax)
        self.rover.plot_estimated_position(self.ax)
        self.rover.plot_error_line(self.ax)
        
        # Add legend
        handles, labels = self.ax.get_legend_handles_labels()
        # Remove duplicate labels
        unique_labels = []
        unique_handles = []
        for handle, label in zip(handles, labels):
            if label not in unique_labels:
                unique_labels.append(label)
                unique_handles.append(handle)
        
        self.ax.legend(unique_handles, unique_labels, loc='upper right', bbox_to_anchor=(1.15, 1))
        
        # Add status text
        self._add_status_text()
        
        # Refresh canvas
        self.fig.canvas.draw()
    
    def _add_status_text(self):
        """Add status text to the plot."""
        status_text = []
        
        # Occlusion status
        if self.last_occlusion_result:
            if self.last_occlusion_result.total_occlusions > 0:
                status_text.append(f"🚫 TARGET OCCLUDED FROM {self.last_occlusion_result.total_occlusions} DRONE(S)")
                status_text.append(f"Occluded Drones: {self.last_occlusion_result.occluded_drones}")
            else:
                status_text.append("✅ NO OCCLUSION DETECTED")
            
            status_text.append(f"Detection Confidence: {self.last_occlusion_result.detection_confidence:.2f}")
        
        # Position error
        error = self.rover.get_position_error()
        if error is not None:
            status_text.append(f"Position Error: {error:.3f}m")
        
        # Combine text
        full_text = "\n".join(status_text)
        
        # Add text box
        self.ax.text(0.02, 0.98, full_text, transform=self.ax.transAxes, 
                    fontsize=10, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))
    
    def run(self):
        """Run the simulation."""
        plt.show()

def main():
    """Main function to run the simulation."""
    print("Starting Target Occlusion Detection Simulation...")
    print("Instructions:")
    print("- Click and drag red obstacles to move them")
    print("- Use buttons to randomize positions")
    print("- Adjust drone count with slider")
    print("- Watch console for detailed occlusion reports")
    print()
    
    sim = OcclusionSimulation()
    sim.run()

if __name__ == "__main__":
    main()