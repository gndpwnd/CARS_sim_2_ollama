"""
Shared type definitions for the GPS simulation system.
"""
from typing import Tuple, List, Dict, Optional
from dataclasses import dataclass

# Type aliases
Position = Tuple[float, float]
PositionWithQuality = Tuple[float, float, float]  # (x, y, comm_quality)
JammingZone = Tuple[float, float, float]  # (center_x, center_y, radius)
Bounds = Tuple[float, float]  # (min, max)

@dataclass
class AgentState:
    """Complete state of an agent"""
    agent_id: str
    position: Position
    communication_quality: float
    is_jammed: bool
    last_safe_position: Optional[Position] = None
    target_position: Optional[Position] = None
    path: List[Position] = None
    
    def __post_init__(self):
        if self.path is None:
            self.path = []

@dataclass
class SimulationState:
    """Complete simulation state"""
    iteration: int
    agents: Dict[str, AgentState]
    jamming_zones: List[JammingZone]
    mission_end: Position
    x_range: Bounds
    y_range: Bounds