import matplotlib.pyplot as plt
from matplotlib.widgets import Button
from matplotlib.animation import FuncAnimation
from matplotlib.gridspec import GridSpec
from config import *
from sim import (
    rover_pos_dict, rover_jammed, rover_pos_dict, rover_path,
    swarm_pos_dict, position_history, jammed_positions, update_swarm_data,
    calculate_distance_to_rover, is_too_close_to_other_agents, AGENT_DIST_TO_ROVER,
    update_freq, RAG_UPDATE_FREQUENCY, log_batch_of_data, iteration_count,
    initialize_agents  # Add this import
)

# Animation control
animation_running = True
animation_object = None

def pause_simulation(event):
    global animation_running
    animation_running = False
    print("Simulation paused")

def continue_simulation(event):
    global animation_running
    animation_running = True
    print("Simulation continued")

def stop_simulation(event):
    global animation_running
    animation_running = False
    plt.close('all')
    print("Simulation stopped")

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
    ax1.plot(mission_end[0], mission_end[1], 'r*', markersize=10, label='Mission Endpoint')
    movement_guide = plt.Circle((0, 0), max_movement_per_step, color='blue', alpha=0.1, fill=False, linestyle='--')
    ax1.add_artist(movement_guide)
    ax1.text(-max_movement_per_step, 0, f"Max step: {max_movement_per_step:.2f}", fontsize=8, color='blue')
    ax2.set_xlim(0, 30)
    ax2.set_ylim(0, 1)
    ax2.set_xlabel('Time (s)')
    ax2.set_ylabel('GPS Quality')
    ax2.set_title('GPS Quality over Time')
    ax2.grid(True)
    return []

def update_plot(frame):
    global iteration_count
    if not animation_running:
        return []
    update_swarm_data(frame)
    ax1.clear()
    ax2.clear()
    ax1.set_xlim(x_range)
    ax1.set_ylim(y_range)
    ax1.set_xlabel('X Position')
    ax1.set_ylabel('Y Position')
    ax1.set_title(f'Agent Position ({"LLM" if USE_LLM else "Algorithm"} Control)')
    ax1.grid(True)
    jamming_circle = plt.Circle(jamming_center, jamming_radius, color='red', alpha=0.3)
    ax1.add_patch(jamming_circle)
    rover_pos = rover_pos_dict["rover"][-1][:2]
    rover_range_circle = plt.Circle(rover_pos, AGENT_DIST_TO_ROVER, color='blue', alpha=0.1, fill=True)
    ax1.add_patch(rover_range_circle)
    ax1.plot(mission_end[0], mission_end[1], 'r*', markersize=10, label='Mission Endpoint')
    max_time = max(30, iteration_count * update_freq)
    ax2.set_xlim(0, max_time)
    ax2.set_ylim(0, 1)
    ax2.set_xlabel('Time (s)')
    ax2.set_ylabel('GPS Quality')
    ax2.set_title('GPS Quality over Time')
    ax2.grid(True)
    agent_data_for_logging = {}

    # Plot rover
    rover_data = rover_pos_dict["rover"][-1]
    rover_is_jammed = rover_jammed
    rover_x_history = [p[0] for p in position_history["rover"]]
    rover_y_history = [p[1] for p in position_history["rover"]]
    ax1.plot(rover_x_history, rover_y_history, 'b-', alpha=0.5)
    rover_color = 'yellow' if rover_is_jammed else 'blue'
    ax1.scatter(rover_data[0], rover_data[1], color=rover_color, s=150, marker='s', label="rover")
    ax1.annotate("ROVER", (rover_data[0], rover_data[1]), fontsize=10, ha='center', va='bottom', weight='bold')
    agent_data_for_logging["rover"] = [{
        'position': (rover_data[0], rover_data[1]),
        'communication_quality': rover_data[2],
        'jammed': rover_is_jammed
    }]
    rover_times = [i * update_freq for i in range(len(rover_pos_dict["rover"]))]
    rover_comm_quality = [data[2] for data in rover_pos_dict["rover"]]
    ax2.plot(rover_times, rover_comm_quality, 'b-', linewidth=2, label="rover", alpha=0.7)

    # Plot agents
    for agent_id in swarm_pos_dict:
        if agent_id == "rover":
            continue
        x_history = [p[0] for p in position_history[agent_id]]
        y_history = [p[1] for p in position_history[agent_id]]
        ax1.plot(x_history, y_history, 'g-', alpha=0.5)
        latest_data = swarm_pos_dict[agent_id][-1]
        agent_pos = (latest_data[0], latest_data[1])
        rover_pos = rover_pos_dict["rover"][-1][:2]
        distance_to_rover = calculate_distance_to_rover(agent_pos, rover_pos)
        in_rover_range = distance_to_rover <= AGENT_DIST_TO_ROVER
        if jammed_positions[agent_id]:
            color = 'red'
        else:
            if in_rover_range:
                maintaining_distance = not is_too_close_to_other_agents(agent_id, agent_pos)
                color = 'green' if maintaining_distance else 'orange'
            else:
                color = 'green'
        ax1.scatter(latest_data[0], latest_data[1], color=color, s=100, label=f"{agent_id}")
        ax1.annotate(agent_id, (latest_data[0], latest_data[1]), fontsize=8, ha='center', va='bottom')
        communication_quality = latest_data[2]
        is_jammed_flag = jammed_positions.get(agent_id, False)
        if agent_id not in agent_data_for_logging:
            agent_data_for_logging[agent_id] = []
        agent_data_for_logging[agent_id].append({
            'position': (latest_data[0], latest_data[1]),
            'communication_quality': communication_quality,
            'jammed': is_jammed_flag
        })
        agent_times = [i * update_freq for i in range(len(swarm_pos_dict[agent_id]))]
        agent_comm_quality = [data[2] for data in swarm_pos_dict[agent_id]]
        ax2.plot(agent_times, agent_comm_quality, label=f"{agent_id}", alpha=0.7)

    # Log data every RAG_UPDATE_FREQUENCY iterations
    if iteration_count % RAG_UPDATE_FREQUENCY == 0:
        log_batch_of_data(agent_data_for_logging)

    # Unique legends
    handles, labels = ax1.get_legend_handles_labels()
    unique_labels = []
    unique_handles = []
    for handle, label in zip(handles, labels):
        if label not in unique_labels:
            unique_labels.append(label)
            unique_handles.append(handle)
    ax1.legend(unique_handles, unique_labels, loc='upper left')
    handles, labels = ax2.get_legend_handles_labels()
    unique_labels = []
    unique_handles = []
    for handle, label in zip(handles, labels):
        if label not in unique_labels:
            unique_labels.append(label)
            unique_handles.append(handle)
    ax2.legend(unique_handles, unique_labels, loc='upper left')
    return []

def run_simulation_with_plots():
    global fig, ax1, ax2, animation_object
    
    # Initialize agents before starting the animation
    print("Initializing agents and rover...")
    initialize_agents()
    print(f"Initialized {num_agents} agents and rover")
    
    fig = plt.figure(figsize=(16, 8))
    gs = GridSpec(1, 2, figure=fig)
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    button_width = 0.1
    button_height = 0.05
    button_bottom = 0.02
    button_spacing = 0.05
    button_start_left = 0.5 - (3*button_width + 2*button_spacing)/2
    pause_ax = plt.axes([button_start_left, button_bottom, button_width, button_height])
    continue_ax = plt.axes([button_start_left + button_width + button_spacing, button_bottom, button_width, button_height])
    stop_ax = plt.axes([button_start_left + 2*button_width + 2*button_spacing, button_bottom, button_width, button_height])
    pause_button = Button(pause_ax, 'Pause', color='lightgoldenrodyellow')
    continue_button = Button(continue_ax, 'Continue', color='lightblue')
    stop_button = Button(stop_ax, 'Stop', color='salmon')
    pause_button.on_clicked(pause_simulation)
    continue_button.on_clicked(continue_simulation)
    stop_button.on_clicked(stop_simulation)
    fig.suptitle(f"Agent Navigation Simulation - {'LLM' if USE_LLM else 'Algorithm'} Control", fontsize=16)
    animation_object = FuncAnimation(fig, update_plot, init_func=init_plot, interval=int(update_freq * 1000), blit=False, cache_frame_data=False)
    plt.subplots_adjust(bottom=0.15)
    plt.show()

if __name__ == "__main__":
    print(f"Running simulation with {'LLM' if USE_LLM else 'Algorithm'} control")
    run_simulation_with_plots()