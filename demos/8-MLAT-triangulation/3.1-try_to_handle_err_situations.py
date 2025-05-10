import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Button, TextBox
from mpl_toolkits.mplot3d import Axes3D
import random
from scipy.optimize import least_squares
import time
from itertools import combinations

# Constants
GAMMA = 1.4
R_GAS = 287.05
TEMPERATURE = 25  # Celsius
SPEED_OF_SOUND = np.sqrt(GAMMA * R_GAS * (TEMPERATURE + 273.15))  # m/s
NUM_DRONES = 7

MIN_ANGLE_DIVERSITY = 20.0  # degrees
MIN_XYZ_POINTS = [-10, -10, -10]
MAX_XYZ_POINTS = [10, 10, 10]
ERROR_THRESH = 0.1  # meters

# Globals
drone_positions = []
real_rover_pos = (0, 3, 2)
estimated_rover_pos = None
show_distances = True
show_spheres = True
reposition_done = False

def calculate_distance(pos1, pos2):
    return np.linalg.norm(np.array(pos1) - np.array(pos2))

def simulate_signal_time_of_flight(drone_position, rover_position):
    distance = calculate_distance(drone_position, rover_position)
    return distance / SPEED_OF_SOUND

def objective_function(point, drone_positions, distances):
    x, y, z = point
    return [calculate_distance((x, y, z), drone_positions[i]) - distances[i]
            for i in range(len(drone_positions))]

def localize_rover_multilateration(drone_positions, distances):
    x_avg = np.mean([p[0] for p in drone_positions])
    y_avg = np.mean([p[1] for p in drone_positions])
    z_avg = np.mean([p[2] for p in drone_positions])
    initial_guess = [x_avg, y_avg, z_avg]

    result = least_squares(objective_function, initial_guess,
                           args=(drone_positions, distances), method='lm')
    if not result.success:
        print(f"Least squares did not converge: {result.message}")
        return initial_guess
    return tuple(result.x)

def reset_drones():
    global drone_positions
    drone_positions = [
        (random.uniform(-8, 8), random.uniform(-8, 8), random.uniform(-8, 8))
        for _ in range(NUM_DRONES)
    ]

def angular_diversity(drone_positions, rover_pos):
    """
    Check whether any 4 drones have a minimum pairwise angular separation >= MIN_ANGLE_DIVERSITY degrees.
    Returns True if such a set exists, False otherwise.
    """
    n = len(drone_positions)
    if n < 4:
        return False
    threshold = np.deg2rad(MIN_ANGLE_DIVERSITY)
    # Compute vectors from rover to drones
    vectors = [np.array(dp) - np.array(rover_pos) for dp in drone_positions]
    # Check all combinations of 4 drones
    for combo in combinations(range(n), 4):
        min_angle = np.inf
        # compute pairwise angles
        for i in range(4):
            for j in range(i+1, 4):
                v1 = vectors[combo[i]]
                v2 = vectors[combo[j]]
                norm1 = np.linalg.norm(v1)
                norm2 = np.linalg.norm(v2)
                if norm1 == 0 or norm2 == 0:
                    continue
                cos_val = np.dot(v1, v2) / (norm1 * norm2)
                cos_val = np.clip(cos_val, -1.0, 1.0)
                angle = np.arccos(cos_val)
                if angle < min_angle:
                    min_angle = angle
        # If this group's min pairwise angle meets threshold
        if min_angle >= threshold:
            return True
    return False

def sphere_sphere_intersection(c1, r1, c2, r2):
    """Find the intersection of two spheres in 3D."""
    x0, y0, z0 = c1
    x1, y1, z1 = c2
    d = np.linalg.norm(np.array(c1) - np.array(c2))

    # Check for no intersection or infinite intersection conditions
    if d == 0:
        print("Sphere centers are coincident; no unique intersection.")
        return []
    if d > r1 + r2:
        print(f"Spheres are separate (d={d:.2f} > r1+r2={r1+r2:.2f}); no intersection.")
        return []
    if d < abs(r1 - r2):
        print(f"One sphere is contained within another (d={d:.2f} < |r1-r2|={abs(r1-r2):.2f}); no intersection.")
        return []

    # Find intersection circle center
    a = (r1**2 - r2**2 + d**2) / (2 * d)
    h = np.sqrt(max(r1**2 - a**2, 0))
    xm = x0 + a * (x1 - x0) / d
    ym = y0 + a * (y1 - y0) / d
    zm = z0 + a * (z1 - z0) / d

    # Compute normal vector for the circle of intersection
    dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
    if dx == 0 and dy == 0:
        # Vertical alignment case
        print("Drone centers are vertically aligned; undefined intersection circle.")
        return []
    nx, ny, nz = dy, -dx, 0  # tangent to plane of intersection
    norm = np.linalg.norm([nx, ny, nz])
    if norm == 0:
        print("Normal vector calculation failed; skipping intersection.")
        return []
    nx, ny, nz = nx / norm, ny / norm, nz / norm

    # Points on the intersection circle
    intersection_points = []
    for t in np.linspace(0, 2 * np.pi, 20):
        x = xm + h * np.cos(t) * nx
        y = ym + h * np.cos(t) * ny
        z = zm + h * np.sin(t) * nz
        intersection_points.append((x, y, z))

    return intersection_points

def exact_intersection_3d(drone_positions, distances, tolerance=1e-2):
    """Return the 3D intersection point lying on the most spheres, or fallback."""
    intersections = []
    n = len(drone_positions)
    for i in range(n):
        for j in range(i + 1, n):
            points = sphere_sphere_intersection(drone_positions[i], distances[i],
                                                drone_positions[j], distances[j])
            intersections.extend(points)

    if not intersections:
        print("No intersections found, falling back to multilateration.")
        return localize_rover_multilateration(drone_positions, distances)

    # Count how many spheres each intersection lies on
    best_point = None
    max_count = 0
    for point in intersections:
        count = sum(
            abs(calculate_distance(point, drone_positions[k]) - distances[k]) <= tolerance
            for k in range(n)
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
    global estimated_rover_pos, reposition_done
    ax.clear()
    # Set up axes
    ax.set_xlim(-10, 10)
    ax.set_ylim(-10, 10)
    ax.set_zlim(-10, 10)
    ax.set_xlabel('X (m)')
    ax.set_ylabel('Y (m)')
    ax.set_zlabel('Z (m)')
    ax.set_title(f'3D Rover Localization with {NUM_DRONES} Drones')

    # Compute true distances
    distances = [calculate_distance(drone, real_rover_pos) for drone in drone_positions]

    # Check for coincident drones and jitter if necessary
    for i in range(len(drone_positions)):
        for j in range(i+1, len(drone_positions)):
            d_ij = calculate_distance(drone_positions[i], drone_positions[j])
            if d_ij < 0.01:
                print(f"Drones D{i+1} and D{j+1} are too close (dist={d_ij:.4f}). Adding jitter.")
                jitter = (random.uniform(-0.1, 0.1),
                          random.uniform(-0.1, 0.1),
                          random.uniform(-0.1, 0.1))
                new_pos = (
                    drone_positions[j][0] + jitter[0],
                    drone_positions[j][1] + jitter[1],
                    drone_positions[j][2] + jitter[2]
                )
                new_pos_clamped = (
                    min(max(new_pos[0], MIN_XYZ_POINTS[0]), MAX_XYZ_POINTS[0]),
                    min(max(new_pos[1], MIN_XYZ_POINTS[1]), MAX_XYZ_POINTS[1]),
                    min(max(new_pos[2], MIN_XYZ_POINTS[2]), MAX_XYZ_POINTS[2])
                )
                drone_positions[j] = new_pos_clamped

    # Plot drones and optionally spheres
    for i, (drone_pos, distance) in enumerate(zip(drone_positions, distances)):
        ax.scatter(*drone_pos, color='blue', s=100, marker='o')
        ax.text(*drone_pos, f'D{i+1}', fontsize=8)
        if show_distances:
            ax.plot([drone_pos[0], real_rover_pos[0]],
                    [drone_pos[1], real_rover_pos[1]],
                    [drone_pos[2], real_rover_pos[2]],
                    linestyle='--', color='gray', alpha=0.4)
        if show_spheres:
            u, v = np.mgrid[0:2*np.pi:20j, 0:np.pi:10j]
            x = distance * np.cos(u) * np.sin(v) + drone_pos[0]
            y = distance * np.sin(u) * np.sin(v) + drone_pos[1]
            z = distance * np.cos(v) + drone_pos[2]
            ax.plot_surface(x, y, z, color='blue', alpha=0.05, linewidth=0)

    # Plot actual rover
    ax.scatter(*real_rover_pos, color='red', s=200, marker='*', label='Actual Rover')

    # Perform localization if enough drones
    if len(drone_positions) >= 4:
        estimated_rover_pos = exact_intersection_3d(drone_positions, distances)
        ax.scatter(*estimated_rover_pos, color='purple', s=150, marker='x', label='Estimated Rover')
        error = calculate_distance(estimated_rover_pos, real_rover_pos)
        rover_info.set_text(
            f'Actual: ({real_rover_pos[0]:.2f}, {real_rover_pos[1]:.2f}, {real_rover_pos[2]:.2f})\n'
            f'Estimated: ({estimated_rover_pos[0]:.2f}, {estimated_rover_pos[1]:.2f}, {estimated_rover_pos[2]:.2f})\n'
            f'Error: {error:.2f} m'
        )
        # Check for poor localization or angular diversity
        if error > ERROR_THRESH and not reposition_done:
            # Check angular diversity
            diversity_ok = angular_diversity(drone_positions, real_rover_pos)
            # Find best group of 4 drones (largest minimal angle)
            best_min_angle = -1.0
            best_combo = None
            vectors = [np.array(dp) - np.array(real_rover_pos) for dp in drone_positions]
            for combo in combinations(range(len(drone_positions)), 4):
                min_angle = np.inf
                for i in range(4):
                    for j in range(i+1, 4):
                        v1 = vectors[combo[i]]
                        v2 = vectors[combo[j]]
                        norm1 = np.linalg.norm(v1)
                        norm2 = np.linalg.norm(v2)
                        if norm1 == 0 or norm2 == 0:
                            continue
                        cos_val = np.dot(v1, v2) / (norm1 * norm2)
                        cos_val = np.clip(cos_val, -1.0, 1.0)
                        angle_deg = np.degrees(np.arccos(cos_val))
                        if angle_deg < min_angle:
                            min_angle = angle_deg
                if min_angle > best_min_angle:
                    best_min_angle = min_angle
                    best_combo = combo
            # Debug messages
            if not diversity_ok:
                print(f"Angular diversity check failed: best group min angle = {best_min_angle:.2f}° (< {MIN_ANGLE_DIVERSITY}°).")
            else:
                print(f"High localization error detected (error = {error:.2f} m). Angular diversity ok (min angle = {best_min_angle:.2f}°).")
            print(f"Using drones {tuple(i+1 for i in best_combo)} as best candidate group (min angle {best_min_angle:.2f}°).")
            # Pause to allow user to read debug output
            plt.draw()
            plt.pause(0.1)
            time.sleep(2)
            # Compute new positions for the best group (spread around rover)
            tetra_dirs = np.array([[1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1]])
            tetra_dirs = tetra_dirs / np.linalg.norm(tetra_dirs, axis=1)[:, None]
            # Use average distance as radius to place drones
            group_dists = [distances[i] for i in best_combo]
            radius = max(np.mean(group_dists), 1.0)
            print("Repositioning drones to improve configuration.")
            for idx, d_idx in enumerate(best_combo):
                new_pos = tuple(real_rover_pos[i] + tetra_dirs[idx][i] * radius for i in range(3))
                new_pos_clamped = (
                    min(max(new_pos[0], MIN_XYZ_POINTS[0]), MAX_XYZ_POINTS[0]),
                    min(max(new_pos[1], MIN_XYZ_POINTS[1]), MAX_XYZ_POINTS[1]),
                    min(max(new_pos[2], MIN_XYZ_POINTS[2]), MAX_XYZ_POINTS[2])
                )
                print(f" - Drone D{d_idx+1}: {drone_positions[d_idx]} -> {new_pos_clamped}")
                drone_positions[d_idx] = new_pos_clamped
            reposition_done = True
            update_plot()
            reposition_done = False
            return
    else:
        rover_info.set_text("Need at least 4 drones for 3D localization.")

    ax.legend()
    plt.draw()

# UI callbacks
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
