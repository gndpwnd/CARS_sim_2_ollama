"""
Time-of-Flight mathematical utilities for GPS localization simulation.
Centralizes all ToF-related calculations, physics functions, and mathematical operations.
Uses constraints from constraints_ToF.py for consistency.
"""

import numpy as np
import math
from typing import Tuple, Dict, Optional, List
from simulation.utils.constraints_ToF import (
    SPEED_OF_LIGHT, REFRACTIVE_INDEX_AIR, SIGNAL_FREQUENCY, SIGNAL_WAVELENGTH,
    TRANSMIT_POWER, RECEIVER_SENSITIVITY, PRECISION_CLOCK_FREQ, STANDARD_CLOCK_FREQ,
    TEMPERATURE_COEFFICIENT, MIN_SEPARATION_DISTANCE, MAX_RANGE_THEORETICAL,
    DISTANCE_MEASUREMENT_NOISE, PROCESSING_DELAYS_NS, TOTAL_PROCESSING_DELAY_NS
)

# ==============================================
# FUNDAMENTAL PHYSICS CALCULATIONS
# ==============================================

def time_to_distance(time_seconds: float, round_trip: bool = True) -> float:
    """
    Convert time measurement to distance using speed of light
    
    Args:
        time_seconds: Time measurement in seconds
        round_trip: If True, accounts for round-trip time (divide by 2)
        
    Returns:
        Distance in meters
    """
    divisor = 2 if round_trip else 1
    return (SPEED_OF_LIGHT * time_seconds) / divisor

def distance_to_time(distance_meters: float, round_trip: bool = True) -> float:
    """
    Convert distance to time measurement
    
    Args:
        distance_meters: Distance in meters
        round_trip: If True, accounts for round-trip time (multiply by 2)
        
    Returns:
        Time in seconds
    """
    multiplier = 2 if round_trip else 1
    return (distance_meters * multiplier) / SPEED_OF_LIGHT

def calculate_geometric_distance(pos1: Tuple[float, ...], pos2: Tuple[float, ...]) -> float:
    """
    Calculate true geometric distance between two positions
    
    Args:
        pos1: First position (x, y) or (x, y, z)
        pos2: Second position (x, y) or (x, y, z)
        
    Returns:
        Distance in meters
    """
    if len(pos1) >= 3 and len(pos2) >= 3:
        # 3D distance
        return math.sqrt(sum((pos1[i] - pos2[i])**2 for i in range(3)))
    else:
        # 2D distance
        return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)

# ==============================================
# CLOCK AND TIMING CALCULATIONS
# ==============================================

def required_clock_frequency(target_distance_accuracy: float) -> float:
    """
    Calculate required clock frequency for target distance accuracy
    
    Args:
        target_distance_accuracy: Desired distance accuracy in meters
        
    Returns:
        Required clock frequency in Hz
    """
    required_time_resolution = distance_to_time(target_distance_accuracy, round_trip=True)
    return 1.0 / required_time_resolution

def clock_resolution_to_distance_error(clock_freq: float) -> float:
    """
    Convert clock resolution to distance measurement error
    
    Args:
        clock_freq: Clock frequency in Hz
        
    Returns:
        Distance error in meters (1-sigma)
    """
    time_resolution = 1.0 / clock_freq
    # RMS error for uniform quantization
    time_error_rms = time_resolution / math.sqrt(12)
    return time_to_distance(time_error_rms, round_trip=True)

def calculate_thermal_frequency_drift(temp_error_celsius: float) -> float:
    """
    Calculate frequency drift due to temperature variation
    
    Args:
        temp_error_celsius: Temperature error in degrees Celsius
        
    Returns:
        Relative frequency drift (dimensionless)
    """
    return TEMPERATURE_COEFFICIENT * temp_error_celsius

def thermal_error_to_distance_error(temp_error_celsius: float) -> float:
    """
    Convert temperature error to distance measurement error
    
    Args:
        temp_error_celsius: Temperature error in degrees Celsius
        
    Returns:
        Distance error in meters
    """
    freq_drift = calculate_thermal_frequency_drift(temp_error_celsius)
    time_error = abs(freq_drift) * (1.0 / SIGNAL_FREQUENCY)
    return time_to_distance(time_error, round_trip=True)

# ==============================================
# SIGNAL PROPAGATION CALCULATIONS
# ==============================================

def free_space_path_loss_db(distance_km: float, freq_mhz: float) -> float:
    """
    Calculate Free Space Path Loss in dB
    
    Args:
        distance_km: Distance in kilometers
        freq_mhz: Frequency in MHz
        
    Returns:
        Path loss in dB
    """
    return 20 * math.log10(distance_km) + 20 * math.log10(freq_mhz) + 32.44

def calculate_received_power_dbm(distance_m: float, tx_power_w: float = TRANSMIT_POWER) -> float:
    """
    Calculate received power based on distance and transmit power
    
    Args:
        distance_m: Distance in meters
        tx_power_w: Transmit power in watts
        
    Returns:
        Received power in dBm
    """
    freq_mhz = SIGNAL_FREQUENCY / 1e6
    distance_km = distance_m / 1000
    
    tx_power_dbm = 10 * math.log10(tx_power_w * 1000)  # Convert W to dBm
    fspl_db = free_space_path_loss_db(distance_km, freq_mhz)
    
    return tx_power_dbm - fspl_db

def calculate_link_margin_db(distance_m: float, tx_power_w: float = TRANSMIT_POWER) -> float:
    """
    Calculate link margin above receiver sensitivity
    
    Args:
        distance_m: Distance in meters
        tx_power_w: Transmit power in watts
        
    Returns:
        Link margin in dB
    """
    received_power = calculate_received_power_dbm(distance_m, tx_power_w)
    return received_power - RECEIVER_SENSITIVITY

def calculate_max_communication_range(tx_power_w: float = TRANSMIT_POWER) -> float:
    """
    Calculate maximum communication range based on link budget
    
    Args:
        tx_power_w: Transmit power in watts
        
    Returns:
        Maximum range in meters
    """
    tx_power_dbm = 10 * math.log10(tx_power_w * 1000)
    link_budget = tx_power_dbm - RECEIVER_SENSITIVITY
    freq_mhz = SIGNAL_FREQUENCY / 1e6
    
    # Solve FSPL equation for distance
    distance_term = link_budget - 20 * math.log10(freq_mhz) - 32.44
    max_distance_km = 10**(distance_term / 20)
    
    return max_distance_km * 1000  # Convert to meters

def calculate_communication_quality(distance_m: float) -> float:
    """
    Calculate communication quality based on distance and link budget
    
    Args:
        distance_m: Distance in meters
        
    Returns:
        Quality factor between 0.0 and 1.0
    """
    if distance_m > MAX_RANGE_THEORETICAL or distance_m < MIN_SEPARATION_DISTANCE:
        return 0.0
    
    margin = calculate_link_margin_db(distance_m)
    max_margin = calculate_link_margin_db(MIN_SEPARATION_DISTANCE)
    
    return max(0.0, min(1.0, margin / max_margin))

# ==============================================
# NOISE AND ERROR CALCULATIONS
# ==============================================

def calculate_thermal_noise_power_dbm(bandwidth_hz: float, temperature_k: float = 290) -> float:
    """
    Calculate thermal noise power
    
    Args:
        bandwidth_hz: Bandwidth in Hz
        temperature_k: Temperature in Kelvin (default room temperature)
        
    Returns:
        Noise power in dBm
    """
    k_boltzmann = 1.38e-23  # J/K
    noise_power_w = k_boltzmann * temperature_k * bandwidth_hz
    return 10 * math.log10(noise_power_w * 1000)  # Convert to dBm

def calculate_snr_db(distance_m: float, bandwidth_hz: float) -> float:
    """
    Calculate Signal-to-Noise Ratio
    
    Args:
        distance_m: Distance in meters
        bandwidth_hz: Bandwidth in Hz
        
    Returns:
        SNR in dB
    """
    signal_power = calculate_received_power_dbm(distance_m)
    noise_power = calculate_thermal_noise_power_dbm(bandwidth_hz)
    return signal_power - noise_power

def snr_to_distance_error(snr_db: float, bandwidth_hz: float) -> float:
    """
    Convert SNR to distance measurement error
    
    Args:
        snr_db: Signal-to-Noise Ratio in dB
        bandwidth_hz: Bandwidth in Hz
        
    Returns:
        Distance error in meters (1-sigma)
    """
    snr_linear = 10**(snr_db / 10)
    time_error = 1.0 / (bandwidth_hz * math.sqrt(snr_linear))
    return time_to_distance(time_error, round_trip=True)

def calculate_multipath_error(wavelength_m: float = SIGNAL_WAVELENGTH, 
                            multipath_factor: float = 0.1) -> float:
    """
    Calculate multipath-induced distance error
    
    Args:
        wavelength_m: Signal wavelength in meters
        multipath_factor: Fraction of wavelength for multipath error
        
    Returns:
        Maximum multipath error in meters
    """
    return multipath_factor * wavelength_m

# ==============================================
# COMPOSITE ERROR CALCULATIONS
# ==============================================

def calculate_total_measurement_error(distance_m: float, 
                                    temp_error_c: float = 0.1,
                                    processing_jitter_s: float = 1e-9,
                                    snr_db: float = 20,
                                    multipath_factor: float = 0.1) -> float:
    """
    Calculate total distance measurement error from all sources
    
    Args:
        distance_m: Measurement distance in meters
        temp_error_c: Temperature error in Celsius
        processing_jitter_s: Processing delay jitter in seconds
        snr_db: Signal-to-Noise Ratio in dB
        multipath_factor: Multipath error as fraction of wavelength
        
    Returns:
        Total RMS error in meters
    """
    # Clock quantization error
    clock_error = clock_resolution_to_distance_error(PRECISION_CLOCK_FREQ)
    
    # Thermal stability error
    thermal_error = thermal_error_to_distance_error(temp_error_c)
    
    # Processing jitter error
    processing_error = time_to_distance(processing_jitter_s, round_trip=True)
    
    # Signal noise error
    bandwidth = SIGNAL_FREQUENCY * 0.1  # Assume 10% of carrier frequency
    noise_error = snr_to_distance_error(snr_db, bandwidth)
    
    # Multipath error
    multipath_error = calculate_multipath_error(SIGNAL_WAVELENGTH, multipath_factor)
    
    # Root Sum Square combination
    total_error = math.sqrt(
        clock_error**2 + 
        thermal_error**2 + 
        processing_error**2 + 
        noise_error**2 + 
        multipath_error**2
    )
    
    return total_error

# ==============================================
# RANGE AND CONSTRAINT VALIDATION
# ==============================================

def is_valid_measurement_range(distance_m: float) -> bool:
    """
    Check if distance is within valid measurement range
    
    Args:
        distance_m: Distance in meters
        
    Returns:
        True if distance is measurable
    """
    return MIN_SEPARATION_DISTANCE <= distance_m <= MAX_RANGE_THEORETICAL

def can_entities_communicate(pos1: Tuple[float, ...], pos2: Tuple[float, ...]) -> bool:
    """
    Check if two entities can communicate based on range constraints
    
    Args:
        pos1: First position
        pos2: Second position
        
    Returns:
        True if communication is possible
    """
    distance = calculate_geometric_distance(pos1, pos2)
    return is_valid_measurement_range(distance)

def calculate_minimum_separation_for_accuracy(target_accuracy_m: float) -> float:
    """
    Calculate minimum separation needed for target accuracy
    
    Args:
        target_accuracy_m: Target measurement accuracy in meters
        
    Returns:
        Minimum separation distance in meters
    """
    # Based on wavelength constraint and accuracy requirements
    wavelength_constraint = SIGNAL_WAVELENGTH
    accuracy_constraint = target_accuracy_m * 10  # Conservative factor
    
    return max(wavelength_constraint, accuracy_constraint, MIN_SEPARATION_DISTANCE)

# ==============================================
# TIME SYNCHRONIZATION UTILITIES
# ==============================================

def calculate_measurement_window_duration(rover_velocity_ms: float, 
                                        target_accuracy_m: float) -> float:
    """
    Calculate maximum measurement window for moving rover
    
    Args:
        rover_velocity_ms: Rover velocity in m/s
        target_accuracy_m: Target position accuracy in meters
        
    Returns:
        Maximum measurement window in seconds
    """
    if rover_velocity_ms <= 0:
        return float('inf')
    
    return target_accuracy_m / rover_velocity_ms

def processing_delay_to_distance_offset(delay_ns: float) -> float:
    """
    Convert processing delay to distance offset
    
    Args:
        delay_ns: Processing delay in nanoseconds
        
    Returns:
        Distance offset in meters
    """
    delay_s = delay_ns * 1e-9
    return time_to_distance(delay_s, round_trip=True)

def calculate_total_processing_offset() -> float:
    """
    Calculate total distance offset due to processing delays
    
    Returns:
        Total processing offset in meters
    """
    return processing_delay_to_distance_offset(TOTAL_PROCESSING_DELAY_NS)

# ==============================================
# CALIBRATION UTILITIES
# ==============================================

def calculate_calibration_offset(measured_distances: List[float], 
                                known_distance: float) -> float:
    """
    Calculate system calibration offset from measurements
    
    Args:
        measured_distances: List of measured distances
        known_distance: Known reference distance
        
    Returns:
        Calibration offset in meters (to add to future measurements)
    """
    if not measured_distances:
        return 0.0
    
    mean_measured = np.mean(measured_distances)
    return known_distance - mean_measured

def is_calibration_acceptable(offset_m: float, tolerance_m: float = 0.01) -> bool:
    """
    Check if calibration offset is within acceptable limits
    
    Args:
        offset_m: Calibration offset in meters
        tolerance_m: Maximum acceptable offset
        
    Returns:
        True if calibration is acceptable
    """
    return abs(offset_m) <= tolerance_m

# ==============================================
# POWER AND PERFORMANCE CALCULATIONS
# ==============================================

def calculate_precision_clock_duty_cycle(measurement_duration_s: float,
                                       thermal_stabilization_s: float,
                                       cycle_period_s: float) -> float:
    """
    Calculate duty cycle for precision clock operation
    
    Args:
        measurement_duration_s: Time for actual measurement
        thermal_stabilization_s: Time for thermal stabilization
        cycle_period_s: Total cycle period
        
    Returns:
        Duty cycle as fraction (0-1)
    """
    active_time = measurement_duration_s + thermal_stabilization_s
    return min(1.0, active_time / cycle_period_s)

def calculate_power_savings(continuous_power_w: float, 
                           duty_cycle: float) -> Dict[str, float]:
    """
    Calculate power savings from duty cycle operation
    
    Args:
        continuous_power_w: Continuous operation power
        duty_cycle: Duty cycle fraction
        
    Returns:
        Dictionary with power consumption and savings
    """
    average_power = continuous_power_w * duty_cycle
    power_savings = continuous_power_w - average_power
    savings_percent = (power_savings / continuous_power_w) * 100
    
    return {
        'continuous_power_w': continuous_power_w,
        'average_power_w': average_power,
        'power_savings_w': power_savings,
        'savings_percent': savings_percent
    }

# ==============================================
# STATISTICAL ANALYSIS UTILITIES
# ==============================================

def calculate_measurement_statistics(measurements: List[float], 
                                   true_values: List[float]) -> Dict:
    """
    Calculate comprehensive measurement statistics
    
    Args:
        measurements: List of measured values
        true_values: List of true values
        
    Returns:
        Dictionary with statistical measures
    """
    if len(measurements) != len(true_values) or not measurements:
        return {}
    
    errors = [abs(m - t) for m, t in zip(measurements, true_values)]
    biases = [m - t for m, t in zip(measurements, true_values)]
    
    return {
        'count': len(measurements),
        'mean_error_m': np.mean(errors),
        'std_error_m': np.std(errors),
        'max_error_m': np.max(errors),
        'min_error_m': np.min(errors),
        'rms_error_m': np.sqrt(np.mean([e**2 for e in errors])),
        'mean_bias_m': np.mean(biases),
        'std_bias_m': np.std(biases),
        'error_95_percentile_m': np.percentile(errors, 95),
        'mean_error_cm': np.mean(errors) * 100,
        'std_error_cm': np.std(errors) * 100
    }

# ==============================================
# SYSTEM CAPABILITY ASSESSMENT
# ==============================================

def assess_system_capabilities(target_accuracy_m: float = 0.134) -> Dict:
    """
    Assess overall system capabilities against requirements
    
    Args:
        target_accuracy_m: Target position accuracy requirement
        
    Returns:
        Dictionary with capability assessment
    """
    expected_distance_error = DISTANCE_MEASUREMENT_NOISE
    max_range = MAX_RANGE_THEORETICAL
    min_separation = MIN_SEPARATION_DISTANCE
    
    # Check if target is achievable
    achievable = expected_distance_error <= target_accuracy_m
    
    return {
        'target_accuracy_m': target_accuracy_m,
        'expected_distance_error_m': expected_distance_error,
        'achievable': achievable,
        'max_range_m': max_range,
        'min_separation_m': min_separation,
        'signal_frequency_mhz': SIGNAL_FREQUENCY / 1e6,
        'wavelength_m': SIGNAL_WAVELENGTH,
        'precision_clock_ghz': PRECISION_CLOCK_FREQ / 1e9,
        'margin_factor': target_accuracy_m / expected_distance_error if expected_distance_error > 0 else float('inf')
    }