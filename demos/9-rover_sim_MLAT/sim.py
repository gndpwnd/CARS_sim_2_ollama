import math
import random
import numpy as np
import datetime
from config import *
from rover_helpers import (
    get_rover_path, calculate_distance_to_rover, get_closest_safe_point,
    ROVER_START_POINT, ROVER_END_POINT, ROVER_SPEED, AGENT_DIST_TO_ROVER
)
from sim_helpers import (
    convert_numpy_coords, round_coord, is_jammed
)
from rag_store import add_log

# Global state variables
rover_pos_dict = {}  # Track rover positions and communication quality
rover_path = []  # Store the rover's path
rover_jammed = False  # Track if the rover is jammed
rover_last_safe_position = None  # Store the last safe position
rover_waiting_for_agents = False  # Track if the rover is waiting for agents

# Swarm data tracking
swarm_pos_dict = {}
position_history = {}
jammed_positions = {}
last_safe_position = {}
time_points = []
iteration_count = 0

# Simulation state tracking
agent_paths = {}
pending_llm_actions = {}
returned_to_safe = {}

def log_batch_of_data(agent_histories: dict, prefix="batch"):
    """Log a batch of data from all agents. One log per agent per data point."""
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

            add_log(log_text=log_text, metadata=metadata, log_id=log_id)

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
        if not is_jammed(suggestion, jamming_center, jamming_radius):
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
    """Parses the LLM response to extract the new coordinates (x, y)."""
    # Try different regex patterns to match coordinates
    patterns = [
        r"\((-?\d+\.?\d*),\s*(-?\d+\.?\d*)\)",  # (x, y) format
        r"x:?\s*(-?\d+\.?\d*)[,\s]*y:?\s*(-?\d+\.?\d*)",  # x: value, y: value
        r"(-?\d+\.?\d*)[,\s]+(-?\d+\.?\d*)",  # two numbers separated by comma
        r"(-?\d+\.?\d*)\s*\n\s*(-?\d+\.?\d*)"  # two numbers on separate lines
    ]
    
    for pattern in patterns:
        match = re.search(pattern, response)
        if match:
            try:
                new_x = float(match.group(1))
                new_y = float(match.group(2))
                return (round_coord(new_x), round_coord(new_y))
            except ValueError:
                print(f"Matched pattern but couldn't convert to float: {match.group(1)}, {match.group(2)}")
                continue
    
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
    
    # Fall back to algorithm if LLM fails
    return algorithm_make_move(agent_id)

def get_last_safe_position(agent_id):
    """Retrieves the last known safe position for an agent."""
    if agent_id in last_safe_position:
        safe_pos = last_safe_position[agent_id]
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
    """Check if the given position would place the agent too close to any other agent"""
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
    is_rover_jammed = is_jammed(last_position, jamming_center, jamming_radius)
    
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
                if is_jammed(next_pos, jamming_center, jamming_radius):
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
            if is_jammed(next_pos, jamming_center, jamming_radius):
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
    """Update an individual agent's position based on its relationship to the rover"""
    global swarm_pos_dict, rover_pos_dict
    
    current_pos = swarm_pos_dict[agent_id][-1][:2]
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
        new_comm_quality = high_comm_qual if not is_jammed(next_pos, jamming_center, jamming_radius) else low_comm_qual
        swarm_pos_dict[agent_id].append([next_pos[0], next_pos[1], new_comm_quality])
        position_history[agent_id].append(next_pos)
        
        # Check if still jammed at new position
        if not is_jammed(next_pos, jamming_center, jamming_radius):
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
                    
                    if not is_jammed(potential_pos, jamming_center, jamming_radius) and distance_to_potential <= max_movement_per_step:
                        next_pos = potential_pos
        
        # Save current position as safe if not jammed
        if not is_jammed(last_position, jamming_center, jamming_radius):
            last_safe_position[agent_id] = last_position
        
        # Update position with new communication quality
        new_comm_quality = high_comm_qual if not is_jammed(next_pos, jamming_center, jamming_radius) else low_comm_qual
        swarm_pos_dict[agent_id].append([next_pos[0], next_pos[1], new_comm_quality])
        position_history[agent_id].append(next_pos)
        
        # Check if new position is jammed
        if is_jammed(next_pos, jamming_center, jamming_radius) and not jammed_positions[agent_id]:
            print(f"{agent_id} has entered jamming zone at {next_pos}")
            jammed_positions[agent_id] = True
            swarm_pos_dict[agent_id][-1][2] = low_comm_qual

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
    
    iteration_count += 1
    
    # First update the rover position
    update_rover_position()
    
    # Then update all regular agents
    for agent_id in swarm_pos_dict:
        if agent_id == "rover":  # Skip rover as it's already updated
            continue
            
        update_agent_position(agent_id)