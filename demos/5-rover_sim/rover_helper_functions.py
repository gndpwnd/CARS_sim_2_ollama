import math
import numpy as np

# Configuration for rover behavior
ROVER_START_POINT = (-10, 2)
ROVER_END_POINT = (10, 5)
ROVER_SPEED = 0.5  # Units per step - can be adjusted
AGENT_DIST_TO_ROVER = 5  # Maximum allowed distance between agents and rover

def get_rover_path(start_point, end_point, rover_speed):
    """Generate a path for the rover from start to end point"""
    # Convert points to numpy arrays with float64 type
    start_point = np.array(start_point, dtype=np.float64)
    end_point = np.array(end_point, dtype=np.float64)
    
    # Calculate direction vector
    direction = end_point - start_point
    distance = np.linalg.norm(direction)
    
    if distance > 0:
        unit_vector = direction / distance
    else:
        return [tuple(end_point)]  # Return end point if start and end are the same
    
    # Calculate how many steps to reach the end point based on rover speed
    step_size = rover_speed  # Distance per step
    steps = int(np.ceil(distance / step_size))
    
    # Generate path points
    path = []
    current_point = start_point.copy()  # Make a copy to avoid modifying the original
    
    for _ in range(steps):
        current_point += step_size * unit_vector
        # Check if we've overshot the end point
        if np.linalg.norm(current_point - start_point) >= distance:
            path.append(tuple(end_point))  # Add the exact end point
            break
        else:
            # Round coordinates and convert to tuple
            path.append(tuple(np.round(current_point, 3)))
    
    return path

def calculate_distance_to_rover(agent_pos, rover_pos):
    """Calculate the Euclidean distance between an agent and the rover"""
    return math.sqrt((agent_pos[0] - rover_pos[0])**2 + (agent_pos[1] - rover_pos[1])**2)

def get_closest_safe_point(agent_pos, rover_pos, jamming_center, jamming_radius, max_dist=AGENT_DIST_TO_ROVER):
    """
    Find a safe point (outside jamming zone) that's closest to the rover and within maximum distance
    """
    # Vector from agent to rover
    direction = np.array([rover_pos[0] - agent_pos[0], rover_pos[1] - agent_pos[1]])
    distance = np.linalg.norm(direction)
    
    if distance <= max_dist:
        # Agent is already within allowed distance
        if not is_jammed(agent_pos, jamming_center, jamming_radius):
            return agent_pos  # Agent doesn't need to move
    
    # Create points around the rover within the max distance
    # Check multiple angles to find a good point
    best_point = None
    min_dist_to_agent = float('inf')
    
    # Try 16 directions around the rover
    for angle in np.linspace(0, 2*np.pi, 16, endpoint=False):
        # Point at the maximum allowed distance from rover
        test_point = (
            rover_pos[0] + max_dist * np.cos(angle),
            rover_pos[1] + max_dist * np.sin(angle)
        )
        
        # Check if the point is outside jamming zone
        if not is_jammed(test_point, jamming_center, jamming_radius):
            # Calculate distance from agent to this point
            dist_to_agent = math.sqrt((test_point[0] - agent_pos[0])**2 + (test_point[1] - agent_pos[1])**2)
            
            # Check if this is the closest point to the agent so far
            if dist_to_agent < min_dist_to_agent:
                min_dist_to_agent = dist_to_agent
                best_point = test_point
    
    # If no safe point was found, try a point halfway between agent and rover
    if best_point is None:
        midpoint = (
            (agent_pos[0] + rover_pos[0]) / 2,
            (agent_pos[1] + rover_pos[1]) / 2
        )
        
        # Check if the midpoint is outside jamming zone
        if not is_jammed(midpoint, jamming_center, jamming_radius):
            best_point = midpoint
    
    # If still no point found, just stay where we are
    if best_point is None:
        return agent_pos
    
    return (round(best_point[0], 3), round(best_point[1], 3))

def is_jammed(pos, jamming_center, jamming_radius):
    """Check if a position is inside the jamming zone"""
    if isinstance(pos, tuple) or isinstance(pos, list):
        pos_x, pos_y = pos[0], pos[1]
    else:  # Assume numpy array
        pos_x, pos_y = pos[0], pos[1]
    
    distance = math.sqrt((pos_x - jamming_center[0])**2 + (pos_y - jamming_center[1])**2)
    return distance <= jamming_radius