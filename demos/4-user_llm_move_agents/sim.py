import math
import random
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Button
from matplotlib.animation import FuncAnimation
import datetime

# Import shared LLM configuration
from llm_config import get_ollama_client, get_model_name
ollama = get_ollama_client()
LLM_MODEL = get_model_name()

from rag_store import add_log  # Import additional needed functions

# Configuration parameters
update_freq = 0.5
x_range = (-10, 10)
y_range = (-10, 10)
num_agents = 5
num_history_segments = 5

# Calculate maximum movement step (diagonal/20)
plane_width = x_range[1] - x_range[0]
plane_height = y_range[1] - y_range[0]
diagonal_length = np.sqrt(plane_width**2 + plane_height**2)
max_movement_per_step = diagonal_length / 20
print(f"[CONFIG] Maximum movement per step: {max_movement_per_step:.2f} units")

# Swarm data tracking
swarm_pos_dict = {}
position_history = {}
time_points = []
iteration_count = 0

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

def log_agent_data(agent_id, position, metadata=None):
    """
    Log agent position data to the RAG store.
    """
    if metadata is None:
        metadata = {}
    
    position = convert_numpy_coords(position)
    timestamp = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')

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
    
    # Generate a unique log ID
    log_id = f"agent-{agent_id}-{timestamp}"
    
    # Add the log to the RAG store
    add_log(log_text=log_text, metadata=log_metadata, log_id=log_id)
    print(f"[LOGGING] Logged data for agent {agent_id} at {position}")

def round_coord(value):
    """Round coordinates to 3 decimal places"""
    return round(value, 3)

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

# Function to be called from the chatapp
def move_agent(agent_id, target_x, target_y):
    """
    Move the specified agent towards the target coordinates.
    Respects the maximum movement distance per step.
    
    Args:
        agent_id (str): The ID of the agent to move.
        target_x (float): The target x-coordinate.
        target_y (float): The target y-coordinate.
        
    Returns:
        dict: A status message and the new position.
    """
    agent_id_str = f"agent{agent_id}" if not agent_id.startswith("agent") else agent_id
    
    # Check if agent exists
    if agent_id_str not in swarm_pos_dict:
        return {
            "success": False,
            "message": f"Agent {agent_id_str} does not exist.",
            "position": None
        }
    
    # Get current position
    current_pos = swarm_pos_dict[agent_id_str][-1][:2]
    
    # Ensure target is within bounds
    target_x = max(min(target_x, x_range[1]), x_range[0])
    target_y = max(min(target_y, y_range[1]), y_range[0])
    target_pos = (target_x, target_y)
    
    # Calculate the limited movement position
    new_pos = limit_movement(current_pos, target_pos)
    
    # Update agent position
    swarm_pos_dict[agent_id_str].append([new_pos[0], new_pos[1]])
    position_history[agent_id_str].append(new_pos)
    
    # Log the movement
    log_agent_data(agent_id_str, new_pos, {
        'action': 'move',
        'target': target_pos,
        'source': 'user_command'
    })
    
    return {
        "success": True,
        "message": f"Agent {agent_id_str} moved from {current_pos} towards {target_pos}. New position: {new_pos}",
        "position": new_pos
    }

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
    ax.clear()
    
    ax.set_xlim(x_range)
    ax.set_ylim(y_range)
    ax.set_xlabel('X Position')
    ax.set_ylabel('Y Position')
    ax.set_title('Agent Position')
    ax.grid(True)
    
    # Show the max movement radius as a visual guide
    movement_guide = plt.Circle((0, 0), max_movement_per_step, color='blue', 
                               alpha=0.1, fill=False, linestyle='--')
    ax.add_artist(movement_guide)
    ax.text(-max_movement_per_step, 0, f"Max step: {max_movement_per_step:.2f}", 
            fontsize=8, color='blue')
    
    return []

def initialize_agents():
    """Initialize agent positions and states"""
    global swarm_pos_dict, position_history
    
    for i in range(num_agents):
        agent_id = f"agent{i+1}"
        start_x = round_coord(random.uniform(x_range[0], x_range[1]))
        start_y = round_coord(random.uniform(y_range[0], y_range[1]))
        
        # Initialize position
        swarm_pos_dict[agent_id] = [[start_x, start_y]]
        position_history[agent_id] = [(start_x, start_y)]
        
        # Log initial position
        log_agent_data(agent_id, (start_x, start_y), {
            'action': 'initialize',
            'source': 'system'
        })

def update_plot(frame):
    """Update the plot for animation"""
    global iteration_count
    
    # Only update if animation is running
    if not animation_running:
        return []
    
    iteration_count += 1
    
    ax.clear()

    # Configure position plot
    ax.set_xlim(x_range)
    ax.set_ylim(y_range)
    ax.set_xlabel('X Position')
    ax.set_ylabel('Y Position')
    ax.set_title('Manual Agent Control Simulation')
    ax.grid(True)

    for agent_id in swarm_pos_dict:
        # Plot path history
        x_history = [p[0] for p in position_history[agent_id]]
        y_history = [p[1] for p in position_history[agent_id]]
        ax.plot(x_history, y_history, 'b-', alpha=0.5)

        # Plot current position
        latest_data = swarm_pos_dict[agent_id][-1]
        ax.scatter(latest_data[0], latest_data[1], color='green', s=100)

        # Annotate agent ID
        ax.annotate(agent_id, (latest_data[0], latest_data[1]),
                     fontsize=8, ha='center', va='bottom')

    # Draw coordinate grid lines
    for x in range(int(x_range[0]), int(x_range[1])+1):
        ax.axvline(x, color='gray', linestyle='--', alpha=0.3)
    for y in range(int(y_range[0]), int(y_range[1])+1):
        ax.axhline(y, color='gray', linestyle='--', alpha=0.3)

    return []

def run_simulation_with_plots():
    """Main function to run the simulation with plotting"""
    global fig, ax, animation_object
    
    # Create figure
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111)
    
    # Create button axes at the bottom of the figure
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
    
    # Add title with information
    fig.suptitle("Manual Agent Control Simulation", fontsize=16)
    
    # Initialize agents
    initialize_agents()
    
    # Create animation
    animation_object = FuncAnimation(fig, update_plot, init_func=init_plot, 
                      interval=int(update_freq * 1000), blit=False, cache_frame_data=False)
    
    # Adjust layout to make room for buttons at the bottom
    plt.subplots_adjust(bottom=0.15)
    
    plt.show()

if __name__ == "__main__":
    print("Running manual agent control simulation")
    run_simulation_with_plots()