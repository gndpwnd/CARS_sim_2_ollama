import time
import math
import random
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.animation import FuncAnimation
import ollama
import threading
import re

llm_responses = {}

# Configuration parameters
update_freq = 0.5
high_comm_qual = 0.80
low_comm_qual = 0.20
x_range = (-10, 10)
y_range = (-10, 10)
num_agents = 5
num_history_segments = 5

# Mission parameters
mission_end = (10, 10)

# Jamming zone parameters
jamming_center = (0, 0)
jamming_radius = 5

# Swarm data
swarm_pos_dict = {}
position_history = {}
jammed_positions = {}
time_points = []
iteration_count = 0

def round_coord(value):
    return round(value, 3)

# Plotting setup
def init_plot():
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
    update_swarm_data(frame)

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

    max_time = max(30, max(time_points) if time_points else 30)
    ax2.set_xlim(0, max_time)
    ax2.set_ylim(0, 1)
    ax2.set_xlabel('Time (s)')
    ax2.set_ylabel('Communication Quality')
    ax2.set_title('Communication Quality over Time')
    ax2.grid(True)

    # Initialize the lists to hold communication quality and time points
    comm_quality = []
    agent_time_points = []

    for agent_id, pos_history in position_history.items():
        ax1.plot([p[0] for p in pos_history], [p[1] for p in pos_history], 'b-', alpha=0.5)
        latest_data = swarm_pos_dict[agent_id][-1]
        color = 'red' if agent_id in jammed_positions and jammed_positions[agent_id] else 'green'
        ax1.scatter(latest_data[0], latest_data[1], color=color, s=100, label=f"{agent_id}")

        # Extract communication quality (assuming it's the third value in swarm_pos_dict)
        comm_quality.append(latest_data[2])  # Communication quality (3rd value)
        
        # Synchronize time points with the communication quality
        agent_time_points.append(iteration_count * update_freq)

    # Now that we have comm_quality and time_points, they must have the same length
    if len(agent_time_points) == len(comm_quality):
        ax2.plot(agent_time_points, comm_quality, label=f"Comm Quality")
    else:
        print("Error: time_points and comm_quality lengths do not match.")

    ax1.legend(loc='upper left')
    return []

def initialize_agents():
    global swarm_pos_dict, position_history, jammed_positions
    for i in range(num_agents):
        agent_id = f"agent{i+1}"
        start_x = round_coord(random.uniform(x_range[0], x_range[0] + 5))
        start_y = round_coord(random.uniform(y_range[0], y_range[0] + 5))
        swarm_pos_dict[agent_id] = [[start_x, start_y, 1.0]]
        position_history[agent_id] = [(start_x, start_y)]
        jammed_positions[agent_id] = []

def call_llm(iteration):
    global llm_responses
    response = ollama.chat(
        model="llama3.2:1b",
        messages=[{"role": "user", "content": f"Movement data: {position_history}"}]
    )
    llm_responses[iteration] = response.get('message', {}).get('content', 'No response')
    print(f"LLM Response at iteration {iteration}: {llm_responses[iteration]}")

def llm_make_move(agent_id):
    last_valid_position = swarm_pos_dict[agent_id][-1][:2]
    print(f"Prompting LLM for new coordinate for {agent_id} from {last_valid_position}")
    
    # Provide the prompt with clearer instructions
    response = ollama.chat(
        model="llama3.2:1b",
        messages=[{"role": "user", "content": f"Agent {agent_id} is jammed at {last_valid_position}. Provide a new coordinate (x, y). Only respond with the new coordinate."}]
    )
    
    # Parse the response for the new coordinate
    new_coordinate = parse_llm_response(response.get('message', {}).get('content', ''))
    
    if new_coordinate:
        print(f"LLM provided new coordinate for {agent_id}: {new_coordinate}")
        return new_coordinate
    else:
        print(f"Failed to parse new coordinates for {agent_id}. Returning last valid position.")
        return last_valid_position

def parse_llm_response(response):
    """
    Parses the LLM response to extract the new coordinates (x, y).
    Returns a tuple (x, y) if successful, or None if the format is incorrect.
    """
    # Regex to extract coordinates (float or integer)
    match = re.search(r"\((-?\d+\.\d+), (-?\d+\.\d+)\)", response)
    if match:
        try:
            # Convert matched coordinates to floats
            new_x = float(match.group(1))
            new_y = float(match.group(2))
            return (new_x, new_y)
        except ValueError:
            print("Error parsing coordinates.")
    return None

def update_swarm_data(frame):
    global iteration_count
    iteration_count += 1
    
    for agent_id in swarm_pos_dict:
        last_position = swarm_pos_dict[agent_id][-1][:2]
        distance_to_jamming = math.sqrt((last_position[0] - jamming_center[0])**2 + (last_position[1] - jamming_center[1])**2)
        
        if distance_to_jamming <= jamming_radius:
            print(f"{agent_id} is jammed at {last_position}. Requesting new coordinate from LLM.")
            swarm_pos_dict[agent_id].append([last_position[0], last_position[1], low_comm_qual])
            jammed_positions[agent_id].append(last_position)

            # Get a new coordinate from LLM
            new_coordinate = llm_make_move(agent_id)
            path = linear_path(new_coordinate, mission_end)
        else:
            path = linear_path(last_position, mission_end)
        
        if path:
            next_position = path[0]
            swarm_pos_dict[agent_id].append([round_coord(next_position[0]), round_coord(next_position[1]), 1.0])
            position_history[agent_id].append(next_position)

    # Call LLM asynchronously to avoid blocking the simulation
    if iteration_count % num_history_segments == 0:
        print(f"Sending movement data to LLM at iteration {iteration_count}")
        print(f"Data: {position_history}")
        print("LLM is responding...")
        thread = threading.Thread(target=call_llm, args=(iteration_count,))
        thread.start()

def linear_path(start, end):
    step_size = 0.5
    path = []
    direction_x, direction_y = end[0] - start[0], end[1] - start[1]
    distance = math.sqrt(direction_x**2 + direction_y**2)
    if distance > 0:
        unit_x, unit_y = direction_x / distance, direction_y / distance
    else:
        return [end]
    
    current_x, current_y = start
    while math.sqrt((current_x - end[0])**2 + (current_y - end[1])**2) > step_size:
        current_x += step_size * unit_x
        current_y += step_size * unit_y
        path.append((round_coord(current_x), round_coord(current_y)))
    
    path.append((round_coord(end[0]), round_coord(end[1])))
    return path

def run_simulation_with_plots():
    global fig, ax1, ax2
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
    initialize_agents()
    ani = FuncAnimation(fig, update_plot, init_func=init_plot, interval=int(update_freq * 1000), blit=False, cache_frame_data=False)
    plt.show()

if __name__ == "__main__":
    run_simulation_with_plots()
