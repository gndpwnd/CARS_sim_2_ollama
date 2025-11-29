"""
Simulation update logic for the GUI with two-step recovery process.
FIXED: Logs telemetry AFTER agent moves (not before) for live Qdrant data
"""
import datetime
import math
import requests
from simulation import (
    linear_path, limit_movement, algorithm_make_move,
    check_multiple_zones, get_last_safe_position, is_at_target,
    convert_numpy_coords
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
        self.recovery_targets = {}
        self.returning_to_safe = {}
        self.endpoint_reached_logged = {}
        
        # Track API sync failures to avoid spam
        self.api_sync_failures = 0
    
    def _sync_to_simulation_api(self, agent_id: str):
        """
        Sync agent state to Simulation API so LLM can see real-time data.
        CRITICAL: This allows the LLM to see actual positions, not just [0,0]
        """
        try:
            current_pos = self.parent.swarm_pos_dict[agent_id][-1][:2]
            is_jammed = self.parent.jammed_positions[agent_id]
            comm_quality = self.parent.swarm_pos_dict[agent_id][-1][2]
            
            # Push update to API
            response = requests.put(
                f"{SIMULATION_API_URL}/agents/{agent_id}",
                json={
                    "position": [float(current_pos[0]), float(current_pos[1])],
                    "jammed": bool(is_jammed),
                    "communication_quality": float(comm_quality)
                },
                timeout=0.5  # Short timeout to avoid blocking GUI
            )
            
            if response.status_code == 200:
                # Reset failure counter on success
                if self.api_sync_failures > 0:
                    print("[API_SYNC] ✅ Reconnected to Simulation API")
                    self.api_sync_failures = 0
            else:
                self.api_sync_failures += 1
                if self.api_sync_failures == 1:  # Only log first failure
                    print(f"[API_SYNC] ⚠️  HTTP {response.status_code} updating {agent_id}")
                    
        except requests.exceptions.Timeout:
            self.api_sync_failures += 1
            if self.api_sync_failures == 1:
                print("[API_SYNC] ⚠️  Timeout - is sim_api.py running?")
        except requests.exceptions.ConnectionError:
            self.api_sync_failures += 1
            if self.api_sync_failures == 1:
                print("[API_SYNC] ⚠️  Connection error - is sim_api.py running on port 5001?")
        except Exception as e:
            # Silently ignore other errors to avoid spam
            pass

    def update_all_agents(self):
        """Update all agents in the simulation"""
        if not self.parent.animation_running:
            return
        
        # Check for LLM-commanded targets
        llm_targets = {}
        try:
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
        
        if agent_id in self.endpoint_reached_logged:
            self.endpoint_reached_logged[agent_id] = False
        
        self.parent.agent_targets[agent_id] = tuple(llm_target)
        
        if is_at_target(current_pos, llm_target):
            print(f"[GUI] {agent_id} reached LLM target!")
            self._clear_llm_target(agent_id)
            self.parent.agent_targets[agent_id] = None
            self._update_agent(agent_id)
        else:
            next_pos = limit_movement(current_pos, llm_target, MAX_MOVEMENT_PER_STEP)
            
            comm_quality = LOW_COMM_QUAL if is_jammed else HIGH_COMM_QUAL
            self.parent.swarm_pos_dict[agent_id].append([
                next_pos[0],
                next_pos[1],
                comm_quality
            ])
            
            self.parent.jammed_positions[agent_id] = is_jammed
            
            # FIXED: Log telemetry AFTER movement with NEW position
            log_telemetry_to_qdrant(
                agent_id=agent_id,
                position=convert_numpy_coords(next_pos),  # <-- NEW position
                is_jammed=is_jammed,
                comm_quality=float(comm_quality),
                iteration=self.parent.iteration_count
            )
            
            # Sync to API
            self._sync_to_simulation_api(agent_id)
            
            if self.parent.subsystem_manager.gps_manager:
                self.parent.subsystem_manager.update_agent_gps(
                    agent_id, next_pos, is_jammed
                )
    
    def _clear_llm_target(self, agent_id):
        """Clear LLM target via API"""
        try:
            response = requests.delete(
                f"{SIMULATION_API_URL}/llm_targets/{agent_id}",
                timeout=2.0
            )
            if response.status_code == 200:
                print(f"[GUI] Cleared LLM target for {agent_id}")
        except Exception as e:
            print(f"[GUI] Error clearing LLM target: {e}")

    def _update_agent(self, agent_id):
        """
        Update a single agent with two-step recovery process.
        FIXED: Telemetry logged AFTER movement, not before!
        """
        last_position = self.parent.swarm_pos_dict[agent_id][-1][:2]
        is_jammed = check_multiple_zones(last_position, self.parent.jamming_zones)
        
        # ============================================================
        # STEP 1: DETERMINE MOVEMENT (but don't log telemetry yet!)
        # ============================================================
        
        if is_jammed:
            was_jammed = self.parent.jammed_positions[agent_id]
            
            if not was_jammed and agent_id in self.endpoint_reached_logged:
                self.endpoint_reached_logged[agent_id] = False
            
            if not was_jammed:
                print(f"[RECOVERY] {agent_id} entered jamming zone at {last_position}")
                self.parent.jammed_positions[agent_id] = True
                self.parent.swarm_pos_dict[agent_id][-1][2] = LOW_COMM_QUAL
                
                self.parent.agent_paths[agent_id] = []
                self.returning_to_safe[agent_id] = True
                self.recovery_targets[agent_id] = None
                
                log_event(
                    'error', agent_id, convert_numpy_coords(last_position),
                    f"Agent {agent_id} entered jamming zone, initiating recovery",
                    {'jammed': True, 'recovery_step': 'return_to_safe'}
                )
            
            self._handle_jammed_agent_movement(agent_id, last_position)
            
        else:
            was_jammed = self.parent.jammed_positions[agent_id]
            in_recovery = (self.returning_to_safe.get(agent_id, False) or 
                        (agent_id in self.recovery_targets and self.recovery_targets[agent_id] is not None))
            
            if in_recovery:
                if agent_id in self.recovery_targets and self.recovery_targets[agent_id]:
                    recovery_target = self.recovery_targets[agent_id]
                    
                    if is_at_target(last_position, recovery_target, tolerance=0.2):
                        print(f"[RECOVERY] {agent_id} exploratory step SUCCESS - escaped jamming at {last_position}!")
                        self.parent.jammed_positions[agent_id] = False
                        self.parent.swarm_pos_dict[agent_id][-1][2] = HIGH_COMM_QUAL
                        
                        self.returning_to_safe[agent_id] = False
                        self.recovery_targets[agent_id] = None
                        self.parent.last_safe_position[agent_id] = last_position
                        
                        self.parent.agent_paths[agent_id] = linear_path(
                            last_position, MISSION_END, MAX_MOVEMENT_PER_STEP
                        )
                        
                        print(f"[RECOVERY] {agent_id} plotting new path to mission end from {last_position}")
                        
                        log_event(
                            'notification', agent_id, convert_numpy_coords(last_position),
                            f"Agent {agent_id} successfully recovered, resuming mission to endpoint",
                            {'jammed': False, 'recovery_step': 'complete', 'resuming_mission': True}
                        )
                    else:
                        self._handle_jammed_agent_movement(agent_id, last_position)
                else:
                    self._handle_jammed_agent_movement(agent_id, last_position)
                    
            elif was_jammed:
                print(f"[RECOVERY] {agent_id} left jamming zone unexpectedly")
                self.parent.jammed_positions[agent_id] = False
                self._handle_normal_agent_movement(agent_id, last_position)
            else:
                self._handle_normal_agent_movement(agent_id, last_position)
        
        # ============================================================
        # STEP 2: LOG TELEMETRY WITH NEW POSITION (after movement!)
        # ============================================================
        
        # Get the UPDATED position (last entry in history)
        new_position = self.parent.swarm_pos_dict[agent_id][-1][:2]
        new_jammed_status = self.parent.jammed_positions[agent_id]
        new_comm_quality = self.parent.swarm_pos_dict[agent_id][-1][2]
        
        # Now log telemetry with CURRENT position
        log_telemetry_to_qdrant(
            agent_id=agent_id,
            position=convert_numpy_coords(new_position),  # <-- CURRENT position!
            is_jammed=new_jammed_status,
            comm_quality=float(new_comm_quality),
            iteration=self.parent.iteration_count
        )
        
        # CRITICAL: Sync to API after every update
        self._sync_to_simulation_api(agent_id)
        
        # Update GPS data
        if self.parent.subsystem_manager.gps_manager:
            self.parent.subsystem_manager.update_agent_gps(
                agent_id, 
                new_position,
                new_jammed_status
            )

    def _handle_jammed_agent_movement(self, agent_id, current_pos):
        """Handle movement for jammed agent using two-step recovery"""
        if self.returning_to_safe.get(agent_id, False):
            safe_pos = get_last_safe_position(
                agent_id,
                self.parent.last_safe_position,
                self.parent.swarm_pos_dict
            )
            
            if is_at_target(current_pos, safe_pos, tolerance=0.5):
                print(f"[RECOVERY] {agent_id} reached safe position {safe_pos}")
                self.returning_to_safe[agent_id] = False
                
                recovery_target = algorithm_make_move(
                    agent_id,
                    safe_pos,
                    self.parent.jamming_zones,
                    MAX_MOVEMENT_PER_STEP,
                    self.parent.x_range,
                    self.parent.y_range
                )
                
                one_step = limit_movement(safe_pos, recovery_target, MAX_MOVEMENT_PER_STEP)
                self.recovery_targets[agent_id] = one_step
                
                print(f"[RECOVERY] {agent_id} will take one exploratory step to: {one_step}")
                
                log_event(
                    'notification', agent_id, convert_numpy_coords(safe_pos),
                    f"Agent {agent_id} at safe position, taking exploratory step to {one_step}",
                    {'jammed': True, 'recovery_step': 'taking_random_step'}
                )
            else:
                next_pos = limit_movement(current_pos, safe_pos, MAX_MOVEMENT_PER_STEP)
                self.parent.swarm_pos_dict[agent_id].append([
                    next_pos[0], next_pos[1], LOW_COMM_QUAL
                ])
                
                if self.parent.iteration_count % 5 == 0:
                    print(f"[RECOVERY] {agent_id} moving to safe position: {current_pos} → {next_pos}")
        
        elif agent_id in self.recovery_targets and self.recovery_targets[agent_id]:
            one_step_target = self.recovery_targets[agent_id]
            
            print(f"[RECOVERY] {agent_id} taking exploratory step from {current_pos} to {one_step_target}")
            
            step_is_jammed = check_multiple_zones(one_step_target, self.parent.jamming_zones)
            comm_quality = LOW_COMM_QUAL if step_is_jammed else HIGH_COMM_QUAL
            
            self.parent.swarm_pos_dict[agent_id].append([
                one_step_target[0], one_step_target[1], comm_quality
            ])
            
            if step_is_jammed:
                print(f"[RECOVERY] {agent_id} still jammed after exploratory step, returning to safe position")
                self.returning_to_safe[agent_id] = True
                self.recovery_targets[agent_id] = None
                
                log_event(
                    'notification', agent_id, convert_numpy_coords(one_step_target),
                    f"Agent {agent_id} exploratory step still jammed, will retry",
                    {'jammed': True, 'recovery_step': 'retry_return_to_safe'}
                )
            else:
                print(f"[RECOVERY] {agent_id} exploratory step successful - not jammed!")
                
        else:
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
        self.returning_to_safe[agent_id] = False
        self.recovery_targets[agent_id] = None
        
        if not self.parent.agent_paths[agent_id]:
            self.parent.agent_paths[agent_id] = linear_path(
                current_pos, MISSION_END, MAX_MOVEMENT_PER_STEP
            )
        
        if self.parent.agent_paths[agent_id]:
            next_pos = self.parent.agent_paths[agent_id].pop(0)
            self.parent.last_safe_position[agent_id] = current_pos
            
            limited_pos = limit_movement(current_pos, next_pos, MAX_MOVEMENT_PER_STEP)
            self.parent.swarm_pos_dict[agent_id].append([
                limited_pos[0], limited_pos[1], HIGH_COMM_QUAL
            ])
            
            if is_at_target(limited_pos, MISSION_END, tolerance=0.5):
                if not self.endpoint_reached_logged.get(agent_id, False):
                    print(f"[MISSION] {agent_id} reached mission endpoint!")
                    self.parent.agent_paths[agent_id] = []
                    
                    log_event(
                        'notification', agent_id, convert_numpy_coords(limited_pos),
                        f"Agent {agent_id} successfully reached mission endpoint!",
                        {'mission_complete': True}
                    )
                    
                    self.endpoint_reached_logged[agent_id] = True