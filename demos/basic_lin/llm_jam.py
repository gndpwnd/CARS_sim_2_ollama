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

    # Plot agent positions on the top plot
    for agent_id, pos_history in position_history.items():
        ax1.plot([p[0] for p in pos_history], [p[1] for p in pos_history], 'b-', alpha=0.5)
        latest_data = swarm_pos_dict[agent_id][-1]
        
        # Use jammed_positions boolean flag for determining color
        color = 'red' if jammed_positions[agent_id] else 'green'
        ax1.scatter(latest_data[0], latest_data[1], color=color, s=100, label=f"{agent_id}")

    # Plot communication quality for each agent in the bottom plot
    for agent_id, pos_history in position_history.items():
        # Get the communication quality for this agent for every time step
        agent_comm_quality = [swarm_pos_dict[agent_id][i][2] for i in range(len(swarm_pos_dict[agent_id]))]  # Communication quality for each agent
        
        # Create a list of time points for this agent (this assumes you're updating communication quality every `update_freq` frames)
        agent_time_points = [i * update_freq for i in range(len(agent_comm_quality))]  # Time steps for each communication quality point
        
        # Plot communication quality over time for this agent
        ax2.plot(agent_time_points, agent_comm_quality, label=f"{agent_id}", alpha=0.7)

    ax1.legend(loc='upper left')
    ax2.legend(loc='upper left')

    return []

def initialize_agents():
    global swarm_pos_dict, position_history, jammed_positions
    for i in range(num_agents):
        agent_id = f"agent{i+1}"
        start_x = round_coord(random.uniform(x_range[0], x_range[0] + 5))
        start_y = round_coord(random.uniform(y_range[0], y_range[0] + 5))
        swarm_pos_dict[agent_id] = [[start_x, start_y, high_comm_qual]]  # Position with communication quality
        position_history[agent_id] = [(start_x, start_y)]
        jammed_positions[agent_id] = False  # Boolean flag for jamming status

def call_llm(iteration):
    global llm_responses
    
    # Create the message to send, including position and communication quality for each agent
    prompt = f"Movement data (with communication quality): {position_history}"
    print(f"Full prompt sent to LLM: {prompt}")
    
    # Send the prompt to the LLM
    response = ollama.chat(
        model="llama3.2:1b",
        messages=[{"role": "user", "content": prompt}]
    )
    
    # Get and store the response
    response_content = response.get('message', {}).get('content', 'No response')
    llm_responses[iteration] = response_content
    print(f"Full LLM Response at iteration {iteration}: \"{response_content}\"")

def llm_make_move(agent_id):
    # Number of historical segments to include in the prompt
    num_history_segments = 5
    
    # Get the last `num_history_segments` positions for the agent
    last_positions = swarm_pos_dict[agent_id][-num_history_segments:]
    
    # Calculate the distance from the last position to the jamming center
    last_valid_position = last_positions[-1][:2]  # Get the last recorded position
    distance_to_jamming = math.sqrt((last_valid_position[0] - jamming_center[0])**2 + 
                                    (last_valid_position[1] - jamming_center[1])**2)
    
    # If the agent is outside the jamming radius, no LLM input is needed
    if distance_to_jamming > jamming_radius:
        print(f"{agent_id} is already outside jamming zone at {last_valid_position}. No LLM input needed.")
        return last_valid_position
    
    # Prepare a movement history string for the last `num_history_segments` positions
    position_history = "\n".join([f"({pos[0]}, {pos[1]})" for pos in last_positions])
    
    print(f"Prompting LLM for new coordinate for {agent_id} from {last_valid_position}")
    
    # Create the prompt message with the position history
    prompt = f"Agent {agent_id} is jammed at {last_valid_position}. " \
             f"Here are the last {num_history_segments} positions:\n{position_history}\n" \
             f"Provide exactly one new coordinate pair as (x, y) with both values being numbers. " \
             f"Your response must be 25 characters or less and should only contain the coordinate."
    
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

def get_last_safe_position(agent_id):
    """
    Retrieves the last known safe position for an agent, defined as the most recent position with high communication quality.
    """
    # Iterate over the history of the agent's positions in reverse to find the last valid position
    for pos in reversed(swarm_pos_dict[agent_id]):
        if pos[2] >= high_comm_qual:  # Communication quality must be high
            print(f"Agent {agent_id}: Returning to safe position {pos[:2]}")  # Print agent ID and position
            return pos[:2]  # Return the coordinates
    # If no valid position found, return the current position
    print(f"Agent {agent_id}: No valid previous safe position found, using current position {swarm_pos_dict[agent_id][-1][:2]}")
    return swarm_pos_dict[agent_id][-1][:2]  # Return the current position if no safe one is found

def update_swarm_data(frame):
    global iteration_count
    iteration_count += 1
    
    # Track which agents need LLM input
    jammed_agents = {}

    # First pass - identify jammed agents and move non-jammed agents
    for agent_id in swarm_pos_dict:
        last_position = swarm_pos_dict[agent_id][-1][:2]
        comm_quality = swarm_pos_dict[agent_id][-1][2]
        distance_to_jamming = math.sqrt((last_position[0] - jamming_center[0])**2 + (last_position[1] - jamming_center[1])**2)
        
        if distance_to_jamming <= jamming_radius:
            print(f"{agent_id} is jammed at {last_position}. Requesting new coordinate from LLM.")
            # Mark communication quality as low
            swarm_pos_dict[agent_id].append([last_position[0], last_position[1], low_comm_qual])
            jammed_positions[agent_id] = True  # Mark as currently jammed
            
            # Store this agent for LLM processing
            jammed_agents[agent_id] = True
            
            # Do not move to a new position yet, wait until the next iteration
            # Move to the last safe position (non-jammed, high communication quality) on the next iteration
            safe_position = get_last_safe_position(agent_id)
            position_history[agent_id].append(safe_position)  # Add safe position to history
        else:
            # Agent is outside jamming zone
            # Check if it was previously jammed and now recovered
            if agent_id in jammed_positions and jammed_positions[agent_id]:
                print(f"{agent_id} has recovered from jamming at {last_position}. Resuming normal operation.")
                jammed_positions[agent_id] = False  # Mark as no longer jammed
            
            # Non-jammed agent - proceed with normal movement
            path = linear_path(last_position, mission_end)
            if path:
                next_position = path[0]
                # High communication quality for agents outside jamming zone
                swarm_pos_dict[agent_id].append([round_coord(next_position[0]), round_coord(next_position[1]), high_comm_qual])
                position_history[agent_id].append(next_position)
    
    # Second pass - handle jammed agents that need to be moved to their safe position
    for agent_id in jammed_agents:
        # Get the last safe position and move there in the next iteration
        safe_position = get_last_safe_position(agent_id)
        
        # Move agent to its last safe position on the next iteration
        if len(swarm_pos_dict[agent_id]) > 1:
            # Use safe position
            swarm_pos_dict[agent_id].append([round_coord(safe_position[0]), round_coord(safe_position[1]), low_comm_qual])
            position_history[agent_id].append(safe_position)
        
        # Now, get LLM input for new coordinates after returning to the safe position
        new_coordinate = llm_make_move(agent_id)
        
        # Update position history with new coordinate from LLM
        if new_coordinate:
            # Only update if we got valid coordinates
            swarm_pos_dict[agent_id][-1] = [round_coord(new_coordinate[0]), round_coord(new_coordinate[1]), low_comm_qual]
            position_history[agent_id][-1] = new_coordinate
            
            # Check if the new position is outside the jamming zone
            distance_to_jamming = math.sqrt((new_coordinate[0] - jamming_center[0])**2 + 
                                            (new_coordinate[1] - jamming_center[1])**2)
            if distance_to_jamming > jamming_radius:
                print(f"{agent_id} moved out of jamming zone to {new_coordinate}. Comm quality restored.")
                # Update comm quality to high since agent is now outside jamming zone
                swarm_pos_dict[agent_id][-1][2] = high_comm_qual
                jammed_positions[agent_id] = False  # Mark as no longer jammed


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