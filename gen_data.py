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