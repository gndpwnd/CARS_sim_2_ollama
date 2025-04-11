import sys
import random
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button
from PyQt5.QtWidgets import QApplication

# Simulation parameters
num_agents = 5
jamming_radius = 5
jamming_center = np.array([0, 0])  # Center of jamming
communication_threshold = 0.2
mission_endpoint = np.array([10, 10])
num_history_segments = 5
update_freq = 0.5  # seconds

# Calculate the maximum movement distance (diagonal/20)
plane_width = 20  # -10 to 10
plane_height = 20  # -10 to 10
diagonal_length = np.sqrt(plane_width**2 + plane_height**2)
max_movement_per_step = diagonal_length / 20
print(f"[CONFIG] Maximum movement per step: {max_movement_per_step:.2f} units")

def linear_path(start, end):
    """Create a linear path between start and end points with max step distance constraint"""
    path = []
    start_np = np.array(start)
    end_np = np.array(end)
    total_distance = np.linalg.norm(end_np - start_np)
    direction = (end_np - start_np) / total_distance if total_distance > 0 else np.array([0, 0])
    
    # Calculate number of steps needed
    num_steps = int(np.ceil(total_distance / max_movement_per_step))
    
    for i in range(1, num_steps + 1):
        # For the last step, make sure we arrive exactly at the endpoint
        if i == num_steps:
            next_point = end_np
        else:
            next_point = start_np + direction * i * max_movement_per_step
            
        path.append(next_point)
    
    return path

def round_coord(value):
    """Round coordinates to 3 decimal places"""
    return round(value, 3)

def limit_movement(current_pos, target_pos):
    """Limit movement to max_movement_per_step"""
    current_np = np.array(current_pos)
    target_np = np.array(target_pos)
    distance = np.linalg.norm(target_np - current_np)
    
    if distance <= max_movement_per_step:
        return target_np  # We can reach the target directly
    
    # Otherwise, move in the direction of the target, but only by max_movement_per_step
    direction = (target_np - current_np) / distance
    return current_np + direction * max_movement_per_step

# Initialize agent states
def initialize_agents():
    """Initialize agent positions and states"""
    agent_positions = [np.array([random.uniform(-10, -5), random.uniform(-10, -5)]) for _ in range(num_agents)]
    agent_paths = [linear_path(pos, mission_endpoint) for pos in agent_positions]
    agent_jammed = [False] * num_agents
    agent_comm_quality = [1.0] * num_agents
    movement_history = [[] for _ in range(num_agents)]
    for i, pos in enumerate(agent_positions):
        movement_history[i].append(pos.copy())
    last_safe_position = [pos.copy() for pos in agent_positions]
    
    return agent_positions, agent_paths, agent_jammed, agent_comm_quality, movement_history, last_safe_position

# Placeholder LLM call
def llm_make_move(agent_id, history, current_pos):
    """Simulated LLM call to make decision for jammed agents, with movement constraint"""
    print(f"[LLM] Requesting new move for Agent {agent_id} with history: {history[-3:]}")
    
    # Try to find a valid move that's outside the jamming zone
    max_attempts = 10
    for _ in range(max_attempts):
        # Generate a random direction (unit vector)
        angle = random.uniform(0, 2 * np.pi)
        direction = np.array([np.cos(angle), np.sin(angle)])
        
        # Move max_movement_per_step in that direction
        suggestion = current_pos + direction * max_movement_per_step
        
        # Clamp to the boundaries of the plane
        suggestion[0] = max(min(suggestion[0], 10), -10)
        suggestion[1] = max(min(suggestion[1], 10), -10)
        
        # Check if this would be outside the jamming zone
        if not is_jammed(suggestion):
            print(f"[LLM] Suggested new coordinate for Agent {agent_id}: {suggestion}")
            return suggestion
    
    # If we failed to find a good move after max_attempts, just move in a random valid direction
    print(f"[LLM] Couldn't find non-jammed position for Agent {agent_id}, moving randomly")
    angle = random.uniform(0, 2 * np.pi)
    direction = np.array([np.cos(angle), np.sin(angle)])
    suggestion = current_pos + direction * max_movement_per_step
    
    # Clamp to the boundaries
    suggestion[0] = max(min(suggestion[0], 10), -10)
    suggestion[1] = max(min(suggestion[1], 10), -10)
    
    return suggestion

# Check if inside jamming zone
def is_jammed(pos):
    """Check if a position is inside the jamming zone"""
    return np.linalg.norm(pos - jamming_center) <= jamming_radius

def run_simulation():
    """Main function to run the simulation"""
    # Initialize figure with subplot layout - add space for two buttons now
    fig = plt.figure(figsize=(10, 9))
    ax = plt.subplot2grid((9, 1), (0, 0), rowspan=7)  # Main plot area
    stop_button_ax = plt.subplot2grid((9, 1), (7, 0))  # Stop button area
    close_button_ax = plt.subplot2grid((9, 1), (8, 0))  # Close button area
    
    # Setup plot area
    ax.set_xlim(-10, 10)
    ax.set_ylim(-10, 10)
    ax.set_xlabel('X Position')
    ax.set_ylabel('Y Position')
    ax.set_title('Agent Position Simulation')
    ax.grid(True)
    
    # Add jamming circle
    circle = plt.Circle(jamming_center, jamming_radius, color='red', alpha=0.3)
    ax.add_artist(circle)
    
    # Add mission endpoint marker
    endpoint_marker, = ax.plot(mission_endpoint[0], mission_endpoint[1], 'r*', markersize=10, label='Mission Endpoint')
    
    # Show the max movement radius
    movement_circle = plt.Circle((0, 0), max_movement_per_step, color='blue', alpha=0.1, fill=False, linestyle='--')
    ax.add_artist(movement_circle)
    ax.text(-max_movement_per_step, 0, f"Max step: {max_movement_per_step:.2f}", fontsize=8, color='blue')
    
    # Initialize agent data
    agent_positions, agent_paths, agent_jammed, agent_comm_quality, movement_history, last_safe_position = initialize_agents()
    
    # Initialize agent markers and path lines
    agent_markers = []
    path_lines = []
    legend_handles = [endpoint_marker]  # Start with the endpoint marker
    
    for i in range(num_agents):
        # Green markers for agents
        marker, = ax.plot([agent_positions[i][0]], [agent_positions[i][1]], 'go', markersize=8, label=f"Agent {i+1}")
        agent_markers.append(marker)
        legend_handles.append(marker)
        
        # Blue lines for path tracers
        line, = ax.plot([], [], 'b-', alpha=0.5)
        path_lines.append(line)
    
    # Create legend with all agents
    legend = ax.legend(handles=legend_handles, loc='upper left')
    
    # Add buttons with clear labels
    stop_button = Button(stop_button_ax, 'STOP SIMULATION', color='yellow', hovercolor='gold')
    close_button = Button(close_button_ax, 'CLOSE SIMULATION', color='red', hovercolor='darkred')
    
    # Variables to track simulation state
    simulation_state = {
        'running': True,
        'close_requested': False,
        'pending_llm_actions': [False] * num_agents,
        'returned_to_safe': [False] * num_agents,
        'legend': legend  # Store the legend in the state so it's accessible
    }
    
    def stop_simulation(event):
        """Callback for stop button - pauses the simulation but keeps window open"""
        if simulation_state['running']:
            print("[GUI] Stop button clicked. Pausing simulation.")
            simulation_state['running'] = False
            stop_button.label.set_text('RESUME SIMULATION')
            stop_button.color = 'lightgreen'
        else:
            print("[GUI] Resume button clicked. Resuming simulation.")
            simulation_state['running'] = True
            stop_button.label.set_text('STOP SIMULATION')
            stop_button.color = 'yellow'
        
        # Force a redraw of the button
        stop_button_ax.figure.canvas.draw()
    
    def close_simulation(event):
        """Callback for close button - terminates simulation and closes window"""
        print("[GUI] Close button clicked. Terminating simulation.")
        simulation_state['close_requested'] = True
        simulation_state['running'] = False
        plt.close(fig)
    
    stop_button.on_clicked(stop_simulation)
    close_button.on_clicked(close_simulation)
    
    # Core iteration logic
    iteration = [0]
    
    # Update function for animation
    def update(frame):
        if simulation_state['close_requested']:
            ani.event_source.stop()
            return agent_markers + path_lines
        
        if not simulation_state['running']:
            return agent_markers + path_lines
        
        for i in range(num_agents):
            history = movement_history[i]
            
            # Handle jammed agents in the correct sequence:
            # 1. If jammed, first return to safety
            # 2. Only after return is confirmed, ask LLM for new move
            if agent_jammed[i]:
                if not simulation_state['returned_to_safe'][i]:
                    # Step 1: Return to last safe position first
                    print(f"[Agent {i}] Jammed - returning to last safe position: {last_safe_position[i]}")
                    # Apply movement constraint to return to safety
                    if np.linalg.norm(last_safe_position[i] - agent_positions[i]) > max_movement_per_step:
                        # Can't reach safe point in one step, move towards it
                        new_pos = limit_movement(agent_positions[i], last_safe_position[i])
                        agent_positions[i] = new_pos
                        movement_history[i].append(new_pos.copy())
                        # Update the marker - fixed to use sequences
                        agent_markers[i].set_data([agent_positions[i][0]], [agent_positions[i][1]])
                        print(f"[Agent {i}] Moving towards safe position: {agent_positions[i]}")
                    else:
                        # Can reach safe point directly
                        agent_positions[i] = last_safe_position[i].copy()
                        movement_history[i].append(agent_positions[i].copy())
                        simulation_state['returned_to_safe'][i] = True  # Mark as returned to safety
                        simulation_state['pending_llm_actions'][i] = True  # Need LLM action next
                        # Update the marker - fixed to use sequences
                        agent_markers[i].set_data([agent_positions[i][0]], [agent_positions[i][1]])
                        print(f"[Agent {i}] Arrived at safe position: {agent_positions[i]}")
                    continue
                
                elif simulation_state['pending_llm_actions'][i]:
                    # Step 2: Now that we're back to safety, ask LLM for advice
                    print(f"[Agent {i}] At safety, now consulting LLM")
                    # Get a valid move from LLM respecting movement constraints
                    new_coord = llm_make_move(i, history, agent_positions[i])
                    
                    # Update the agent's position based on LLM recommendation
                    agent_positions[i] = new_coord
                    movement_history[i].append(agent_positions[i].copy())
                    
                    # Reset jammed status and create new path to mission endpoint
                    agent_jammed[i] = False
                    simulation_state['returned_to_safe'][i] = False
                    simulation_state['pending_llm_actions'][i] = False
                    agent_paths[i] = linear_path(agent_positions[i], mission_endpoint)
                    
                    # Update the marker - fixed to use sequences
                    agent_markers[i].set_data([agent_positions[i][0]], [agent_positions[i][1]])
                    
                    # Check if still jammed at the new position
                    if is_jammed(agent_positions[i]):
                        print(f"[Agent {i}] Still jammed at new position {agent_positions[i]} - will try again")
                        agent_comm_quality[i] = 0.0
                        agent_jammed[i] = True
                        agent_markers[i].set_color('red')
                    else:
                        print(f"[Agent {i}] Successfully moved to non-jammed position: {agent_positions[i]}")
                        agent_comm_quality[i] = 1.0
                        agent_markers[i].set_color('green')
                    
                    continue
            
            # Regular movement for non-jammed agents
            if agent_paths[i]:
                next_pos = agent_paths[i][0]  # Look at next position without removing it
                
                # Save current position as safe if not jammed
                if not is_jammed(agent_positions[i]):
                    last_safe_position[i] = agent_positions[i].copy()
                
                # Move to next position (already constrained by linear_path)
                agent_positions[i] = next_pos
                agent_paths[i].pop(0)  # Now remove from path
                movement_history[i].append(next_pos.copy())
                if len(movement_history[i]) > 100:
                    movement_history[i].pop(0)
                
                # Check if the new position is jammed
                if is_jammed(next_pos):
                    agent_comm_quality[i] = 0.0
                    agent_jammed[i] = True
                    print(f"[Agent {i}] JAMMED at {next_pos} — comm quality dropped to 0.0")
                    agent_markers[i].set_color('red')
                else:
                    agent_comm_quality[i] = 1.0
                    agent_markers[i].set_color('green')
            
            # Update marker position - fixed to use sequences
            agent_markers[i].set_data([agent_positions[i][0]], [agent_positions[i][1]])
            
            # Update path tracer
            if len(movement_history[i]) > 1:
                path_x = [pos[0] for pos in movement_history[i]]
                path_y = [pos[1] for pos in movement_history[i]]
                path_lines[i].set_data(path_x, path_y)
        
        # Update the legend to show jammed status
        for i in range(num_agents):
            label = f"Agent {i+1}"
            if agent_jammed[i]:
                label += " (JAMMED)"
                agent_markers[i].set_label(label)
                agent_markers[i].set_color('red')
            else:
                agent_markers[i].set_label(label)
                agent_markers[i].set_color('green')
        
        # Force legend update every few frames to show jammed status
        if iteration[0] % 5 == 0:
            # Access legend from simulation state to avoid "referenced before assignment" error
            if simulation_state['legend']:
                simulation_state['legend'].remove()
            legend_handles = [endpoint_marker] + agent_markers
            simulation_state['legend'] = ax.legend(handles=legend_handles, loc='upper left')
        
        iteration[0] += 1
        
        if iteration[0] % num_history_segments == 0:
            print("\n[LOG] Sending data to LLM...")
            for i in range(num_agents):
                print(f"[Agent {i}] Position: {agent_positions[i]} | Comm Quality: {agent_comm_quality[i]}")
            print("[LOG] Data sent.\n")
        
        return agent_markers + path_lines
    
    # Create animation
    ani = FuncAnimation(fig, update, interval=int(update_freq * 1000), blit=True)
    
    plt.tight_layout()
    plt.show()
    
    # This ensures the program exits properly after closing the plot
    print("[Simulation] Finished.")
    
if __name__ == "__main__":
    # Initialize PyQt5 application
    app = QApplication(sys.argv)
    run_simulation()