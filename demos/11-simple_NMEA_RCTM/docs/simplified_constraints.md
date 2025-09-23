This response draws upon the provided sources regarding GNSS message protocols and requirements for detecting GPS denial.

The query specifies that Arduino GPS modules typically use NMEA sentences for standard data, while RTK modules use RTCM for high-precision correction data and NMEA for lower-accuracy GPS data output.

> condense 85 requirements and constraints to 12

### Summary of Information Contained in NMEA and RTCM Messages

**NMEA (National Marine Electronics Association) Messages**
NMEA 0183 is a standard for interfacing marine electronic devices. The NMEA sentences primarily transmit standard position, time, velocity, and basic satellite visibility and quality data. Key information fields typically found in NMEA messages include:

*   **Position and Time:** Latitude, Longitude, UTC Time, and Date.
*   **Fix Status and Quality:** Position Fix Indicator (e.g., 0=invalid, 1=GPS SPS mode, 2=Differential GPS, 6=Dead Reckoning), Status (A=valid, V=not valid), and Mode (A=Autonomous, D=DGPS, E=DR).
*   **Velocity and Heading:** Speed Over Ground (knots/km/hr) and Course Over Ground (True/Magnetic).
*   **Satellite Geometry and Count:** Number of satellites used in the position solution, Horizontal Dilution of Precision (HDOP), Vertical Dilution of Precision (VDOP), and Position Dilution of Precision (PDOP) values (found in `GSA` sentences).
*   **Signal Strength (C/N₀):** Carrier-to-Noise Ratio (SNR) values for satellites in view (found in `GSV` sentences).
*   **Altitude:** MSL Altitude and Geoid Separation.

**RTCM (Radio Technical Commission for Maritime Services) Messages**
RTCM Standard 10403 (Version 3) is a modern, efficient standard developed primarily for Differential GNSS and Real-Time Kinematic (RTK) services, supporting centimeter-level accuracy. RTCM messages contain raw observational data, detailed integrity metrics, precise ephemeris data, and correction information for network operations, primarily targeting GPS, GLONASS, Galileo, QZSS, and BeiDou. Key information categories include:

*   **RTK Observables (MT 1001-1012, MSM messages):** Raw measurements used for positioning, including L1/L2 Pseudorange, L1/L2 Phaserange (relative to Pseudorange), and L1/L2 Lock Time Indicators. These also contain detailed C/N₀ measurements.
*   **High-Precision Corrections (SSR/Network RTK):** Precise correction parameters for satellite orbits, clocks, and code biases (e.g., Delta Radial, Delta Clock C0/C1/C2, Code Bias). Network RTK corrections provide differences in ionospheric (ICPCD) and geometric (GCPCD) carrier phase between reference stations.
*   **Integrity and Quality Metrics:** Status of RTK fix (RTK-FIX, RTK-FLOAT, DGPS), satellite integrity information (e.g., GPS IODE, GLONASS IOD, SSR User Range Accuracy (URA)), and information regarding the status of carrier phase ambiguity resolution (Ambiguity Status Flag, Non Sync Count).
*   **Receiver Health and Setup:** Information about the reference station receiver (Type, Firmware Version, Serial Number, Clock Steering Indicator) and antenna geometry (Antenna Reference Point ECEF coordinates, Antenna Height).
*   **Message Integrity:** RTCM messages include a 24-bit Cyclic Redundancy Check (CRC) for ensuring high data transfer integrity.

---

### Detailed Monitoring Requirements for GPS Denial Detection

To determine GPS denial or loss of GPS quality, the system must continuously monitor multiple requirements and constraints. The following list details criteria drawn from the source documentation that can be evaluated using information extracted from NMEA and RTCM messages or related system functions:

*   **1. Fix Quality Degradation Detection**
    *   **Information Used:** The **Fix Quality** status (NMEA GGA Position Fix Indicator, NMEA GSA Mode 2, or RTK fix status metrics like `rtkFixStatus`). This includes states such as No Fix, 2D Fix, 3D Fix, RTK-FIX, RTK-FLOAT, DGPS, and Single Point.
    *   **How Information is Used:** The system must implement a state machine to track sequential degradation patterns. If the `fixQuality` degrades in progression (e.g., **3D → 2D → No Fix**) or degrades below an acceptable precision level (e.g., RTK-FIX to RTK-FLOAT to DGPS), it flags a potential GPS denial.

*   **2. Satellite Count Monitoring (Critical Threshold)**
    *   **Information Used:** The **Tracked Satellite Count** (`trackedSatelliteCount`) reported by the receiver (available in NMEA GSV sentences or RTCM fields like DF006, DF035, DF387).
    *   **How Information is Used:** The system monitors the count against critical, environment-specific thresholds. If `trackedSatelliteCount` drops below the **SATELLITE\_COUNT\_CRITICAL\_THRESHOLD** (e.g., $< 4$ satellites), it indicates insufficient satellites for reliable positioning and triggers the Alternative Positioning System (APS).

*   **3. Satellite Count Drop Rate Detection**
    *   **Information Used:** The instantaneous **Tracked Satellite Count**.
    *   **How Information is Used:** The system calculates the rate of satellite loss over a configurable time window. If the **satellite count drops > SATELLITE\_COUNT\_DROP\_RATE\_THRESHOLD** (e.g., $> 50\%$ drop in $< 5$ seconds), this sudden constellation degradation triggers APS.

*   **4. Carrier-to-Noise Ratio (C/N₀) Degradation Detection**
    *   **Information Used:** The **Carrier-to-Noise Ratio** (`carrierToNoiseRatio` or C/N₀) values for each tracked satellite (NMEA GSV SNR, or RTCM fields DF015, DF020, DF045, DF050, DF403).
    *   **How Information is Used:** The system monitors signal strength measurements for each satellite and compares them against established environmental baselines. If **all channels C/N₀ fall significantly below a baseline**, it detects uniform signal degradation, which often flags jamming.

*   **5. Automatic Gain Control (AGC) Monitoring**
    *   **Information Used:** The **Automatic Gain Control** (`automaticGainControl` or AGC) voltage or digital equivalent, if provided by the receiver.
    *   **How Information is Used:** The AGC metric measures the receiver's attempt to compensate for the noise floor. Monitoring this value detects elevated noise floor conditions. If **AGC > AGC\_JAMMING\_THRESHOLD**, it flags jamming or potential RF interference.

*   **6. Checksum Failure Rate Monitoring**
    *   **Information Used:** The **Checksum Failure Rate** (`checksumFailureRate`) derived from monitoring GPS receiver message parsing results. This applies to NMEA sentence checksum validation or RTCM message CRC errors.
    *   **How Information is Used:** The system counts checksum validation failures over time. If the calculated **checksumFailureRate > CHECKSUM\_FAILURE\_RATE\_THRESHOLD** (e.g., $> 5\%$), it signals interference affecting data integrity.

*   **7. Truncated Sentence Rate Monitoring**
    *   **Information Used:** The **Truncated Sentence Rate** (`truncatedSentenceRate`) derived from monitoring the communication interface for incomplete message reception.
    *   **How Information is Used:** The system tracks the frequency of partial or truncated data sentences. If the calculated **truncatedSentenceRate > TRUNCATED\_SENTENCE\_RATE\_THRESHOLD** (e.g., $> 2\%$), it flags signal disruption or interference.

*   **8. Position Jump Magnitude Detection**
    *   **Information Used:** Consecutive **GPS Position Outputs** (`gpsPosition`) (extracted from NMEA GGA/GLL or RTCM equivalent messages).
    *   **How Information is Used:** The system calculates the positional change between consecutive measurements (`positionJumpMagnitude`) and compares it against kinematic constraints for the robot. If `positionJumpMagnitude` exceeds the calculated maximum expected displacement times a safety factor, it flags an anomaly (e.g., a static jump $> 10$ meters triggers APS).

*   **9. Rover Velocity Limit Monitoring**
    *   **Information Used:** The **Rover Velocity** (`roverVelocity`) derived from GPS (NMEA RMC, VTG, or RTCM velocity equivalent outputs).
    *   **How Information is Used:** GPS velocity is monitored and compared against the physical limitations and expected operational speeds of the rover. If `roverVelocity` exceeds the **MAX\_ROVER\_SPEED\_EXPECTED** (e.g., $> 15 \ \mathrm{m/s}$), it indicates an unrealistic calculation or anomaly.

*   **10. Carrier Phase Cycle Slip Detection**
    *   **Information Used:** The **Carrier Phase Lock Time Indicator** (found in RTCM observation messages: DF013/DF019 for legacy messages or DF402/DF407 for MSM) or the simultaneous **Cycle Slip Count** (`carrierPhaseCycleSlipCount`).
    *   **How Information is Used:** The system monitors carrier phase measurements to detect discontinuities (cycle slips). If **cycle slips exceed a threshold simultaneously on multiple satellites**, it flags signal interference, crucial for maintaining RTK integrity.

*   **11. GPS-INS Position Consistency Check (Cross-Sensor Validation)**
    *   **Information Used:** The **GPS Position** (`gpsPosition`) and the **Inertial Navigation System Position** (`insPosition`) estimates, along with the combined position uncertainty (`combinedUncertainty`).
    *   **How Information is Used:** GPS position updates are compared against inertial navigation predictions. If the absolute difference **|gpsPosition - insPosition| > (statisticalThreshold × combinedUncertainty)**, it flags a major inconsistency, potentially triggering APS activation if the difference exceeds critical limits (e.g., $ > 5\sigma$ consistently).

*   **12. Time-of-Week (TOW) Anomaly Detection**
    *   **Information Used:** The **GPS Time of Week** (TOW) transmitted in various messages (NMEA GGA/RMC/ZDA, or RTCM DF004/DF065/DF240).
    *   **How Information is Used:** The system tracks the TOW chronologically. If **backwards time jumps, excessive forward jumps, or missing time increments** are detected (e.g., a jump $> 2 \ \mathrm{seconds}$), it flags GPS time inconsistencies, potentially indicating a spoofing attack or receiver error.