import json
import random
import time
import threading
from typing import Dict, Any
from dataclasses import dataclass, asdict
import math

@dataclass
class GPSSimulationState:
    """Current state of GPS simulation parameters."""
    # Basic GPS metrics
    num_satellites: int = 8
    signal_strength_agent_1: float = 85.0
    fix_quality: int = 3  # 1=no fix, 2=2D, 3=3D
    
    # Signal Quality metrics
    carrier_to_noise_ratio: float = 45.0
    automatic_gain_control: float = 25.0
    lock_degradation_events: int = 0
    reacquisition_time_cold: float = 30.0
    reacquisition_time_warm: float = 5.0
    satellite_count_drop_rate: float = 0.5
    cn0_drop_rate: float = 2.0
    
    # Data Integrity metrics
    checksum_failure_rate: float = 0.01
    truncated_sentence_rate: float = 0.005
    parity_error_frequency: float = 0.002
    raim_test_statistic: float = 2.5
    horizontal_alert_limit: float = 0.05
    vertical_alert_limit: float = 0.08
    time_to_alert: float = 6.0
    
    # Position and Velocity metrics
    position_jump_magnitude: float = 0.02
    position_oscillation: float = 0.01
    static_position_variance: float = 0.003
    rover_velocity: float = 2.5
    rover_acceleration: float = 0.8
    heading_change_rate: float = 5.0
    
    # RTK metrics
    rtk_fix_status: int = 5  # 0=invalid, 1=autonomous, 4=RTK fixed, 5=RTK float
    carrier_phase_cycle_slip_count: int = 0
    
    # Cross-sensor validation metrics
    gps_ins_position_difference: float = 0.02
    gps_ins_innovation_vector: float = 1.5
    ins_drift_rate: float = 0.001
    gps_wheel_distance_difference: float = 0.01
    gps_wheel_speed_difference: float = 0.05
    gps_imu_angular_rate_difference: float = 0.5
    heading_error: float = 1.0
    uwb_distance_error: float = 0.03
    
    # Environmental factors
    current_environment: str = "open_field"  # open_field, urban, forest, mountain
    noise_floor_estimate: float = 20.0
    ionospheric_activity: float = 15.0
    
    # System health metrics
    gps_health_score: float = 95.0
    detection_counter: int = 0
    false_positive_rate: float = 0.001
    false_negative_rate: float = 0.002
    cpu_utilization: float = 25.0
    system_memory_usage: float = 512.0
    power_consumption: float = 15.0
    
    # Timing metrics
    detection_latency: float = 0.05
    processing_latency: float = 0.02
    position_update_rate: float = 1.0
    
    # Mission state
    simulation_time: float = 0.0
    gps_denied_areas_count: int = 0
    active_alerts: int = 0


class GPSRequirementsSimulator:
    """Simulates GPS requirements data and feeds it to the notification dashboard."""
    
    def __init__(self, config_file: str = "requirements_config.json"):
        self.config_file = config_file
        self.requirements_config = self.load_requirements_config()
        self.simulation_state = GPSSimulationState()
        self.is_running = False
        self.simulation_thread = None
        
        # Scenario control
        self.current_scenario = "normal"  # normal, degraded, denied, recovery
        self.scenario_start_time = 0.0
        self.scenario_duration = 30.0  # seconds
        
        # Data sharing - in a real implementation, this could be a message queue,
        # shared memory, or network interface
        self.latest_data = {}
        self.data_lock = threading.Lock()
        
    def load_requirements_config(self) -> Dict[str, Any]:
        """Load the requirements configuration."""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: Config file {self.config_file} not found, using defaults")
            return {}
    
    def start_simulation(self):
        """Start the simulation in a separate thread."""
        if not self.is_running:
            self.is_running = True
            self.simulation_thread = threading.Thread(target=self._simulation_loop, daemon=True)
            self.simulation_thread.start()
            print("GPS Requirements Simulation started")
    
    def stop_simulation(self):
        """Stop the simulation."""
        self.is_running = False
        if self.simulation_thread:
            self.simulation_thread.join()
        print("GPS Requirements Simulation stopped")
    
    def _simulation_loop(self):
        """Main simulation loop."""
        start_time = time.time()
        
        while self.is_running:
            current_time = time.time()
            self.simulation_state.simulation_time = current_time - start_time
            
            # Update scenario if needed
            self._update_scenario()
            
            # Update all simulation parameters based on current scenario
            self._update_simulation_state()
            
            # Convert simulation state to requirements format and update
            self._update_requirements_data()
            
            # Print status occasionally
            if int(self.simulation_state.simulation_time) % 10 == 0 and int(self.simulation_state.simulation_time * 10) % 10 == 0:
                print(f"Sim Time: {self.simulation_state.simulation_time:.1f}s, "
                      f"Scenario: {self.current_scenario}, "
                      f"Satellites: {self.simulation_state.num_satellites}, "
                      f"Health: {self.simulation_state.gps_health_score:.1f}%")
            
            time.sleep(0.1)  # 10 Hz update rate
    
    def _update_scenario(self):
        """Update the current scenario based on time."""
        elapsed_in_scenario = self.simulation_state.simulation_time - self.scenario_start_time
        
        if elapsed_in_scenario >= self.scenario_duration:
            # Cycle through scenarios
            scenarios = ["normal", "degraded", "denied", "recovery"]
            current_idx = scenarios.index(self.current_scenario)
            next_idx = (current_idx + 1) % len(scenarios)
            
            self.current_scenario = scenarios[next_idx]
            self.scenario_start_time = self.simulation_state.simulation_time
            self.scenario_duration = random.uniform(20, 40)  # Vary scenario duration
            
            print(f"Scenario changed to: {self.current_scenario} (duration: {self.scenario_duration:.1f}s)")
    
    def _update_simulation_state(self):
        """Update simulation state based on current scenario."""
        # Add some random variation to all parameters
        self._add_realistic_variations()
        
        # Apply scenario-specific effects
        if self.current_scenario == "normal":
            self._apply_normal_conditions()
        elif self.current_scenario == "degraded":
            self._apply_degraded_conditions()
        elif self.current_scenario == "denied":
            self._apply_denied_conditions()
        elif self.current_scenario == "recovery":
            self._apply_recovery_conditions()
        
        # Calculate overall GPS health score
        self._calculate_gps_health_score()
    
    def _add_realistic_variations(self):
        """Add realistic random variations to parameters."""
        # Satellite count variations
        self.simulation_state.num_satellites += random.randint(-1, 1)
        self.simulation_state.num_satellites = max(0, min(12, self.simulation_state.num_satellites))
        
        # Signal strength variations
        self.simulation_state.signal_strength_agent_1 += random.uniform(-2, 2)
        self.simulation_state.signal_strength_agent_1 = max(0, min(100, self.simulation_state.signal_strength_agent_1))
        
        # C/N0 variations
        self.simulation_state.carrier_to_noise_ratio += random.uniform(-1, 1)
        self.simulation_state.carrier_to_noise_ratio = max(10, min(60, self.simulation_state.carrier_to_noise_ratio))
        
        # Position accuracy variations
        self.simulation_state.position_jump_magnitude += random.uniform(-0.005, 0.005)
        self.simulation_state.position_jump_magnitude = max(0, self.simulation_state.position_jump_magnitude)
    
    def _apply_normal_conditions(self):
        """Apply normal GPS conditions."""
        # Good satellite count
        target_sats = 8 + random.randint(-1, 2)
        self.simulation_state.num_satellites = max(4, min(target_sats, self.simulation_state.num_satellites + random.choice([-1, 0, 1])))
        
        # Good signal strength
        target_signal = 85 + random.uniform(-5, 5)
        self.simulation_state.signal_strength_agent_1 = max(70, min(95, target_signal))
        
        # Low error rates
        self.simulation_state.checksum_failure_rate = max(0.001, self.simulation_state.checksum_failure_rate * 0.99)
        self.simulation_state.lock_degradation_events = max(0, self.simulation_state.lock_degradation_events - 1)
    
    def _apply_degraded_conditions(self):
        """Apply degraded GPS conditions."""
        # Reduced satellite count
        if self.simulation_state.num_satellites > 5:
            self.simulation_state.num_satellites -= random.choice([0, 1])
        
        # Reduced signal strength
        self.simulation_state.signal_strength_agent_1 *= random.uniform(0.95, 0.98)
        self.simulation_state.signal_strength_agent_1 = max(30, self.simulation_state.signal_strength_agent_1)
        
        # Increased error rates
        self.simulation_state.checksum_failure_rate = min(0.1, self.simulation_state.checksum_failure_rate * random.uniform(1.01, 1.05))
        self.simulation_state.cn0_drop_rate = min(10, self.simulation_state.cn0_drop_rate * random.uniform(1.0, 1.1))
    
    def _apply_denied_conditions(self):
        """Apply GPS denied conditions."""
        # Very low satellite count
        self.simulation_state.num_satellites = max(0, min(3, self.simulation_state.num_satellites))
        
        # Very low signal strength
        self.simulation_state.signal_strength_agent_1 = max(5, min(25, self.simulation_state.signal_strength_agent_1))
        
        # High error rates
        self.simulation_state.checksum_failure_rate = min(0.5, self.simulation_state.checksum_failure_rate * random.uniform(1.1, 1.3))
        self.simulation_state.lock_degradation_events += random.randint(0, 2)
        
        # Poor positioning
        self.simulation_state.position_jump_magnitude = min(5.0, self.simulation_state.position_jump_magnitude * random.uniform(1.1, 1.5))
    
    def _apply_recovery_conditions(self):
        """Apply GPS recovery conditions."""
        # Gradually improving satellite count
        if self.simulation_state.num_satellites < 8:
            self.simulation_state.num_satellites += random.choice([0, 1, 1])  # Bias toward increase
        
        # Gradually improving signal strength
        if self.simulation_state.signal_strength_agent_1 < 80:
            self.simulation_state.signal_strength_agent_1 *= random.uniform(1.02, 1.05)
        
        # Decreasing error rates
        self.simulation_state.checksum_failure_rate = max(0.001, self.simulation_state.checksum_failure_rate * 0.95)
        self.simulation_state.lock_degradation_events = max(0, self.simulation_state.lock_degradation_events - 1)
    
    def _calculate_gps_health_score(self):
        """Calculate overall GPS health score from individual metrics."""
        # Simple weighted scoring (in practice this would be more sophisticated)
        score = 100.0
        
        # Penalize low satellite count
        if self.simulation_state.num_satellites < 4:
            score -= 40
        elif self.simulation_state.num_satellites < 6:
            score -= 20
        
        # Penalize low signal strength
        if self.simulation_state.signal_strength_agent_1 < 30:
            score -= 30
        elif self.simulation_state.signal_strength_agent_1 < 60:
            score -= 15
        
        # Penalize high error rates
        if self.simulation_state.checksum_failure_rate > 0.1:
            score -= 20
        elif self.simulation_state.checksum_failure_rate > 0.05:
            score -= 10
        
        # Penalize position errors
        if self.simulation_state.position_jump_magnitude > 1.0:
            score -= 25
        elif self.simulation_state.position_jump_magnitude > 0.5:
            score -= 10
        
        self.simulation_state.gps_health_score = max(0, min(100, score))
    
    def _update_requirements_data(self):
        """Update requirements data in the format expected by the notification GUI."""
        # Convert simulation state to requirements format
        updated_data = {}
        
        for section_name, section_data in self.requirements_config.items():
            updated_data[section_name] = {}
            
            for subsection_name, subsection_data in section_data.items():
                updated_data[section_name][subsection_name] = {}
                
                for req_name, req_data in subsection_data.items():
                    # Map simulation state values to requirement parameters
                    current_value = self._get_current_value_for_requirement(req_name, req_data)
                    
                    updated_data[section_name][subsection_name][req_name] = {
                        'name': req_data['name'],
                        'current_value': current_value,
                        'threshold': req_data['threshold'],
                        'warning_threshold': req_data['warning_threshold'],
                        'unit': req_data['unit']
                    }
        
        # Thread-safe update of shared data
        with self.data_lock:
            self.latest_data = updated_data
    
    def _get_current_value_for_requirement(self, req_name: str, req_data: Dict[str, Any]) -> float:
        """Map requirement name to current simulation value."""
        # This mapping connects requirement names to simulation state attributes
        req_name_lower = req_name.lower()
        
        # Direct mappings
        if 'satellite' in req_name_lower and 'count' in req_name_lower:
            return float(self.simulation_state.num_satellites)
        elif 'signal_strength' in req_name_lower:
            return self.simulation_state.signal_strength_agent_1
        elif 'carrier_to_noise' in req_name_lower or 'cn0' in req_name_lower:
            return self.simulation_state.carrier_to_noise_ratio
        elif 'checksum_failure' in req_name_lower:
            return self.simulation_state.checksum_failure_rate * 100  # Convert to percentage
        elif 'position_jump' in req_name_lower:
            return self.simulation_state.position_jump_magnitude
        elif 'health_score' in req_name_lower:
            return self.simulation_state.gps_health_score
        elif 'reacquisition' in req_name_lower:
            if 'cold' in req_name_lower:
                return self.simulation_state.reacquisition_time_cold
            else:
                return self.simulation_state.reacquisition_time_warm
        elif 'lock_degradation' in req_name_lower:
            return float(self.simulation_state.lock_degradation_events)
        elif 'agc' in req_name_lower or 'gain_control' in req_name_lower:
            return self.simulation_state.automatic_gain_control
        elif 'rtk' in req_name_lower and 'status' in req_name_lower:
            return float(self.simulation_state.rtk_fix_status)
        elif 'cycle_slip' in req_name_lower:
            return float(self.simulation_state.carrier_phase_cycle_slip_count)
        elif 'innovation' in req_name_lower:
            return self.simulation_state.gps_ins_innovation_vector
        elif 'drift' in req_name_lower:
            return self.simulation_state.ins_drift_rate * 1000  # Convert to mm/s
        elif 'cpu' in req_name_lower:
            return self.simulation_state.cpu_utilization
        elif 'memory' in req_name_lower:
            return self.simulation_state.system_memory_usage
        elif 'power' in req_name_lower:
            return self.simulation_state.power_consumption
        elif 'detection_latency' in req_name_lower:
            return self.simulation_state.detection_latency * 1000  # Convert to ms
        elif 'false_positive' in req_name_lower:
            return self.simulation_state.false_positive_rate * 100  # Convert to percentage
        elif 'false_negative' in req_name_lower:
            return self.simulation_state.false_negative_rate * 100  # Convert to percentage
        else:
            # For unmapped requirements, generate reasonable values based on thresholds
            threshold = req_data.get('threshold', 50)
            warning_threshold = req_data.get('warning_threshold', 75)
            
            # Determine if this is an error metric (lower is better) or quality metric (higher is better)
            error_keywords = ['error', 'failure', 'degradation', 'slip', 'drop', 'variance', 'drift']
            is_error_metric = any(keyword in req_name_lower for keyword in error_keywords)
            
            if is_error_metric:
                # For error metrics, generate values around the warning threshold
                base_value = warning_threshold * 0.7
                variation = base_value * 0.3 * random.uniform(-1, 1)
                return max(0, base_value + variation)
            else:
                # For quality metrics, generate values around the warning threshold
                base_value = warning_threshold * 1.2
                variation = base_value * 0.2 * random.uniform(-1, 1)
                return max(0, base_value + variation)
    
    def get_latest_data(self) -> Dict[str, Any]:
        """Get the latest requirements data (thread-safe)."""
        with self.data_lock:
            return self.latest_data.copy()
    
    def get_simulation_status(self) -> Dict[str, Any]:
        """Get current simulation status information."""
        return {
            'is_running': self.is_running,
            'simulation_time': self.simulation_state.simulation_time,
            'current_scenario': self.current_scenario,
            'gps_health_score': self.simulation_state.gps_health_score,
            'num_satellites': self.simulation_state.num_satellites,
            'signal_strength': self.simulation_state.signal_strength_agent_1
        }


def main():
    """Main function to run the simulation."""
    print("GPS Requirements Simulation Controller")
    print("=====================================")
    
    # Create simulator
    simulator = GPSRequirementsSimulator()
    
    try:
        # Start simulation
        simulator.start_simulation()
        
        print("\nSimulation running... Press Ctrl+C to stop")
        print("Commands:")
        print("  - Press Enter to show current status")
        print("  - Type 'status' and press Enter for detailed status")
        print("  - Type 'data' and press Enter to see latest data sample")
        print("  - Ctrl+C to exit")
        
        # Keep the main thread alive and handle user input
        while True:
            try:
                user_input = input().strip().lower()
                
                if user_input == 'status' or user_input == '':
                    status = simulator.get_simulation_status()
                    print(f"\nSimulation Status:")
                    print(f"  Running: {status['is_running']}")
                    print(f"  Time: {status['simulation_time']:.1f}s")
                    print(f"  Scenario: {status['current_scenario']}")
                    print(f"  GPS Health: {status['gps_health_score']:.1f}%")
                    print(f"  Satellites: {status['num_satellites']}")
                    print(f"  Signal Strength: {status['signal_strength']:.1f}%")
                    print()
                
                elif user_input == 'data':
                    data = simulator.get_latest_data()
                    print(f"\nSample of latest data:")
                    # Show first few items as example
                    count = 0
                    for section_name, section_data in data.items():
                        for subsection_name, subsection_data in section_data.items():
                            for req_name, req_data in subsection_data.items():
                                print(f"  {req_data['name']}: {req_data['current_value']:.2f} {req_data['unit']}")
                                count += 1
                                if count >= 5:  # Show only first 5 for brevity
                                    break
                            if count >= 5:
                                break
                        if count >= 5:
                            break
                    print(f"  ... (and {sum(len(ss) for s in data.values() for ss in s.values()) - count} more)")
                    print()
                
            except EOFError:
                break
                
    except KeyboardInterrupt:
        print("\nShutting down simulation...")
        simulator.stop_simulation()
        print("Simulation stopped.")


if __name__ == "__main__":
    main()