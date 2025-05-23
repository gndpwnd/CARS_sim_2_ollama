# 2-2D_multilateration.py

# Comprehensive 2D multilateration using known distances from rover

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Button, TextBox
import random
import math
from scipy.optimize import least_squares

# Constants
GAMMA = 1.4
R_GAS = 287.05
TEMPERATURE = 25
SPEED_OF_SOUND = np.sqrt(GAMMA * R_GAS * (TEMPERATURE + 273.15))
NUM_DRONES = 7

# Global variables
drone_positions = []
real_rover_pos = (0, 3)
estimated_rover_pos = None
running = False

def calculate_distance(pos1, pos2):
    return np.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)

def simulate_signal_time_of_flight(drone_position, rover_position):
    distance = calculate_distance(drone_position, rover_position)
    round_trip_time = distance / SPEED_OF_SOUND
    return round_trip_time * SPEED_OF_SOUND / 2

def objective_function(point, drone_positions, distances):
    x, y = point
    return [calculate_distance((x, y), drone_positions[i]) - distances[i] for i in range(len(drone_positions))]

def localize_rover_multilateration(drone_positions, distances):
    x_avg = sum(pos[0] for pos in drone_positions) / len(drone_positions)
    y_avg = sum(pos[1] for pos in drone_positions) / len(drone_positions)
    initial_guess = [x_avg, y_avg]

    result = least_squares(
        objective_function,
        initial_guess,
        args=(drone_positions, distances),
        method='lm'
    )

    if result.success:
        return tuple(result.x)
    else:
        print("Failed to converge on a solution")
        return initial_guess

def circle_circle_intersections(c1, r1, c2, r2):
    """Return intersection points between two circles (if they exist)"""
    x0, y0 = c1
    x1, y1 = c2
    dx, dy = x1 - x0, y1 - y0
    d = math.hypot(dx, dy)

    if d > r1 + r2 or d < abs(r1 - r2) or d == 0:
        return []  # No intersections

    a = (r1**2 - r2**2 + d**2) / (2 * d)
    h = math.sqrt(r1**2 - a**2)
    xm = x0 + a * dx / d
    ym = y0 + a * dy / d
    rx = -dy * (h / d)
    ry = dx * (h / d)

    p1 = (xm + rx, ym + ry)
    p2 = (xm - rx, ym - ry)
    return [p1, p2]

def exact_intersection(drone_positions, distances, tolerance=1e-2):
    """
    Return the point where the most circles intersect (within tolerance).
    """
    intersections = []

    # Generate all pairwise circle intersections
    for i in range(len(drone_positions)):
        for j in range(i + 1, len(drone_positions)):
            points = circle_circle_intersections(
                drone_positions[i], distances[i],
                drone_positions[j], distances[j]
            )
            intersections.extend(points)

    if not intersections:
        print("No intersections found, falling back to multilateration.")
        return localize_rover_multilateration(drone_positions, distances)

    # Count how many circles each intersection point lies on
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
        print("Could not find a point on 3+ circles. Falling back to multilateration.")
        return localize_rover_multilateration(drone_positions, distances)

def reset_drones():
    global drone_positions
    drone_positions = []
    for _ in range(NUM_DRONES):
        drone_positions.append((random.uniform(-8, 8), random.uniform(-8, 8)))

def update_plot():
    global estimated_rover_pos
    ax.clear()

    ax.set_xlim(-10, 10)
    ax.set_ylim(-10, 10)
    ax.set_xlabel('X Coordinate (m)')
    ax.set_ylabel('Y Coordinate (m)')
    ax.set_title(f'Rover Localization with {NUM_DRONES} Drones')

    for i, drone_pos in enumerate(drone_positions):
        ax.scatter(drone_pos[0], drone_pos[1], color='blue', s=100, marker='o', zorder=10)
        ax.text(drone_pos[0], drone_pos[1] + 0.5, f'D{i+1}', fontsize=9, ha='center',
                bbox=dict(facecolor='white', alpha=0.7))

    ax.scatter(real_rover_pos[0], real_rover_pos[1], color='red', s=200, marker='*',
               label='Actual Rover', zorder=10)

    distances = [calculate_distance(drone_pos, real_rover_pos) for drone_pos in drone_positions]

    for i, (drone_pos, distance) in enumerate(zip(drone_positions, distances)):
        circle = plt.Circle(drone_pos, distance, fill=False, color='blue', linestyle='--', alpha=0.3)
        ax.add_patch(circle)
        ax.plot([drone_pos[0], real_rover_pos[0]], [drone_pos[1], real_rover_pos[1]],
                color='blue', linestyle='--', alpha=0.3)

    if len(drone_positions) >= 3:
        estimated_rover_pos = exact_intersection(drone_positions, distances)
    else:
        estimated_rover_pos = localize_rover_multilateration(drone_positions, distances)

    info_text = f'Actual: ({real_rover_pos[0]:.2f}, {real_rover_pos[1]:.2f})\n'

    if estimated_rover_pos:
        ax.scatter(estimated_rover_pos[0], estimated_rover_pos[1], color='purple', s=150, marker='x',
                   label='Estimated Rover', zorder=5)
        ax.plot([estimated_rover_pos[0], real_rover_pos[0]],
                [estimated_rover_pos[1], real_rover_pos[1]],
                'r-', alpha=0.7, linewidth=1)

        error = calculate_distance(estimated_rover_pos, real_rover_pos)
        error_text = f'Error: {error:.2f}m'
        ax.text(0, 9, error_text, fontsize=12, ha='center',
                bbox=dict(facecolor='white', alpha=0.7))

        info_text += f'Estimated: ({estimated_rover_pos[0]:.2f}, {estimated_rover_pos[1]:.2f})\n'
        info_text += f'Error: {error:.2f}m'
    else:
        info_text += 'Estimation failed'

    rover_info.set_text(info_text)

    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend(loc='lower right')
    fig.canvas.draw()

def randomize_rover(event):
    global real_rover_pos, running
    real_rover_pos = (random.uniform(-8, 8), random.uniform(-8, 8))
    running = True
    update_plot()

def randomize_drones(event):
    reset_drones()
    update_plot()

def update_num_drones(text):
    global NUM_DRONES
    try:
        new_num = int(text)
        if 2 <= new_num <= 20:
            NUM_DRONES = new_num
            reset_drones()
            update_plot()
        else:
            print("Number of drones should be between 2 and 20")
    except ValueError:
        print("Please enter a valid integer")

fig, ax = plt.subplots(figsize=(10, 10))
plt.subplots_adjust(bottom=0.2)

ax_rand_rover = plt.axes([0.2, 0.05, 0.2, 0.05])
ax_rand_drones = plt.axes([0.45, 0.05, 0.2, 0.05])
ax_num_drones = plt.axes([0.7, 0.05, 0.1, 0.05])

btn_rand_rover = Button(ax_rand_rover, 'Randomize Rover')
btn_rand_drones = Button(ax_rand_drones, 'Randomize Drones')
txt_num_drones = TextBox(ax_num_drones, 'Drones: ', initial=str(NUM_DRONES))

rover_info = plt.figtext(0.5, 0.12, "", fontsize=10, ha="center",
                         bbox=dict(facecolor='white', edgecolor='black', boxstyle='round,pad=1'))

btn_rand_rover.on_clicked(randomize_rover)
btn_rand_drones.on_clicked(randomize_drones)
txt_num_drones.on_submit(update_num_drones)

reset_drones()
rover_info.set_text("")
update_plot()
plt.show()
