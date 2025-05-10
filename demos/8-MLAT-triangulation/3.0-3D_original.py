# can't handle certain instances, need to find out why - intersecting spheres, planes, lines, etc...
# might have two drones that are equidistant - might be throwing error.


'''
Coincident Drone Positions:
If two or more drones are positioned in such a way that they are equidistant or very close to each other, they may generate identical or nearly identical distances to the rover. This can lead to numerical instability in the localization algorithm. Specifically, when the positions of drones are nearly identical, the optimization algorithm (least_squares) may struggle because there is insufficient diversity in the data for accurate triangulation or multilateration.

Singular or Near-Singular Matrix in Least Squares:
In the case of multilateration (where distances from drones are used to estimate the rover's position), if the drone positions are collinear or too close, the optimization problem becomes nearly degenerate. The Jacobian matrix for the least squares problem may become singular or near-singular, causing the algorithm to fail or return incorrect results. This can happen when drone positions are highly symmetric or aligned in a way that the problem lacks sufficient independent constraints to solve for the rover's position.

Sphere-Sphere Intersection Issues:
Your sphere_sphere_intersection function attempts to find the intersection between spheres, which assumes that two spheres will intersect at a set of points (often a circle). However, when drone positions are too close to each other or identical, the intersection points may not be well-defined or could overlap significantly. This leads to a problem when trying to determine a valid intersection. As the error message suggests, this happens when no valid intersection is found, and the system falls back to multilateration.
'''

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Button, TextBox
from mpl_toolkits.mplot3d import Axes3D
import random
from scipy.optimize import least_squares

# Constants
GAMMA = 1.4
R_GAS = 287.05
TEMPERATURE = 25  # Celsius
SPEED_OF_SOUND = np.sqrt(GAMMA * R_GAS * (TEMPERATURE + 273.15))  # m/s
NUM_DRONES = 7

# Globals
drone_positions = []
real_rover_pos = (0, 3, 2)
estimated_rover_pos = None
show_distances = True
show_spheres = True

def calculate_distance(pos1, pos2):
    return np.linalg.norm(np.array(pos1) - np.array(pos2))

def simulate_signal_time_of_flight(drone_position, rover_position):
    distance = calculate_distance(drone_position, rover_position)
    return distance / SPEED_OF_SOUND

def objective_function(point, drone_positions, distances):
    x, y, z = point
    return [calculate_distance((x, y, z), drone_positions[i]) - distances[i] for i in range(len(drone_positions))]

def localize_rover_multilateration(drone_positions, distances):
    x_avg = np.mean([p[0] for p in drone_positions])
    y_avg = np.mean([p[1] for p in drone_positions])
    z_avg = np.mean([p[2] for p in drone_positions])
    initial_guess = [x_avg, y_avg, z_avg]

    result = least_squares(objective_function, initial_guess, args=(drone_positions, distances), method='lm')
    return tuple(result.x) if result.success else initial_guess

def reset_drones():
    global drone_positions
    drone_positions = [
        (random.uniform(-8, 8), random.uniform(-8, 8), random.uniform(-8, 8))
        for _ in range(NUM_DRONES)
    ]

def sphere_sphere_intersection(c1, r1, c2, r2):
    """Find the intersection of two spheres in 3D."""
    x0, y0, z0 = c1
    x1, y1, z1 = c2
    d = np.linalg.norm(np.array(c1) - np.array(c2))

    if d > r1 + r2 or d < abs(r1 - r2) or d == 0:
        return []  # No intersection

    # Find intersection circle center
    a = (r1**2 - r2**2 + d**2) / (2 * d)
    h = np.sqrt(r1**2 - a**2)
    xm = x0 + a * (x1 - x0) / d
    ym = y0 + a * (y1 - y0) / d
    zm = z0 + a * (z1 - z0) / d

    # Circle normal vector
    dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
    nx, ny, nz = dy, -dx, 0  # Tangent to the plane formed by both spheres

    # Compute the intersection circle points
    intersection_points = []
    for t in np.linspace(0, 2 * np.pi, 20):
        x = xm + h * np.cos(t) * nx
        y = ym + h * np.cos(t) * ny
        z = zm + h * np.sin(t) * nz
        intersection_points.append((x, y, z))

    return intersection_points

def exact_intersection_3d(drone_positions, distances, tolerance=1e-2):
    """Return the 3D intersection with the most spheres."""
    intersections = []

    # Generate all pairwise sphere intersections
    for i in range(len(drone_positions)):
        for j in range(i + 1, len(drone_positions)):
            points = sphere_sphere_intersection(
                drone_positions[i], distances[i],
                drone_positions[j], distances[j]
            )
            intersections.extend(points)

    if not intersections:
        print("No intersections found, falling back to multilateration.")
        return localize_rover_multilateration(drone_positions, distances)

    # Count how many spheres each intersection point lies within
    best_point = None
    max_count = 0

    for point in intersections:
        count = sum(
            abs(calculate_distance(point, drone_positions[k]) - distances[k]) <= tolerance
            for k in range(len(drone_positions))
        )
        if count > max_count:
            max_count = count
            best_point = point

    if best_point is not None and max_count >= 3:
        return best_point
    else:
        print("Could not find a point on 3+ spheres. Falling back to multilateration.")
        return localize_rover_multilateration(drone_positions, distances)

def update_plot():
    global estimated_rover_pos
    ax.clear()

    ax.set_xlim(-10, 10)
    ax.set_ylim(-10, 10)
    ax.set_zlim(-10, 10)
    ax.set_xlabel('X (m)')
    ax.set_ylabel('Y (m)')
    ax.set_zlabel('Z (m)')
    ax.set_title(f'3D Rover Localization with {NUM_DRONES} Drones')

    distances = [calculate_distance(drone, real_rover_pos) for drone in drone_positions]

    for i, (drone_pos, distance) in enumerate(zip(drone_positions, distances)):
        ax.scatter(*drone_pos, color='blue', s=100, marker='o')
        ax.text(*drone_pos, f'D{i+1}', fontsize=8)

        if show_distances:
            ax.plot([drone_pos[0], real_rover_pos[0]],
                    [drone_pos[1], real_rover_pos[1]],
                    [drone_pos[2], real_rover_pos[2]],
                    linestyle='--', color='gray', alpha=0.4)

        if show_spheres:
            u, v = np.mgrid[0:2 * np.pi:20j, 0:np.pi:10j]
            x = distance * np.cos(u) * np.sin(v) + drone_pos[0]
            y = distance * np.sin(u) * np.sin(v) + drone_pos[1]
            z = distance * np.cos(v) + drone_pos[2]
            ax.plot_surface(x, y, z, color='blue', alpha=0.05, linewidth=0)

    ax.scatter(*real_rover_pos, color='red', s=200, marker='*', label='Actual Rover')

    if len(drone_positions) >= 4:
        estimated_rover_pos = exact_intersection_3d(drone_positions, distances)
        ax.scatter(*estimated_rover_pos, color='purple', s=150, marker='x', label='Estimated Rover')

        error = calculate_distance(estimated_rover_pos, real_rover_pos)
        rover_info.set_text(
            f'Actual: ({real_rover_pos[0]:.2f}, {real_rover_pos[1]:.2f}, {real_rover_pos[2]:.2f})\n'
            f'Estimated: ({estimated_rover_pos[0]:.2f}, {estimated_rover_pos[1]:.2f}, {estimated_rover_pos[2]:.2f})\n'
            f'Error: {error:.2f} m'
        )
    else:
        rover_info.set_text("Need at least 4 drones for 3D localization.")

    ax.legend()
    plt.draw()

def randomize_rover(event):
    global real_rover_pos
    real_rover_pos = (
        random.uniform(-8, 8),
        random.uniform(-8, 8),
        random.uniform(-8, 8)
    )
    update_plot()

def randomize_drones(event):
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
            print("Number of drones should be between 4 and 20 for 3D localization.")
    except ValueError:
        print("Please enter a valid integer.")

def toggle_distances(event):
    global show_distances
    show_distances = not show_distances
    update_plot()

def toggle_spheres(event):
    global show_spheres
    show_spheres = not show_spheres
    update_plot()

# Plot and UI setup
fig = plt.figure(figsize=(10, 10))
ax = fig.add_subplot(111, projection='3d')
plt.subplots_adjust(bottom=0.2, top=0.88)

# UI Widgets
ax_rand_rover = plt.axes([0.2, 0.05, 0.2, 0.05])
ax_rand_drones = plt.axes([0.45, 0.05, 0.2, 0.05])
ax_num_drones = plt.axes([0.7, 0.05, 0.1, 0.05])
ax_apply_num = plt.axes([0.82, 0.05, 0.1, 0.05])

ax_toggle_distances = plt.axes([0.2, 0.91, 0.2, 0.05])
ax_toggle_spheres = plt.axes([0.45, 0.91, 0.2, 0.05])

btn_rand_rover = Button(ax_rand_rover, 'Randomize Rover')
btn_rand_drones = Button(ax_rand_drones, 'Randomize Drones')
txt_num_drones = TextBox(ax_num_drones, 'Drones: ', initial=str(NUM_DRONES))

btn_toggle_distances = Button(ax_toggle_distances, 'Toggle Distances')
btn_toggle_spheres = Button(ax_toggle_spheres, 'Toggle Spheres')

btn_apply_num = Button(ax_apply_num, 'Apply Count')

rover_info = plt.figtext(0.5, 0.12, "", fontsize=10, ha="center",
                         bbox=dict(facecolor='white', edgecolor='black', boxstyle='round,pad=1'))

# Event bindings
btn_rand_rover.on_clicked(randomize_rover)
btn_rand_drones.on_clicked(randomize_drones)
txt_num_drones.on_submit(update_num_drones)
btn_toggle_distances.on_clicked(toggle_distances)
btn_toggle_spheres.on_clicked(toggle_spheres)
btn_apply_num.on_clicked(lambda event: update_num_drones(txt_num_drones.text))

# Initialize
reset_drones()
rover_info.set_text("")
update_plot()
plt.show()
