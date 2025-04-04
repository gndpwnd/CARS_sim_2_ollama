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

# LLM Prompt Constraints
MAX_CHARS_PER_AGENT = 25
LLM_PROMPT_TIMEOUT = 5  # seconds to wait for LLM response before giving up
MAX_RETRIES = 3  # maximum number of retries for LLM prompting

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
        
        # Use jammed_positions boolean flag for determining color
        color = 'red' if jammed_positions[agent_id] else 'green'
        ax1.scatter(latest_data[0], latest_data[1], color=color, s=100, label=f"{agent_id}")

        # Extract communication quality
        comm_quality.append(latest_data[2])  # Communication quality
        
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
        swarm_pos_dict[agent_id] = [[start_x, start_y, high_comm_qual]]  # Start with high quality
        position_history[agent_id] = [(start_x, start_y)]
        jammed_positions[agent_id] = False  # Boolean flag for jamming status

def call_llm(iteration):
    global llm_responses
    
    # Create the message to send
    prompt = f"Movement data: {position_history}"
    print(f"Full movement data prompt sent to LLM: {prompt}")
    
    # Send the prompt
    response = ollama.chat(
        model="llama3.2:1b",
        messages=[{"role": "user", "content": prompt}]
    )
    
    # Get and store the response
    response_content = response.get('message', {}).get('content', 'No response')
    llm_responses[iteration] = response_content
    print(f"Full LLM Response at iteration {iteration}: \"{response_content}\"")

def llm_make_move(agent_id):
    last_valid_position = swarm_pos_dict[agent_id][-1][:2]

    distance_to_jamming = math.sqrt((last_valid_position[0] - jamming_center[0])**2 + 
                                    (last_valid_position[1] - jamming_center[1])**2)
    
    if distance_to_jamming > jamming_radius:
        print(f"{agent_id} is already outside jamming zone at {last_valid_position}. No LLM input needed.")
        return last_valid_position


    print(f"Prompting LLM for new coordinate for {agent_id} from {last_valid_position}")
    
    # Create the prompt message - make it very clear what format is needed
    prompt = f"Agent {agent_id} is jammed at {last_valid_position}. Provide exactly one new coordinate pair as (x, y) with both values being numbers. Your response must be 25 characters or less and should only contain the coordinate."
    print(f"Full prompt sent to LLM: {prompt}")
    
    # Try multiple times to get a valid response
    for attempt in range(MAX_RETRIES):
        try:
            # Send the prompt with a timeout
            response = ollama.chat(
                model="llama3.2:1b",
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Get and print the full response
            response_content = response.get('message', {}).get('content', '')
            print(f"Full LLM response: \"{response_content}\"")
            
            # Check if response exceeds character limit
            if len(response_content) > MAX_CHARS_PER_AGENT:
                print(f"Response exceeds character limit ({len(response_content)} > {MAX_CHARS_PER_AGENT}), retrying...")
                continue
            
            # Parse the response for the new coordinate
            new_coordinate = parse_llm_response(response_content)
            
            if new_coordinate:
                print(f"LLM provided new coordinate for {agent_id}: {new_coordinate}")
                return new_coordinate
            else:
                print(f"Failed to parse coordinates, retrying (attempt {attempt+1}/{MAX_RETRIES})...")
        
        except Exception as e:
            print(f"Error getting LLM response: {e}. Retrying (attempt {attempt+1}/{MAX_RETRIES})...")
    
    # If we get here, we didn't get a valid response after all retries
    print(f"Failed to get valid coordinates after {MAX_RETRIES} attempts. Using safe position.")
    
    # Return the second-to-last position as a safe fallback
    if len(swarm_pos_dict[agent_id]) > 1:
        return swarm_pos_dict[agent_id][-2][:2]
    return last_valid_position

def parse_llm_response(response):
    """
    Parses the LLM response to extract the new coordinates (x, y).
    Returns a tuple (x, y) if successful, or None if the format is incorrect.
    """
    # Try different regex patterns to match coordinates
    # Pattern 1: (x, y) format with any number of digits
    pattern1 = r"\((-?\d+\.?\d*),\s*(-?\d+\.?\d*)\)"
    # Pattern 2: x: value, y: value format
    pattern2 = r"x:?\s*(-?\d+\.?\d*)[,\s]*y:?\s*(-?\d+\.?\d*)"
    # Pattern 3: Just two numbers separated by comma
    pattern3 = r"(-?\d+\.?\d*)[,\s]+(-?\d+\.?\d*)"
    # Pattern 4: Just two numbers on separate lines
    pattern4 = r"(-?\d+\.?\d*)\s*\n\s*(-?\d+\.?\d*)"
    
    # Try each pattern
    for pattern in [pattern1, pattern2, pattern3, pattern4]:
        match = re.search(pattern, response)
        if match:
            try:
                new_x = float(match.group(1))
                new_y = float(match.group(2))
                return (new_x, new_y)
            except ValueError:
                print(f"Matched pattern but couldn't convert to float: {match.group(1)}, {match.group(2)}")
                continue
    
    # If we got here, no pattern matched
    print(f"No valid coordinate format found in response: \"{response}\"")
    return None

import time
import math
import random
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib import gridspec
import numpy as np

# Configuration parameters
update_freq = 0.5  # How often to generate new data in seconds
converged = False  # Is the swarm in optimal communication
diverged = False   # Is the swarm in poor communication
high_comm_qual = 0.80  # Threshold for optimal communication
low_comm_qual = 0.20   # Threshold for lost communication
x_range = (-25, 25)    # Range for x positions
y_range = (-25, 25)    # Range for y positions
num_agents = 8         # Number of agents
num_history_segments = 5  # History data points before LLM prompt
time_elapsed = 0

# Swarm position dictionary {agent_id: [[x, y, comm_qual], ...]}
swarm_pos_dict = {}

# For plotting
comm_history = []
time_points = []
position_history = {}  # To track paths

# Mission parameters - from 3rd to 1st quadrant
mission_start = {
    "x": x_range[0],  # Bottom left corner 
    "y": y_range[0]
}
mission_end = {
    "x": x_range[1],  # Top right corner
    "y": y_range[1]
}

# Time tracking for sine wave
time_elapsed = 0
sine_period = 20  # Period of sine wave in seconds (complete oscillation takes 20 seconds)
sine_amplitude = (high_comm_qual - low_comm_qual) / 2  # Amplitude of the sine wave
sine_midpoint = (high_comm_qual + low_comm_qual) / 2  # Midpoint of the sine wave
simulation_start_time = None

def initialize_agents():
    """Initialize agents with starting positions"""
    global swarm_pos_dict, position_history
    
    for i in range(num_agents):
        agent_id = f"agent{i+1}"
        # Random starting positions
        start_x = random.uniform(x_range[0], x_range[0]/2)
        start_y = random.uniform(y_range[0], y_range[0]/2)
        
        # Initial communication quality based on sine wave at time 0
        start_comm_qual = sine_midpoint + sine_amplitude * math.sin(0)
        start_comm_qual = round(start_comm_qual, 2)
        
        swarm_pos_dict[agent_id] = [[start_x, start_y, start_comm_qual]]
        position_history[agent_id] = {"x": [start_x], "y": [start_y]}

def new_data_generator(agent_id):
    """Generate new position and communication quality data for an agent."""
    global converged, diverged
    
    # Get the latest data for this agent
    latest_data = swarm_pos_dict[agent_id][-1]
    current_x, current_y, _ = latest_data  # Ignore old comm_qual

    # Move along the path with some randomness
    progress_step = random.uniform(0.01, 0.03)  # Random step size
    x_step = progress_step * (mission_end["x"] - mission_start["x"])
    y_step = progress_step * (mission_end["y"] - mission_start["y"])
    
    # Add small random noise
    x_noise = random.uniform(-0.5, 0.5)
    y_noise = random.uniform(-0.5, 0.5)
    
    # Calculate new position
    new_x = min(max(current_x + x_step + x_noise, x_range[0]), x_range[1])
    new_y = min(max(current_y + y_step + y_noise, y_range[0]), y_range[1])
    
    # Compute new communication quality based on absolute time
    current_time = time.time() - simulation_start_time
    new_comm_qual = sine_midpoint + sine_amplitude * math.sin(2 * math.pi * current_time / sine_period)
    new_comm_qual = round(new_comm_qual, 2)
    
    # Update status flags
    converged = new_comm_qual >= high_comm_qual
    diverged = new_comm_qual <= low_comm_qual

    return new_x, new_y, new_comm_qual

def update_swarm_data():
    """Update data for all agents in the swarm and check for mission completion."""
    global comm_history, time_points, ani

    # Get absolute time
    current_time = time.time() - simulation_start_time
    time_points.append(current_time)

    for agent_id in swarm_pos_dict:
        # Generate new data for each agent
        new_x, new_y, new_comm_qual = new_data_generator(agent_id)

        # Store new data
        swarm_pos_dict[agent_id].append([new_x, new_y, new_comm_qual])
        position_history[agent_id]["x"].append(new_x)
        position_history[agent_id]["y"].append(new_y)

        # Use one agent (e.g., agent1) to store communication quality for plotting
        if agent_id == "agent1":
            comm_history.append(new_comm_qual)

        # Print message when we have enough data to send to LLM
        if len(swarm_pos_dict[agent_id]) > num_history_segments:
            print(f"Agent {agent_id} has collected enough data. Would send to LLM now.")

        # Check if agent reached the mission end
        distance_to_end = math.sqrt((new_x - mission_end["x"])**2 + (new_y - mission_end["y"])**2)
        if distance_to_end <= 3:
            print(f"Agent {agent_id} reached the destination. Stopping simulation...")
            ani.event_source.stop()  # Stop animation
            plt.pause(0.1)  # Allow final update
            print("Close the graph window to exit the program.")
            plt.show(block=True)  # Wait for user to close
            exit(0)  # Exit program after graph is closed

        # Limit stored history for efficient plotting
        if len(time_points) > 100:
            time_points.pop(0)
            comm_history.pop(0)
            position_history[agent_id]["x"] = position_history[agent_id]["x"][-100:]
            position_history[agent_id]["y"] = position_history[agent_id]["y"][-100:]

        # Keep only the latest position for LLM updates
        if len(swarm_pos_dict[agent_id]) > num_history_segments:
            swarm_pos_dict[agent_id] = swarm_pos_dict[agent_id][-1:]

def init_plot():
    """Initialize the plot"""
    # Clear axes
    ax1.clear()
    ax2.clear()
    
    # Setup position plot (ax1)
    ax1.set_xlim(x_range)
    ax1.set_ylim(y_range)
    ax1.set_xlabel('X Position')
    ax1.set_ylabel('Y Position')
    ax1.set_title('Agent Position')
    ax1.grid(True)
    
    # Setup communication quality plot (ax2)
    ax2.set_xlim(0, 30)  # 30 seconds of history
    ax2.set_ylim(0, 1)   # Comm quality range
    ax2.axhline(y=high_comm_qual, color='g', linestyle='--', alpha=0.7)
    ax2.axhline(y=low_comm_qual, color='r', linestyle='--', alpha=0.7)
    ax2.set_xlabel('Time (s)')
    ax2.set_ylabel('Communication Quality')
    ax2.set_title('Communication Quality over Time')
    ax2.grid(True)
    
    # Plot theoretical sine wave to show expected oscillation
    t = np.linspace(0, 30, 300)
    comm_sine = sine_midpoint + sine_amplitude * np.sin(2 * np.pi * t / sine_period)
    ax2.plot(t, comm_sine, 'k--', alpha=0.3, label='Expected Sine Wave')
    
    return []

def update_plot(frame):
    """Update the plot with new data, stop if agents reach the goal."""
    global ani  # Ensure we can stop animation if needed

    # Update data
    update_swarm_data()
    
    # Clear axes
    ax1.clear()
    ax2.clear()
    
    # Reinitialize axes
    ax1.set_xlim(x_range)
    ax1.set_ylim(y_range)
    ax1.set_xlabel('X Position')
    ax1.set_ylabel('Y Position')
    ax1.set_title('Agent Position')
    ax1.grid(True)
    
    max_time = max(30, max(time_points) if time_points else 30)
    ax2.set_xlim(0, max_time)
    ax2.set_ylim(0, 1)
    ax2.axhline(y=high_comm_qual, color='g', linestyle='--', alpha=0.7, label='High Quality')
    ax2.axhline(y=low_comm_qual, color='r', linestyle='--', alpha=0.7, label='Low Quality')
    ax2.set_xlabel('Time (s)')
    ax2.set_ylabel('Communication Quality')
    ax2.set_title('Communication Quality over Time (Sine Wave)')
    ax2.grid(True)
    
    # Plot theoretical sine wave to show expected oscillation
    t = np.linspace(0, max_time, 300)
    comm_sine = sine_midpoint + sine_amplitude * np.sin(2 * np.pi * t / sine_period)
    ax2.plot(t, comm_sine, 'k--', alpha=0.3, label='Expected Sine Wave')
    
    # Plot position data for each agent
    for agent_id, pos_history in position_history.items():
        # Show trail with increasing opacity
        trail_length = len(pos_history["x"])
        for i in range(max(0, trail_length-20), trail_length-1):
            alpha = 0.05 + (i - max(0, trail_length-20)) * 0.9 / min(20, trail_length)
            ax1.plot([pos_history["x"][i], pos_history["x"][i+1]], 
                    [pos_history["y"][i], pos_history["y"][i+1]], 
                    'b-', alpha=alpha)
        
        # Current position
        latest_data = swarm_pos_dict[agent_id][-1]
        comm_quality = latest_data[2]
        
        # Color dot based on communication quality
        if comm_quality >= high_comm_qual:
            color = 'green'
        elif comm_quality <= low_comm_qual:
            color = 'red'
        else:
            # Gradient between red and green based on quality
            green_intensity = (comm_quality - low_comm_qual) / (high_comm_qual - low_comm_qual)
            red_intensity = 1 - green_intensity
            color = (red_intensity, green_intensity, 0)
        
        ax1.scatter(latest_data[0], latest_data[1], color=color, s=100, 
                   label=f"{agent_id} (Comm: {comm_quality:.2f})")

        # Check if this agent has reached the mission end
        distance_to_end = math.sqrt((latest_data[0] - mission_end["x"])**2 + 
                                    (latest_data[1] - mission_end["y"])**2)
        if distance_to_end <= 3:
            print(f"Agent {agent_id} reached the destination. Stopping simulation...")
            ani.event_source.stop()  # Stop animation
            plt.pause(0.1)  # Allow final update
            print("Close the graph window to exit the program.")
            plt.show(block=True)  # Wait for user to close
            exit(0)  # Exit program after graph is closed

    # Plot communication quality data
    if time_points and comm_history:
        # Color regions
        for i in range(len(time_points)-1):
            if comm_history[i] >= high_comm_qual:
                color = 'green'
                alpha = 0.3
            elif comm_history[i] <= low_comm_qual:
                color = 'red'
                alpha = 0.3
            else:
                color = 'yellow'
                alpha = 0.2
            
            ax2.fill_between([time_points[i], time_points[i+1]], 
                            [comm_history[i], comm_history[i+1]], 
                            color=color, alpha=alpha)
        
        # Line plot
        ax2.plot(time_points, comm_history, 'b-', linewidth=2, label='Actual Comm Quality')
    
    # Status text
    status_text = "Status: "
    if converged:
        status_text += "CONVERGED - Optimal Communication"
        ax1.set_title('Agent Position - CONVERGED', color='green')
    elif diverged:
        status_text += "DIVERGED - Poor Communication"
        ax1.set_title('Agent Position - DIVERGED', color='red')
    else:
        status_text += "Normal Operation"
    
    fig.suptitle(status_text, fontsize=14)
    
    # Add legends
    ax1.legend(loc='upper left')
    ax2.legend(loc='upper right')
    
    return []


def run_simulation_with_plots():
    """Run the simulation with real-time plotting"""
    global simulation_start_time, ani
    simulation_start_time = time.time()

    # Initialize agents
    initialize_agents()

    # Create animation and store it in `ani`
    ani = FuncAnimation(fig, update_plot, init_func=init_plot, 
                        frames=None, interval=update_freq*1000, blit=False,
                        cache_frame_data=False, save_count=100)

    plt.tight_layout()
    plt.show()

# Create figure and axes
fig = plt.figure(figsize=(12, 10))
gs = gridspec.GridSpec(2, 1, height_ratios=[1, 1])
ax1 = fig.add_subplot(gs[0])  # Position plot
ax2 = fig.add_subplot(gs[1])  # Communication quality plot

# Main execution
if __name__ == "__main__":
    run_simulation_with_plots()

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
