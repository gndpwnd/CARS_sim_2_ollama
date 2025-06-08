"""
Enhanced distance measurement system for GPS localization simulation.
Refactored to use utils_ToF.py for calculations and constraints_ToF.py for parameters.
Maintains same interface while reducing code redundancy.
"""

import numpy as np
import random
import time
from typing import Tuple, Optional, Dict, List
from dataclasses import dataclass
from enum import Enum

# Import centralized utilities and constraints
from simulation.utils.utils_ToF import (
    time_to_distance, distance_to_time, calculate_geometric_distance,
    clock_resolution_to_distance_error, thermal_error_to_distance_error,
    calculate_total_measurement_error, calculate_communication_quality,
    is_valid_measurement_range, calculate_calibration_offset,
    calculate_measurement_statistics, processing_delay_to_distance_offset
)

from simulation.utils.constraints_ToF import (
    SPEED_OF_LIGHT, SIGNAL_FREQUENCY, SIGNAL_WAVELENGTH, TRANSMIT_POWER,
    RECEIVER_SENSITIVITY, PRECISION_CLOCK_FREQ, STANDARD_CLOCK_FREQ,
    THERMAL_STABILIZATION_TIME, TEMPERATURE_STABILITY, TEMPERATURE_COEFFICIENT,
    MIN_SEPARATION_DISTANCE, MAX_RANGE_THEORETICAL, DISTANCE_MEASUREMENT_NOISE,
    PROCESSING_DELAYS_NS, TOTAL_PROCESSING_DELAY_NS, CALIBRATION_DISTANCE_M,
    CALIBRATION_MEASUREMENTS, SYSTEM_OFFSET_TOLERANCE_M
)

class ClockType(Enum):
    STANDARD = "standard"
    PRECISION = "precision"

@dataclass
class HardwareConfig:
    """Hardware configuration parameters for ToF system"""
    # Use values from constraints_ToF.py
    standard_clock_freq: float = STANDARD_CLOCK_FREQ
    precision_clock_freq: float = PRECISION_CLOCK_FREQ
    signal_frequency: float = SIGNAL_FREQUENCY
    transmit_power: float = TRANSMIT_POWER
    receiver_sensitivity: float = RECEIVER_SENSITIVITY
    thermal_stabilization_time: float = THERMAL_STABILIZATION_TIME
    measurement_duration: float = 0.002  # seconds per ToF measurement
    processing_delay_std: float = 1e-9  # seconds (±1ns typical)
    temperature_stability: float = TEMPERATURE_STABILITY
    temperature_coefficient: float = TEMPERATURE_COEFFICIENT
    activation_jitter: float = 100e-12  # seconds (100 ps)
    multipath_factor: float = 0.1  # fraction of wavelength

@dataclass
class SystemOffsets:
    """System-level timing offsets and calibrations"""
    distance_offset: float = 0.0
    time_offset: float = 0.0
    processing_delays: Dict[str, float] = None
    
    def __post_init__(self):
        if self.processing_delays is None:
            # Convert from nanoseconds to seconds using constraints
            self.processing_delays = {
                key: value * 1e-9 for key, value in PROCESSING_DELAYS_NS.items()
            }

class PrecisionClock:
    """Models a precision timing clock with thermal management"""
    
    def __init__(self, config: HardwareConfig):
        self.config = config
        self.is_active = False
        self.activation_time = 0.0
        self.temperature = 20.0  # °C
        self.target_temperature = 20.0
        self.frequency_drift = 0.0
        
    def activate(self):
        """Activate precision clock and begin thermal stabilization"""
        self.is_active = True
        self.activation_time = time.time()
        self._thermal_stabilization()
        
    def deactivate(self):
        """Deactivate precision clock to save power"""
        self.is_active = False
        self.frequency_drift = 0.0
        
    def _thermal_stabilization(self):
        """Simulate thermal stabilization process"""
        time_constant = self.config.thermal_stabilization_time / 3
        elapsed = min(self.config.thermal_stabilization_time, 0.1)
        
        self.temperature = (self.target_temperature + 
                          (self.temperature - self.target_temperature) * 
                          np.exp(-elapsed / time_constant))
        
        # Use utility function for frequency drift calculation
        temp_error = self.temperature - self.target_temperature
        self.frequency_drift = self.config.temperature_coefficient * temp_error
        
    def get_timing_error(self) -> float:
        """Get current timing error using utility functions"""
        if not self.is_active:
            return float('inf')
            
        # Use utility functions for error calculations
        clock_error = clock_resolution_to_distance_error(self.config.precision_clock_freq)
        thermal_error = thermal_error_to_distance_error(abs(self.temperature - self.target_temperature))
        activation_error = time_to_distance(self.config.activation_jitter, round_trip=True)
        
        # Combined RMS error
        total_error = np.sqrt(clock_error**2 + thermal_error**2 + activation_error**2)
        return distance_to_time(total_error, round_trip=True)

class ToFDistanceMeasurement:
    """Enhanced Time-of-Flight distance measurement system"""
    
    def __init__(self, hardware_config: HardwareConfig = None):
        self.config = hardware_config or HardwareConfig()
        self.precision_clock = PrecisionClock(self.config)
        self.system_offsets = SystemOffsets()
        self.measurement_history = []
        self.noise_generator = random.Random()
        self.is_calibrated = False
        
        # Use constraints for derived parameters
        self.wavelength = SIGNAL_WAVELENGTH
        self.min_separation = MIN_SEPARATION_DISTANCE
        self.max_range = MAX_RANGE_THEORETICAL
        
    def calibrate_system(self, known_distance: float = CALIBRATION_DISTANCE_M, 
                        num_measurements: int = CALIBRATION_MEASUREMENTS) -> bool:
        """Calibrate system using known distance reference"""
        if not self.precision_clock.is_active:
            self.precision_clock.activate()
            
        measurements = []
        for _ in range(num_measurements):
            # Create dummy positions at known distance
            pos1 = (0.0, 0.0)
            pos2 = (known_distance, 0.0)
            measured_distance = self._simulate_measurement(pos1, pos2, add_noise=True)
            measurements.append(measured_distance)
            
        # Use utility function for calibration offset calculation
        self.system_offsets.distance_offset = calculate_calibration_offset(measurements, known_distance)
        self.system_offsets.time_offset = distance_to_time(self.system_offsets.distance_offset, round_trip=True)
        
        # Check if calibration is acceptable
        self.is_calibrated = abs(self.system_offsets.distance_offset) <= SYSTEM_OFFSET_TOLERANCE_M
        return self.is_calibrated
    
    def measure_distance(
        self, 
        pos1: Tuple[float, ...], 
        pos2: Tuple[float, ...],
        use_precision_timing: bool = True
    ) -> Optional[float]:
        """
        Measure distance between two positions using ToF methodology
        Maintains same interface as original
        """
        try:
            # Use utility function for geometric distance
            true_distance = calculate_geometric_distance(pos1, pos2)
            
            # Use utility function for range validation
            if not is_valid_measurement_range(true_distance):
                return None
                
            # Activate precision clock if needed
            if use_precision_timing and not self.precision_clock.is_active:
                self.precision_clock.activate()
            
            # Perform measurement simulation
            if use_precision_timing:
                measured_distance = self._perform_precision_measurement(true_distance)
            else:
                measured_distance = self._perform_standard_measurement(true_distance)
            
            # Apply calibration corrections
            if self.is_calibrated:
                measured_distance += self.system_offsets.distance_offset
            
            # Store measurement for analysis
            self._store_measurement(true_distance, measured_distance, use_precision_timing)
            
            return max(0.0, measured_distance)
            
        except Exception as e:
            print(f"ToF distance measurement error: {e}")
            return None
    
    def _perform_precision_measurement(self, true_distance: float) -> float:
        """Perform high-precision ToF measurement using utility functions"""
        # Use utility function for total measurement error
        measurement_error = calculate_total_measurement_error(
            distance_m=true_distance,
            temp_error_c=abs(self.precision_clock.temperature - self.precision_clock.target_temperature),
            processing_jitter_s=self.config.processing_delay_std,
            snr_db=20,  # Assume 20 dB SNR
            multipath_factor=self.config.multipath_factor
        )
        
        # Add noise based on calculated error
        noise = self.noise_generator.gauss(0, measurement_error)
        measured_distance = true_distance + noise
        
        return measured_distance
    
    def _perform_standard_measurement(self, true_distance: float) -> float:
        """Perform standard-precision measurement using utility functions"""
        # Standard clock has much lower precision
        standard_error = clock_resolution_to_distance_error(self.config.standard_clock_freq)
        
        # Add processing delays and other errors
        total_error = np.sqrt(standard_error**2 + (DISTANCE_MEASUREMENT_NOISE * 2)**2)
        
        noise = self.noise_generator.gauss(0, total_error)
        measured_distance = true_distance + noise
        
        return measured_distance
    
    def _simulate_measurement(self, pos1: Tuple[float, ...], pos2: Tuple[float, ...], 
                            add_noise: bool = True) -> float:
        """Simulate measurement process for calibration"""
        true_distance = calculate_geometric_distance(pos1, pos2)
        
        if add_noise:
            return self._perform_precision_measurement(true_distance)
        else:
            # Add only processing delays without noise
            processing_offset = processing_delay_to_distance_offset(TOTAL_PROCESSING_DELAY_NS)
            return true_distance + processing_offset
    
    def _store_measurement(self, true_distance: float, measured_distance: float, precision_mode: bool):
        """Store measurement data for analysis"""
        measurement = {
            'timestamp': time.time(),
            'true_distance': true_distance,
            'measured_distance': measured_distance,
            'error': abs(measured_distance - true_distance),
            'precision_mode': precision_mode,
            'clock_active': self.precision_clock.is_active
        }
        
        self.measurement_history.append(measurement)
        
        # Keep only recent measurements
        if len(self.measurement_history) > 1000:
            self.measurement_history.pop(0)
    
    def get_system_capabilities(self) -> Dict:
        """Get current system capabilities and constraints"""
        return {
            'max_range': self.max_range,
            'min_separation': self.min_separation,
            'wavelength': self.wavelength,
            'signal_frequency': self.config.signal_frequency,
            'precision_clock_freq': self.config.precision_clock_freq,
            'expected_precision_cm': self._calculate_expected_precision(),
            'calibrated': self.is_calibrated,
            'precision_clock_active': self.precision_clock.is_active
        }
    
    def _calculate_expected_precision(self) -> float:
        """Calculate expected distance measurement precision in cm"""
        if self.precision_clock.is_active:
            # Use utility function for precision calculation
            distance_precision = clock_resolution_to_distance_error(self.config.precision_clock_freq)
        else:
            distance_precision = clock_resolution_to_distance_error(self.config.standard_clock_freq)
        
        return distance_precision * 100  # Convert to cm
    
    def get_measurement_statistics(self) -> Dict:
        """Get comprehensive measurement statistics using utility functions"""
        if not self.measurement_history:
            return {'count': 0}
        
        recent_measurements = self.measurement_history[-100:]
        measured_values = [m['measured_distance'] for m in recent_measurements]
        true_values = [m['true_distance'] for m in recent_measurements]
        
        # Use utility function for statistics calculation
        stats = calculate_measurement_statistics(measured_values, true_values)
        
        # Add mode-specific statistics
        precision_measurements = [m for m in recent_measurements if m['precision_mode']]
        standard_measurements = [m for m in recent_measurements if not m['precision_mode']]
        
        stats.update({
            'total_count': len(self.measurement_history),
            'precision_mode_count': len(precision_measurements),
            'standard_mode_count': len(standard_measurements),
            'calibrated': self.is_calibrated
        })
        
        if precision_measurements:
            precision_measured = [m['measured_distance'] for m in precision_measurements]
            precision_true = [m['true_distance'] for m in precision_measurements]
            precision_stats = calculate_measurement_statistics(precision_measured, precision_true)
            stats['precision_mean_error_cm'] = precision_stats.get('mean_error_cm', 0)
            stats['precision_std_error_cm'] = precision_stats.get('std_error_cm', 0)
            
        return stats
    
    def can_communicate(self, pos1: Tuple[float, ...], pos2: Tuple[float, ...]) -> bool:
        """Check if two entities can communicate using utility functions"""
        distance = calculate_geometric_distance(pos1, pos2)
        return is_valid_measurement_range(distance)
    
    def get_communication_quality(self, pos1: Tuple[float, ...], pos2: Tuple[float, ...]) -> float:
        """Get communication quality using utility functions"""
        distance = calculate_geometric_distance(pos1, pos2)
        return calculate_communication_quality(distance)
    
    def power_cycle_precision_clock(self):
        """Power cycle the precision clock (for thermal management)"""
        if self.precision_clock.is_active:
            self.precision_clock.deactivate()
            time.sleep(0.001)  # Small delay to simulate power down
        
        self.precision_clock.activate()
    
    def get_thermal_status(self) -> Dict:
        """Get thermal management status"""
        return {
            'precision_clock_active': self.precision_clock.is_active,
            'current_temperature': self.precision_clock.temperature,
            'target_temperature': self.precision_clock.target_temperature,
            'frequency_drift': self.precision_clock.frequency_drift,
            'thermal_stable': abs(self.precision_clock.temperature - 
                                self.precision_clock.target_temperature) < self.config.temperature_stability
        }