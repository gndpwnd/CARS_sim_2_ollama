# GPS Denial Detection Requirements and Monitoring

## Signal Quality Indicators

Signal quality indicators monitor the fundamental characteristics of GPS signals to detect degradation, interference, or denial conditions.

### Fix Quality and Satellite Monitoring

#### Fix Quality Level
Monitors the GPS receiver's ability to calculate position solutions. The fix quality progresses from No Fix (1) through 2D positioning (2), 3D positioning (3), Differential GPS (4), RTK Float (5), to RTK Fixed (6). Degradation from higher to lower fix quality indicates potential GPS denial or interference.

**Monitoring Method**: Extract fix quality status from NMEA GGA sentences or equivalent binary messages. Implement state machine to track sequential degradation patterns (e.g., 3D → 2D → No Fix).

#### Active Satellites
Tracks the number of satellites used in the position solution. Fewer than 4 satellites makes 3D positioning impossible, while fewer than 6 indicates marginal geometry that's vulnerable to further degradation.

**Monitoring Method**: Parse NMEA GSV sentences or binary equivalent to count actively tracked satellites. Compare against environment-specific thresholds for warning and critical levels.

#### Satellite Drop Rate
Detects rapid loss of satellite visibility, which can indicate jamming or environmental interference. A sudden drop in satellite count suggests active denial rather than gradual environmental changes.

**Monitoring Method**: Calculate rate of satellite loss over sliding 5-second windows. Monitor constellation visibility messages to detect sudden degradation patterns.

### Signal Strength Analysis

#### C/N0 Degradation
Monitors Carrier-to-Noise ratio, which indicates signal quality for each tracked satellite. Uniform degradation across all satellites suggests jamming, while selective degradation may indicate environmental factors.

**Monitoring Method**: Extract C/N0 values from NMEA GSV SNR fields or RTCM carrier-to-noise measurements. Compare against environmental baselines to detect uniform signal degradation.

#### AGC Jamming Level
Monitors Automatic Gain Control levels, which indicate the receiver's attempt to compensate for noise. High AGC levels suggest elevated noise floor conditions typical of jamming attacks.

**Monitoring Method**: Monitor GPS receiver AGC voltage or digital equivalent. Elevated AGC above threshold indicates potential RF interference or intentional jamming.

## Data Integrity Monitoring

Data integrity monitoring detects corruption or interference in GPS message transmission that could indicate signal manipulation or environmental interference.

### Message Corruption Detection

#### Checksum Failure Rate
Monitors the rate of message validation failures in GPS data streams. Increased checksum failures indicate signal corruption from interference or transmission problems.

**Monitoring Method**: Monitor GPS receiver message parsing results. Count NMEA sentence checksum validation failures and RTCM message CRC errors. Calculate failure percentage over time windows.

#### Truncated Message Rate
Detects incomplete GPS message reception, which can indicate signal disruption or interference affecting data transmission quality.

**Monitoring Method**: Monitor GPS receiver communication interface for incomplete message reception. Track frequency of partial or truncated data sentences compared to expected complete messages.

## Position and Velocity Validation

Position and velocity validation ensures GPS-reported motion is consistent with physical constraints and realistic vehicle dynamics.

### Position Consistency Checks

#### Position Jump
Detects instantaneous position changes that exceed realistic vehicle movement. Large position jumps can indicate GPS calculation errors, multipath effects, or spoofing attacks.

**Monitoring Method**: Monitor consecutive GPS position outputs. Calculate position change magnitude between measurements and compare against maximum expected displacement based on vehicle kinematics and safety factors.

#### Velocity Check
Validates GPS-reported velocity against known vehicle limitations. Unrealistic velocities indicate GPS calculation errors or potential spoofing attempts.

**Monitoring Method**: Monitor GPS receiver velocity outputs from NMEA RMC/VTG sentences. Compare against physical rover speed limitations and expected operational velocities.

## RTK-Specific Indicators

RTK-specific indicators monitor high-precision GPS systems that use carrier phase measurements for centimeter-level accuracy.

### Carrier Phase Monitoring

#### Cycle Slips
Detects discontinuities in carrier phase tracking, which degrade RTK positioning accuracy. Multiple simultaneous cycle slips across satellites indicate signal interference.

**What is Carrier Phase Tracking?**: GPS satellites transmit signals on specific frequencies (L1, L2, L5). RTK systems track not just the time-of-arrival of these signals, but also the phase of the carrier wave itself. By measuring the phase difference between the satellite signal and a local reference, RTK can achieve centimeter-level accuracy. However, signal interruptions or interference can cause the receiver to lose track of the carrier phase cycles, creating "cycle slips" - sudden jumps in the phase measurement that corrupt the high-precision positioning solution.

**Monitoring Method**: Monitor RTK GPS receiver carrier phase measurements from RTCM observation messages. Track carrier phase lock time indicators and count simultaneous cycle slips across satellite constellation.

## Cross-Sensor Validation

Cross-sensor validation compares GPS measurements with other positioning sensors to detect GPS-specific errors or manipulation.

### GPS-INS Comparison

#### GPS-INS Position Diff
Compares GPS position estimates with Inertial Navigation System predictions to detect GPS-specific errors. Large persistent differences indicate GPS problems while INS remains reliable.

**Monitoring Method**: Monitor GPS receiver position outputs and INS position estimates. Calculate position differences and compare against combined uncertainty bounds using statistical thresholds.

### Time Validation

#### GPS Time Anomalies
Detects inconsistencies in GPS time-of-week messages that could indicate spoofing attacks or receiver errors. GPS time should increment consistently without backwards jumps.

**Monitoring Method**: Monitor GPS receiver time-of-week messages from NMEA and RTCM sources. Detect backwards time jumps, excessive forward jumps, or missing time increments that violate expected time progression.

---

## Status Indicators

Each requirement uses a three-level status system:

- **Green (OK)**: Values within normal operating parameters
- **Yellow (WARNING)**: Values approaching threshold limits requiring attention
- **Red (CRITICAL)**: Values exceeding safe thresholds requiring immediate action

The warning thresholds provide early indication of degrading conditions, while critical thresholds trigger alternative positioning system activation.