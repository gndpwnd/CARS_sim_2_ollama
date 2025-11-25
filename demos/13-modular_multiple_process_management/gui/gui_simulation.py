"""
Simulation update logic for the GUI.
"""
import datetime
import math
from simulation import (
    linear_path, limit_movement, algorithm_make_move,
    check_multiple_zones, get_nearest_jamming_center, get_nearest_jamming_radius
)
from integrations import (
    request_llm_recovery_position, log_event, log_telemetry_to_qdrant
)
from core.config import MISSION_END, MAX_MOVEMENT_PER_STEP, LOW_COMM_QUAL, HIGH_COMM_QUAL, SIMULATION_API_URL

class SimulationUpdater:
    """Handles simulation state updates"""
    
    def __init__(self, parent):
        """
        Initialize simulation updater.
        
        Args:
            parent: Parent GUI window
        """
        self.parent = parent
    
    def update_all_agents(self):
        """Update all agents in the simulation"""
        if not self.parent.animation_running:
            return
        
        # Check for LLM-commanded targets
        llm_targets = {}
        try:
            import requests
            response = requests.get(f"{SIMULATION_API_URL}/llm_targets", timeout=1.0)
            if response.status_code == 200:
                llm_targets = response.json().get('targets', {})
        except:
            pass
        
        self.parent.iteration_count += 1
        
        for agent_id in self.parent.swarm_pos_dict:
            # LLM TARGET HAS HIGHEST PRIORITY
            if agent_id in llm_targets:
                self._handle_llm_target(agent_id, llm_targets[agent_id])
            else:
                self._update_agent(agent_id)
        
        # Update plot and status
        self.parent.plot_manager.update_plot()
        self.parent.status_label.setText(f"Iteration: {self.parent.iteration_count}")
    
    def _handle_llm_target(self, agent_id, llm_target):
        """Handle LLM-commanded target movement (highest priority)"""
        current_pos = self.parent.swarm_pos_dict[agent_id][-1][:2]
        is_jammed = check_multiple_zones(current_pos, self.parent.jamming_zones)
        
        print(f"[GUI] {agent_id} following LLM command to {llm_target}")
        
        # Set as target
        self.parent.agent_targets[agent_id] = tuple(llm_target)
        
        # Check if reached target
        distance = ((current_pos[0] - llm_target[0])**2 + 
                   (current_pos[1] - llm_target[1])**2)**0.5
        
        if distance < 0.5:
            # Reached target - clear it
            print(f"[GUI] {agent_id} reached LLM target!")
            self._clear_llm_target(agent_id)
            self.parent.agent_targets[agent_id] = None
            # Continue with normal update
            self._update_agent(agent_id)
        else:
            # Move toward LLM target (even if jammed - LLM has authority)
            next_pos = limit_movement(current_pos, llm_target, MAX_MOVEMENT_PER_STEP)
            
            # Update agent position
            comm_quality = LOW_COMM_QUAL if is_jammed else HIGH_COMM_QUAL
            self.parent.swarm_pos_dict[agent_id].append([
                next_pos[0],
                next_pos[1],
                comm_quality
            ])
            
            # Log telemetry
            log_telemetry_to_qdrant(
                agent_id=agent_id,
                position=next_pos,
                is_jammed=is_jammed,
                comm_quality=comm_quality,
                iteration=self.parent.iteration_count
            )
            
            # Update GPS data
            if self.parent.subsystem_manager.gps_manager:
                self.parent.subsystem_manager.update_agent_gps(
                    agent_id, next_pos, is_jammed
                )
    
    def _clear_llm_target(self, agent_id):
        """Clear LLM target via API"""
        try:
            import requests
            response = requests.delete(
                f"{SIMULATION_API_URL}/llm_targets/{agent_id}",
                timeout=2.0
            )
            if response.status_code == 200:
                print(f"[GUI] Cleared LLM target for {agent_id}")
        except Exception as e:
            print(f"[GUI] Error clearing LLM target: {e}")

    def _update_agent(self, agent_id):
        """Update a single agent"""
        last_position = self.parent.swarm_pos_dict[agent_id][-1][:2]
        
        # Check jamming status
        is_jammed = check_multiple_zones(last_position, self.parent.jamming_zones)
        
        # Always log telemetry to Qdrant
        log_telemetry_to_qdrant(
            agent_id=agent_id,
            position=last_position,
            is_jammed=is_jammed,
            comm_quality=LOW_COMM_QUAL if is_jammed else HIGH_COMM_QUAL,
            iteration=self.parent.iteration_count
        )
        
        # Handle jamming state changes
        self._handle_jamming_state_change(agent_id, last_position, is_jammed)
        
        # Determine next movement
        self._determine_agent_movement(agent_id, last_position, is_jammed)
        
        # Execute movement
        self._execute_agent_movement(agent_id, last_position, is_jammed)
        
        # Update GPS data
        if self.parent.subsystem_manager.gps_manager:
            self.parent.subsystem_manager.update_agent_gps(
                agent_id, 
                self.parent.swarm_pos_dict[agent_id][-1][:2],
                is_jammed
            )
    
    def _handle_jamming_state_change(self, agent_id, position, is_jammed):
        """Handle changes in jamming state"""
        was_jammed = self.parent.jammed_positions[agent_id]
        
        if is_jammed and not was_jammed:
            # Just entered jamming zone
            print(f"{agent_id} entered jamming zone at {position}")
            self.parent.jammed_positions[agent_id] = True
            self.parent.swarm_pos_dict[agent_id][-1][2] = LOW_COMM_QUAL
            
            log_event(
                'error', agent_id, position,
                f"Agent {agent_id} entered jamming zone at position ({position[0]:.2f}, {position[1]:.2f})",
                {'jammed': True}
            )
            
        elif not is_jammed and was_jammed:
            # Just left jamming zone
            print(f"{agent_id} left jamming zone at {position}")
            self.parent.jammed_positions[agent_id] = False
            self.parent.swarm_pos_dict[agent_id][-1][2] = HIGH_COMM_QUAL
            
            log_event(
                'notification', agent_id, position,
                f"Agent {agent_id} left jamming zone at position ({position[0]:.2f}, {position[1]:.2f})",
                {'jammed': False}
            )
    
    def _determine_agent_movement(self, agent_id, current_pos, is_jammed):
        """Determine next movement for agent"""
        # Skip if agent already has a path
        if self.parent.agent_paths[agent_id]:
            return
        
        if is_jammed:
            # Recovery behavior
            next_pos = self._get_recovery_position(agent_id, current_pos)
        else:
            # Normal behavior - move toward mission endpoint
            next_pos = self._get_normal_movement(agent_id, current_pos)
        
        if next_pos:
            self.parent.agent_paths[agent_id] = linear_path(
                current_pos, next_pos, MAX_MOVEMENT_PER_STEP
            )
    
    def _get_recovery_position(self, agent_id, current_pos):
        """Get recovery position for jammed agent"""
        print(f"[RECOVERY] {agent_id} attempting recovery from jamming")
        
        # Try LLM-based recovery
        llm_position = request_llm_recovery_position(agent_id, current_pos)
        
        if llm_position:
            print(f"[RECOVERY] {agent_id} using LLM-suggested position ({llm_position[0]:.2f}, {llm_position[1]:.2f})")
            log_event(
                'notification', agent_id, llm_position,
                f"Agent {agent_id} using LLM recovery position ({llm_position[0]:.2f}, {llm_position[1]:.2f})",
                {'recovery_method': 'llm', 'jammed': True}
            )
            return llm_position
        
        # Fallback to algorithm-based recovery
        nearest_center = get_nearest_jamming_center(current_pos, self.parent.jamming_zones)
        nearest_radius = get_nearest_jamming_radius(current_pos, self.parent.jamming_zones)
        
        algo_position = algorithm_make_move(
            agent_id, current_pos, nearest_center, nearest_radius,
            MAX_MOVEMENT_PER_STEP, 
            self.parent.x_range, self.parent.y_range
        )
        
        print(f"[RECOVERY] {agent_id} using algorithm recovery ({algo_position[0]:.2f}, {algo_position[1]:.2f})")
        log_event(
            'notification', agent_id, algo_position,
            f"Agent {agent_id} using algorithm recovery position ({algo_position[0]:.2f}, {algo_position[1]:.2f})",
            {'recovery_method': 'algorithm', 'jammed': True}
        )
        
        return algo_position
    
    def _get_normal_movement(self, agent_id, current_pos):
        """Get normal movement toward mission endpoint"""
        target = MISSION_END
        
        # Calculate distance to target
        dist_to_target = math.sqrt(
            (current_pos[0] - target[0])**2 + 
            (current_pos[1] - target[1])**2
        )
        
        # Only create path if not at target
        if dist_to_target > MAX_MOVEMENT_PER_STEP:
            # Only print occasionally to reduce spam
            if self.parent.iteration_count % 10 == 0:
                print(f"[MOVEMENT] {agent_id} moving toward mission endpoint {target}")
            return target
        
        return None
    
    def _execute_agent_movement(self, agent_id, current_pos, is_jammed):
        """Execute planned movement for agent"""
        if not self.parent.agent_paths[agent_id]:
            return
        
        next_pos = self.parent.agent_paths[agent_id].pop(0)
        limited_pos = limit_movement(current_pos, next_pos, MAX_MOVEMENT_PER_STEP)
        
        # Update agent position
        comm_quality = LOW_COMM_QUAL if is_jammed else HIGH_COMM_QUAL
        self.parent.swarm_pos_dict[agent_id].append([
            limited_pos[0],
            limited_pos[1],
            comm_quality
        ])
        
        # Update last safe position if not jammed
        if not is_jammed:
            self.parent.last_safe_position[agent_id] = limited_pos