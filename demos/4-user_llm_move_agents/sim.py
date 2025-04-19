import matplotlib.pyplot as plt
from matplotlib.widgets import Button
from matplotlib.animation import FuncAnimation
import numpy as np

# Import the simulation controller
import simulation_controller

# Import the log functions from the RAG store script
from rag_store import add_log

# Import the simulation controller functions
from simulation_controller import (
    initialize_agents, 
    stop_simulation, 
    position_history,
    x_range,
    y_range,
    max_movement_per_step,
    start_simulation
)

# Animation control
animation_running = True
animation_object = None
manual_update_mode = False  # Set this True to debug manually with update_plot() + plt.pause()

# Button callback functions
def pause_simulation(event):
    """Callback for pause button"""
    global animation_running
    animation_running = False
    add_log("Simulation paused", metadata={"jammed": True})  # Log when simulation is paused
    print("Simulation paused")

def continue_simulation(event):
    """Callback for continue button"""
    global animation_running
    animation_running = True
    add_log("Simulation continued", metadata={"jammed": True})  # Log when simulation is continued
    print("Simulation continued")

def stop_simulation_button(event):
    """Callback for stop button"""
    global animation_running
    animation_running = False
    stop_simulation()
    add_log("Simulation stopped", metadata={"jammed": True})  # Log when simulation is stopped
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
    
    return []

def update_plot(frame=None):
    """Update the plot for animation or manual mode."""
    global animation_running
    if not animation_running:
        return []

    handles = []
    labels = []
    
    ax.clear()

    # Configure position plot
    ax.set_xlim(x_range)
    ax.set_ylim(y_range)
    ax.set_xlabel('X Position')
    ax.set_ylabel('Y Position')
    ax.set_title('Manual Agent Control Simulation')
    ax.grid(True)

    # Debug: Print simulation_controller.swarm_pos_dict to verify agent positions
    print("[DEBUG] simulation_controller.swarm_pos_dict:", simulation_controller.swarm_pos_dict)

    for agent_id, positions in simulation_controller.swarm_pos_dict.items():
        if not positions:
            continue

        # Plot path history (no label to avoid legend clutter)
        x_history = [p[0] for p in positions]
        y_history = [p[1] for p in positions]
        ax.plot(x_history, y_history, 'b-', alpha=0.5)

        # Plot current position
        latest_position = positions[-1]
        scatter = ax.scatter(latest_position[0], latest_position[1], color='green', s=100)

        # Annotate agent ID
        ax.annotate(agent_id, (latest_position[0], latest_position[1]),
                    fontsize=8, ha='center', va='bottom')

        # Collect legend handles and labels
        handles.append(scatter)
        labels.append(f"{agent_id}")

        # Log agent movement
        add_log(f"Agent {agent_id} moved to {latest_position}", metadata={"jammed": True, "agent_id": agent_id})

    # Prevent duplicate legends
    if ax.get_legend():
        ax.get_legend().remove()

    # Only add legend once, using the green dots
    if handles:
        ax.legend(handles, labels, loc='upper left')

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
    stop_button.on_clicked(stop_simulation_button)

    # Add title
    fig.suptitle("Manual Agent Control Simulation", fontsize=16)

    # Initialize agents
    initialize_agents()
    start_simulation()

    if manual_update_mode:
        # Manual update loop (e.g., for debugging or live control)
        plt.ion()
        plt.show()
        while animation_running:
            update_plot()
            plt.pause(1.0)  # Adjust pause for smoother/faster update
    else:
        # Create animation
        animation_object = FuncAnimation(fig, update_plot, init_func=init_plot, 
                                         interval=1000, blit=False, cache_frame_data=False)
        plt.subplots_adjust(bottom=0.15)
        plt.show()

if __name__ == "__main__":
    print("Running manual agent control simulation")
    run_simulation_with_plots()
