import math
import random
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Button
from matplotlib.animation import FuncAnimation
import re
import datetime

# Import shared LLM configuration
from llm_config import get_ollama_client, get_model_name
ollama = get_ollama_client()
LLM_MODEL = get_model_name()

from rag_store import add_log  # Import additional needed functions

# Toggle between LLM and algorithm-based control
USE_LLM = True  # Set to True to use LLM, False to use algorithm

RAG_UPDATE_FREQUENCY = 5  # Log agent data every 5 iterations (same as buffer size)
iteration_count = 0  # Track the number of iterations

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

# Calculate maximum movement step (diagonal/20)
plane_width = x_range[1] - x_range[0]
plane_height = y_range[1] - y_range[0]
diagonal_length = np.sqrt(plane_width**2 + plane_height**2)
max_movement_per_step = diagonal_length / 20
print(f"[CONFIG] Maximum movement per step: {max_movement_per_step:.2f} units")

# Swarm data tracking
swarm_pos_dict = {}
position_history = {}
jammed_positions = {}
last_safe_position = {}
time_points = []
iteration_count = 0

# LLM Prompt Constraints
MAX_CHARS_PER_AGENT = 25
LLM_PROMPT_TIMEOUT = 5  # seconds to wait for LLM response before giving up
MAX_RETRIES = 3  # maximum number of retries for LLM prompting

# Simulation state tracking
agent_paths = {}
pending_llm_actions = {}
returned_to_safe = {}

# Animation control
animation_running = True
animation_object = None


import numpy as np
import datetime

def convert_numpy_coords(obj):
    """
    Recursively convert numpy data types to native Python types for JSON serialization.
    """
    if isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        return float(obj)
    elif isinstance(obj, (np.complexfloating,)):
        return complex(obj)
    elif isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (list, tuple)):
        converted = [convert_numpy_coords(item) for item in obj]
        return tuple(converted) if isinstance(obj, tuple) else converted
    elif isinstance(obj, dict):
        return {key: convert_numpy_coords(value) for key, value in obj.items()}
    return obj  # Unchanged types

def log_batch_of_data(agent_histories: dict, prefix="batch"):
    """
    Log a batch of data from all agents. One log per agent per data point.
    
    Parameters:
        agent_histories (dict): Mapping of agent_id to list of data points
        prefix (str): Prefix used to construct a unique log ID
    """
    print(f"[LOGGING] Logging batch of data with prefix: {prefix}")
    
    for agent_id, history in agent_histories.items():
        prev_entry = None
        
        for i, data in enumerate(history):
            if data == prev_entry:
                continue
            prev_entry = data

            log_id = f"{prefix}-{agent_id}-{i}"
            position = convert_numpy_coords(data['position'])
            comm_quality = convert_numpy_coords(data['communication_quality'])
            jammed = data['jammed']
            timestamp = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')

            log_text = (
                f"Agent {agent_id} is at position {position}. "
                f"Communication quality: {comm_quality}. "
                f"Status: {'Jammed' if jammed else 'Clear'}."
            )

            metadata = {
                'timestamp': timestamp,
                'agent_id': agent_id,
                'comm_quality': comm_quality,
                'position': position,
                'jammed': jammed
            }

            # Correct order of parameters: log_text, metadata, agent_id=None, log_id=None
            add_log(log_text=log_text, metadata=metadata, log_id=log_id)

def round_coord(value):
    """Round coordinates to 3 decimal places"""
    return round(value, 3)

def is_jammed(pos):
    """Check if a position is inside the jamming zone"""
    if isinstance(pos, tuple) or isinstance(pos, list):
        pos_x, pos_y = pos[0], pos[1]
    else:  # Assume numpy array
        pos_x, pos_y = pos[0], pos[1]
    
    distance = math.sqrt((pos_x - jamming_center[0])**2 + (pos_y - jamming_center[1])**2)
    return distance <= jamming_radius

def linear_path(start, end):
    """Create a linear path between start and end points with max step distance constraint"""
    step_size = max_movement_per_step
    path = []
    
    # Convert to numpy arrays if they aren't already
    if isinstance(start, tuple) or isinstance(start, list):
        start_np = np.array([start[0], start[1]])
    else:
        start_np = start
        
    if isinstance(end, tuple) or isinstance(end, list):
        end_np = np.array([end[0], end[1]])
    else:
        end_np = end
    
    direction_x, direction_y = end_np[0] - start_np[0], end_np[1] - start_np[1]
    distance = math.sqrt(direction_x**2 + direction_y**2)
    
    if distance > 0:
        unit_x, unit_y = direction_x / distance, direction_y / distance
    else:
        return [(round_coord(end_np[0]), round_coord(end_np[1]))]
    
    current_x, current_y = start_np[0], start_np[1]
    while math.sqrt((current_x - end_np[0])**2 + (current_y - end_np[1])**2) > step_size:
        current_x += step_size * unit_x
        current_y += step_size * unit_y
        path.append((round_coord(current_x), round_coord(current_y)))
    
    path.append((round_coord(end_np[0]), round_coord(end_np[1])))
    return path

def limit_movement(current_pos, target_pos):
    """Limit movement to max_movement_per_step"""
    if isinstance(current_pos, tuple) or isinstance(current_pos, list):
        current_np = np.array([current_pos[0], current_pos[1]])
    else:
        current_np = current_pos
        
    if isinstance(target_pos, tuple) or isinstance(target_pos, list):
        target_np = np.array([target_pos[0], target_pos[1]])
    else:
        target_np = target_pos
    
    distance = np.linalg.norm(target_np - current_np)
    
    if distance <= max_movement_per_step:
        return target_np  # We can reach the target directly
    
    # Otherwise, move in the direction of the target, but only by max_movement_per_step
    direction = (target_np - current_np) / distance
    limited_pos = current_np + direction * max_movement_per_step
    
    return (round_coord(limited_pos[0]), round_coord(limited_pos[1]))

def algorithm_make_move(agent_id):
    """Use the fittest path algorithm for jammed agents"""
    current_pos = swarm_pos_dict[agent_id][-1][:2]
    print(f"[Algorithm] Finding path for Agent {agent_id} at {current_pos}")
    
    # Try to find a valid move that's outside the jamming zone
    max_attempts = 10
    for _ in range(max_attempts):
        # Generate a random direction (unit vector)
        angle = random.uniform(0, 2 * np.pi)
        direction = np.array([np.cos(angle), np.sin(angle)])
        
        # Move max_movement_per_step in that direction
        suggestion = np.array(current_pos) + direction * max_movement_per_step
        
        # Clamp to the boundaries of the plane
        suggestion[0] = max(min(suggestion[0], x_range[1]), x_range[0])
        suggestion[1] = max(min(suggestion[1], y_range[1]), y_range[0])
        
        # Check if this would be outside the jamming zone
        if not is_jammed(suggestion):
            print(f"[Algorithm] Found non-jammed position for Agent {agent_id}: {suggestion}")
            return (round_coord(suggestion[0]), round_coord(suggestion[1]))
    
    # If we failed to find a good move after max_attempts, try to move away from center
    print(f"[Algorithm] Couldn't find non-jammed position, moving away from jamming center")
    
    # Direction away from jamming center
    direction = np.array(current_pos) - np.array(jamming_center)
    direction_norm = np.linalg.norm(direction)
    
    if direction_norm > 0:
        unit_direction = direction / direction_norm
        suggestion = np.array(current_pos) + unit_direction * max_movement_per_step
    else:
        # If at center, move in random direction
        angle = random.uniform(0, 2 * np.pi)
        unit_direction = np.array([np.cos(angle), np.sin(angle)])
        suggestion = np.array(current_pos) + unit_direction * max_movement_per_step
    
    # Clamp to the boundaries
    suggestion[0] = max(min(suggestion[0], x_range[1]), x_range[0])
    suggestion[1] = max(min(suggestion[1], y_range[1]), y_range[0])
    
    return (round_coord(suggestion[0]), round_coord(suggestion[1]))

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
                return (round_coord(new_x), round_coord(new_y))
            except ValueError:
                print(f"Matched pattern but couldn't convert to float: {match.group(1)}, {match.group(2)}")
                continue
    
    # If we got here, no pattern matched
    print(f"No valid coordinate format found in response: \"{response}\"")
    return None

def llm_make_move(agent_id):
    """Use LLM to determine movement for jammed agents"""
    # Get the last positions for the agent
    last_positions = swarm_pos_dict[agent_id][-num_history_segments:]
    last_valid_position = last_positions[-1][:2]  # Get the last recorded position
    
    # Prepare a movement history string for the last positions
    position_history_str = "\n".join([f"({pos[0]}, {pos[1]})" for pos in last_positions])
    
    print(f"Prompting LLM for new coordinate for {agent_id} from {last_valid_position}")
    
    # Create the prompt message with the position history
    prompt = f"Agent {agent_id} is jammed at {last_valid_position}. " \
             f"Here are the last {num_history_segments} positions:\n{position_history_str}\n" \
             f"Provide exactly one new coordinate pair as (x, y) with both values being numbers. " \
             f"Your response must be 25 characters or less and should only contain the coordinate. "
    
    print(f"Full prompt sent to LLM: {prompt}")
    
    # Try multiple times to get a valid response
    for attempt in range(MAX_RETRIES):
        try:
            # Send the prompt with a timeout
            response = ollama.chat(
                model=LLM_MODEL,
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
    print(f"Failed to get valid coordinates after {MAX_RETRIES} attempts. Using algorithm instead.")
    
    # Fall back to algorithm if LLM fails
    return algorithm_make_move(agent_id)

def get_last_safe_position(agent_id):
    """
    Retrieves the last known safe position for an agent, 
    defined as the most recent position with high communication quality.
    """
    if agent_id in last_safe_position:
        safe_pos = last_safe_position[agent_id]
        print(f"Agent {agent_id}: Returning to stored safe position {safe_pos}")
        return safe_pos

    # If no stored safe position, find one from history
    for pos in reversed(swarm_pos_dict[agent_id]):
        if pos[2] >= high_comm_qual:  # Communication quality must be high
            print(f"Agent {agent_id}: Found historical safe position {pos[:2]}")
            return pos[:2]  # Return the coordinates
            
    # If no valid position found, return the current position
    current_pos = swarm_pos_dict[agent_id][-1][:2]
    print(f"Agent {agent_id}: No valid safe position found, using current position {current_pos}")
    return current_pos

# Button callback functions
def pause_simulation(event):
    """Callback for pause button"""
    global animation_running
    animation_running = False
    print("Simulation paused")

def continue_simulation(event):
    """Callback for continue button"""
    global animation_running
    animation_running = True
    print("Simulation continued")

def stop_simulation(event):
    """Callback for stop button"""
    global animation_running
    animation_running = False
    plt.close('all')  # Close all figures
    print("Simulation stopped")

# Plotting setup
def init_plot():
    """Initialize the plot for animation"""
    ax1.clear()
    ax2.clear()
    
    ax1.set_xlim(x_range)
    ax1.set_ylim(y_range)
    ax1.set_xlabel('X Position')
    ax1.set_ylabel('Y Position')
    ax1.set_title('Agent Position')
    ax1.grid(True)
    
    # Add jamming circle
    jamming_circle = plt.Circle(jamming_center, jamming_radius, color='red', alpha=0.3)
    ax1.add_patch(jamming_circle)
    
    # Add endpoint marker
    ax1.plot(mission_end[0], mission_end[1], 'r*', markersize=10, label='Mission Endpoint')
    
    # Show the max movement radius as a visual guide
    movement_guide = plt.Circle((0, 0), max_movement_per_step, color='blue', 
                               alpha=0.1, fill=False, linestyle='--')
    ax1.add_artist(movement_guide)
    ax1.text(-max_movement_per_step, 0, f"Max step: {max_movement_per_step:.2f}", 
            fontsize=8, color='blue')
    
    ax2.set_xlim(0, 30)
    ax2.set_ylim(0, 1)
    ax2.set_xlabel('Time (s)')
    ax2.set_ylabel('Communication Quality')
    ax2.set_title('Communication Quality over Time')
    ax2.grid(True)
    
    return []

def initialize_agents():
    """Initialize agent positions and states"""
    global swarm_pos_dict, position_history, jammed_positions, last_safe_position
    global agent_paths, pending_llm_actions, returned_to_safe
    
    for i in range(num_agents):
        agent_id = f"agent{i+1}"
        start_x = round_coord(random.uniform(x_range[0], x_range[0] + 5))
        start_y = round_coord(random.uniform(y_range[0], y_range[0] + 5))
        
        # Initialize position with communication quality
        swarm_pos_dict[agent_id] = [[start_x, start_y, high_comm_qual]]
        position_history[agent_id] = [(start_x, start_y)]
        jammed_positions[agent_id] = False  # Boolean flag for jamming status
        last_safe_position[agent_id] = (start_x, start_y)  # Store initial position as safe
        
        # Create path to mission end
        agent_paths[agent_id] = linear_path((start_x, start_y), mission_end)
        
        # Initialize state tracking for the two-step process (return to safe, then move)
        pending_llm_actions[agent_id] = False
        returned_to_safe[agent_id] = False

def update_swarm_data(frame):
    """Update the swarm data for each agent on each frame"""
    global iteration_count
    
    # Only update if animation is running
    if not animation_running:
        return
        
    iteration_count += 1
    
    for agent_id in swarm_pos_dict:
        last_position = swarm_pos_dict[agent_id][-1][:2]
        comm_quality = swarm_pos_dict[agent_id][-1][2]
        is_agent_jammed = is_jammed(last_position)
        
        # Update jammed status
        if is_agent_jammed and not jammed_positions[agent_id]:
            print(f"{agent_id} has entered jamming zone at {last_position}. Communication quality degraded.")
            jammed_positions[agent_id] = True
            # Mark communication quality as low
            swarm_pos_dict[agent_id][-1][2] = low_comm_qual
        
        # Handle movement logic based on jammed status
        if jammed_positions[agent_id]:
            # Two-step process: 1) Return to safe position, 2) Get new move
            
            if not returned_to_safe[agent_id]:
                # Step 1: Return to last safe position
                safe_pos = get_last_safe_position(agent_id)
                
                # Check if we can reach the safe position in one step
                if math.sqrt((safe_pos[0] - last_position[0])**2 + 
                           (safe_pos[1] - last_position[1])**2) > max_movement_per_step:
                    # Can't reach in one step, move toward it
                    next_pos = limit_movement(last_position, safe_pos)
                    print(f"{agent_id} moving toward safe position. Current: {last_position}, Next: {next_pos}")
                    
                    # Update positions
                    swarm_pos_dict[agent_id].append([next_pos[0], next_pos[1], low_comm_qual])
                    position_history[agent_id].append(next_pos)
                else:
                    # Can reach safe position directly
                    print(f"{agent_id} arrived at safe position: {safe_pos}")
                    swarm_pos_dict[agent_id].append([safe_pos[0], safe_pos[1], low_comm_qual])
                    position_history[agent_id].append(safe_pos)
                    returned_to_safe[agent_id] = True
                    pending_llm_actions[agent_id] = True
            
            elif pending_llm_actions[agent_id]:
                # Step 2: Now that we're at a safe position, get next move from LLM or algorithm
                if USE_LLM:
                    print(f"{agent_id} requesting move from LLM")
                    new_coordinate = llm_make_move(agent_id)
                else:
                    print(f"{agent_id} using fittest path algorithm")
                    new_coordinate = algorithm_make_move(agent_id)
                
                # Update position with new coordinates
                swarm_pos_dict[agent_id].append([new_coordinate[0], new_coordinate[1], low_comm_qual])
                position_history[agent_id].append(new_coordinate)
                
                # Reset state flags
                returned_to_safe[agent_id] = False
                pending_llm_actions[agent_id] = False
                
                # Check if still jammed at new position
                if is_jammed(new_coordinate):
                    print(f"{agent_id} still jammed at new position {new_coordinate}")
                    # Stay jammed, will try again next iteration
                else:
                    print(f"{agent_id} has moved out of jamming zone to {new_coordinate}")
                    jammed_positions[agent_id] = False
                    swarm_pos_dict[agent_id][-1][2] = high_comm_qual  # Restore comm quality
                    
                    # Create new path to mission end from new position
                    agent_paths[agent_id] = linear_path(new_coordinate, mission_end)
        
        else:
            # Not jammed, proceed with normal movement
            if agent_id in agent_paths and agent_paths[agent_id]:
                next_pos = agent_paths[agent_id].pop(0)
                
                # Save current position as safe if not jammed
                if not is_jammed(last_position):
                    last_safe_position[agent_id] = last_position
                
                # Update position
                swarm_pos_dict[agent_id].append([next_pos[0], next_pos[1], high_comm_qual])
                position_history[agent_id].append(next_pos)
                
                # Check if new position is jammed
                if is_jammed(next_pos):
                    print(f"{agent_id} has entered jamming zone at {next_pos}")
                    jammed_positions[agent_id] = True
                    swarm_pos_dict[agent_id][-1][2] = low_comm_qual  # Lower comm quality
                
                # Check if we've reached the mission end
                if math.sqrt((next_pos[0] - mission_end[0])**2 + 
                          (next_pos[1] - mission_end[1])**2) < 0.5:
                    print(f"{agent_id} has reached mission endpoint!")
                    # Clear path to stop further movement
                    agent_paths[agent_id] = []

def update_plot(frame):
    """Update the plot for animation, including logging agent data."""
    global iteration_count
    iteration_count += 1
    update_swarm_data(frame)

    ax1.clear()
    ax2.clear()

    # Configure main position plot
    ax1.set_xlim(x_range)
    ax1.set_ylim(y_range)
    ax1.set_xlabel('X Position')
    ax1.set_ylabel('Y Position')
    ax1.set_title(f'Agent Position ({"LLM" if USE_LLM else "Algorithm"} Control)')
    ax1.grid(True)

    # Add jamming circle
    jamming_circle = plt.Circle(jamming_center, jamming_radius, color='red', alpha=0.3)
    ax1.add_patch(jamming_circle)

    # Add endpoint marker
    ax1.plot(mission_end[0], mission_end[1], 'r*', markersize=10, label='Mission End')

    # Configure communication quality plot
    max_time = max(30, iteration_count * update_freq)
    ax2.set_xlim(0, max_time)
    ax2.set_ylim(0, 1)
    ax2.set_xlabel('Time (s)')
    ax2.set_ylabel('Communication Quality')
    ax2.set_title('Communication Quality over Time')
    ax2.grid(True)

    # Track agent data for logging
    agent_data_for_logging = {}  # This will store the history of all agents

    for agent_id in swarm_pos_dict:
        # Plot path history
        x_history = [p[0] for p in position_history[agent_id]]
        y_history = [p[1] for p in position_history[agent_id]]
        ax1.plot(x_history, y_history, 'b-', alpha=0.5)

        # Plot current position
        latest_data = swarm_pos_dict[agent_id][-1]

        # Color based on jammed status
        color = 'red' if jammed_positions[agent_id] else 'green'
        ax1.scatter(latest_data[0], latest_data[1], color=color, s=100, label=f"{agent_id}")

        # Annotate agent ID
        ax1.annotate(agent_id, (latest_data[0], latest_data[1]),
                     fontsize=8, ha='center', va='bottom')

        # Get the communication quality and jammed status
        communication_quality = latest_data[2]  # Assuming the third element is communication quality
        is_jammed = jammed_positions.get(agent_id, False)  # Assuming jammed status is stored in `jammed_positions`

        # Store the data for this agent in the agent_data_for_logging dict
        if agent_id not in agent_data_for_logging:
            agent_data_for_logging[agent_id] = []

        # Record the data (position, communication quality, jammed status)
        agent_data_for_logging[agent_id].append({
            'position': (latest_data[0], latest_data[1]),
            'communication_quality': communication_quality,
            'jammed': is_jammed
        })

        # Plot communication quality over time
        agent_times = [i * update_freq for i in range(len(swarm_pos_dict[agent_id]))]
        agent_comm_quality = [data[2] for data in swarm_pos_dict[agent_id]]
        ax2.plot(agent_times, agent_comm_quality, label=f"{agent_id}", alpha=0.7)

    # Log data every `RAG_UPDATE_FREQUENCY` iterations
    if iteration_count % RAG_UPDATE_FREQUENCY == 0:
        # Log the collected data to the RAG store for all agents
        log_batch_of_data(agent_data_for_logging)

    # Add legends
    ax1.legend(loc='upper left')
    ax2.legend(loc='upper left')

    return []

def run_simulation_with_plots():
    """Main function to run the simulation with plotting"""
    global fig, ax1, ax2, animation_object
    
    # Create figure and arrange subplots side by side
    fig = plt.figure(figsize=(16, 8))
    from matplotlib.gridspec import GridSpec
    gs = GridSpec(1, 2, figure=fig)
    
    # Create the main subplots
    ax1 = fig.add_subplot(gs[0, 0])  # Agent positions plot (left)
    ax2 = fig.add_subplot(gs[0, 1])  # Communication quality plot (right)
    
    # Create button axes at the bottom of the figure (outside GridSpec)
    # Calculate button dimensions and positions
    button_width = 0.1
    button_height = 0.05
    button_bottom = 0.02
    button_spacing = 0.05
    button_start_left = 0.5 - (3*button_width + 2*button_spacing)/2
    
    # Create button axes
    pause_ax = plt.axes([button_start_left, button_bottom, button_width, button_height])
    continue_ax = plt.axes([button_start_left + button_width + button_spacing, 
                           button_bottom, button_width, button_height])
    stop_ax = plt.axes([button_start_left + 2*button_width + 2*button_spacing, 
                        button_bottom, button_width, button_height])
    
    # Create buttons with distinctive colors
    pause_button = Button(pause_ax, 'Pause', color='lightgoldenrodyellow')
    continue_button = Button(continue_ax, 'Continue', color='lightblue')
    stop_button = Button(stop_ax, 'Stop', color='salmon')
    
    # Connect button events to callbacks
    pause_button.on_clicked(pause_simulation)
    continue_button.on_clicked(continue_simulation)
    stop_button.on_clicked(stop_simulation)
    
    # Add title with control mode information
    fig.suptitle(f"Agent Navigation Simulation - {'LLM' if USE_LLM else 'Algorithm'} Control", fontsize=16)
    
    # Initialize agents
    initialize_agents()
    
    # Create animation
    animation_object = FuncAnimation(fig, update_plot, init_func=init_plot, 
                      interval=int(update_freq * 1000), blit=False, cache_frame_data=False)
    
    # Adjust layout to make room for buttons at the bottom
    plt.subplots_adjust(bottom=0.15)
    
    plt.show()

if __name__ == "__main__":
    print(f"Running simulation with {'LLM' if USE_LLM else 'Algorithm'} control")
    run_simulation_with_plots()