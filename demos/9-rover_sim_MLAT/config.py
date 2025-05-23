# Configuration parameters
import numpy as np

# Simulation parameters
update_freq = 0.5
high_comm_qual = 0.80
low_comm_qual = 0.20
x_range = (-10, 10)
y_range = (-10, 10)
num_agents = 3
num_history_segments = 5
RAG_UPDATE_FREQUENCY = 5  # log data every 5 iterations
DIST_BETWEEN_AGENTS = 2  # Minimum required distance between agents

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

# LLM Prompt Constraints
MAX_CHARS_PER_AGENT = 25
LLM_PROMPT_TIMEOUT = 5  # seconds to wait for LLM response before giving up
MAX_RETRIES = 3  # maximum number of retries for LLM prompting

# Simulation state tracking
USE_LLM = False  # Set to True to use LLM, False to use algorithm