"""
Agent initialization and state management.
"""
import random
from typing import Dict, List, Optional
from core.types import Position, JammingZone
from core.config import (
    NUM_AGENTS, get_agent_ids, X_RANGE, Y_RANGE, 
    HIGH_COMM_QUAL, LOW_COMM_QUAL
)
from .sim_jamming import check_multiple_zones

def initialize_agents(num_agents: int = NUM_AGENTS,
                     jamming_zones: Optional[List[JammingZone]] = None,
                     x_range = X_RANGE,
                     y_range = Y_RANGE) -> Dict:
    """
    Initialize all agents with random non-jammed starting positions.
    
    Args:
        num_agents: Number of agents to create
        jamming_zones: List of jamming zones to avoid
        x_range: X coordinate boundaries
        y_range: Y coordinate boundaries
        
    Returns:
        Dictionary with agent initialization data
    """
    if jamming_zones is None:
        jamming_zones = []
    
    agent_ids = get_agent_ids(num_agents)
    
    swarm_pos_dict = {}
    jammed_positions = {}
    last_safe_position = {}
    agent_paths = {}
    agent_targets = {}
    
    print(f"[INIT] Initializing {num_agents} agents...")
    
    for agent_id in agent_ids:
        # Keep trying until we get a non-jammed starting position
        max_attempts = 50
        for attempt in range(max_attempts):
            start_pos = (
                random.uniform(x_range[0], x_range[1]),
                random.uniform(y_range[0], y_range[1])
            )
            
            # Check if this position is jammed
            if not check_multiple_zones(start_pos, jamming_zones):
                break  # Found a clear position
        
        if check_multiple_zones(start_pos, jamming_zones):
            print(f"[INIT] WARNING: {agent_id} spawned in jammed area after {max_attempts} attempts")
        
        swarm_pos_dict[agent_id] = [list(start_pos) + [HIGH_COMM_QUAL]]
        jammed_positions[agent_id] = False
        last_safe_position[agent_id] = start_pos
        agent_paths[agent_id] = []
        agent_targets[agent_id] = None
        
        print(f"[INIT] {agent_id} starting at {start_pos}")
    
    print(f"[INIT] All {num_agents} agents initialized")
    
    return {
        'swarm_pos_dict': swarm_pos_dict,
        'jammed_positions': jammed_positions,
        'last_safe_position': last_safe_position,
        'agent_paths': agent_paths,
        'agent_targets': agent_targets
    }

def update_agent_position(agent_id: str,
                         new_position: Position,
                         is_jammed: bool,
                         swarm_pos_dict: Dict,
                         jammed_positions: Dict,
                         last_safe_position: Dict) -> None:
    """
    Update an agent's position and state.
    
    Args:
        agent_id: Agent identifier
        new_position: New position (x, y)
        is_jammed: Whether agent is currently jammed
        swarm_pos_dict: Dictionary of agent positions
        jammed_positions: Dictionary of jamming states
        last_safe_position: Dictionary of last safe positions
    """
    comm_quality = LOW_COMM_QUAL if is_jammed else HIGH_COMM_QUAL
    
    swarm_pos_dict[agent_id].append([
        new_position[0],
        new_position[1],
        comm_quality
    ])
    
    jammed_positions[agent_id] = is_jammed
    
    # Update last safe position if not jammed
    if not is_jammed:
        last_safe_position[agent_id] = new_position