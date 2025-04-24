# simulation_controller.py
import random
import numpy as np
import datetime
import time
from rag_store import add_log
import threading


# Simulation configuration
x_range = (-10, 10)
y_range = (-10, 10)
num_agents = 1
max_movement_per_step = np.sqrt((x_range[1] - x_range[0])**2 + (y_range[1] - y_range[0])**2) / 20
MAX_POSITIONS = 10  # Maximum number of positions to keep in swarm_pos_dict for each agent
UPDATE_FREQ = 3  # Frequency of updates in seconds
AGENT_CLOSE_TO_WAYPOINT_THRESHOLD = 0.2  # Threshold for considering an agent close to a waypoint

# State management
swarm_pos_dict = {}
position_history = {}
agent_waypoints = {}  # Dictionary to store {agent_id: [(x1, y1), (x2, y2), ...]}
simulation_active = False
simulation_thread = None

# Path planning & targeting
agent_targets = {}  # Dictionary to store {agent_id: (target_x, target_y)}
agent_paths = {}    # Dictionary to store {agent_id: [(x1,y1), (x2,y2), ...]} - waypoints along path
agent_full_paths = {}  # new: track full path for plotting
agent_modes = {}    # Dictionary to store {agent_id: "random" or "user_directed"}

def round_coord(value):
    """Round coordinates to 3 decimal places"""
    return round(value, 3)

def convert_numpy_coords(obj):
    """Convert numpy data types to native Python types for JSON serialization and display."""
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
        converted_list = [convert_numpy_coords(item) for item in obj]
        return tuple(converted_list) if isinstance(obj, tuple) else converted_list
    elif isinstance(obj, dict):
        return {key: convert_numpy_coords(value) for key, value in obj.items()}
    return obj

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

            add_log(log_text=log_text, metadata=metadata, log_id=log_id)

# Track previous positions to avoid redundant logging
previous_positions = {}

def log_agent_data(agent_id, position, metadata=None):
    """
    Log agent position data to the RAG store only if the position has changed.
    """
    global previous_positions

    # Convert position to a tuple for comparison
    position_tuple = tuple(position)

    # Check if the position has changed
    if previous_positions.get(agent_id) == position_tuple:
        return  # Skip logging if the position hasn't changed

    # Update the previous position
    previous_positions[agent_id] = position_tuple

    if metadata is None:
        metadata = {}

    position = convert_numpy_coords(position)
    timestamp = datetime.datetime.now().isoformat()

    log_text = f"Agent {agent_id} is at position {position}."

    log_metadata = {
        'timestamp': timestamp,
        'agent_id': agent_id,
        'position': position,
        'role': 'system',
        'source': 'simulation'
    }

    # Add any additional metadata
    log_metadata.update(metadata)

    # Add the log to the RAG store
    add_log(log_text=log_text, metadata=log_metadata)
    print(f"[LOGGING] Logged data for agent {agent_id} at {position}")

def is_close_to_target(position, target, threshold=AGENT_CLOSE_TO_WAYPOINT_THRESHOLD):
    """Check if position is close to the target within the given threshold."""
    pos_np = np.array(position)
    target_np = np.array(target)
    distance = np.linalg.norm(pos_np - target_np)
    return distance <= threshold

def generate_linear_path(start_pos, target_pos):
    """Generate a linear path from start to target using steps based on max_movement_per_step."""
    start_np = np.array(start_pos)
    target_np = np.array(target_pos)
    
    # Calculate the total distance
    total_distance = np.linalg.norm(target_np - start_np)
    
    # Calculate how many steps we need based on max_movement_per_step
    num_steps = max(1, int(total_distance / max_movement_per_step))
    
    # Generate path points
    path = []
    for i in range(1, num_steps + 1):  # Start from 1 to exclude the starting position
        t = i / num_steps
        point = start_np + t * (target_np - start_np)
        path.append((round_coord(point[0]), round_coord(point[1])))
    
    print(f"[DEBUG] Generated linear path: {path}")
    return path

def update_simulation():
    """Periodically update the simulation and log agent positions."""
    global simulation_active, agent_targets, agent_paths, agent_modes, agent_waypoints, agent_full_paths

    while simulation_active:
        for agent_id, positions in swarm_pos_dict.items():
            # Get the current position (most recent)
            current_pos = positions[-1][:2]
            new_pos = None  # We'll set this based on movement logic

            # Check if the agent has a path to follow
            if agent_id in agent_paths and agent_paths[agent_id]:
                # Follow the next point in the path
                next_point = agent_paths[agent_id].pop(0)
                new_pos = next_point
                agent_modes[agent_id] = "user_directed"  # Ensure mode is set to user-directed
                print(f"[DEBUG] Following path: Agent {agent_id} moving from {current_pos} to {new_pos}")

                # If the path is now empty, switch to random movement
                if not agent_paths[agent_id]:
                    print(f"[DEBUG] Agent {agent_id} completed its path")
                    
                    # Check if agent has reached waypoint
                    if agent_id in agent_waypoints and agent_waypoints[agent_id]:
                        current_waypoint = agent_waypoints[agent_id][0]
                        if is_close_to_target(new_pos, current_waypoint):
                            print(f"[DEBUG] Agent {agent_id} reached waypoint {current_waypoint}")
                            # Remove the reached waypoint
                            agent_waypoints[agent_id].pop(0)
                            
                            # Clear the full path since waypoint is reached
                            if agent_id in agent_full_paths:
                                agent_full_paths[agent_id] = []
                                print(f"[DEBUG] Cleared full path for agent {agent_id} after reaching waypoint")
                    
                    agent_modes[agent_id] = "random"

            # If no path, check for waypoints
            elif agent_id in agent_waypoints and agent_waypoints[agent_id]:
                if not agent_paths.get(agent_id):
                    target_pos = agent_waypoints[agent_id][0]
                    agent_paths[agent_id] = generate_linear_path(current_pos, target_pos)
                    agent_full_paths[agent_id] = agent_paths[agent_id].copy()
                    print(f"[DEBUG] Generated new path for agent {agent_id} with {len(agent_paths[agent_id])} points")

                if agent_paths[agent_id]:
                    next_point = agent_paths[agent_id].pop(0)
                    new_pos = next_point

            # If no waypoints or paths, use random movement
            if new_pos is None:
                agent_modes[agent_id] = "random"
                target_x = round_coord(random.uniform(x_range[0], x_range[1]))
                target_y = round_coord(random.uniform(y_range[0], y_range[1]))
                random_target = (target_x, target_y)
                new_pos = limit_movement(current_pos, random_target)
                print(f"[DEBUG] Random move for agent {agent_id} from {current_pos} to {new_pos}")

            # Update agent position in swarm_pos_dict
            swarm_pos_dict[agent_id].append([new_pos[0], new_pos[1]])

            # If the number of positions exceeds MAX_POSITIONS, remove the oldest one
            if len(swarm_pos_dict[agent_id]) > MAX_POSITIONS:
                swarm_pos_dict[agent_id].pop(0)

            # Update the position history (keep all logs)
            position_history[agent_id].append(new_pos)

            # Log the movement
            log_agent_data(agent_id, new_pos, {
                'action': 'move',
                'mode': agent_modes[agent_id],
                'source': 'simulation'
            })

        print(f"[DEBUG] Updated swarm_pos_dict: {convert_numpy_coords(swarm_pos_dict)}")
        time.sleep(UPDATE_FREQ)

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

def parse_agent_id(agent_id):
    """Parse agent ID from different formats."""
    # Convert to string if it's a number
    if isinstance(agent_id, (int, float)):
        agent_id = str(int(agent_id))
    
    # If it's just a number as string, add the 'agent' prefix
    if agent_id.isdigit():
        return f"agent{agent_id}"
    
    # If it already has 'agent' prefix, return as is
    if agent_id.startswith("agent"):
        return agent_id
    
    # Try to extract the number and add prefix
    import re
    numbers = re.findall(r'\d+', agent_id)
    if numbers:
        return f"agent{numbers[0]}"
    
    # If all else fails, return as is
    return agent_id

def initialize_agents(log=True):
    """Initialize agent positions and states"""
    global swarm_pos_dict, position_history, agent_modes

    # Clear existing state
    swarm_pos_dict = {}
    position_history = {}
    agent_modes = {}

    for i in range(1, num_agents + 1):
        agent_id = f"agent{i}"
        start_x = round_coord(random.uniform(x_range[0], x_range[1]))
        start_y = round_coord(random.uniform(y_range[0], y_range[1]))

        # Initialize position
        swarm_pos_dict[agent_id] = [[start_x, start_y]]
        position_history[agent_id] = [(start_x, start_y)]
        agent_modes[agent_id] = "random"  # Start in random mode

        # Log initial position if logging is enabled
        if log:
            log_agent_data(agent_id, (start_x, start_y), {
                'action': 'initialize',
                'source': 'system'
            })

    print(f"[DEBUG] Initialized agents: {swarm_pos_dict}")
    return list(swarm_pos_dict.keys())

def start_simulation(log=True):
    """Start the simulation in a separate thread"""
    global simulation_active, simulation_thread
    
    if simulation_active:
        return False  # Already running
    
    # Initialize agents if not already done
    if not swarm_pos_dict:
        initialize_agents(log=log)
    
    # Set flag and start thread
    simulation_active = True
    simulation_thread = threading.Thread(target=update_simulation)
    simulation_thread.daemon = True  # Thread will exit when main program exits
    simulation_thread.start()
    
    print("[DEBUG] Simulation started")
    return True

def move_agent(agent_id, target_x, target_y):
    """Move the specified agent towards the target coordinates."""
    global agent_targets, agent_paths, agent_modes
    
    # Parse the agent ID to handle different formats
    agent_id_str = parse_agent_id(agent_id)
    
    print(f"[DEBUG] Moving agent {agent_id_str} to ({target_x}, {target_y})")
    print(f"[DEBUG] Available agents: {list(swarm_pos_dict.keys())}")
    
    # Check if agent exists
    if agent_id_str not in swarm_pos_dict:
        return {
            "success": False,
            "message": f"Agent {agent_id_str} does not exist. Available agents: {list(swarm_pos_dict.keys())}",
            "position": None
        }
    
    # Get current position
    current_pos = swarm_pos_dict[agent_id_str][-1][:2]
    
    # Ensure target is within bounds
    target_x = max(min(float(target_x), x_range[1]), x_range[0])
    target_y = max(min(float(target_y), y_range[1]), y_range[0])
    target_pos = (target_x, target_y)
    
    # Generate a path to the target
    path = generate_linear_path(current_pos, target_pos)
    
    # Save the target and path
    agent_targets[agent_id_str] = target_pos
    agent_paths[agent_id_str] = path[1:]  # Skip the first point which is the current position
    agent_modes[agent_id_str] = "user_directed"  # Set to user-directed mode
    
    # Calculate the first step (this will be within max_movement_per_step)
    new_pos = limit_movement(current_pos, target_pos) if not agent_paths[agent_id_str] else agent_paths[agent_id_str][0]
    
    # Update agent position
    swarm_pos_dict[agent_id_str].append([new_pos[0], new_pos[1]])
    position_history[agent_id_str].append(new_pos)
    
    # Log the movement
    log_agent_data(agent_id_str, new_pos, {
        'action': 'move',
        'target': target_pos,
        'mode': 'user_directed',
        'source': 'user_command'
    })
    
    # Calculate total path length and remaining waypoints
    remaining_waypoints = len(agent_paths[agent_id_str])
    estimated_steps_to_target = remaining_waypoints
    
    print(f"[DEBUG] Agent {agent_id_str} moved to {new_pos}")
    print(f"[DEBUG] Path generated with {remaining_waypoints} waypoints")
    
    return {
        "success": True,
        "message": f"Agent {agent_id_str} moved from {current_pos} towards {target_pos}. New position: {new_pos}. "
                   f"Estimated steps to target: {estimated_steps_to_target}.",
        "position": new_pos,
        "path_length": remaining_waypoints + 1
    }

def stop_simulation():
    """Stop the simulation thread"""
    global simulation_active
    simulation_active = False
    if simulation_thread and simulation_thread.is_alive():
        simulation_thread.join(timeout=1.0)
    return True

def get_agent_positions():
    """Get current positions of all agents"""
    positions_dict = {agent_id: positions[-1][:2] for agent_id, positions in swarm_pos_dict.items()}
    
    # Add information about user-assigned targets and modes
    for agent_id, pos in positions_dict.items():
        mode = agent_modes.get(agent_id, "random")
        if mode == "user_directed" and agent_id in agent_targets:
            target = agent_targets[agent_id]
            remaining_waypoints = len(agent_paths.get(agent_id, []))
            positions_dict[agent_id] = (
                pos, 
                f"Moving to {target} ({remaining_waypoints} steps remaining)"
            )
    
    return positions_dict

def check_simulation_status():
    """Check if simulation is running and initialize if not"""
    global swarm_pos_dict, simulation_active
    
    print(f"Current simulation status - Active: {simulation_active}, Agents: {len(swarm_pos_dict)}")
    
    if not swarm_pos_dict or len(swarm_pos_dict) == 0:
        # First time startup - initialize
        initialize_agents()
        start_simulation()
        return "Simulation initialized and started"
    elif not simulation_active:
        # Simulation was stopped - restart
        start_simulation()
        return "Simulation restarted"
    else:
        # Already running
        return "Simulation is running with agents: " + ", ".join(swarm_pos_dict.keys())
    
def add_waypoint(agent_id, target_x, target_y):
    """
    Add a waypoint for the specified agent.
    The agent will move to this waypoint in a linear path.
    """
    global agent_waypoints, agent_paths, agent_full_paths
    
    # Parse the agent ID to handle different formats
    agent_id_str = parse_agent_id(agent_id)
    
    # Check if agent exists
    if agent_id_str not in swarm_pos_dict:
        print(f"[ERROR] Cannot add waypoint - Agent {agent_id_str} does not exist")
        return False
    
    # Ensure target is within bounds
    target_x = max(min(float(target_x), x_range[1]), x_range[0])
    target_y = max(min(float(target_y), y_range[1]), y_range[0])
    target_pos = (target_x, target_y)
    
    # Initialize waypoints list if not exists
    if agent_id_str not in agent_waypoints:
        agent_waypoints[agent_id_str] = []
    
    # Add the waypoint to the queue
    agent_waypoints[agent_id_str].append((target_x, target_y))
    
    # Generate a linear path from current position to waypoint
    current_pos = swarm_pos_dict[agent_id_str][-1][:2]
    linear_path = generate_linear_path(current_pos, target_pos)
    
    # Save the path
    agent_paths[agent_id_str] = linear_path
    agent_full_paths[agent_id_str] = linear_path.copy()
    
    # Set the agent mode to user_directed
    agent_modes[agent_id_str] = "user_directed"
    
    # Log the addition of a waypoint
    log_agent_data(agent_id_str, current_pos, {
        'action': 'waypoint_added',
        'waypoint': target_pos,
        'source': 'user_command'
    })
    
    print(f"[DEBUG] Added waypoint for {agent_id_str}: ({target_x}, {target_y})")
    print(f"[DEBUG] Generated linear path with {len(linear_path)} points")
    return True

def print_waypoints_status():
    """Print the current status of all waypoints for debugging."""
    print("\n=== WAYPOINTS STATUS ===")
    for agent_id, waypoints in agent_waypoints.items():
        if waypoints:
            current_pos = swarm_pos_dict[agent_id][-1][:2] if agent_id in swarm_pos_dict else "Unknown"
            distance = np.linalg.norm(np.array(current_pos) - np.array(waypoints[0])) if current_pos != "Unknown" else "Unknown"
            print(f"Agent {agent_id}: Current pos {current_pos}, Waypoint {waypoints[0]}, Distance {distance:.2f}")
        else:
            print(f"Agent {agent_id}: No waypoints")
    print("========================\n")