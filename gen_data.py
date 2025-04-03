import ollama
import time
import math
import random
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib import gridspec
import numpy as np

# Configuration parameters
update_freq = 0.5  # Update frequency in seconds
low_comm_qual = 0.20   # Lost communication threshold
x_range = (-10, 10)  # X-axis range
y_range = (-10, 10)  # Y-axis range
num_agents = 5       # Number of agents
num_history_segments = 5  # History data points before LLM prompt

# Swarm data
swarm_pos_dict = {}
comm_history = {}
time_points = []
position_history = {}
jammed_agents = {}
jammed_positions = {}

# Mission parameters
mission_start = {"x": x_range[0], "y": y_range[0]}  # Bottom-left
mission_end = {"x": 10, "y": 10}  # Fixed target at (10,10)

# Jamming zone parameters
jamming_center = (0, 0)
jamming_radius = 5
simulation_start_time = None

def initialize_agents():
    """Initialize agents with starting positions."""
    global swarm_pos_dict, position_history, jammed_agents, jammed_positions
    
    for i in range(num_agents):
        agent_id = f"agent{i+1}"
        start_x = random.uniform(x_range[0], x_range[0] + 5)
        start_y = random.uniform(y_range[0], y_range[0] + 5)
        swarm_pos_dict[agent_id] = [[start_x, start_y, 1.0]]  # Start with full comm quality
        position_history[agent_id] = {"x": [start_x], "y": [start_y]}
        comm_history[agent_id] = []
        jammed_agents[agent_id] = False
        jammed_positions[agent_id] = []

def move_towards_target(start_x, start_y, end_x, end_y, step_size=0.5):
    """Generate the next step towards the target in a straight line."""
    direction_x = end_x - start_x
    direction_y = end_y - start_y
    distance = math.sqrt(direction_x**2 + direction_y**2)
    
    if distance > step_size:
        unit_x = direction_x / distance
        unit_y = direction_y / distance
        new_x = start_x + step_size * unit_x
        new_y = start_y + step_size * unit_y
    else:
        new_x, new_y = end_x, end_y  # Reached target
    
    return new_x, new_y

def determine_next_coordinates(agent_id):
    """Determine the next set of coordinates based on jamming history."""
    last_position = swarm_pos_dict[agent_id][-1][:2]

    if jammed_agents[agent_id]:
        # Move back to the last known non-jammed position
        last_valid_position = jammed_positions[agent_id][-1]
        jammed_positions[agent_id] = []  # Reset jammed history
        new_x, new_y = last_valid_position
    else:
        # Continue moving linearly towards (10,10)
        new_x, new_y = move_towards_target(last_position[0], last_position[1], mission_end["x"], mission_end["y"])
    
    # Check if the new position is inside the jamming zone
    distance_to_jamming = math.sqrt((new_x - jamming_center[0])**2 + (new_y - jamming_center[1])**2)
    new_comm_qual = low_comm_qual if distance_to_jamming <= jamming_radius else 1.0

    # If jammed, record last known position and pick a new random point
    if new_comm_qual <= low_comm_qual:
        jammed_agents[agent_id] = True
        jammed_positions[agent_id].append(last_position)
        # Pick a new random point within 2 units radius and move from there
        angle = random.uniform(0, 2 * math.pi)
        radius = random.uniform(0, 2)
        new_x = last_position[0] + radius * math.cos(angle)
        new_y = last_position[1] + radius * math.sin(angle)
    
    return new_x, new_y, new_comm_qual

def update_swarm_data(frame):
    """Update data for all agents and track jamming status."""
    global comm_history, time_points

    current_time = time.time() - simulation_start_time
    time_points.append(current_time)

    for agent_id in swarm_pos_dict:
        new_x, new_y, new_comm_qual = determine_next_coordinates(agent_id)

        swarm_pos_dict[agent_id].append([new_x, new_y, new_comm_qual])
        position_history[agent_id]["x"].append(new_x)
        position_history[agent_id]["y"].append(new_y)
        comm_history[agent_id].append(new_comm_qual)

        if new_comm_qual > low_comm_qual:
            jammed_agents[agent_id] = False  # Clear jamming status

def init_plot():
    """Initialize the plot."""
    ax1.clear()
    ax2.clear()
    
    ax1.set_xlim(x_range)
    ax1.set_ylim(y_range)
    ax1.set_xlabel('X Position')
    ax1.set_ylabel('Y Position')
    ax1.set_title('Agent Position')
    ax1.grid(True)
    
    jamming_circle = plt.Circle(jamming_center, jamming_radius, color='red', alpha=0.3)
    ax1.add_patch(jamming_circle)
    
    ax2.set_xlim(0, 30)
    ax2.set_ylim(0, 1)
    ax2.set_xlabel('Time (s)')
    ax2.set_ylabel('Communication Quality')
    ax2.set_title('Communication Quality over Time')
    ax2.grid(True)
    
    return []

def update_plot(frame):
    """Update the plot with agent movements and communication quality."""
    update_swarm_data(frame)

    ax1.clear()
    ax2.clear()

    ax1.set_xlim(x_range)
    ax1.set_ylim(y_range)
    ax1.set_xlabel('X Position')
    ax1.set_ylabel('Y Position')
    ax1.set_title('Agent Position')
    ax1.grid(True)

    # Draw jamming zone
    jamming_circle = plt.Circle(jamming_center, jamming_radius, color='red', alpha=0.3)
    ax1.add_patch(jamming_circle)

    max_time = max(30, max(time_points) if time_points else 30)
    ax2.set_xlim(0, max_time)
    ax2.set_ylim(0, 1)
    ax2.set_xlabel('Time (s)')
    ax2.set_ylabel('Communication Quality')
    ax2.set_title('Communication Quality over Time')
    ax2.grid(True)

    for agent_id, pos_history in position_history.items():
        # Plot agent trajectory
        ax1.plot(pos_history["x"], pos_history["y"], 'b-', alpha=0.5)

        # Get latest position
        latest_data = swarm_pos_dict[agent_id][-1]
        comm_quality = latest_data[2]

        # Mark agents
        color = 'red' if jammed_agents.get(agent_id, False) else 'green'
        ax1.scatter(latest_data[0], latest_data[1], color=color, s=100, label=f"{agent_id}")

    for agent_id, history in comm_history.items():
        ax2.plot(time_points, history, label=f"{agent_id}")

    ax1.legend(loc='upper left')
    ax2.legend(loc='upper right')

    return []

def run_simulation_with_plots():
    """Run the simulation with real-time plotting."""
    global simulation_start_time, ani
    simulation_start_time = time.time()
    initialize_agents()
    ani = FuncAnimation(fig, update_plot, init_func=init_plot, interval=update_freq * 1000, blit=False, cache_frame_data=False)
    plt.show()

fig = plt.figure(figsize=(12, 10))
gs = gridspec.GridSpec(2, 1, height_ratios=[1, 1])
ax1 = fig.add_subplot(gs[0])
ax2 = fig.add_subplot(gs[1])

if __name__ == "__main__":
    run_simulation_with_plots()
