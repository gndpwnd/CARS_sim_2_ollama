#!/usr/bin/env python3
"""
Simplified Vehicle Requirements Tracker

Monitors GPS denial detection requirements for each vehicle.
Receives GPS data from external sources and calculates the 12 key requirements.
"""

import json
import time
import threading
import random
import math
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from gps_client_lib import GPSFix, SatelliteInfo


@dataclass
class VehicleMetrics:
    """Simplified GPS metrics"""
    vehicle_id: str
    
    # Core 4 metrics only
    fix_quality_level: int = 0
    active_satellites: int = 0
    signal_quality: float = 45.0
    jamming_level: float = 0.0
    
    # Additional tracking attributes
    satellite_drop_rate: float = 0.0
    cn0_degradation: float = 45.0
    agc_jamming_level: float = 45.0
    checksum_failure_rate: float = 0.0
    truncated_message_rate: float = 0.0
    position_jump: float = 0.0
    velocity_check: float = 0.0
    cycle_slips: float = 0.0
    gps_ins_position_diff: float = 0.0
    gps_time_anomalies: float = 0.0
    
    # History tracking
    satellite_history: List[int] = field(default_factory=list)
    last_position: Optional[tuple] = None
    last_position_time: float = 0.0
    message_count: int = 0
    error_count: int = 0
    
    # Minimal tracking
    last_update_time: float = 0.0


class VehicleRequirementsTracker:
    """Simplified tracker that monitors GPS requirements for multiple vehicles."""
    
    def __init__(self, requirements_config_file: str = "requirements_config.json"):
        self.requirements_config_file = requirements_config_file
        self.requirements_config = self.load_requirements_config()
        
        # Vehicle tracking
        self.vehicle_metrics: Dict[str, VehicleMetrics] = {}
        self.data_lock = threading.Lock()
        
    def load_requirements_config(self) -> Dict[str, Any]:
        """Load requirements configuration."""
        try:
            with open(self.requirements_config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: {self.requirements_config_file} not found")
            return {}
    
    def add_vehicle(self, vehicle_id: str):
        """Add a vehicle to track."""
        with self.data_lock:
            if vehicle_id not in self.vehicle_metrics:
                self.vehicle_metrics[vehicle_id] = VehicleMetrics(vehicle_id=vehicle_id)
                print(f"Added vehicle {vehicle_id} to requirements tracker")
    
    def remove_vehicle(self, vehicle_id: str):
        """Remove a vehicle from tracking."""
        with self.data_lock:
            if vehicle_id in self.vehicle_metrics:
                del self.vehicle_metrics[vehicle_id]
                print(f"Removed vehicle {vehicle_id} from requirements tracker")
    
    def update_gps_fix(self, vehicle_id: str, fix: GPSFix):
        """Update GPS fix data for a vehicle."""
        with self.data_lock:
            if vehicle_id not in self.vehicle_metrics:
                self.add_vehicle(vehicle_id)
            
            metrics = self.vehicle_metrics[vehicle_id]
            current_time = time.time()
            
            # Update basic metrics
            metrics.fix_quality_level = fix.fix_quality
            metrics.velocity_check = fix.speed_kmh / 3.6  # Convert to m/s
            
            # Calculate position jump
            if fix.valid and fix.latitude != 0 and fix.longitude != 0:
                current_pos = (fix.latitude, fix.longitude)
                
                if metrics.last_position:
                    # Calculate distance in meters (approximate)
                    lat_diff = current_pos[0] - metrics.last_position[0]
                    lon_diff = current_pos[1] - metrics.last_position[1]
                    lat_meters = lat_diff * 111000
                    lon_meters = lon_diff * 111000 * math.cos(math.radians(current_pos[0]))
                    distance = math.sqrt(lat_meters**2 + lon_meters**2)
                    
                    time_diff = current_time - metrics.last_position_time
                    if time_diff > 0:
                        expected_max = 15.0 * time_diff  # Max 15 m/s vehicle
                        if distance > expected_max * 2:
                            metrics.position_jump = distance
                        else:
                            metrics.position_jump = max(0, metrics.position_jump - 0.1)
                
                metrics.last_position = current_pos
                metrics.last_position_time = current_time
            
            # Update message statistics
            metrics.message_count += 1
            if random.random() < 0.002:  # Simulate 0.2% error rate
                metrics.error_count += 1
            
            if metrics.message_count > 0:
                metrics.checksum_failure_rate = (metrics.error_count / metrics.message_count) * 100
                metrics.truncated_message_rate = metrics.checksum_failure_rate * 0.5  # Estimate
    
    def update_satellites(self, vehicle_id: str, satellites: List[SatelliteInfo]):
        """Update satellite data for a vehicle."""
        with self.data_lock:
            if vehicle_id not in self.vehicle_metrics:
                self.add_vehicle(vehicle_id)
            
            metrics = self.vehicle_metrics[vehicle_id]
            
            # Count active satellites
            active_sats = len([sat for sat in satellites if sat.used_in_solution])
            metrics.active_satellites = active_sats
            
            # Update satellite history for drop rate calculation
            metrics.satellite_history.append(active_sats)
            if len(metrics.satellite_history) > 20:  # Keep last 20 samples
                metrics.satellite_history.pop(0)
            
            # Calculate satellite drop rate
            if len(metrics.satellite_history) >= 10:  # Need at least 10 samples
                recent = metrics.satellite_history[-5:]  # Last 5 samples
                older = metrics.satellite_history[-10:-5]  # Previous 5 samples
                if older and recent:
                    avg_old = sum(older) / len(older)
                    avg_recent = sum(recent) / len(recent)
                    drop = max(0, avg_old - avg_recent)
                    metrics.satellite_drop_rate = drop  # satellites per 5-second window
            
            # Calculate average C/N0
            if satellites:
                avg_snr = sum(sat.snr for sat in satellites) / len(satellites)
                metrics.cn0_degradation = max(10.0, avg_snr)
                metrics.signal_quality = avg_snr
    
    def update_environmental_conditions(self, vehicle_id: str, 
                                      jamming_level: float = 0.0, 
                                      gps_denied: bool = False):
        """Update environmental conditions for a vehicle."""
        with self.data_lock:
            if vehicle_id not in self.vehicle_metrics:
                self.add_vehicle(vehicle_id)
            
            metrics = self.vehicle_metrics[vehicle_id]
            metrics.jamming_level = jamming_level
            
            # Update AGC based on jamming
            base_agc = 45.0
            metrics.agc_jamming_level = min(100.0, base_agc + jamming_level * 0.5)
            
            # Simulate other environmental effects
            metrics.cycle_slips = max(0, metrics.cycle_slips + (1 if random.random() < jamming_level/200 else -0.1))
            metrics.gps_ins_position_diff = 0.5 + jamming_level/100 + random.uniform(-0.1, 0.1)
            
            if gps_denied:
                metrics.fix_quality_level = 0
                metrics.active_satellites = 0
                metrics.cn0_degradation = 0
    
    def get_vehicle_requirements_data(self, vehicle_id: str) -> Dict[str, Any]:
        """Get requirements data for a vehicle in the format expected by notification GUI."""
        with self.data_lock:
            if vehicle_id not in self.vehicle_metrics:
                return {}
            
            metrics = self.vehicle_metrics[vehicle_id]
            requirements_data = {}
            
            # Map metrics to requirements config structure
            for section_name, section_data in self.requirements_config.items():
                requirements_data[section_name] = {}
                
                for subsection_name, subsection_data in section_data.items():
                    requirements_data[section_name][subsection_name] = {}
                    
                    for req_name, req_config in subsection_data.items():
                        current_value = self._get_metric_value(req_name, metrics)
                        
                        requirements_data[section_name][subsection_name][req_name] = {
                            'name': req_config['name'],
                            'current_value': current_value,
                            'threshold': req_config['threshold'],
                            'warning_threshold': req_config['warning_threshold'],
                            'unit': req_config['unit']
                        }
            
            return requirements_data
    
    def _get_metric_value(self, req_name: str, metrics: VehicleMetrics) -> float:
        """Map requirement name to metric value."""
        mapping = {
            'Fix Quality Level': metrics.fix_quality_level,
            'Satellite Count': metrics.active_satellites,
            'Signal Strength': metrics.signal_quality,
            'Jamming Indicator': metrics.jamming_level
        }
        
        return mapping.get(req_name, 0.0)
    
    def get_all_vehicle_ids(self) -> List[str]:
        """Get list of all tracked vehicle IDs."""
        with self.data_lock:
            return list(self.vehicle_metrics.keys())
    
    def get_vehicle_metrics(self, vehicle_id: str) -> Optional[VehicleMetrics]:
        """Get raw metrics for a vehicle."""
        with self.data_lock:
            return self.vehicle_metrics.get(vehicle_id)


# Test function
def main():
    """Test the requirements tracker."""
    tracker = VehicleRequirementsTracker()
    
    # Add test vehicles
    for i in range(3):
        vehicle_id = f"Vehicle-{i+1}"
        tracker.add_vehicle(vehicle_id)
        
        # Simulate some GPS data
        from gps_client_lib import GPSFix, SatelliteInfo
        
        fix = GPSFix(
            latitude=40.7128 + i * 0.001,
            longitude=-74.0060 + i * 0.001,
            fix_quality=3,
            satellites_used=8,
            speed_kmh=10.0,
            valid=True
        )
        
        satellites = [
            SatelliteInfo(prn=j+1, elevation=45, azimuth=j*45, snr=42, used_in_solution=True)
            for j in range(8)
        ]
        
        tracker.update_gps_fix(vehicle_id, fix)
        tracker.update_satellites(vehicle_id, satellites)
    
    # Test data retrieval
    for vehicle_id in tracker.get_all_vehicle_ids():
        data = tracker.get_vehicle_requirements_data(vehicle_id)
        print(f"\n{vehicle_id} requirements data structure:")
        for section in data.keys():
            print(f"  {section}")


if __name__ == "__main__":
    main()