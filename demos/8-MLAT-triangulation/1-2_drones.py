# Multilateration
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Button, Slider
import random
import math

# Constants
GAMMA = 1.4  # Adiabatic index for air
R_GAS = 287.05  # Specific gas constant for dry air in J/(kg·K)
TEMPERATURE = 25  # Temperature in Celsius
SPEED_OF_SOUND = np.sqrt(GAMMA * R_GAS * (TEMPERATURE + 273.15))  # Speed of sound in m/s

# Global variables
drone1_pos = (-5, 0)  # Initial position of drone 1
drone2_pos = (5, 0)   # Initial position of drone 2
real_rover_pos = (0, 3)  # Initial position of the actual rover (for simulation)
estimated_rover_pos = None  # Will store the estimated rover position
distances = []  # Will store distances from drones to rover
running = False
show_all_solutions = True  # Whether to show both possible rover positions

def calculate_distance(pos1, pos2):
    """Calculate Euclidean distance between two points"""
    return np.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)

def simulate_signal_time_of_flight(drone_position, rover_position):
    """Simulate sending and receiving a signal between drone and rover"""
    # Calculate the distance between the drone and the rover
    distance = calculate_distance(drone_position, rover_position)
    # Simulate the round-trip time for the signal
    round_trip_time = distance / SPEED_OF_SOUND
    return round_trip_time * SPEED_OF_SOUND / 2  # One-way distance

def localize_rover(drone1, drone2, r1, r2):
    """
    Calculate rover position based on drone positions and distances
    
    Parameters:
    drone1: (x1, y1) position of first drone
    drone2: (x2, y2) position of second drone
    r1: distance from drone1 to rover
    r2: distance from drone2 to rover
    
    Returns:
    Two possible solutions as [(x_sol1, y_sol1), (x_sol2, y_sol2)]
    """
    x1, y1 = drone1
    x2, y2 = drone2
    
    # Distance between drones
    a = calculate_distance(drone1, drone2)
    
    # Check if solution exists
    if abs(r1 - r2) > a or r1 + r2 < a:
        print("No solution exists: drone distances are incompatible")
        return None
    
    # Calculate rover position using law of cosines and coordinate geometry
    # We're solving for the intersection of two circles:
    # Circle 1: center at drone1, radius r1
    # Circle 2: center at drone2, radius r2
    
    # Calculate intermediate values
    d_squared = (x2 - x1)**2 + (y2 - y1)**2
    d = math.sqrt(d_squared)
    
    # Using the law of cosines
    cos_angle = (r1**2 + d_squared - r2**2) / (2 * r1 * d)
    
    # Clamp cos_angle to [-1, 1] to handle floating point errors
    cos_angle = max(-1, min(1, cos_angle))
    
    # Distance from drone1 to the point on the line between drones where the height to the rover begins
    l = r1 * cos_angle
    
    # Normalized vector from drone1 to drone2
    if d > 0:
        ex = (x2 - x1) / d
        ey = (y2 - y1) / d
    else:
        # If drones are at the same position (should not happen in practice)
        return None
    
    # Calculate the point on the line between drones
    p_x = x1 + l * ex
    p_y = y1 + l * ey
    
    # Height of the triangle (distance from the rover to the line between drones)
    h_squared = r1**2 - l**2
    
    # Handle the case where h_squared is slightly negative due to numerical precision
    if h_squared < 0 and h_squared > -1e-10:
        h_squared = 0
    
    h = math.sqrt(h_squared)
    
    # Unit vector perpendicular to the line between drones
    nx = -ey
    ny = ex
    
    # Calculate the two possible rover positions
    rover_pos1 = (p_x + h * nx, p_y + h * ny)
    rover_pos2 = (p_x - h * nx, p_y - h * ny)
    
    return [rover_pos1, rover_pos2]

def update_plot():
    """Update the plot with current drone and rover positions"""
    ax.clear()
    
    # Set plot limits and labels
    ax.set_xlim(-10, 10)
    ax.set_ylim(-10, 10)
    ax.set_xlabel('X Coordinate (m)')
    ax.set_ylabel('Y Coordinate (m)')
    ax.set_title('Rover Localization with Two Drones')
    
    # Plot the drones
    ax.scatter(drone1_pos[0], drone1_pos[1], color='blue', s=100, marker='o', label='Drone 1', zorder=10)
    ax.scatter(drone2_pos[0], drone2_pos[1], color='green', s=100, marker='o', label='Drone 2', zorder=10)
    
    # Plot the actual rover position
    ax.scatter(real_rover_pos[0], real_rover_pos[1], color='red', s=200, marker='*', label='Actual Rover', zorder=10)
    
    # Calculate and plot distances from drones to rover
    r1 = calculate_distance(drone1_pos, real_rover_pos)
    r2 = calculate_distance(drone2_pos, real_rover_pos)
    
    # Plot distance circles
    circle1 = plt.Circle(drone1_pos, r1, fill=False, color='blue', linestyle='--', alpha=0.5)
    circle2 = plt.Circle(drone2_pos, r2, fill=False, color='green', linestyle='--', alpha=0.5)
    ax.add_patch(circle1)
    ax.add_patch(circle2)
    
    # Plot lines connecting drones to rover
    ax.plot([drone1_pos[0], real_rover_pos[0]], [drone1_pos[1], real_rover_pos[1]], 'b--', alpha=0.5)
    ax.plot([drone2_pos[0], real_rover_pos[0]], [drone2_pos[1], real_rover_pos[1]], 'g--', alpha=0.5)
    
    # Add distance labels
    midpoint1 = ((drone1_pos[0] + real_rover_pos[0])/2, (drone1_pos[1] + real_rover_pos[1])/2)
    midpoint2 = ((drone2_pos[0] + real_rover_pos[0])/2, (drone2_pos[1] + real_rover_pos[1])/2)
    ax.text(midpoint1[0], midpoint1[1], f'R1 = {r1:.2f}m', 
            fontsize=9, ha='center', va='center',
            bbox=dict(facecolor='white', alpha=0.7))
    ax.text(midpoint2[0], midpoint2[1], f'R2 = {r2:.2f}m', 
            fontsize=9, ha='center', va='center',
            bbox=dict(facecolor='white', alpha=0.7))
    
    # Calculate the estimated rover position
    solutions = localize_rover(drone1_pos, drone2_pos, r1, r2)
    
    if solutions:
        # Plot the estimated rover position(s)
        for i, solution in enumerate(solutions):
            if i == 0 or show_all_solutions:
                solution_color = 'purple' if i == 0 else 'orange'
                solution_label = 'Estimated Rover' if i == 0 else 'Alternative Position'
                ax.scatter(solution[0], solution[1], color=solution_color, s=150, marker='x', 
                          label=solution_label, zorder=5)
                
                # Plot error lines
                if i == 0:  # Only for the first solution
                    ax.plot([solution[0], real_rover_pos[0]], 
                            [solution[1], real_rover_pos[1]], 
                            'r-', alpha=0.5, linewidth=1)
                    
                    # Calculate and display error
                    error = calculate_distance(solution, real_rover_pos)
                    error_text = f'Error: {error:.2f}m'
                    ax.text(0, 9, error_text, fontsize=12, ha='center',
                            bbox=dict(facecolor='white', alpha=0.7))
        
        # Plot the distance between drones
        ax.plot([drone1_pos[0], drone2_pos[0]], [drone1_pos[1], drone2_pos[1]], 'k-', alpha=0.7)
        drone_dist = calculate_distance(drone1_pos, drone2_pos)
        drone_mid = ((drone1_pos[0] + drone2_pos[0])/2, (drone1_pos[1] + drone2_pos[1])/2)
        ax.text(drone_mid[0], drone_mid[1] - 0.5, f'A = {drone_dist:.2f}m', 
                fontsize=9, ha='center', va='center',
                bbox=dict(facecolor='white', alpha=0.7))
    
    # Add grid for better visualization
    ax.grid(True, linestyle='--', alpha=0.5)
    
    # Add legend
    ax.legend(loc='lower right')
    
    # Draw the updated plot
    fig.canvas.draw()

def start_simulation(event):
    """Start the simulation with random rover position"""
    global real_rover_pos, running
    
    # Generate a random rover position
    real_rover_pos = (random.uniform(-8, 8), random.uniform(-8, 8))
    running = True
    update_plot()

def toggle_solutions(event):
    """Toggle showing all solutions vs just one"""
    global show_all_solutions
    show_all_solutions = not show_all_solutions
    update_plot()

def update_drone1_x(val):
    """Update x-position of drone 1"""
    global drone1_pos
    drone1_pos = (val, drone1_pos[1])
    update_plot()

def update_drone1_y(val):
    """Update y-position of drone 1"""
    global drone1_pos
    drone1_pos = (drone1_pos[0], val)
    update_plot()

def update_drone2_x(val):
    """Update x-position of drone 2"""
    global drone2_pos
    drone2_pos = (val, drone2_pos[1])
    update_plot()

def update_drone2_y(val):
    """Update y-position of drone 2"""
    global drone2_pos
    drone2_pos = (drone2_pos[0], val)
    update_plot()

# Create figure and axes
fig, ax = plt.subplots(figsize=(10, 10))
plt.subplots_adjust(bottom=0.3)

# Create buttons
ax_start = plt.axes([0.6, 0.05, 0.3, 0.05])
ax_toggle = plt.axes([0.1, 0.05, 0.3, 0.05])
btn_start = Button(ax_start, 'Randomize Rover')
btn_toggle = Button(ax_toggle, 'Toggle Solutions')

# Create sliders
ax_drone1_x = plt.axes([0.25, 0.2, 0.65, 0.03])
ax_drone1_y = plt.axes([0.25, 0.15, 0.65, 0.03])
ax_drone2_x = plt.axes([0.25, 0.1, 0.65, 0.03])
ax_drone2_y = plt.axes([0.25, 0.05, 0.65, 0.03])

slider_drone1_x = Slider(ax_drone1_x, 'Drone 1 X', -9, 9, valinit=drone1_pos[0])
slider_drone1_y = Slider(ax_drone1_y, 'Drone 1 Y', -9, 9, valinit=drone1_pos[1])
slider_drone2_x = Slider(ax_drone2_x, 'Drone 2 X', -9, 9, valinit=drone2_pos[0])
slider_drone2_y = Slider(ax_drone2_y, 'Drone 2 Y', -9, 9, valinit=drone2_pos[1])

# Connect events
btn_start.on_clicked(start_simulation)
btn_toggle.on_clicked(toggle_solutions)
slider_drone1_x.on_changed(update_drone1_x)
slider_drone1_y.on_changed(update_drone1_y)
slider_drone2_x.on_changed(update_drone2_x)
slider_drone2_y.on_changed(update_drone2_y)

# Initial plot
update_plot()

# Show plot
plt.show()
