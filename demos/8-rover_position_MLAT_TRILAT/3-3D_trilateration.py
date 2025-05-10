# 3-3D_trilateration.py

# Comprehensive 3D trilateration using known distances from rover
# trilateration relies on distance measurements, while triangulation uses angle measurements

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Button, TextBox, Slider, CheckButtons
from mpl_toolkits.mplot3d import Axes3D
import random

plt.style.use('dark_background')

# Constants
GAMMA = 1.4
R_GAS = 287.05
TEMPERATURE = 25
SPEED_OF_SOUND = np.sqrt(GAMMA * R_GAS * (TEMPERATURE + 273.15))
NUM_DRONES = 7
ROVER_ON_HILL = 10  # degrees
MIN_DRONE_SEPARATION = 1.5  # Minimum distance between drones
MIN_DRONE_SAME_DIST_TO_ROVER = 2.0  # Minimum distance difference to rover

# Globals
drone_positions = []
real_rover_pos = (0, 3, 2)
estimated_rover_pos = None
hill_plane = None
show_paths = True
show_spheres = True
show_intersections = True

def calculate_distance(pos1, pos2):
    return np.linalg.norm(np.array(pos1) - np.array(pos2))

def simulate_signal_time_of_flight(drone_position, rover_position):
    distance = calculate_distance(drone_position, rover_position)
    return distance / SPEED_OF_SOUND

def localize_rover_plane_intersection(drone_positions, distances):
    A = []
    b = []
    n = len(drone_positions)
    for i in range(n):
        for j in range(i+1, n):
            center1 = drone_positions[i]
            radius1 = distances[i]
            center2 = drone_positions[j]
            radius2 = distances[j]
            circle_center, normal, h, d = calculate_circle_of_intersection(center1, radius1, center2, radius2)
            if circle_center is None:
                continue
            A_row = [normal[0], normal[1], normal[2]]
            A.append(A_row)
            b.append(np.dot(normal, circle_center))
    if len(A) < 1:
        x_avg = np.mean([p[0] for p in drone_positions])
        y_avg = np.mean([p[1] for p in drone_positions])
        z_avg = np.mean([p[2] for p in drone_positions])
        return (x_avg, y_avg, z_avg)
    A_np = np.array(A)
    b_np = np.array(b)
    result, _, _, _ = np.linalg.lstsq(A_np, b_np, rcond=None)
    return tuple(result)

def compute_hill_plane():
    global hill_plane
    rover_x, rover_y, rover_z = real_rover_pos
    angle_rad = np.radians(ROVER_ON_HILL)
    direction = np.arctan2(rover_y, rover_x)
    nx = -np.sin(direction) * np.sin(angle_rad)
    ny = np.cos(direction) * np.sin(angle_rad)
    nz = -np.cos(angle_rad)
    d = nx * rover_x + ny * rover_y + nz * rover_z
    hill_plane = (nx, ny, nz, d)

def z_from_plane(x, y):
    nx, ny, nz, d = hill_plane
    if nz == 0:
        return 0
    return (d - nx * x - ny * y) / nz

def generate_drones_above_hill():
    global drone_positions
    compute_hill_plane()
    drone_positions = []
    MAX_ATTEMPTS = 100

    for _ in range(NUM_DRONES):
        attempts = 0
        placed = False
        
        while not placed and attempts < MAX_ATTEMPTS:
            x = random.uniform(-8, 8)
            y = random.uniform(-8, 8)
            z_min = z_from_plane(x, y)
            z = random.uniform(z_min + 0.5, z_min + 5.0)
            new_pos = (x, y, z)

            if z > z_min:
                valid_position = True
                new_dist = calculate_distance(new_pos, real_rover_pos)

                for existing_pos in drone_positions:
                    if calculate_distance(new_pos, existing_pos) < MIN_DRONE_SEPARATION:
                        valid_position = False
                        break
                    existing_dist = calculate_distance(existing_pos, real_rover_pos)
                    if abs(new_dist - existing_dist) < MIN_DRONE_SAME_DIST_TO_ROVER:
                        valid_position = False
                        break

                if valid_position or not drone_positions:
                    drone_positions.append(new_pos)
                    placed = True

                attempts += 1

        if not placed:
            print(f"Warning: Could not place drone {_} after {MAX_ATTEMPTS} attempts")

def reset_drones():
    generate_drones_above_hill()

def randomize_rover(event=None):
    global real_rover_pos
    real_rover_pos = (random.uniform(-8, 8), random.uniform(-8, 8), random.uniform(0, 5))
    compute_hill_plane()
    reset_drones()
    update_plot()

def randomize_drones(event=None):
    reset_drones()
    update_plot()

def update_num_drones(text):
    global NUM_DRONES
    try:
        new_num = int(text)
        if 4 <= new_num <= 20:
            NUM_DRONES = new_num
            reset_drones()
            update_plot()
        else:
            print("Number of drones should be between 4 and 20.")
    except ValueError:
        print("Please enter a valid integer.")

def update_hill_angle(val):
    global ROVER_ON_HILL
    ROVER_ON_HILL = val
    compute_hill_plane()
    update_plot()

def toggle_visualization(event):
    global show_paths, show_spheres, show_intersections
    status = check_buttons.get_status()
    show_paths = status[0]
    show_spheres = status[1]
    show_intersections = status[2]
    update_plot()

def plot_sphere(center, radius, color='blue', alpha=0.1, resolution=20):
    u = np.linspace(0, 2 * np.pi, resolution)
    v = np.linspace(0, np.pi, resolution)
    x = center[0] + radius * np.outer(np.cos(u), np.sin(v))
    y = center[1] + radius * np.outer(np.sin(u), np.sin(v))
    z = center[2] + radius * np.outer(np.ones(np.size(u)), np.cos(v))
    return ax.plot_surface(x, y, z, color=color, alpha=alpha, shade=True)

def calculate_circle_of_intersection(center1, radius1, center2, radius2):
    center1 = np.array(center1)
    center2 = np.array(center2)
    d = np.linalg.norm(center2 - center1)
    if d > radius1 + radius2 or d < abs(radius1 - radius2) or d == 0:
        return None, None, None, 0
    a = (radius1**2 - radius2**2 + d**2) / (2 * d)
    h = np.sqrt(radius1**2 - a**2)
    circle_center = center1 + a * (center2 - center1) / d
    normal = (center2 - center1) / d
    return circle_center, normal, h, d

def plot_intersection_circle(center1, radius1, center2, radius2, color='purple', alpha=0.5, resolution=100):
    circle_center, normal, radius, d = calculate_circle_of_intersection(center1, radius1, center2, radius2)
    if circle_center is None:
        return
    if abs(normal[0]) > abs(normal[1]):
        basis1 = np.array([-normal[2], 0, normal[0]])
    else:
        basis1 = np.array([0, -normal[2], normal[1]])
    basis1 = basis1 / np.linalg.norm(basis1)
    basis2 = np.cross(normal, basis1)
    theta = np.linspace(0, 2 * np.pi, resolution)
    circle_points = circle_center[:, np.newaxis] + radius * (basis1[:, np.newaxis] * np.cos(theta) + basis2[:, np.newaxis] * np.sin(theta))
    ax.plot(circle_points[0], circle_points[1], circle_points[2], color=color, alpha=alpha)

def update_plot():
    global estimated_rover_pos
    if not drone_positions or not real_rover_pos:
        print("Plot skipped: positions not initialized.")
        return
        
    elev, azim = ax.elev, ax.azim

    distances = [calculate_distance(drone, real_rover_pos) for drone in drone_positions]
    estimated_rover_pos = localize_rover_plane_intersection(drone_positions, distances)

    ax.clear()
    ax.set_title("3D Drone Localization")
    ax.set_xlim([-10, 10])
    ax.set_ylim([-10, 10])
    ax.set_zlim([0, 12])
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    ax.view_init(elev=elev, azim=azim)

    plot_hill_plane()

    for i, drone_pos in enumerate(drone_positions):
        ax.scatter(drone_pos[0], drone_pos[1], drone_pos[2], c='blue', s=50)
        ax.text(drone_pos[0], drone_pos[1], drone_pos[2], f'D{i}', fontsize=8)
        if show_paths:
            ax.plot([drone_pos[0], real_rover_pos[0]], 
                    [drone_pos[1], real_rover_pos[1]], 
                    [drone_pos[2], real_rover_pos[2]], 
                    'k--', alpha=0.3)
        if show_spheres:
            radius = calculate_distance(drone_pos, real_rover_pos)
            plot_sphere(drone_pos, radius, color='blue', alpha=0.1)
    
    if show_intersections and len(drone_positions) >= 2:
        for i in range(len(drone_positions)):
            for j in range(i+1, len(drone_positions)):
                radius_i = distances[i]
                radius_j = distances[j]
                plot_intersection_circle(drone_positions[i], radius_i, 
                                        drone_positions[j], radius_j, 
                                        color='purple', alpha=0.7)

    x, y, z = real_rover_pos
    ax.scatter(x, y, z, c='green', s=80, label='Real Rover')
    if estimated_rover_pos:
        xe, ye, ze = estimated_rover_pos
        ax.scatter(xe, ye, ze, c='red', s=80, marker='^', label='Estimated Rover')
        error = calculate_distance(real_rover_pos, estimated_rover_pos)
        ax.text(-9, -9, 11, f'Error: {error:.3f} m', fontsize=10)

    ax.legend()
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.3)
    ax.text2D(0.02, 0.98, 'Mouse Controls:\n• Left click + drag: Rotate view\n• Right click + drag: Zoom in/out\n• Middle click + drag: Pan view', 
             transform=ax.transAxes, fontsize=9, verticalalignment='top', bbox=props)
    
    plt.draw()

def plot_hill_plane():
    if not hill_plane:
        return
    nx, ny, nz, d = hill_plane
    x = np.linspace(-10, 10, 20)
    y = np.linspace(-10, 10, 20)
    X, Y = np.meshgrid(x, y)
    Z = (d - nx * X - ny * Y) / nz
    ax.plot_surface(X, Y, Z, alpha=0.3, color='brown')

fig = plt.figure(figsize=(12, 10))
ax = fig.add_subplot(111, projection='3d')
plt.subplots_adjust(bottom=0.3, left=0.2)

ax.mouse_init()
ax.view_init(elev=30, azim=45)

btn_ax1 = plt.axes([0.2, 0.05, 0.2, 0.05])
btn1 = Button(btn_ax1, 'Randomize Rover')
btn1.on_clicked(randomize_rover)

btn_ax2 = plt.axes([0.5, 0.05, 0.2, 0.05])
btn2 = Button(btn_ax2, 'Randomize Drones')
btn2.on_clicked(randomize_drones)

text_ax = plt.axes([0.2, 0.15, 0.2, 0.05])
text_box = TextBox(text_ax, 'Num Drones', initial=str(NUM_DRONES))
text_box.on_submit(update_num_drones)

slider_ax = plt.axes([0.5, 0.15, 0.2, 0.05])
angle_slider = Slider(slider_ax, 'Hill Angle', 0, 90, valinit=ROVER_ON_HILL)
angle_slider.on_changed(update_hill_angle)

check_ax = plt.axes([0.05, 0.25, 0.15, 0.15])
check_buttons = CheckButtons(check_ax, ['Show Paths', 'Show Spheres', 'Show Intersections'], 
                           [show_paths, show_spheres, show_intersections])
check_buttons.on_clicked(toggle_visualization)

reset_drones()
update_plot()
plt.show()