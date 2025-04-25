import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.widgets import Button, TextBox
import random
import requests
import json
import re

UPDATE_FREQ = 2  # how fast to update the simulation (in seconds)

# === Agent Config ===
NUM_AGENTS = 2
AGENTS = {f"agent{i+1}": {"pos": [random.uniform(-10, 10), random.uniform(-10, 10)], "target": None} for i in range(NUM_AGENTS)}

# === Control State ===
is_running = False
ani = None

# List to store labels (for removal)
labels = []

def move_agent(agent, x, y):
    if agent in AGENTS:
        print(f"[ACTION] Moving {agent} to ({x}, {y})")
        AGENTS[agent]["pos"] = [x, y]
        AGENTS[agent]["target"] = [x, y]  # Set target to new position
        scat.set_offsets([agent_data["pos"] for agent_data in AGENTS.values()])  # Redraw the plot
        fig.canvas.draw_idle()  # Ensure the plot is updated immediately
    else:
        print(f"[WARNING] Unknown agent '{agent}'")



def query_ollama_for_move(command):
    url = "http://localhost:11434/api/chat"
    
    # Parse the command (e.g., "move agent1 to 5,5")
    parts = command.split()
    agent = parts[1]  # agent name (e.g., "agent1")
    target_x, target_y = map(float, parts[3].split(','))  # target coordinates (e.g., "5,5")
    
    if agent not in AGENTS:
        print(f"[ERROR] Agent {agent} not found.")
        return

    current_x, current_y = AGENTS[agent]["pos"]  # Get the current position of the agent
    
    # Construct the prompt with current position and target position
    prompt = f"""
Please move {agent}, currently at coordinates ({current_x:.1f}, {current_y:.1f}), 
to the target coordinates ({target_x:.1f}, {target_y:.1f}). 
The response should include the new position in the exact format: 
'New position of agent1 is (x, y)' where x and y are numeric values. 
Do not include any other text or explanations.
"""

    # Prepare the request data
    data = {
        "model": "llama3.2:3b-instruct-q5_K_M",
        "messages": [{"role": "user", "content": prompt}],
        "functions": [
            {
                "name": "move_agent",
                "description": "Moves an agent to a specific coordinate on a 2D plot",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "agent": {"type": "string"},
                        "x": {"type": "number"},
                        "y": {"type": "number"}
                    },
                    "required": ["agent", "x", "y"]
                }
            }
        ],
        "stream": False
    }

    print(f"[QUERY] Sending prompt to Ollama: {prompt}")
    try:
        response = requests.post(url, json=data)
        response_json = response.json()
        print(f"[RESPONSE] Full Ollama response:\n{json.dumps(response_json, indent=2)}")

        message = response_json.get("message", {}).get("content")
        if message:
            # Try to extract the new coordinates from Ollama's response
            new_x, new_y = extract_coordinates_from_message(message)
            
            if new_x is not None and new_y is not None:
                # Move the agent to the new coordinates
                move_agent(agent, new_x, new_y)
            else:
                print("[INFO] Unable to extract valid coordinates from the LLM response.")
        else:
            print("[INFO] No message content returned from Ollama.")
    except Exception as e:
        print(f"[ERROR] Failed to contact Ollama: {e}")

def extract_coordinates_from_message(message):
    """
    Extracts the new x, y coordinates from the response message content.
    The response should be in the format:
    - 'New position of agent1 is (x, y)'
    - or simply '(x, y)' or "'(x, y)'" (with or without extra quotes).
    """
    # Try extracting full sentence format: 'New position of agent1 is (x, y)'
    match_full = re.search(r"New position of .* is \((-?\d*\.?\d+), (-?\d*\.?\d+)\)", message)
    if match_full:
        try:
            x = float(match_full.group(1))
            y = float(match_full.group(2))
            return x, y
        except ValueError:
            print("[ERROR] Invalid coordinates in response.")
    
    # Try extracting simple coordinates format with or without extra quotes: '(x, y)' or "'(x, y)'"
    match_simple = re.search(r"'?\((-?\d*\.?\d+), (-?\d*\.?\d+)\)'?", message)
    if match_simple:
        try:
            x = float(match_simple.group(1))
            y = float(match_simple.group(2))
            return x, y
        except ValueError:
            print("[ERROR] Invalid coordinates in response.")
    
    return None, None

# === Plot Setup ===
fig, ax = plt.subplots()
plt.subplots_adjust(bottom=0.28)  # More space for UI
ax.set_xlim(-10, 10)
ax.set_ylim(-10, 10)
ax.set_title("Ollama-Controlled Agents Simulation", fontsize=14, fontweight='bold', loc='center')
scat = ax.scatter([], [], c='blue')

# === Animation Function ===
# Modify the update function to wait for the LLM's response
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
        query_ollama_for_move(command)

btn_send.on_clicked(handle_send)

# === Run GUI ===
plt.show()
