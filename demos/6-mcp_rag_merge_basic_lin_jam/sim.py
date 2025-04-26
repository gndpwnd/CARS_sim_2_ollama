import math
import random
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Button
from matplotlib.animation import FuncAnimation
import datetime
from matplotlib.gridspec import GridSpec

# Import shared LLM configuration
from llm_config import get_ollama_client, get_model_name
from rag_store import add_log  # Import additional needed functions

# Import helper functions
from sim_helper_funcs import (
    round_coord, is_jammed, linear_path, limit_movement, 
    algorithm_make_move, llm_make_move, parse_llm_response,
    get_last_safe_position, log_batch_of_data
)

# Toggle between LLM and algorithm-based control
USE_LLM = False  # Set to True to use LLM, False to use algorithm

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

# RAG parameters
RAG_UPDATE_FREQUENCY = 5  # Log agent data every 5 iterations (same as buffer size)

# LLM Prompt Constraints
MAX_CHARS_PER_AGENT = 25
LLM_PROMPT_TIMEOUT = 5  # seconds to wait for LLM response before giving up
MAX_RETRIES = 3  # maximum number of retries for LLM prompting

# Global variables for simulation state
swarm_pos_dict = {}
position_history = {}
jammed_positions = {}
last_safe_position = {}
time_points = []
iteration_count = 0
agent_paths = {}
pending_llm_actions = {}
returned_to_safe = {}
animation_running = True
animation_object = None
fig = None
ax1 = None
ax2 = None

# Initialize LLM client
ollama = get_ollama_client()
LLM_MODEL = get_model_name()

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
        agent_paths[agent_id] = linear_path((start_x, start_y), mission_end, max_movement_per_step)
        
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
        is_agent_jammed = is_jammed(last_position, jamming_center, jamming_radius)
        
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
                safe_pos = get_last_safe_position(agent_id, last_safe_position, swarm_pos_dict, high_comm_qual)
                
                # Check if we can reach the safe position in one step
                if math.sqrt((safe_pos[0] - last_position[0])**2 + 
                           (safe_pos[1] - last_position[1])**2) > max_movement_per_step:
                    # Can't reach in one step, move toward it
                    next_pos = limit_movement(last_position, safe_pos, max_movement_per_step)
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
                    new_coordinate = llm_make_move(
                        agent_id, swarm_pos_dict, num_history_segments, ollama, LLM_MODEL, 
                        MAX_CHARS_PER_AGENT, MAX_RETRIES, jamming_center, jamming_radius, 
                        max_movement_per_step, x_range, y_range
                    )
                else:
                    print(f"{agent_id} using fittest path algorithm")
                    current_pos = swarm_pos_dict[agent_id][-1][:2]
                    new_coordinate = algorithm_make_move(
                        agent_id, current_pos, jamming_center, jamming_radius, 
                        max_movement_per_step, x_range, y_range
                    )
                
                # Update position with new coordinates
                swarm_pos_dict[agent_id].append([new_coordinate[0], new_coordinate[1], low_comm_qual])
                position_history[agent_id].append(new_coordinate)
                
                # Reset state flags
                returned_to_safe[agent_id] = False
                pending_llm_actions[agent_id] = False
                
                # Check if still jammed at new position
                if is_jammed(new_coordinate, jamming_center, jamming_radius):
                    print(f"{agent_id} still jammed at new position {new_coordinate}")
                    # Stay jammed, will try again next iteration
                else:
                    print(f"{agent_id} has moved out of jamming zone to {new_coordinate}")
                    jammed_positions[agent_id] = False
                    swarm_pos_dict[agent_id][-1][2] = high_comm_qual  # Restore comm quality
                    
                    # Create new path to mission end from new position
                    agent_paths[agent_id] = linear_path(new_coordinate, mission_end, max_movement_per_step)
        
        else:
            # Not jammed, proceed with normal movement
            if agent_id in agent_paths and agent_paths[agent_id]:
                next_pos = agent_paths[agent_id].pop(0)
                
                # Save current position as safe if not jammed
                if not is_jammed(last_position, jamming_center, jamming_radius):
                    last_safe_position[agent_id] = last_position
                
                # Update position
                swarm_pos_dict[agent_id].append([next_pos[0], next_pos[1], high_comm_qual])
                position_history[agent_id].append(next_pos)
                
                # Check if new position is jammed
                if is_jammed(next_pos, jamming_center, jamming_radius):
                    print(f"{agent_id} has entered jamming zone at {next_pos}")
                    jammed_positions[agent_id] = True
                    swarm_pos_dict[agent_id][-1][2] = low_comm_qual  # Lower comm quality
                
                # Check if we've reached the mission end
                if math.sqrt((next_pos[0] - mission_end[0])**2 + 
                          (next_pos[1] - mission_end[1])**2) < 0.5:
                    print(f"{agent_id} has reached mission endpoint!")
                    # Clear path to stop further movement
                    agent_paths[agent_id] = []

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

def update_plot(frame):
    """Update the plot for animation, including logging agent data."""
    global iteration_count
    
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
        log_batch_of_data(agent_data_for_logging, add_log)

    # Add legends
    ax1.legend(loc='upper left')
    ax2.legend(loc='upper left')

    return []

def run_simulation_with_plots():
    """Main function to run the simulation with plotting"""
    global fig, ax1, ax2, animation_object
    
    print(f"[CONFIG] Maximum movement per step: {max_movement_per_step:.2f} units")
    
    # Create figure and arrange subplots side by side
    fig = plt.figure(figsize=(16, 8))
    gs = GridSpec(1, 2, figure=fig)
    
    # Create the main subplots
    ax1 = fig.add_subplot(gs[0, 0])  # Agent positions plot (left)
    ax2 = fig.add_subplot(gs[0, 1])  # Communication quality plot (right)
    
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