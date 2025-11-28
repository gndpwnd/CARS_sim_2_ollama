"""
Simulation update logic for the GUI with two-step recovery process.
"""
import datetime
import math
from simulation import (
    linear_path, limit_movement, algorithm_make_move,
    check_multiple_zones, get_last_safe_position, is_at_target,
    convert_numpy_coords  # ADDED: For JSON serialization
)
from integrations import (
    request_llm_recovery_position, log_event, log_telemetry_to_qdrant
)
from core.config import (
    MISSION_END, MAX_MOVEMENT_PER_STEP, LOW_COMM_QUAL, 
    HIGH_COMM_QUAL, SIMULATION_API_URL, X_RANGE, Y_RANGE
)

class SimulationUpdater:
    """Handles simulation state updates with two-step recovery"""
    
    def __init__(self, parent):
        """
        Initialize simulation updater.
        
        Args:
            parent: Parent GUI window
        """
        self.parent = parent
        
        # Track recovery state for each agent
        self.recovery_targets = {}  # Random point each agent is moving toward
        self.returning_to_safe = {}  # Whether agent is returning to safe position
    
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
        if is_at_target(current_pos, llm_target):
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
            
            # Log telemetry (FIXED: Convert numpy types)
            log_telemetry_to_qdrant(
                agent_id=agent_id,
                position=convert_numpy_coords(next_pos),
                is_jammed=is_jammed,
                comm_quality=float(comm_quality),
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
        """Update a single agent with two-step recovery process"""
        last_position = self.parent.swarm_pos_dict[agent_id][-1][:2]
        
        # Check jamming status at current position
        is_jammed = check_multiple_zones(last_position, self.parent.jamming_zones)
        
        # Always log telemetry to Qdrant (FIXED: Convert numpy types)
        log_telemetry_to_qdrant(
            agent_id=agent_id,
            position=convert_numpy_coords(last_position),
            is_jammed=is_jammed,
            comm_quality=float(LOW_COMM_QUAL if is_jammed else HIGH_COMM_QUAL),
            iteration=self.parent.iteration_count
        )
        
        # Check if agent is currently jammed
        if is_jammed:
            # Agent is jammed - use recovery logic
            was_jammed = self.parent.jammed_positions[agent_id]
            
            if not was_jammed:
                # JUST ENTERED JAMMING ZONE
                print(f"[RECOVERY] {agent_id} entered jamming zone at {last_position}")
                self.parent.jammed_positions[agent_id] = True
                self.parent.swarm_pos_dict[agent_id][-1][2] = LOW_COMM_QUAL
                
                # Clear any existing path
                self.parent.agent_paths[agent_id] = []
                
                # Start recovery: return to safe position
                self.returning_to_safe[agent_id] = True
                self.recovery_targets[agent_id] = None
                
                # FIXED: Convert numpy types before logging
                log_event(
                    'error', agent_id, convert_numpy_coords(last_position),
                    f"Agent {agent_id} entered jamming zone, initiating recovery",
                    {'jammed': True, 'recovery_step': 'return_to_safe'}
                )
            
            # Execute recovery movement
            self._handle_jammed_agent_movement(agent_id, last_position)
            
        else:
            # Agent is NOT jammed
            was_jammed = self.parent.jammed_positions[agent_id]
            
            # Check if agent is still in recovery mode (returning to safe or has recovery target)
            in_recovery = (self.returning_to_safe.get(agent_id, False) or 
                          (agent_id in self.recovery_targets and self.recovery_targets[agent_id] is not None))
            
            if in_recovery:
                # Agent is in recovery mode and currently not jammed
                # Could be: at safe position, moving to recovery target, or just took exploratory step
                
                if agent_id in self.recovery_targets and self.recovery_targets[agent_id]:
                    # Has taken or is about to take the exploratory step
                    recovery_target = self.recovery_targets[agent_id]
                    
                    # Check if we're at the exploratory step position
                    if is_at_target(last_position, recovery_target, tolerance=0.2):
                        # Just completed the exploratory step and we're not jammed!
                        print(f"[RECOVERY] {agent_id} exploratory step SUCCESS - escaped jamming at {last_position}!")
                        self.parent.jammed_positions[agent_id] = False
                        self.parent.swarm_pos_dict[agent_id][-1][2] = HIGH_COMM_QUAL
                        
                        # Clear recovery state
                        self.returning_to_safe[agent_id] = False
                        self.recovery_targets[agent_id] = None
                        
                        # Update last safe position to current position
                        self.parent.last_safe_position[agent_id] = last_position
                        
                        # Create new path to mission end from this new position
                        self.parent.agent_paths[agent_id] = linear_path(
                            last_position, MISSION_END, MAX_MOVEMENT_PER_STEP
                        )
                        
                        print(f"[RECOVERY] {agent_id} plotting new path to mission end from {last_position}")
                        
                        # FIXED: Convert numpy types before logging
                        log_event(
                            'notification', agent_id, convert_numpy_coords(last_position),
                            f"Agent {agent_id} successfully recovered, resuming mission to endpoint",
                            {'jammed': False, 'recovery_step': 'complete', 'resuming_mission': True}
                        )
                    else:
                        # Still need to take the exploratory step or moving
                        self._handle_jammed_agent_movement(agent_id, last_position)
                else:
                    # No recovery target yet - continue recovery process
                    self._handle_jammed_agent_movement(agent_id, last_position)
                    
            elif was_jammed:
                # Was jammed but not in recovery mode - this shouldn't happen
                print(f"[RECOVERY] {agent_id} left jamming zone unexpectedly")
                self.parent.jammed_positions[agent_id] = False
                self._handle_normal_agent_movement(agent_id, last_position)
            else:
                # Normal movement - not jammed, wasn't jammed, not in recovery
                self._handle_normal_agent_movement(agent_id, last_position)
        
        # Update GPS data
        if self.parent.subsystem_manager.gps_manager:
            self.parent.subsystem_manager.update_agent_gps(
                agent_id, 
                self.parent.swarm_pos_dict[agent_id][-1][:2],
                self.parent.jammed_positions[agent_id]
            )
    
    def _handle_jammed_agent_movement(self, agent_id, current_pos):
        """
        Handle movement for jammed agent using two-step recovery:
        Step 1: Return to last safe position
        Step 2: Take ONE STEP in a random direction
        Step 3: Check if jammed - if not, resume mission
        """
        # STEP 1: Return to safe position
        if self.returning_to_safe.get(agent_id, False):
            safe_pos = get_last_safe_position(
                agent_id,
                self.parent.last_safe_position,
                self.parent.swarm_pos_dict
            )
            
            # Check if we've reached safe position
            if is_at_target(current_pos, safe_pos, tolerance=0.5):
                print(f"[RECOVERY] {agent_id} reached safe position {safe_pos}")
                self.returning_to_safe[agent_id] = False
                
                # Generate random direction for ONE STEP exploration
                recovery_target = algorithm_make_move(
                    agent_id,
                    safe_pos,
                    self.parent.jamming_zones,
                    MAX_MOVEMENT_PER_STEP,
                    self.parent.x_range,
                    self.parent.y_range
                )
                
                # Take ONE STEP toward that random direction (not go all the way there)
                one_step = limit_movement(safe_pos, recovery_target, MAX_MOVEMENT_PER_STEP)
                self.recovery_targets[agent_id] = one_step  # Store the ONE STEP position
                
                print(f"[RECOVERY] {agent_id} will take one exploratory step to: {one_step}")
                
                # FIXED: Convert numpy types before logging
                log_event(
                    'notification', agent_id, convert_numpy_coords(safe_pos),
                    f"Agent {agent_id} at safe position, taking exploratory step to {one_step}",
                    {'jammed': True, 'recovery_step': 'taking_random_step'}
                )
            else:
                # Move toward safe position
                next_pos = limit_movement(current_pos, safe_pos, MAX_MOVEMENT_PER_STEP)
                self.parent.swarm_pos_dict[agent_id].append([
                    next_pos[0], next_pos[1], LOW_COMM_QUAL
                ])
                
                if self.parent.iteration_count % 5 == 0:  # Log occasionally
                    print(f"[RECOVERY] {agent_id} moving to safe position: {current_pos} → {next_pos}")
        
        # STEP 2: Take the ONE exploratory step
        elif agent_id in self.recovery_targets and self.recovery_targets[agent_id]:
            one_step_target = self.recovery_targets[agent_id]
            
            # Take the step
            print(f"[RECOVERY] {agent_id} taking exploratory step from {current_pos} to {one_step_target}")
            
            # Check if this step will be jammed
            step_is_jammed = check_multiple_zones(one_step_target, self.parent.jamming_zones)
            comm_quality = LOW_COMM_QUAL if step_is_jammed else HIGH_COMM_QUAL
            
            self.parent.swarm_pos_dict[agent_id].append([
                one_step_target[0], one_step_target[1], comm_quality
            ])
            
            # After taking the step, check result
            if step_is_jammed:
                # Still jammed after exploration - return to safe and try again
                print(f"[RECOVERY] {agent_id} still jammed after exploratory step, returning to safe position")
                self.returning_to_safe[agent_id] = True
                self.recovery_targets[agent_id] = None
                
                log_event(
                    'notification', agent_id, convert_numpy_coords(one_step_target),
                    f"Agent {agent_id} exploratory step still jammed, will retry",
                    {'jammed': True, 'recovery_step': 'retry_return_to_safe'}
                )
            else:
                # SUCCESS! Not jammed after step - will exit recovery on next update
                print(f"[RECOVERY] {agent_id} exploratory step successful - not jammed!")
                # Don't clear recovery_targets yet - let the main update loop handle it
                
        else:
            # No recovery target set - shouldn't happen, but generate one
            print(f"[RECOVERY] {agent_id} no recovery target, generating one")
            recovery_target = algorithm_make_move(
                agent_id,
                current_pos,
                self.parent.jamming_zones,
                MAX_MOVEMENT_PER_STEP,
                self.parent.x_range,
                self.parent.y_range
            )
            one_step = limit_movement(current_pos, recovery_target, MAX_MOVEMENT_PER_STEP)
            self.recovery_targets[agent_id] = one_step
    
    def _handle_normal_agent_movement(self, agent_id, current_pos):
        """Handle normal movement toward mission endpoint"""
        # Clear any recovery state
        self.returning_to_safe[agent_id] = False
        self.recovery_targets[agent_id] = None
        
        # Follow existing path or create new one
        if not self.parent.agent_paths[agent_id]:
            # No path - create one to mission end
            self.parent.agent_paths[agent_id] = linear_path(
                current_pos, MISSION_END, MAX_MOVEMENT_PER_STEP
            )
        
        if self.parent.agent_paths[agent_id]:
            next_pos = self.parent.agent_paths[agent_id].pop(0)
            
            # Save current position as safe
            self.parent.last_safe_position[agent_id] = current_pos
            
            # Move to next position
            limited_pos = limit_movement(current_pos, next_pos, MAX_MOVEMENT_PER_STEP)
            self.parent.swarm_pos_dict[agent_id].append([
                limited_pos[0], limited_pos[1], HIGH_COMM_QUAL
            ])
            
            # Check if reached mission end
            if is_at_target(limited_pos, MISSION_END, tolerance=0.5):
                print(f"[MISSION] {agent_id} reached mission endpoint!")
                self.parent.agent_paths[agent_id] = []
                
                # FIXED: Convert numpy types before logging
                log_event(
                    'notification', agent_id, convert_numpy_coords(limited_pos),
                    f"Agent {agent_id} successfully reached mission endpoint!",
                    {'mission_complete': True}
                )