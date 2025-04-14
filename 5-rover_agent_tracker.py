import math
import random
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Button
from matplotlib.animation import FuncAnimation
import ollama
import re
import datetime

from rag_store import add_log

# Import the rover helper functions at the top of your script
from rover_helper_functions import (
    get_rover_path, calculate_distance_to_rover, get_closest_safe_point,
    ROVER_START_POINT, ROVER_END_POINT, ROVER_SPEED, AGENT_DIST_TO_ROVER
)

# Add rover-specific variables in the global variables section
rover_pos_dict = {}  # Track rover positions and communication quality
rover_path = []  # Store the rover's path
rover_jammed = False  # Track if the rover is jammed
rover_last_safe_position = None  # Store the last safe position
rover_waiting_for_agents = False  # Track if the rover is waiting for agents

# Toggle between LLM and algorithm-based control
USE_LLM = False  # Set to True to use LLM, False to use algorithm

# Configuration parameters
update_freq = 0.5
high_comm_qual = 0.80
low_comm_qual = 0.20
x_range = (-10, 10)
y_range = (-10, 10)
num_agents = 3
num_history_segments = 5
RAG_UPDATE_FREQUENCY = 5  # Add this line - log data every 5 iterations
DIST_BETWEEN_AGENTS = 2  # Minimum required distance between agents

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
                'jammed': jammed,
                'role': 'system',
                'source': 'simulation'
            }

            # Correct order of parameters: log_text, metadata, agent_id=None, log_id=None
            add_log(log_text=log_text, metadata=metadata, log_id=log_id)

def round_coord(value):
    """Round coordinates to 3 decimal places"""
    return round(value, 3)

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

def limit_movement(current_pos, target_pos, agent_id=None):
    """Limit movement to max_movement_per_step and check distance to other agents only when near rover"""
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
        limited_pos = target_np  # We can reach the target directly
    else:
        # Move in the direction of the target, but only by max_movement_per_step
        direction = (target_np - current_np) / distance
        limited_pos = current_np + direction * max_movement_per_step
    
    # Convert to tuple with rounded coordinates
    result_pos = (round_coord(limited_pos[0]), round_coord(limited_pos[1]))
    
    # We don't check for agent distances here anymore, as it's done in update_agent_position
    return result_pos

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

def calculate_rover_comm_quality(rover_pos, agent_positions):
    """Calculate communication quality between rover and all agents"""
    total_quality = 0
    num_agents = len(agent_positions)
    
    for agent_id, positions in agent_positions.items():
        if agent_id == "rover":  # Skip rover itself
            continue
            
        agent_pos = positions[-1][:2]  # Get latest position
        distance = calculate_distance_to_rover(agent_pos, rover_pos)
        
        # Communication quality degrades with distance
        if distance <= AGENT_DIST_TO_ROVER:
            # Good communication within range
            agent_quality = high_comm_qual
        else:
            # Degraded communication beyond range
            degradation = min(1.0, (distance - AGENT_DIST_TO_ROVER) / 10)
            agent_quality = max(low_comm_qual, high_comm_qual - degradation)
            
        total_quality += agent_quality
    
    # Average quality across all agents
    if num_agents > 0:
        return total_quality / num_agents
    return high_comm_qual  # Default if no agents

def is_too_close_to_other_agents(agent_id, position):
    """
    Check if the given position would place the agent too close to any other agent,
    but only enforce this constraint when agent is within range of the rover
    """
    # Get current rover position
    rover_position = rover_pos_dict["rover"][-1][:2]
    
    # Calculate distance to rover
    distance_to_rover = calculate_distance_to_rover(position, rover_position)
    
    # Only enforce minimum distance if in range of rover
    if distance_to_rover <= AGENT_DIST_TO_ROVER:
        for other_id, positions in swarm_pos_dict.items():
            # Skip self and rover
            if other_id == agent_id or other_id == "rover":
                continue
                
            other_pos = positions[-1][:2]  # Get latest position of other agent
            
            # Check if other agent is also in range of rover
            other_distance_to_rover = calculate_distance_to_rover(other_pos, rover_position)
            if other_distance_to_rover <= AGENT_DIST_TO_ROVER:
                # Both agents in range of rover, check distance between them
                distance = math.sqrt((position[0] - other_pos[0])**2 + (position[1] - other_pos[1])**2)
                
                if distance < DIST_BETWEEN_AGENTS:
                    return True
    
    return False

def update_rover_position():
    """Update the rover's position based on its path and jamming status"""
    global rover_jammed, rover_waiting_for_agents, rover_last_safe_position, rover_path
    
    # Get current rover position
    last_position = rover_pos_dict["rover"][-1][:2]
    
    # Check if rover is jammed
    is_rover_jammed = is_jammed(last_position)
    
    # If rover just entered jamming zone
    if is_rover_jammed and not rover_jammed:
        print(f"Rover has entered jamming zone at {last_position}. Communication quality degraded.")
        rover_jammed = True
        # Mark communication quality as low
        rover_pos_dict["rover"][-1][2] = low_comm_qual
    
    # If rover just exited jamming zone
    if not is_rover_jammed and rover_jammed:
        print(f"Rover has exited jamming zone at {last_position}. Communication quality restored.")
        rover_jammed = False
        rover_pos_dict["rover"][-1][2] = high_comm_qual
    
    # Store the last safe position when not jammed
    if not is_rover_jammed:
        rover_last_safe_position = last_position
    
    # Handle rover movement based on jammed status
    if rover_jammed:
        # Check if all agents are within required distance
        all_agents_close = True
        for agent_id in swarm_pos_dict:
            if agent_id == "rover":
                continue
                
            agent_pos = swarm_pos_dict[agent_id][-1][:2]
            distance = calculate_distance_to_rover(agent_pos, last_position)
            
            if distance > AGENT_DIST_TO_ROVER:
                all_agents_close = False
                break
        
        if all_agents_close:
            # All agents are close, rover can continue on its path
            rover_waiting_for_agents = False
            
            if rover_path:
                next_pos = rover_path.pop(0)
                # Update rover position
                comm_quality = calculate_rover_comm_quality(next_pos, swarm_pos_dict)
                rover_pos_dict["rover"].append([next_pos[0], next_pos[1], comm_quality])
                position_history["rover"].append(next_pos)
                
                # Check if still jammed at new position
                if is_jammed(next_pos):
                    print(f"Rover still jammed at new position {next_pos}")
                else:
                    print(f"Rover has moved out of jamming zone to {next_pos}")
                    rover_jammed = False
        else:
            # Rover is waiting for agents to get closer
            if not rover_waiting_for_agents:
                print("Rover is jammed and waiting for all agents to get within range")
                rover_waiting_for_agents = True
                
            # Stay in place
            rover_pos_dict["rover"].append([last_position[0], last_position[1], low_comm_qual])
            position_history["rover"].append(last_position)
    else:
        # Not jammed, proceed with normal movement
        if rover_path:
            next_pos = rover_path.pop(0)
            
            # Update position with current communication quality
            comm_quality = calculate_rover_comm_quality(next_pos, swarm_pos_dict)
            rover_pos_dict["rover"].append([next_pos[0], next_pos[1], comm_quality])
            position_history["rover"].append(next_pos)
            
            # Check if new position is jammed
            if is_jammed(next_pos):
                print(f"Rover has entered jamming zone at {next_pos}")
                rover_jammed = True
                rover_pos_dict["rover"][-1][2] = low_comm_qual  # Lower comm quality
            
            # Check if we've reached the end point
            if math.sqrt((next_pos[0] - ROVER_END_POINT[0])**2 + 
                       (next_pos[1] - ROVER_END_POINT[1])**2) < 0.5:
                print(f"Rover has reached endpoint!")
                # Keep path empty to stop further movement
                rover_path = []
        else:
            # No more path points, stay in place
            rover_pos_dict["rover"].append([last_position[0], last_position[1], 
                                           rover_pos_dict["rover"][-1][2]])
            position_history["rover"].append(last_position)

def update_agent_position(agent_id):
    global swarm_pos_dict, rover_pos_dict
    """Update an individual agent's position based on its relationship to the rover"""
    current_pos = swarm_pos_dict[agent_id][-1][:2]
    # Get current agent position
    last_position = swarm_pos_dict[agent_id][-1][:2]
    comm_quality = swarm_pos_dict[agent_id][-1][2]

    # get the next position to check distance from rover
    next_pos = get_last_safe_position(agent_id)

    # Get current rover position
    rover_position = rover_pos_dict["rover"][-1][:2]
    distance_to_rover = calculate_distance_to_rover(next_pos, rover_position)
    
    if distance_to_rover <= AGENT_DIST_TO_ROVER and is_too_close_to_other_agents(agent_id, next_pos):
        print(f"{agent_id} is too close to other agents within rover range, adjusting position")
        
        # Try up to 8 positions in different directions
        original_pos = next_pos
        found_valid_pos = False
        
        for angle in [0, np.pi/4, np.pi/2, 3*np.pi/4, np.pi, 5*np.pi/4, 3*np.pi/2, 7*np.pi/4]:
            # Try moving DIST_BETWEEN_AGENTS away in this direction
            adjusted_pos = (
                original_pos[0] + DIST_BETWEEN_AGENTS * np.cos(angle),
                original_pos[1] + DIST_BETWEEN_AGENTS * np.sin(angle)
            )
            
            # Make sure we don't exceed maximum movement
            if np.linalg.norm(np.array(adjusted_pos) - np.array(last_position)) <= max_movement_per_step:
                # Check if this new position is valid
                if not is_too_close_to_other_agents(agent_id, adjusted_pos):
                    next_pos = (round_coord(adjusted_pos[0]), round_coord(adjusted_pos[1]))
                    found_valid_pos = True
                    break
        
        # If we couldn't find a valid position, just maintain our current position
        if not found_valid_pos:
            print(f"{agent_id} couldn't find valid position, staying put")
            next_pos = last_position
    
        # Update position with new communication quality
        new_comm_quality = high_comm_qual if not is_jammed(next_pos) else low_comm_qual
        swarm_pos_dict[agent_id].append([next_pos[0], next_pos[1], new_comm_quality])
        position_history[agent_id].append(next_pos)
        
        # Check if still jammed at new position
        if not is_jammed(next_pos):
            print(f"{agent_id} has moved out of jamming zone to {next_pos}")
            jammed_positions[agent_id] = False
            swarm_pos_dict[agent_id][-1][2] = high_comm_qual  # Restore comm quality
    
    else:
        # Agent is not jammed, check distance to rover
        if distance_to_rover > AGENT_DIST_TO_ROVER:
            # Agent is too far from rover, find a closer point
            print(f"{agent_id} is too far from rover ({distance_to_rover:.2f} > {AGENT_DIST_TO_ROVER}), moving closer")
            
            # Get a safe point closer to the rover
            target_pos = get_closest_safe_point(
                last_position, rover_position, jamming_center, jamming_radius, AGENT_DIST_TO_ROVER
            )
            
            # Check if we can reach the target position in one step
            if math.sqrt((target_pos[0] - last_position[0])**2 + 
                       (target_pos[1] - last_position[1])**2) > max_movement_per_step:
                # Can't reach in one step, move toward it
                next_pos = limit_movement(last_position, target_pos, agent_id)
            else:
                # Can reach target position directly
                next_pos = target_pos
        else:
            # Agent is within range of rover, just follow along
            # Stay at current position if already in good position
            next_pos = last_position
            
            # If rover moved, adjust position to follow
            if len(position_history["rover"]) > 1:
                prev_rover_pos = position_history["rover"][-2]
                curr_rover_pos = position_history["rover"][-1]
                
                # If rover moved, move agent by same vector if possible
                if prev_rover_pos != curr_rover_pos:
                    rover_movement = (
                        curr_rover_pos[0] - prev_rover_pos[0],
                        curr_rover_pos[1] - prev_rover_pos[1]
                    )
                    
                    # Potential new position for agent
                    potential_pos = (
                        last_position[0] + rover_movement[0],
                        last_position[1] + rover_movement[1]
                    )
                    
                    # Check if new position is safe and within step size
                    distance_to_potential = math.sqrt((potential_pos[0] - last_position[0])**2 + 
                                                    (potential_pos[1] - last_position[1])**2)
                    
                    if not is_jammed(potential_pos) and distance_to_potential <= max_movement_per_step:
                        next_pos = potential_pos
        
        # Save current position as safe if not jammed
        if not is_jammed(last_position):
            last_safe_position[agent_id] = last_position
        
        # Update position with new communication quality
        new_comm_quality = high_comm_qual if not is_jammed(next_pos) else low_comm_qual
        swarm_pos_dict[agent_id].append([next_pos[0], next_pos[1], new_comm_quality])
        position_history[agent_id].append(next_pos)
        
        # Check if new position is jammed
        if is_jammed(next_pos) and not jammed_positions[agent_id]:
            print(f"{agent_id} has entered jamming zone at {next_pos}")
            jammed_positions[agent_id] = True
            swarm_pos_dict[agent_id][-1][2] = low_comm_qual

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
    global rover_pos_dict, rover_path, rover_jammed, rover_last_safe_position
    
    # Initialize rover
    rover_start_x, rover_start_y = ROVER_START_POINT
    rover_pos_dict["rover"] = [[rover_start_x, rover_start_y, high_comm_qual]]
    position_history["rover"] = [(rover_start_x, rover_start_y)]
    rover_path = get_rover_path(ROVER_START_POINT, ROVER_END_POINT, ROVER_SPEED)
    rover_jammed = False
    rover_last_safe_position = ROVER_START_POINT
    
    # Initialize regular agents with minimum distance constraint
    agent_positions = []  # Track positions to check minimum distance
    
    for i in range(num_agents):
        agent_id = f"agent{i+1}"
        
        # Try multiple times to find a position that satisfies the minimum distance
        max_attempts = 20
        valid_position = False
        
        for _ in range(max_attempts):
            # Start agents randomly near the rover's starting position
            start_x = round_coord(rover_start_x + random.uniform(-3, 3))
            start_y = round_coord(rover_start_y + random.uniform(-3, 3))
            
            # Check distance to other agents
            too_close = False
            for pos in agent_positions:
                distance = math.sqrt((start_x - pos[0])**2 + (start_y - pos[1])**2)
                if distance < DIST_BETWEEN_AGENTS:
                    too_close = True
                    break
            
            if not too_close:
                valid_position = True
                agent_positions.append((start_x, start_y))
                break
        
        # If couldn't find a valid position, use the last attempt anyway
        if not valid_position:
            print(f"Warning: Could not place {agent_id} with minimum distance constraint after {max_attempts} attempts")
            start_x = round_coord(rover_start_x + random.uniform(-3, 3))
            start_y = round_coord(rover_start_y + random.uniform(-3, 3))
            agent_positions.append((start_x, start_y))
        
        # Initialize position with communication quality
        swarm_pos_dict[agent_id] = [[start_x, start_y, high_comm_qual]]
        position_history[agent_id] = [(start_x, start_y)]
        jammed_positions[agent_id] = False  # Boolean flag for jamming status
        last_safe_position[agent_id] = (start_x, start_y)  # Store initial position as safe
        
        # Paths will be dynamically updated to follow rover
        agent_paths[agent_id] = []
        
        # Initialize state tracking
        pending_llm_actions[agent_id] = False
        returned_to_safe[agent_id] = False

def update_swarm_data(frame):
    """Update the swarm data for each agent and the rover on each frame"""
    global iteration_count, rover_waiting_for_agents
    
    # Only update if animation is running
    if not animation_running:
        return
        
    iteration_count += 1
    
    # First update the rover position
    update_rover_position()
    
    # Then update all regular agents
    for agent_id in swarm_pos_dict:
        if agent_id == "rover":  # Skip rover as it's already updated
            continue
            
        update_agent_position(agent_id)

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

    # Add rover circle showing communication range
    rover_pos = rover_pos_dict["rover"][-1][:2]
    rover_range_circle = plt.Circle(rover_pos, AGENT_DIST_TO_ROVER, color='blue', alpha=0.1, fill=True)
    ax1.add_patch(rover_range_circle)

    # Add endpoint marker
    ax1.plot(ROVER_END_POINT[0], ROVER_END_POINT[1], 'r*', markersize=10, label='Rover End')

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

    # First plot rover data
    rover_data = rover_pos_dict["rover"][-1]
    rover_is_jammed = rover_jammed
    
    # Plot rover's path history
    rover_x_history = [p[0] for p in position_history["rover"]]
    rover_y_history = [p[1] for p in position_history["rover"]]
    ax1.plot(rover_x_history, rover_y_history, 'b-', alpha=0.5)
    
    # Plot rover's current position with different colors based on jamming status
    if rover_is_jammed:
        rover_color = 'yellow'  # Yellow when jammed
    else:
        rover_color = 'blue'    # Blue when not jammed
        
    ax1.scatter(rover_data[0], rover_data[1], color=rover_color, s=150, marker='s', label="rover")
    
    # Annotate rover
    ax1.annotate("ROVER", (rover_data[0], rover_data[1]),
                 fontsize=10, ha='center', va='bottom', weight='bold')
    
    # Store rover data for logging
    agent_data_for_logging["rover"] = [{
        'position': (rover_data[0], rover_data[1]),
        'communication_quality': rover_data[2],
        'jammed': rover_is_jammed
    }]
    
    # Plot rover communication quality over time
    rover_times = [i * update_freq for i in range(len(rover_pos_dict["rover"]))]
    rover_comm_quality = [data[2] for data in rover_pos_dict["rover"]]
    ax2.plot(rover_times, rover_comm_quality, 'b-', linewidth=2, label="rover", alpha=0.7)

    # Then plot regular agent data
    for agent_id in swarm_pos_dict:
        if agent_id == "rover":  # Skip rover as it's already plotted
            continue
            
        # Plot path history
        x_history = [p[0] for p in position_history[agent_id]]
        y_history = [p[1] for p in position_history[agent_id]]
        ax1.plot(x_history, y_history, 'g-', alpha=0.5)

        # Plot current position
        # Get the latest agent position
        latest_data = swarm_pos_dict[agent_id][-1]
        agent_pos = (latest_data[0], latest_data[1])
        
        # Calculate if agent is in range of rover and maintaining distance
        rover_pos = rover_pos_dict["rover"][-1][:2]
        distance_to_rover = calculate_distance_to_rover(agent_pos, rover_pos)
        in_rover_range = distance_to_rover <= AGENT_DIST_TO_ROVER
        
        # Color based on jammed status and rover range
        if jammed_positions[agent_id]:
            color = 'red'  # Red when jammed
        else:
            if in_rover_range:
                # Check if maintaining distance from other agents
                maintaining_distance = not is_too_close_to_other_agents(agent_id, agent_pos)
                color = 'green' if maintaining_distance else 'orange'  # Orange if too close to others
            else:
                color = 'green'  # Regular green when not in rover range
                
        ax1.scatter(latest_data[0], latest_data[1], color=color, s=100, label=f"{agent_id}")
        

        # Annotate agent ID
        ax1.annotate(agent_id, (latest_data[0], latest_data[1]),
                     fontsize=8, ha='center', va='bottom')

        # Get the communication quality and jammed status
        communication_quality = latest_data[2]
        is_jammed = jammed_positions.get(agent_id, False)

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

    # Add legends with fewer items
    # Get unique labels from the plotted data
    handles, labels = ax1.get_legend_handles_labels()
    unique_labels = []
    unique_handles = []
    
    # Keep only one instance of each label
    for handle, label in zip(handles, labels):
        if label not in unique_labels:
            unique_labels.append(label)
            unique_handles.append(handle)
    
    # Add a legend with only unique labels
    ax1.legend(unique_handles, unique_labels, loc='upper left')
    
    # Same for the second plot
    handles, labels = ax2.get_legend_handles_labels()
    unique_labels = []
    unique_handles = []
    
    for handle, label in zip(handles, labels):
        if label not in unique_labels:
            unique_labels.append(label)
            unique_handles.append(handle)
    
    ax2.legend(unique_handles, unique_labels, loc='upper left')

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