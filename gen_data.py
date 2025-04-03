import time
import math
import random
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib import gridspec
import numpy as np

# Configuration parameters
update_freq = 0.5  # Update frequency in seconds
high_comm_qual = 0.80  # Optimal communication threshold
low_comm_qual = 0.20   # Lost communication threshold
x_range = (-25, 25)  # X-axis range
y_range = (-25, 25)  # Y-axis range
num_agents = 5       # Number of agents
num_history_segments = 5  # History data points before LLM prompt

# Swarm data
swarm_pos_dict = {}
comm_history = {}
time_points = []
position_history = {}

# Mission parameters
mission_start = {"x": x_range[0], "y": y_range[0]}  # Bottom-left
mission_end = {"x": x_range[1], "y": y_range[1]}  # Top-right

# Jamming zone parameters
jamming_center = (0, 0)
jamming_radius = 5
simulation_start_time = None

def initialize_agents():
    """Initialize agents with starting positions."""
    global swarm_pos_dict, position_history
    
    for i in range(num_agents):
        agent_id = f"agent{i+1}"
        start_x = random.uniform(x_range[0], x_range[0] + 5)
        start_y = random.uniform(y_range[0], y_range[0] + 5)
        swarm_pos_dict[agent_id] = [[start_x, start_y, 1.0]]  # Start with full comm quality
        position_history[agent_id] = {"x": [start_x], "y": [start_y]}
        comm_history[agent_id] = []

def new_data_generator(agent_id):
    """Generate new position and communication quality data for an agent."""
    latest_data = swarm_pos_dict[agent_id][-1]
    current_x, current_y, _ = latest_data
    
    # Linear movement towards (max x, max y)
    step_size = 0.5  # Step size per update
    direction_x = (mission_end["x"] - current_x)
    direction_y = (mission_end["y"] - current_y)
    distance = math.sqrt(direction_x**2 + direction_y**2)
    
    if distance > 0:
        new_x = current_x + step_size * (direction_x / distance)
        new_y = current_y + step_size * (direction_y / distance)
    else:
        new_x, new_y = current_x, current_y
    
    # Check if agent is inside the jamming zone
    distance_to_jamming = math.sqrt((new_x - jamming_center[0])**2 + (new_y - jamming_center[1])**2)
    new_comm_qual = low_comm_qual if distance_to_jamming <= jamming_radius else 1.0
    
    return new_x, new_y, new_comm_qual

jammed_agents = {}  # Dictionary to track jammed agents (agent_id: True/False)

def update_swarm_data():
    """Update data for all agents and track jamming status."""
    global comm_history, time_points, ani

    current_time = time.time() - simulation_start_time
    time_points.append(current_time)

    for agent_id in swarm_pos_dict:
        new_x, new_y, new_comm_qual = new_data_generator(agent_id)

        # Check if agent is inside the jamming zone
        distance_to_jamming_zone = math.sqrt((new_x - 0)**2 + (new_y - 0)**2)
        if distance_to_jamming_zone <= 5:
            new_comm_qual = 0.1  # Drop communication quality if jammed
            jammed_agents[agent_id] = True
        else:
            jammed_agents[agent_id] = False

        # Store new data
        swarm_pos_dict[agent_id].append([new_x, new_y, new_comm_qual])
        position_history[agent_id]["x"].append(new_x)
        position_history[agent_id]["y"].append(new_y)

        # Ensure comm_history exists for each agent
        if agent_id not in comm_history:
            comm_history[agent_id] = []

        comm_history[agent_id].append(new_comm_qual)

        # Limit history storage
        if len(time_points) > 100:
            time_points.pop(0)
            for agent in comm_history:
                comm_history[agent] = comm_history[agent][-100:]
            position_history[agent_id]["x"] = position_history[agent_id]["x"][-100:]
            position_history[agent_id]["y"] = position_history[agent_id]["y"][-100:]


def init_plot():
    """Initialize the plot."""
    ax1.clear()
    ax2.clear()
    
    # Setup position plot
    ax1.set_xlim(x_range)
    ax1.set_ylim(y_range)
    ax1.set_xlabel('X Position')
    ax1.set_ylabel('Y Position')
    ax1.set_title('Agent Position')
    ax1.grid(True)
    
    # Jamming zone
    jamming_circle = plt.Circle(jamming_center, jamming_radius, color='red', alpha=0.3)
    ax1.add_patch(jamming_circle)
    
    # Setup communication quality plot
    ax2.set_xlim(0, 30)
    ax2.set_ylim(0, 1)
    ax2.set_xlabel('Time (s)')
    ax2.set_ylabel('Communication Quality')
    ax2.set_title('Communication Quality over Time')
    ax2.grid(True)
    
    return []

def update_plot(frame):
    """Update the plot and indicate jammed agents."""
    update_swarm_data()

    ax1.clear()
    ax2.clear()

    ax1.set_xlim(x_range)
    ax1.set_ylim(y_range)
    ax1.set_xlabel('X Position')
    ax1.set_ylabel('Y Position')
    ax1.set_title('Agent Position')
    ax1.grid(True)

    # Draw the jamming zone
    jamming_circle = plt.Circle((0, 0), 5, color='red', alpha=0.3)
    ax1.add_patch(jamming_circle)

    max_time = max(30, max(time_points) if time_points else 30)
    ax2.set_xlim(0, max_time)
    ax2.set_ylim(0, 1)
    ax2.set_xlabel('Time (s)')
    ax2.set_ylabel('Communication Quality')
    ax2.set_title('Communication Quality over Time')
    ax2.grid(True)

    for agent_id, pos_history in position_history.items():
        trail_length = len(pos_history["x"])
        for i in range(max(0, trail_length-20), trail_length-1):
            alpha = 0.05 + (i - max(0, trail_length-20)) * 0.9 / min(20, trail_length)
            ax1.plot([pos_history["x"][i], pos_history["x"][i+1]], 
                     [pos_history["y"][i], pos_history["y"][i+1]], 
                     'b-', alpha=alpha)

        # Get latest position and communication status
        latest_data = swarm_pos_dict[agent_id][-1]
        comm_quality = latest_data[2]

        # Mark jammed agents
        if jammed_agents.get(agent_id, False):
            color = 'red'
            label = f"{agent_id} (Jammed)"
        else:
            color = 'green' if comm_quality > low_comm_qual else 'orange'
            label = f"{agent_id}"

        ax1.scatter(latest_data[0], latest_data[1], color=color, s=100, label=label)

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
    ani = FuncAnimation(fig, update_plot, init_func=init_plot, 
                    frames=None, interval=update_freq * 1000, blit=False, 
                    cache_frame_data=False, save_count=100)

    plt.tight_layout()
    plt.show()

fig = plt.figure(figsize=(12, 10))
gs = gridspec.GridSpec(2, 1, height_ratios=[1, 1])
ax1 = fig.add_subplot(gs[0])
ax2 = fig.add_subplot(gs[1])

if __name__ == "__main__":
    run_simulation_with_plots()
