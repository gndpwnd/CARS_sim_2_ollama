import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.widgets import Button, TextBox
import random
import requests
import json
import re

UPDATE_FREQ = 2  # how fast to update the simulation (in seconds)
MCP_SERVER_URL = "http://127.0.0.1:5000"  # URL for the MCP server

# === Agent Config ===
NUM_AGENTS = 2
AGENTS = {f"agent{i+1}": {"pos": [random.uniform(-10, 10), random.uniform(-10, 10)], "target": None} for i in range(NUM_AGENTS)}

# === Control State ===
is_running = False
ani = None

# List to store labels (for removal)
labels = []

def move_agent(agent, x, y):
    """Local function to update agent positions in the simulation"""
    if agent in AGENTS:
        print(f"[ACTION] Moving {agent} to ({x}, {y})")
        AGENTS[agent]["pos"] = [x, y]
        AGENTS[agent]["target"] = [x, y]  # Set target to new position
        scat.set_offsets([agent_data["pos"] for agent_data in AGENTS.values()])  # Redraw the plot
        fig.canvas.draw_idle()  # Ensure the plot is updated immediately
    else:
        print(f"[WARNING] Unknown agent '{agent}'")

def parse_command(command_text):
    """Parse simple commands like 'move agent1 to 5,5'"""
    move_pattern = r"move\s+(\w+)\s+to\s+(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)"
    match = re.match(move_pattern, command_text, re.IGNORECASE)
    
    if match:
        agent_name = match.group(1)
        x = float(match.group(2))
        y = float(match.group(3))
        return {"action": "move", "agent": agent_name, "x": x, "y": y}
    
    return None

def send_to_mcp_server(command_text):
    """Send the command to the MCP server for processing"""
    # First try to parse the command locally to determine what API endpoint to use
    parsed = parse_command(command_text)
    
    if parsed and parsed["action"] == "move":
        try:
            # Send to the move_agent endpoint
            response = requests.post(
                f"{MCP_SERVER_URL}/move_agent_via_ollama",
                json={
                    "agent": parsed["agent"],
                    "x": parsed["x"],
                    "y": parsed["y"]
                },
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result["success"]:
                    # Apply the movement in the simulation
                    move_agent(parsed["agent"], result["x"], result["y"])
                    print(f"[MCP] {result['message']}")
                else:
                    print(f"[MCP ERROR] {result['message']}")
            else:
                print(f"[HTTP ERROR] Status code: {response.status_code}")
                
        except Exception as e:
            print(f"[CONNECTION ERROR] Failed to communicate with MCP server: {e}")
    else:
        print(f"[PARSE ERROR] Could not understand command: '{command_text}'")

# === Plot Setup ===
fig, ax = plt.subplots()
plt.subplots_adjust(bottom=0.28)  # More space for UI
ax.set_xlim(-10, 10)
ax.set_ylim(-10, 10)
ax.set_title("Ollama-Controlled Agents Simulation", fontsize=14, fontweight='bold', loc='center')
scat = ax.scatter([], [], c='blue')

# === Animation Function ===
def update(frame):
    if not is_running:
        return scat,

    # Remove old labels
    for label in labels:
        label.remove()

    labels.clear()

    for agent_name, agent_data in AGENTS.items():
        current_pos = agent_data["pos"]
        target = agent_data["target"]

        if target is None:  # Move randomly if no target is set
            new_x, new_y = random.uniform(-10, 10), random.uniform(-10, 10)
            AGENTS[agent_name]["pos"] = [new_x, new_y]
        else:  # Move towards the target if set
            target_x, target_y = target
            current_x, current_y = current_pos
            step_size = 0.1  # Define the step size for movement

            # Move towards the target
            dx = target_x - current_x
            dy = target_y - current_y
            distance = (dx**2 + dy**2) ** 0.5

            # If close enough to the target, set position to target and reset
            if distance < step_size:
                AGENTS[agent_name]["pos"] = [target_x, target_y]
                AGENTS[agent_name]["target"] = None
            else:
                # Move in the direction of the target
                move_x = current_x + step_size * (dx / distance)
                move_y = current_y + step_size * (dy / distance)
                AGENTS[agent_name]["pos"] = [move_x, move_y]

    positions = [agent_data["pos"] for agent_data in AGENTS.values()]
    scat.set_offsets(positions)

    # Update labels
    for i, agent_name in enumerate(AGENTS):
        label = ax.text(AGENTS[agent_name]["pos"][0] + 0.2, AGENTS[agent_name]["pos"][1] + 0.2, agent_name, fontsize=9, color='black')
        labels.append(label)

    return scat,

# === Buttons ===
button_width = 0.1
button_height = 0.05
button_bottom = 0.15
button_spacing = 0.05
button_start_left = 0.5 - (3*button_width + 2*button_spacing)/2

# === Buttons with Colors ===
ax_start = plt.axes([button_start_left, button_bottom, button_width, button_height])
ax_pause = plt.axes([button_start_left + button_width + button_spacing, button_bottom, button_width, button_height])
ax_stop  = plt.axes([button_start_left + 2*(button_width + button_spacing), button_bottom, button_width, button_height])

btn_start = Button(ax_start, 'Start', color='lightgreen', hovercolor='green')
btn_pause = Button(ax_pause, 'Pause', color='lightgoldenrodyellow', hovercolor='gold')
btn_stop  = Button(ax_stop, 'Stop', color='salmon', hovercolor='red')

def start(event):
    global is_running, ani
    is_running = True
    print("[STATE] Simulation started.")
    if ani is None:
        ani = animation.FuncAnimation(fig, update, interval=int(UPDATE_FREQ * 1000), cache_frame_data=False)

def pause(event):
    global is_running
    is_running = False
    print("[STATE] Simulation paused.")

def stop(event):
    global is_running
    is_running = False
    print("[STATE] Simulation stopped. Resetting agents.")
    for agent in AGENTS:
        AGENTS[agent] = {"pos": [random.uniform(-10, 10), random.uniform(-10, 10)], "target": None}
    scat.set_offsets([agent_data["pos"] for agent_data in AGENTS.values()])
    fig.canvas.draw_idle()

btn_start.on_clicked(start)
btn_pause.on_clicked(pause)
btn_stop.on_clicked(stop)

# === Textbox for Custom LLM Commands ===
ax_box = plt.axes([0.15, 0.05, 0.6, 0.05])
text_box = TextBox(ax_box, 'LLM Command:', initial='move agent1 to 0,0')

# === Send Button for LLM Command ===
ax_send = plt.axes([0.75, 0.05, 0.1, 0.05])
btn_send = Button(ax_send, 'Send', color='lightblue', hovercolor='skyblue')

def handle_send(event):
    command = text_box.text.strip()
    if command:
        print(f"[INPUT] User entered command: {command}")
        # Send command to the MCP server for processing
        send_to_mcp_server(command)

btn_send.on_clicked(handle_send)

# === Run GUI ===
plt.show()