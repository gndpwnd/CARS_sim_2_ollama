# sim.py 

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
    x_range,
    y_range,
    start_simulation,
    add_waypoint
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

# New button callback for sending agent1 to (5, 5)
def move_agent1_to_test_point(event):
    """Callback for move agent1 button"""
    # Target coordinates
    target_x, target_y = 5.0, 5.0
    
    # Add waypoint for agent1
    success = add_waypoint("agent1", target_x, target_y)
    
    if success:
        add_log(f"Set waypoint for agent1 to ({target_x}, {target_y})", 
                metadata={"action": "test_waypoint"})
        print(f"Added waypoint for agent1 to ({target_x}, {target_y})")
    else:
        print("Failed to add waypoint for agent1")

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

# filepath: [sim.py](http://_vscodecontentref_/10)
def update_plot(frame=None):
    """Update the plot for animation or manual mode."""
    global animation_running
    if not animation_running:
        return []

    # Use the thread lock to ensure thread-safe access to shared data
    with simulation_controller.data_lock:
        # Debug: Print the current state of waypoints and paths
        print(f"[PLOT DEBUG] agent_waypoints: {simulation_controller.agent_waypoints}")
        print(f"[PLOT DEBUG] agent_full_paths: {simulation_controller.agent_full_paths}")
        
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

        for agent_id, positions in simulation_controller.swarm_pos_dict.items():
            if not positions:
                continue

            # Plot path history
            x_history = [p[0] for p in positions]
            y_history = [p[1] for p in positions]
            ax.plot(x_history, y_history, 'b-', alpha=0.5, label=f"{agent_id} Path History")

            # Plot current position
            latest_position = positions[-1]
            scatter = ax.scatter(latest_position[0], latest_position[1], color='green', s=100)

            # Plot waypoints
            if agent_id in simulation_controller.agent_waypoints:
                waypoints = simulation_controller.agent_waypoints[agent_id]
                for i, waypoint in enumerate(waypoints):
                    ax.scatter(waypoint[0], waypoint[1], color='orange', s=80, marker='o')
                    ax.annotate(f"{agent_id} W{i+1}", (waypoint[0], waypoint[1]),
                                fontsize=8, ha='center', va='bottom')

            # Plot the full linear path
            if agent_id in simulation_controller.agent_full_paths:
                full_path = simulation_controller.agent_full_paths[agent_id]
                if full_path:
                    path_x = [p[0] for p in full_path]
                    path_y = [p[1] for p in full_path]
                    ax.plot(path_x, path_y, 'r--', alpha=0.7, label=f"{agent_id} Linear Path")

            # Annotate agent ID
            ax.annotate(agent_id, (latest_position[0], latest_position[1]),
                        fontsize=8, ha='center', va='bottom')

            # Collect legend handles and labels
            handles.append(scatter)
            labels.append(f"{agent_id}")

        # Prevent duplicate legends
        if ax.get_legend():
            ax.get_legend().remove()

        # Only add legend once, using the green dots
        if handles:
            ax.legend(handles, labels, loc='upper left')

        # Force redraw to ensure all elements are displayed
        plt.draw()
    
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
    button_start_left = 0.5 - (4*button_width + 3*button_spacing)/2  # Adjusted for 4 buttons

    # Create button axes
    pause_ax = plt.axes([button_start_left, button_bottom, button_width, button_height])
    continue_ax = plt.axes([button_start_left + button_width + button_spacing, 
                            button_bottom, button_width, button_height])
    stop_ax = plt.axes([button_start_left + 2*button_width + 2*button_spacing, 
                        button_bottom, button_width, button_height])
    # New button for moving agent1 to (5, 5)
    move_agent1_ax = plt.axes([button_start_left + 3*button_width + 3*button_spacing, 
                             button_bottom, button_width, button_height])

    # Create buttons with distinctive colors
    pause_button = Button(pause_ax, 'Pause', color='lightgoldenrodyellow')
    continue_button = Button(continue_ax, 'Continue', color='lightblue')
    stop_button = Button(stop_ax, 'Stop', color='salmon')
    move_agent1_button = Button(move_agent1_ax, 'Move Agent1', color='lightgreen')  # New button

    # Connect button events to callbacks
    pause_button.on_clicked(pause_simulation)
    continue_button.on_clicked(continue_simulation)
    stop_button.on_clicked(stop_simulation_button)
    move_agent1_button.on_clicked(move_agent1_to_test_point)  # Connect new button

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