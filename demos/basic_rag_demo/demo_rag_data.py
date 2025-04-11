import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import time
import os
import datetime
from rag_store import add_log, retrieve_relevant

FAISS_DIR = './faiss_stuff'

# Create directory if it doesn't exist
os.makedirs(FAISS_DIR, exist_ok=True)

# Set Hugging Face and Transformers cache paths
os.environ['TRANSFORMERS_CACHE'] = FAISS_DIR
os.environ['HF_HOME'] = FAISS_DIR

# Constants
MOVE_SPEED = 50  # Define MOVE_SPEED to control the speed of movement
FREQUENCY = 0.1  # Controls the speed of movement along the sine wave
AMPLITUDE = 1.0  # Amplitude of the sine wave
OFFSET = 0.0  # Vertical offset of the sine wave
UPDATES_PER_SECOND = 1  # How many updates per second
DAYTIME_PERCENTAGE = 50  # Percentage of the time spent in daytime
NIGHTTIME_PERCENTAGE = 50  # Percentage of the time spent in nighttime
Y_AXIS_LIMIT = 1.1  # Limit for the Y-axis of the plot

# Sine Wave Generator
def sine_wave(x, frequency=FREQUENCY, amplitude=AMPLITUDE, offset=OFFSET):
    return amplitude * np.sin(frequency * x) + offset

# Create the x values (time points) for the sine wave
x_values = np.linspace(0, 10 * np.pi, 1000)  # We are going to generate 1000 points for visualization
y_values = sine_wave(x_values)

# Set up the plot
fig, ax = plt.subplots()
ax.plot(x_values, y_values, label='Sine Wave (Day/Night Cycle)')
ax.set_title("Day and Night Cycle Visualization")
ax.set_xlabel("Time")
ax.set_ylabel("Position (Day/Night Cycle)")
ax.set_ylim(-Y_AXIS_LIMIT, Y_AXIS_LIMIT)  # Limiting the Y-axis for visualization
red_dot, = ax.plot([], [], 'ro', label="Moving Point")

# Data Variables
current_index = 0  # Start at the first node (0, 0)
current_time = 0
time_of_day = "Day"  # Initially day
percentage_daytime = DAYTIME_PERCENTAGE  # Percent of the cycle in daytime
percentage_nighttime = NIGHTTIME_PERCENTAGE  # Percent of the cycle in nighttime

# Counter for log entries
log_counter = 0

# Initial Position for the red dot at (0, 0)
red_dot.set_data([x_values[0]], [y_values[0]])

def update(num, x_values, y_values, red_dot):
    global current_index, current_time, time_of_day, percentage_daytime, percentage_nighttime, log_counter

    # Ensure the red dot starts at the correct position on the first update
    if num == 0:
        red_dot.set_data([x_values[0]], [y_values[0]])  # Set the red dot position at the start

    # Update the time based on MOVE_SPEED
    current_index += MOVE_SPEED
    if current_index >= len(x_values):
        current_index = 0  # Loop back to start

    current_index_int = int(current_index)
    current_time = x_values[current_index_int]  # Use the integer index

    # Get the y-value at the current index (sine wave value)
    y_value = y_values[current_index_int]

    # Determine the time of day based on y-value
    if y_value > 0:
        time_of_day = "Day"
    else:
        time_of_day = "Night"

    # Calculate percentage of daytime and nighttime (corrected calculation)
    if y_value >= 0:  # Day time
        percentage_daytime = y_value * 100  # 0-100% as y goes from 0 to 1
        percentage_nighttime = 100 - percentage_daytime
    else:  # Night time
        percentage_nighttime = -y_value * 100  # 0-100% as y goes from 0 to -1
        percentage_daytime = 100 - percentage_nighttime

    # Get the coordinates of the red dot
    x_position = x_values[current_index_int]
    y_position = y_values[current_index_int]

    # Update the red dot on the plot
    red_dot.set_data([x_position], [y_position])

    # Format position as "x,y" string
    position_str = f"{x_position:.3f},{y_position:.3f}"
    
    # Get current timestamp
    timestamp = datetime.datetime.now().isoformat()
    
    # Create log text with all required information
    log_text = (f"Position: {position_str}. "
               f"Daytime: {percentage_daytime:.2f}%, Nighttime: {percentage_nighttime:.2f}%. "
               f"Time of Day: {time_of_day}. Timestamp: {timestamp}")
    
    # Create metadata dictionary with specific fields
    metadata = {
        "position": position_str,
        "daytime": f"daytime, {percentage_daytime:.2f}%",
        "nighttime": f"nighttime, {percentage_nighttime:.2f}%",
        "timestamp": timestamp,
        "time_of_day": time_of_day
    }
    
    # Add data to RAG store
    log_counter += 1
    add_log(
        log_id=f"sine-data-{log_counter}",
        log_text=log_text,
        metadata=metadata
    )

    # Print the time, position, and percentages for debugging
    print(f"Time: {current_time:.2f} s | X: {x_position:.2f} | Y: {y_position:.2f} | "
          f"Daytime: {percentage_daytime:.2f}% | Nighttime: {percentage_nighttime:.2f}% | "
          f"Time of Day: {time_of_day} | Timestamp: {timestamp}")

    return red_dot,

# Create the animation
ani = animation.FuncAnimation(fig, update, frames=len(x_values), fargs=(x_values, y_values, red_dot),
                             interval=1000 / UPDATES_PER_SECOND, blit=True)

# Display the plot with the animated red dot
plt.legend()
plt.show()