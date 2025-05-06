import math
import random
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Button
from matplotlib.animation import FuncAnimation
import datetime
from matplotlib.gridspec import GridSpec
import threading
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
from typing import Dict, List, Tuple, Optional, Any
import time

# Import shared LLM configuration
from llm_config import get_ollama_client, get_model_name
from rag_store import add_telemetry_data

# Import helper functions
from sim_helper_funcs import (
    round_coord, is_jammed, linear_path, limit_movement, 
    algorithm_make_move, llm_make_move,
    get_last_safe_position, log_batch_of_data
)

# Create FastAPI app
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Toggle between LLM and algorithm-based control
USE_LLM = False  # Set to True to use LLM, False to use algorithm

# Configuration parameters
update_freq = 2.5 # seconds 
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
manually_moved_agents = set()
agent_targets = {}  # Format: {agent_id: (target_x, target_y)}

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
        
        # Check if the agent has a target coordinate
        if agent_id in agent_targets:
            target_x, target_y = agent_targets[agent_id]
            distance_to_target = math.sqrt((target_x - last_position[0])**2 + (target_y - last_position[1])**2)

            if distance_to_target <= max_movement_per_step:
                # Target reached
                print(f"{agent_id} reached target coordinate: ({target_x}, {target_y})")
                swarm_pos_dict[agent_id].append([target_x, target_y, high_comm_qual])
                position_history[agent_id].append((target_x, target_y))
                del agent_targets[agent_id]  # Remove the target
                
                # Now create a new path to mission end from this position
                print(f"{agent_id} calculating new path to mission endpoint from ({target_x}, {target_y})")
                agent_paths[agent_id] = linear_path((target_x, target_y), mission_end, max_movement_per_step)
                
                # Store this position as a safe position if we're not in a jamming zone
                if not is_jammed((target_x, target_y), jamming_center, jamming_radius):
                    last_safe_position[agent_id] = (target_x, target_y)
            else:
                # Move toward the target
                next_pos = limit_movement(last_position, (target_x, target_y), max_movement_per_step)
                print(f"{agent_id} moving toward target: {next_pos}")
                
                # Check if this position is jammed and update communication quality accordingly
                is_pos_jammed = is_jammed(next_pos, jamming_center, jamming_radius)
                comm_quality = low_comm_qual if is_pos_jammed else high_comm_qual
                
                # Update position with appropriate communication quality
                swarm_pos_dict[agent_id].append([next_pos[0], next_pos[1], comm_quality])
                position_history[agent_id].append(next_pos)
                
                # Update jammed status if entering jamming zone
                if is_pos_jammed and not jammed_positions[agent_id]:
                    jammed_positions[agent_id] = True
                    print(f"{agent_id} has entered jamming zone while moving to target.")
            continue

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
                if not is_jammed(last_position, jamming_center, jamming_radius):
                    last_safe_position[agent_id] = last_position
                swarm_pos_dict[agent_id].append([next_pos[0], next_pos[1], high_comm_qual])
                position_history[agent_id].append(next_pos)
                if is_jammed(next_pos, jamming_center, jamming_radius):
                    jammed_positions[agent_id] = True
                    swarm_pos_dict[agent_id][-1][2] = low_comm_qual
                if math.sqrt((next_pos[0] - mission_end[0])**2 + (next_pos[1] - mission_end[1])**2) < 0.5:
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

        # Special color if agent was moved manually
        if agent_id in manually_moved_agents:
            color = 'blue'  # Highlight moved agents in blue
        else:
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

# Define Pydantic models for API request/response
class MoveAgentRequest(BaseModel):
    agent: str
    x: float
    y: float

class AgentPosition(BaseModel):
    x: float
    y: float
    communication_quality: float
    jammed: bool

class SimulationStatus(BaseModel):
    running: bool
    iteration_count: int
    agent_positions: Dict[str, AgentPosition]

class SimulationSettings(BaseModel):
    use_llm: bool = None
    mission_end: Tuple[float, float] = None
    jamming_center: Tuple[float, float] = None
    jamming_radius: float = None

# API endpoints
@app.get("/")
async def root():
    return {"message": "Simulation API is running"}

@app.get("/status", response_model=SimulationStatus)
async def get_status():
    """Get the current status of the simulation"""
    global swarm_pos_dict, jammed_positions, iteration_count, animation_running
    
    agent_positions = {}
    for agent_id in swarm_pos_dict:
        if swarm_pos_dict[agent_id]:
            latest_pos = swarm_pos_dict[agent_id][-1]
            agent_positions[agent_id] = AgentPosition(
                x=latest_pos[0],
                y=latest_pos[1],
                communication_quality=latest_pos[2],
                jammed=jammed_positions.get(agent_id, False)
            )
    
    return SimulationStatus(
        running=animation_running,
        iteration_count=iteration_count,
        agent_positions=agent_positions
    )

def add_log(log_text, metadata=None):
    """
    Wrapper function to log telemetry data using add_telemetry_data.
    Formats the log for Qdrant's expected structure.
    """
    if metadata is None:
        metadata = {}

    # Call add_telemetry_data to store the log in Qdrant
    telemetry_id = add_telemetry_data(data_text=log_text, metadata=metadata)
    print(f"Telemetry data logged with ID: {telemetry_id}")

@app.post("/move_agent")
async def move_agent(request: MoveAgentRequest):
    """Move an agent to specific coordinates"""
    global swarm_pos_dict, agent_targets
    
    agent_id = request.agent
    x = request.x
    y = request.y
    
    print(f"[API CALL] Received request to move {agent_id} to ({x}, {y})")
    
    # Check if agent exists
    if agent_id not in swarm_pos_dict:
        print(f"[API ERROR] Agent {agent_id} not found")
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    
    # Set the target coordinates for the agent
    agent_targets[agent_id] = (x, y)
    print(f"[API INFO] Target for {agent_id} set to ({x}, {y})")
    
    # Log the target assignment
    timestamp = datetime.datetime.now().isoformat()
    add_log(f"API set target for agent {agent_id} to coordinates ({x}, {y})", {
        "agent_id": agent_id,
        "target": f"({x}, {y})",
        "timestamp": timestamp,
        "source": "api",
        "action": "set_target"
    })
    
    return {
        "success": True,
        "message": f"Agent {agent_id} will move toward ({x}, {y})"
    }

@app.get("/agents")
async def get_agents():
    """Get list of all agents and their current status"""
    global swarm_pos_dict, jammed_positions
    
    agents = {}
    for agent_id in swarm_pos_dict:
        if swarm_pos_dict[agent_id]:
            latest_pos = swarm_pos_dict[agent_id][-1]
            # Convert numpy types to Python native types
            agents[agent_id] = {
                "position": [float(latest_pos[0]), float(latest_pos[1])],
                "communication_quality": float(latest_pos[2]),
                "jammed": bool(jammed_positions.get(agent_id, False))
            }
    
    return {"agents": agents}

@app.get("/simulation_params")
async def get_simulation_params():
    """Get current simulation parameters"""
    return {
        "use_llm": USE_LLM,
        "mission_end": mission_end,
        "jamming_center": jamming_center,
        "jamming_radius": jamming_radius,
        "max_movement_per_step": max_movement_per_step,
        "x_range": x_range,
        "y_range": y_range
    }

@app.patch("/simulation_params")
async def update_simulation_params(settings: SimulationSettings):
    """Update simulation parameters"""
    global USE_LLM, mission_end, jamming_center, jamming_radius
    
    # Update only the parameters that are provided
    if settings.use_llm is not None:
        USE_LLM = settings.use_llm
    
    if settings.mission_end is not None:
        mission_end = settings.mission_end
    
    if settings.jamming_center is not None:
        jamming_center = settings.jamming_center
    
    if settings.jamming_radius is not None:
        jamming_radius = settings.jamming_radius
    
    return {
        "message": "Simulation parameters updated",
        "current_params": {
            "use_llm": USE_LLM,
            "mission_end": mission_end,
            "jamming_center": jamming_center,
            "jamming_radius": jamming_radius
        }
    }

@app.post("/control/pause")
async def api_pause_simulation():
    """Pause the simulation"""
    global animation_running
    animation_running = False
    return {"message": "Simulation paused"}

@app.post("/control/continue")
async def api_continue_simulation():
    """Continue the simulation"""
    global animation_running
    animation_running = True
    return {"message": "Simulation continued"}

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all API requests and responses"""
    # Generate a unique request ID
    request_id = str(time.time())
    
    # Get the request path and method
    path = request.url.path
    method = request.method
    
    # Log the request
    print(f"[API REQUEST {request_id}] {method} {path}")
    
    # Try to get and log the request body
    try:
        body = await request.body()
        if body:
            print(f"[API REQUEST BODY {request_id}] {body.decode()}")
    except Exception:
        pass
    
    # Process the request
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    # Log the response
    print(f"[API RESPONSE {request_id}] Status: {response.status_code}, Time: {process_time:.4f}s")
    
    return response

def run_api_server():
    """Run FastAPI server in a separate thread"""
    uvicorn.run(app, host="127.0.0.1", port=5001)

if __name__ == "__main__":
    print(f"Running simulation with {'LLM' if USE_LLM else 'Algorithm'} control")
    
    # Start API server in a separate thread
    api_thread = threading.Thread(target=run_api_server, daemon=True)
    api_thread.start()
    
    # Initialize agents before starting the simulation
    initialize_agents()
    
    # Run the simulation with plots
    run_simulation_with_plots()