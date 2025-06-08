"""
System constraints and constants for GPS localization simulation.
Updated to reflect Time-of-Flight distance measurement physics, hardware limitations,
and real-world radio propagation constraints.
"""

import math

# ==============================================
# PHYSICS CONSTANTS
# ==============================================
SPEED_OF_LIGHT = 2.997e8  # m/s (in air, accounting for refractive index ≈ 1.0003)
REFRACTIVE_INDEX_AIR = 1.0003

# ==============================================
# SIMULATION DIMENSIONS
# ==============================================
DIMENSION_3D = False  # Switch between 2D (False) and 3D (True) rendering and calculations

# ==============================================
# ToF HARDWARE SPECIFICATIONS
# ==============================================

# Clock Specifications
STANDARD_CLOCK_FREQ = 100e6  # Hz - Standard system clock
PRECISION_CLOCK_FREQ = 1.4e9  # Hz - Required for 10 cm³ positional accuracy
CLOCK_RESOLUTION_PRECISION = 1.0 / PRECISION_CLOCK_FREQ  # ~714 ps
CLOCK_RESOLUTION_STANDARD = 1.0 / STANDARD_CLOCK_FREQ   # 10 ns

# Signal Specifications
SIGNAL_FREQUENCY = 70e6  # Hz - 70 MHz (recommended for precision requirements)
SIGNAL_WAVELENGTH = SPEED_OF_LIGHT / SIGNAL_FREQUENCY  # ~4.28 m
TRANSMIT_POWER = 1.0  # Watts
RECEIVER_SENSITIVITY = -100  # dBm

# Thermal Management
THERMAL_STABILIZATION_TIME = 0.2  # seconds
TEMPERATURE_STABILITY = 0.1  # ±°C
TEMPERATURE_COEFFICIENT = 1e-6  # per °C for crystal oscillator
PRECISION_CLOCK_DUTY_CYCLE = 0.218  # 21.8% active time per measurement cycle

# ==============================================
# DISTANCE MEASUREMENT CONSTRAINTS
# ==============================================

# Physics-Based Range Constraints
MIN_SEPARATION_DISTANCE = SIGNAL_WAVELENGTH  # 4.28 m - Far-field constraint
MAX_RANGE_THEORETICAL = 1070.0  # meters - Based on link budget analysis (1W transmitter)

# Practical Communication Ranges (reduced for safety margins)
COMM_RANGE = min(25.0, MAX_RANGE_THEORETICAL * 0.7)  # Conservative range for drones/rover
MASTER_COMM_RANGE = min(30.0, MAX_RANGE_THEORETICAL * 0.8)  # Master drone range

# Distance Measurement Accuracy (Physics-Based Error Budget)
# Based on RSS combination of error sources:
CLOCK_ERROR_CM = 6.2  # cm - 1.4 GHz precision clock quantization
THERMAL_ERROR_CM = 1.5  # cm - ±0.1°C thermal stability
ACTIVATION_JITTER_CM = 1.5  # cm - 100 ps activation jitter
SIGNAL_NOISE_ERROR_CM = 7.5  # cm - 20 dB SNR assumption
MULTIPATH_ERROR_CM = 43.0  # cm - 10% of wavelength in environment
PROCESSING_ERROR_CM = 30.0  # cm - ±1 ns processing delay variation

# Total Distance Measurement Error (Root Sum Square)
DISTANCE_MEASUREMENT_NOISE = math.sqrt(
    (CLOCK_ERROR_CM/100)**2 + 
    (THERMAL_ERROR_CM/100)**2 + 
    (ACTIVATION_JITTER_CM/100)**2 + 
    (SIGNAL_NOISE_ERROR_CM/100)**2 + 
    (MULTIPATH_ERROR_CM/100)**2 + 
    (PROCESSING_ERROR_CM/100)**2
) / 3  # Convert to standard deviation (~53.6 cm / 3 ≈ 0.18 m)

MAX_DISTANCE_ERROR = DISTANCE_MEASUREMENT_NOISE * 3  # 3-sigma limit
MIN_ANCHOR_SEPARATION = max(MIN_SEPARATION_DISTANCE, 5.0)  # Ensure geometric constraints

# ==============================================
# GPS AND JAMMING CONSTRAINTS
# ==============================================
GPS_ACCURACY = 1.0  # GPS accuracy in meters when available
JAMMING_DETECTION_THRESHOLD = 2.0  # Distance threshold for detecting jamming
NUM_DRONE_POS_ONBOARD = 10  # Number of previous positions each drone stores

# ==============================================
# MULTILATERATION CONSTRAINTS
# ==============================================
MIN_ANCHORS_2D = 3  # Minimum number of anchor points for 2D multilateration
MIN_ANCHORS_3D = 4  # Minimum number of anchor points for 3D multilateration

# Geometric Dilution of Precision
GEOMETRIC_DILUTION_THRESHOLD = 1.22  # Typical GDOP for well-conditioned geometry
MULTILATERATION_TOLERANCE = DISTANCE_MEASUREMENT_NOISE  # Match measurement precision

# Position Accuracy Targets
TARGET_POSITION_ACCURACY_M = 0.134  # meters - For 10 cm³ volume accuracy
MAX_POSITION_ERROR = TARGET_POSITION_ACCURACY_M * 3  # 3-sigma confidence

# Geometric Constraints
MIN_TRIANGLE_AREA = 15.0  # m² - Increased to account for wavelength constraints
MAX_BASELINE_RATIO = 5.0  # Reduced for better conditioning
CONVERGENCE_THRESHOLD = DISTANCE_MEASUREMENT_NOISE / 10  # Sub-measurement precision

# ==============================================
# TIMING CONSTRAINTS (Dual Architecture)
# ==============================================
MEASUREMENT_CYCLE_TIMING = {
    'stabilization_ms': 200,  # Precision clock thermal stabilization
    'measurement_per_agent_ms': 2,  # ToF measurement duration
    'transmission_per_agent_ms': 10,  # Data transmission via System A
    'computation_ms': 5,  # Multilateration calculation
    'total_budget_ms': 253  # Total cycle time for 4 agents
}

# Synchronization Window (Critical for Position Accuracy)
MAX_MEASUREMENT_WINDOW_MS = 8.2  # ms - Based on rover velocity and accuracy requirements
MEASUREMENT_SYNC_TOLERANCE = MAX_MEASUREMENT_WINDOW_MS / 1000  # Convert to seconds

# Update Frequencies
UPDATE_FREQUENCY = 4  # Hz - Position updates (reduced from 10 Hz for thermal management)
TELEMETRY_FREQUENCY = 2  # Hz - Status telemetry (reduced to match measurement cycle)

# ==============================================
# SIMULATION TIMING
# ==============================================
SIMULATION_DT = 0.1  # Simulation time step (seconds)

# Measurement timing aligned with hardware constraints
PRECISION_MEASUREMENT_INTERVAL = 1.0 / UPDATE_FREQUENCY  # 250 ms between measurements
THERMAL_STABILIZATION_REQUIRED = True  # Flag for precision clock management

# ==============================================
# VEHICLE MOVEMENT CONSTRAINTS
# ==============================================
DRONE_SPEED = 2.0  # Drone movement speed (m/s)
ROVER_SPEED = 1.5  # Rover movement speed (m/s)
MIN_ALTITUDE = 10.0  # Minimum drone altitude (meters) - used in 3D mode
MAX_ALTITUDE = 50.0  # Maximum drone altitude (meters) - used in 3D mode

# Movement constraints for measurement accuracy
MAX_ROVER_VELOCITY_FOR_SYNC = TARGET_POSITION_ACCURACY_M / (MAX_MEASUREMENT_WINDOW_MS / 1000)  # ~16.4 m/s
if ROVER_SPEED > MAX_ROVER_VELOCITY_FOR_SYNC:
    print(f"Warning: Rover speed ({ROVER_SPEED} m/s) may exceed sync window requirements")

# ==============================================
# RECOVERY AND SAFETY CONSTRAINTS
# ==============================================
SAFE_DISTANCE_FROM_JAMMING = max(3.0, COMM_RANGE * 0.2)  # Safety margin from GPS-denied areas
MAX_RECOVERY_ATTEMPTS = 5  # Maximum attempts to recover from jamming
POSITION_HOLD_TIMEOUT = 30.0  # Maximum time rover will wait for position (seconds)

# ==============================================
# COMMUNICATION CONSTRAINTS
# ==============================================

# Dual Communication Architecture
SYSTEM_A_BANDWIDTH_KBPS = 2.2  # Command & control bandwidth requirement
SYSTEM_B_BANDWIDTH_BPS = 100   # Precision timing (minimal data)

# Link Budget Parameters
FREE_SPACE_PATH_LOSS_DB = lambda distance_km, freq_mhz: (
    20 * math.log10(distance_km) + 20 * math.log10(freq_mhz) + 32.44
)

def calculate_communication_quality(distance_m):
    """Calculate communication quality based on distance and link budget"""
    if distance_m > MAX_RANGE_THEORETICAL or distance_m < MIN_SEPARATION_DISTANCE:
        return 0.0
    
    freq_mhz = SIGNAL_FREQUENCY / 1e6
    distance_km = distance_m / 1000
    
    # Free Space Path Loss
    fspl_db = FREE_SPACE_PATH_LOSS_DB(distance_km, freq_mhz)
    tx_power_dbm = 10 * math.log10(TRANSMIT_POWER * 1000)  # Convert W to dBm
    received_power = tx_power_dbm - fspl_db
    
    # Quality based on margin above sensitivity
    margin = received_power - RECEIVER_SENSITIVITY
    max_margin = tx_power_dbm - RECEIVER_SENSITIVITY
    
    return max(0.0, min(1.0, margin / max_margin))

# ==============================================
# DATABASE AND LOGGING
# ==============================================
DB_BATCH_SIZE = 10  # Number of telemetry records to batch before sending
MAX_RETRY_ATTEMPTS = 3  # Maximum database retry attempts
TELEMETRY_BUFFER_SIZE = 100  # Maximum telemetry records to buffer

# ==============================================
# POWER MANAGEMENT CONSTRAINTS
# ==============================================
POWER_BUDGET = {
    'standard_clocks_w': 1.0,  # Continuous operation
    'precision_clocks_avg_w': 1.09,  # 5W × 21.8% duty cycle
    'radio_systems_w': 2.0,
    'total_per_agent_w': 4.09,  # Significant improvement over continuous precision
    'precision_continuous_w': 8.0  # For comparison
}

# ==============================================
# CALIBRATION CONSTRAINTS
# ==============================================
CALIBRATION_DISTANCE_M = 10.0  # Known reference distance for system calibration
CALIBRATION_MEASUREMENTS = 10  # Number of measurements for calibration
SYSTEM_OFFSET_TOLERANCE_M = 0.01  # Maximum acceptable calibration offset

# Processing delays for calibration compensation (typical values)
PROCESSING_DELAYS_NS = {
    'signal_detection': 2.0,    # 2ns
    'ack_generation': 1.0,      # 1ns  
    'tx_preparation': 1.5,      # 1.5ns
    'rx_processing': 1.0,       # 1ns
    'ack_transmission': 0.5     # 0.5ns
}

TOTAL_PROCESSING_DELAY_NS = sum(PROCESSING_DELAYS_NS.values())  # 6.0 ns total

# ==============================================
# VISUAL DISPLAY CONSTANTS
# ==============================================
DRONE_MARKER_SIZE = 8
ROVER_MARKER_SIZE = 12
MASTER_DRONE_MARKER_SIZE = 10
ERROR_CIRCLE_ALPHA = 0.3
TRAJECTORY_ALPHA = 0.4

# Error visualization scaling
ERROR_CIRCLE_SCALE = DISTANCE_MEASUREMENT_NOISE  # Scale error circles to measurement precision
POSITION_UNCERTAINTY_SCALE = TARGET_POSITION_ACCURACY_M

# Colors for different entities
DRONE_COLOR = '#2196F3'  # Blue
MASTER_DRONE_COLOR = '#FF9800'  # Orange
ROVER_COLOR = '#4CAF50'  # Green
JAMMED_COLOR = '#F44336'  # Red
ESTIMATED_POSITION_COLOR = '#FFEB3B'  # Yellow
PRECISION_TIMING_COLOR = '#9C27B0'  # Purple - For precision measurement indicators

# ==============================================
# VALIDATION AND WARNINGS
# ==============================================

def validate_constraints():
    """Validate constraint consistency and physics requirements"""
    warnings = []
    
    # Check if minimum separation meets wavelength requirement
    if MIN_ANCHOR_SEPARATION < SIGNAL_WAVELENGTH:
        warnings.append(f"Minimum anchor separation ({MIN_ANCHOR_SEPARATION}m) < wavelength ({SIGNAL_WAVELENGTH:.2f}m)")
    
    # Check if communication range is realistic for link budget
    max_theoretical_range = MAX_RANGE_THEORETICAL
    if COMM_RANGE > max_theoretical_range:
        warnings.append(f"Communication range ({COMM_RANGE}m) exceeds link budget limit ({max_theoretical_range:.0f}m)")
    
    # Check if position accuracy target is achievable with current error budget
    expected_position_error = DISTANCE_MEASUREMENT_NOISE * GEOMETRIC_DILUTION_THRESHOLD
    if expected_position_error > TARGET_POSITION_ACCURACY_M:
        warnings.append(f"Expected position error ({expected_position_error:.3f}m) > target ({TARGET_POSITION_ACCURACY_M}m)")
    
    # Check timing budget consistency
    total_cycle_time = (MEASUREMENT_CYCLE_TIMING['stabilization_ms'] + 
                       4 * MEASUREMENT_CYCLE_TIMING['measurement_per_agent_ms'] +
                       4 * MEASUREMENT_CYCLE_TIMING['transmission_per_agent_ms'] +
                       MEASUREMENT_CYCLE_TIMING['computation_ms'])
    
    if total_cycle_time > 1000 / UPDATE_FREQUENCY:
        warnings.append(f"Measurement cycle time ({total_cycle_time}ms) > update interval ({1000/UPDATE_FREQUENCY}ms)")
    
    return warnings

# Run validation on import
_validation_warnings = validate_constraints()
if _validation_warnings:
    print("Constraint validation warnings:")
    for warning in _validation_warnings:
        print(f"  - {warning}")

# ==============================================
# PHYSICS-BASED HELPER FUNCTIONS
# ==============================================

def time_to_distance(time_seconds, round_trip=True):
    """Convert time measurement to distance"""
    divisor = 2 if round_trip else 1
    return (SPEED_OF_LIGHT * time_seconds) / divisor

def distance_to_time(distance_meters, round_trip=True):
    """Convert distance to time measurement"""
    multiplier = 2 if round_trip else 1
    return (distance_meters * multiplier) / SPEED_OF_LIGHT

def required_clock_frequency(target_distance_accuracy):
    """Calculate required clock frequency for target distance accuracy"""
    required_time_resolution = distance_to_time(target_distance_accuracy, round_trip=True)
    return 1.0 / required_time_resolution

def calculate_position_accuracy(distance_accuracy, num_agents=4, gdop=GEOMETRIC_DILUTION_THRESHOLD):
    """Calculate expected position accuracy from distance measurement accuracy"""
    return gdop * distance_accuracy / math.sqrt(num_agents)

# ==============================================
# EXPORT SUMMARY
# ==============================================
CONSTRAINT_SUMMARY = {
    'signal_frequency_mhz': SIGNAL_FREQUENCY / 1e6,
    'wavelength_m': SIGNAL_WAVELENGTH,
    'min_separation_m': MIN_SEPARATION_DISTANCE,
    'max_range_m': MAX_RANGE_THEORETICAL,
    'distance_accuracy_cm': DISTANCE_MEASUREMENT_NOISE * 100,
    'position_accuracy_cm': TARGET_POSITION_ACCURACY_M * 100,
    'precision_clock_ghz': PRECISION_CLOCK_FREQ / 1e9,
    'measurement_cycle_ms': MEASUREMENT_CYCLE_TIMING['total_budget_ms'],
    'power_reduction_percent': (1 - POWER_BUDGET['total_per_agent_w'] / POWER_BUDGET['precision_continuous_w']) * 100
}