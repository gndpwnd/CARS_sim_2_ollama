"""
Integration module for tracking GPS denial detection requirements

Connects the vehicle_requirements_tracker with the simulation and GPS client
to monitor the 12 key requirements for detecting GPS denial.
"""

import json
import threading
import time
from typing import Dict, List, Any
from datetime import datetime

# Import the requirements tracker
try:
    from vehicle_requirements_tracker import VehicleRequirementsTracker, VehicleMetrics
    from gps_client_lib import GPSData, parse_nmea_gga
    TRACKER_ENABLED = True
except ImportError as e:
    print(f"Warning: Requirements tracker not available: {e}")
    TRACKER_ENABLED = False


class SimulationRequirementsMonitor:
    """
    Monitors GPS denial requirements for all agents in simulation
    
    Integrates with:
    - Vehicle Requirements Tracker (monitoring)
    - GPS Client (data source)
    - RAG Store (logging)
    - Simulation (agent states)
    """
    
    def __init__(self, requirements_config_file: str = "requirements_config.json"):
        if not TRACKER_ENABLED:
            raise RuntimeError("Requirements tracker not available")
        
        self.tracker = VehicleRequirementsTracker(requirements_config_file)
        self.monitoring = False
        self.monitor_thread = None
        self.update_interval = 1.0  # Check every second
        
    def add_agent(self, agent_id: str):
        """Register an agent for requirements monitoring"""
        self.tracker.add_vehicle(agent_id)
        print(f"[REQ MONITOR] Added {agent_id} to requirements monitoring")
    
    def remove_agent(self, agent_id: str):
        """Unregister an agent from requirements monitoring"""
        self.tracker.remove_vehicle(agent_id)
        print(f"[REQ MONITOR] Removed {agent_id} from requirements monitoring")
    
    def update_from_gps_data(self, agent_id: str, gps_data: GPSData):
        """
        Update requirements metrics from GPS data
        
        Args:
            agent_id: Agent identifier
            gps_data: GPSData object from constellation
        """
        try:
            # Parse NMEA sentences for detailed metrics
            from gps_client_lib import GPSFix, SatelliteInfo
            
            # Extract fix information from GGA sentence
            fix = None
            for sentence in gps_data.nmea_sentences:
                if 'GGA' in sentence:
                    parsed = parse_nmea_gga(sentence)
                    if parsed.get('valid'):
                        fix = GPSFix(
                            latitude=self._parse_coord(parsed.get('latitude', '0'), 
                                                      parsed.get('lat_dir', 'N')),
                            longitude=self._parse_coord(parsed.get('longitude', '0'),
                                                       parsed.get('lon_dir', 'W')),
                            fix_quality=parsed.get('fix_quality', 0),
                            satellites_used=parsed.get('satellites', 0),
                            speed_kmh=0.0,  # Not available in GGA
                            valid=True
                        )
                    break
            
            # Update GPS fix data if available
            if fix:
                self.tracker.update_gps_fix(agent_id, fix)
            
            # Create satellite info from GSV or use counts from GGA
            satellites = []
            # In real implementation, parse GSV sentences for detailed satellite info
            # For now, create placeholder satellite data
            for i in range(gps_data.satellite_count):
                sat = SatelliteInfo(
                    prn=i+1,
                    elevation=45.0,
                    azimuth=i*30.0,
                    snr=gps_data.signal_quality,
                    used_in_solution=True
                )
                satellites.append(sat)
            
            self.tracker.update_satellites(agent_id, satellites)
            
        except Exception as e:
            print(f"[REQ MONITOR] Error updating from GPS data: {e}")
    
    def update_from_simulation_state(self, agent_id: str, position: tuple,
                                    is_jammed: bool, jamming_level: float):
        """
        Update requirements from simulation state
        
        Args:
            agent_id: Agent identifier
            position: (x, y) position
            is_jammed: Whether agent is in jamming zone
            jamming_level: Jamming intensity (0-100%)
        """
        try:
            self.tracker.update_environmental_conditions(
                vehicle_id=agent_id,
                jamming_level=jamming_level,
                gps_denied=is_jammed
            )
        except Exception as e:
            print(f"[REQ MONITOR] Error updating from simulation state: {e}")
    
    def get_requirements_status(self, agent_id: str) -> Dict[str, Any]:
        """
        Get current requirements status for an agent
        
        Returns structured data showing which requirements are violated
        """
        try:
            return self.tracker.get_vehicle_requirements_data(agent_id)
        except Exception as e:
            print(f"[REQ MONITOR] Error getting requirements status: {e}")
            return {}
    
    def get_violations(self, agent_id: str) -> List[Dict[str, Any]]:
        """
        Get list of requirement violations for an agent
        
        Returns list of requirements that exceed critical thresholds
        """
        violations = []
        
        try:
            req_data = self.tracker.get_vehicle_requirements_data(agent_id)
            
            for section_name, section_data in req_data.items():
                for subsection_name, subsection_data in section_data.items():
                    for req_name, req_info in subsection_data.items():
                        current = req_info['current_value']
                        threshold = req_info['threshold']
                        warning = req_info['warning_threshold']
                        
                        # Determine violation level
                        status = 'OK'
                        if self._exceeds_threshold(req_name, current, threshold):
                            status = 'CRITICAL'
                        elif self._exceeds_threshold(req_name, current, warning):
                            status = 'WARNING'
                        
                        if status != 'OK':
                            violations.append({
                                'requirement': req_name,
                                'section': section_name,
                                'subsection': subsection_name,
                                'current_value': current,
                                'threshold': threshold,
                                'warning_threshold': warning,
                                'unit': req_info['unit'],
                                'status': status
                            })
        
        except Exception as e:
            print(f"[REQ MONITOR] Error getting violations: {e}")
        
        return violations
    
    def _exceeds_threshold(self, req_name: str, current: float, threshold: float) -> bool:
        """
        Check if current value exceeds threshold
        Some requirements are "less than" and some are "greater than"
        """
        # Requirements where LOWER is better (should be above threshold)
        lower_is_better = [
            'Fix Quality Degradation Detection',
            'Satellite Count Critical Threshold',
            'Carrier-to-Noise Ratio Degradation Detection'
        ]
        
        if any(name in req_name for name in lower_is_better):
            return current < threshold
        else:
            return current > threshold
    
    def _parse_coord(self, coord_str: str, direction: str) -> float:
        """Parse NMEA coordinate string to decimal degrees"""
        try:
            if not coord_str or coord_str == '0':
                return 0.0
            
            # Format: DDMM.MMMM or DDDMM.MMMM
            if '.' in coord_str:
                parts = coord_str.split('.')
                degrees_minutes = parts[0]
                fraction = parts[1]
                
                # Extract degrees and minutes
                if len(degrees_minutes) <= 4:  # Latitude
                    degrees = int(degrees_minutes[:-2])
                    minutes = int(degrees_minutes[-2:])
                else:  # Longitude
                    degrees = int(degrees_minutes[:-2])
                    minutes = int(degrees_minutes[-2:])
                
                # Convert to decimal
                decimal = degrees + (minutes + float('0.' + fraction)) / 60.0
                
                # Apply direction
                if direction in ['S', 'W']:
                    decimal = -decimal
                
                return decimal
        except Exception as e:
            print(f"Error parsing coordinate: {e}")
            return 0.0
    
    def log_requirements_status(self, agent_id: str):
        """Log requirements status to RAG store"""
        try:
            from rag_store import add_log
            
            violations = self.get_violations(agent_id)
            
            if violations:
                timestamp = datetime.now().isoformat()
                
                # Create summary text
                critical_count = sum(1 for v in violations if v['status'] == 'CRITICAL')
                warning_count = sum(1 for v in violations if v['status'] == 'WARNING')
                
                log_text = (
                    f"GPS Requirements Status for {agent_id}: "
                    f"{critical_count} CRITICAL, {warning_count} WARNING violations"
                )
                
                metadata = {
                    'timestamp': timestamp,
                    'agent_id': agent_id,
                    'violations': violations,
                    'critical_count': critical_count,
                    'warning_count': warning_count,
                    'role': 'system',
                    'source': 'requirements_monitor',
                    'message_type': 'requirements_status'
                }
                
                add_log(log_text, metadata)
                
        except Exception as e:
            print(f"[REQ MONITOR] Error logging requirements status: {e}")
    
    def start_monitoring(self):
        """Start continuous requirements monitoring"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("[REQ MONITOR] Started continuous monitoring")
    
    def stop_monitoring(self):
        """Stop continuous requirements monitoring"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
        print("[REQ MONITOR] Stopped continuous monitoring")
    
    def _monitor_loop(self):
        """Continuous monitoring loop"""
        while self.monitoring:
            try:
                # Log requirements status for all tracked agents
                for agent_id in self.tracker.get_all_vehicle_ids():
                    self.log_requirements_status(agent_id)
                
                time.sleep(self.update_interval)
                
            except Exception as e:
                print(f"[REQ MONITOR] Error in monitor loop: {e}")
                time.sleep(self.update_interval)


# Integration helper functions for use in simulation
def create_requirements_monitor():
    """Factory function to create requirements monitor"""
    if not TRACKER_ENABLED:
        print("[REQ MONITOR] Requirements tracking not available")
        return None
    
    try:
        monitor = SimulationRequirementsMonitor()
        return monitor
    except Exception as e:
        print(f"[REQ MONITOR] Failed to create monitor: {e}")
        return None


def get_requirements_summary(monitor: SimulationRequirementsMonitor, 
                            agent_id: str) -> str:
    """
    Get human-readable summary of requirements status
    
    Returns:
        String summary suitable for logging or display
    """
    if not monitor:
        return "Requirements monitoring not available"
    
    try:
        violations = monitor.get_violations(agent_id)
        
        if not violations:
            return f"{agent_id}: All GPS requirements within normal parameters"
        
        critical = [v for v in violations if v['status'] == 'CRITICAL']
        warnings = [v for v in violations if v['status'] == 'WARNING']
        
        summary = f"{agent_id} GPS Status: "
        
        if critical:
            summary += f"{len(critical)} CRITICAL - "
            summary += ", ".join([v['requirement'].split(' ')[-2:][0] for v in critical[:3]])
            if len(critical) > 3:
                summary += f" +{len(critical)-3} more"
        
        if warnings:
            if critical:
                summary += "; "
            summary += f"{len(warnings)} WARNING"
        
        return summary
        
    except Exception as e:
        return f"Error getting summary: {e}"


# Example integration with simulation
if __name__ == "__main__":
    print("Testing Requirements Monitor Integration")
    
    # Create monitor
    monitor = create_requirements_monitor()
    
    if monitor:
        # Add test agents
        test_agents = ["agent1", "agent2", "agent3"]
        for agent_id in test_agents:
            monitor.add_agent(agent_id)
        
        # Simulate some GPS data updates
        from gps_client_lib import GPSData
        
        # Agent 1: Good GPS
        gps_good = GPSData(
            vehicle_id="agent1",
            nmea_sentences=["$GPGGA,002153.000,3342.6618,N,11751.3858,W,6,10,1.2,27.0,M,-34.2,M,,0000*5E"],
            rtcm_messages=[],
            satellite_count=10,
            fix_quality=6,
            signal_quality=45.0,
            timestamp=time.time()
        )
        monitor.update_from_gps_data("agent1", gps_good)
        monitor.update_from_simulation_state("agent1", (0, 0), False, 0.0)
        
        # Agent 2: Degraded GPS (jamming)
        gps_degraded = GPSData(
            vehicle_id="agent2",
            nmea_sentences=["$GPGGA,002153.000,3342.6618,N,11751.3858,W,1,3,5.5,27.0,M,-34.2,M,,0000*5E"],
            rtcm_messages=[],
            satellite_count=3,
            fix_quality=1,
            signal_quality=28.0,
            timestamp=time.time()
        )
        monitor.update_from_gps_data("agent2", gps_degraded)
        monitor.update_from_simulation_state("agent2", (2, 2), True, 75.0)
        
        # Agent 3: No GPS (fully jammed)
        gps_denied = GPSData(
            vehicle_id="agent3",
            nmea_sentences=["$GPGGA,002153.000,0000.0000,N,00000.0000,W,0,0,99.9,0.0,M,0.0,M,,*5E"],
            rtcm_messages=[],
            satellite_count=0,
            fix_quality=0,
            signal_quality=0.0,
            timestamp=time.time()
        )
        monitor.update_from_gps_data("agent3", gps_denied)
        monitor.update_from_simulation_state("agent3", (0, 0), True, 100.0)
        
        # Check requirements status
        print("\nRequirements Status:")
        for agent_id in test_agents:
            summary = get_requirements_summary(monitor, agent_id)
            print(f"  {summary}")
            
            violations = monitor.get_violations(agent_id)
            if violations:
                print(f"    Violations:")
                for v in violations[:5]:  # Show first 5
                    print(f"      - {v['requirement']}: {v['current_value']:.1f} {v['unit']} "
                          f"(threshold: {v['threshold']:.1f}) [{v['status']}]")
        
        print("\nTest complete")