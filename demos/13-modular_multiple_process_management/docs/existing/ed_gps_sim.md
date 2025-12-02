# GPS as Radio Communication Theory

## Overview

Applying radio message board architecture to GPS constellation for realistic attack simulation (spoofing, jamming, signal degradation).

---

## Core Concept: GPS as Broadcast Radio

### GPS Communication Model

**Theory:** GPS satellites are **broadcast transmitters** that write NMEA messages to the radio message board.

```
ITERATION N:
  
  GPS PHASE (happens first):
    For each visible satellite:
      - Create NMEA message (GGA, RMC, GSV)
      - Post to message board as "gps_broadcast"
      - All drones can read
  
  RADIO PHASE (happens second):
    - Drones write/read inter-drone messages
    - Controller writes command messages
    - Attackers inject spoofing/jamming messages
  
  PROCESSING PHASE:
    - Each drone reads ALL messages (GPS + radio)
    - Processes GPS separately from radio commands
```

**Key Insight:** GPS messages are just special radio messages with `msg_type = "gps_nmea"`.

---

## GPS Message Structure

### GPSRadioMessage (extends RadioMessage)

**Structure:**
```
GPSRadioMessage:
  - msg_id: UUID
  - sender_id: "sat_XX" (e.g., "sat_05" for PRN 5)
  - receiver_id: "broadcast" (all drones)
  - timestamp: Current iteration
  - msg_type: "gps_nmea"
  - payload: {
      "nmea_sentence": "$GPGGA,123519,4807.038,N,...",
      "satellite_prn": 5,
      "elevation": 45.2,
      "azimuth": 180.0,
      "snr": 42.5,
      "constellation": "GPS"  # or GLONASS, Galileo
    }
  - signature: Satellite signature (can be spoofed if attacker has key)
  - frequency: 1575.42 MHz (L1) or 1227.60 MHz (L2)
  - power: Signal strength (used for jamming calculation)
```

**NMEA Sentence Types:**
1. **GGA:** Position fix, satellites, HDOP
2. **RMC:** Navigation data, speed, heading
3. **GSV:** Satellite visibility (PRN, elevation, azimuth, SNR)

---

## GPS Constellation as Transmitter Array

### Satellite Configuration

**From constellation_config.json:**
```
GPS: 32 satellites
GLONASS: 24 satellites
Galileo: 30 satellites

Each satellite:
  - PRN (ID): 1-32 for GPS
  - Orbital position: Calculated from ephemeris
  - Visibility: Based on elevation mask (>10°)
  - Signal strength: Base CNR 45 dB-Hz
```

**Visibility Calculation Theory:**
```
For each satellite:
  1. Calculate position from orbital parameters
  2. Compute elevation angle to drone
  3. IF elevation > elevation_mask:
       Satellite is visible
       Generate NMEA message
       Post to message board
     ELSE:
       Satellite below horizon
       Do not post message
```

**Message Generation Per Iteration:**
```
For each drone:
  visible_sats = calculate_visible_satellites(drone_position)
  
  For each visible_sat:
    GGA = generate_gga(drone_position, visible_sats)
    RMC = generate_rmc(drone_position, drone_velocity)
    GSV = generate_gsv(visible_sats)
    
    Post GGA, RMC, GSV to message_board
```

---

## GPS Signal Degradation Model

### Jamming Effects on GPS

**Theory:** Jamming reduces number of visible satellites and signal strength.

**Degradation Levels (from sat_constellation.py):**

**Level 0: No Jamming (0-30%)**
```
Satellites: 8-12 visible
Fix Quality: 6 (RTK fixed)
Signal Strength: 42-48 dB-Hz
HDOP: 0.8-1.2 (excellent)
```

**Level 1: Light Jamming (30-50%)**
```
Satellites: 6-8 visible
Fix Quality: 4 (DGPS)
Signal Strength: 35-42 dB-Hz
HDOP: 1.2-2.5 (moderate)
```

**Level 2: Moderate Jamming (50-70%)**
```
Satellites: 3-5 visible
Fix Quality: 1 (GPS fix only)
Signal Strength: 25-35 dB-Hz
HDOP: 2.5-5.0 (poor)
```

**Level 3: Heavy Jamming (70-100%)**
```
Satellites: 0 visible
Fix Quality: 0 (no fix)
Signal Strength: 0 dB-Hz
HDOP: 99.9 (unusable)
```

### Implementation Theory

**Message Board Modification:**
```
For each satellite message:
  jamming_level = calculate_jamming(drone_position, jamming_zones)
  
  IF jamming_level > 70%:
    DO NOT POST MESSAGE (signal too weak)
  
  ELSE IF jamming_level > 30%:
    POST MESSAGE with degraded SNR:
      msg.payload["snr"] = base_snr * (1 - jamming_level/100)
      msg.power = base_power * (1 - jamming_level/100)
  
  ELSE:
    POST MESSAGE with normal signal strength
```

**Drone Processing:**
```
drone reads GPS messages from board:
  
  count = number of GPS messages received
  avg_snr = average of all msg.payload["snr"]
  
  IF count < 4:
    fix_quality = 0 (no fix)
  ELIF count < 6:
    fix_quality = 1 (GPS)
  ELIF avg_snr < 35:
    fix_quality = 4 (DGPS, degraded)
  ELSE:
    fix_quality = 6 (RTK)
```

---

## GPS Spoofing Attack

### Attack Mechanism

**Theory:** Inject fake GPS messages with false position data.

**Spoofing Attack Flow:**
```
ATTACKER:
  1. Calculate fake position for target drone
  2. Generate valid-looking NMEA sentences with fake lat/lon
  3. Create GPSRadioMessage with:
     - sender_id = "sat_XX" (impersonate real satellite)
     - payload = fake NMEA
     - signature = forged (if attacker has satellite key)
  4. Post to message board
  5. Optionally jam real satellites to make fake signal dominant

TARGET DRONE:
  1. Reads both real and fake GPS messages
  2. IF fake messages outnumber real:
       Computes position from fake data
       Moves incorrectly
  3. IF signature verification enabled:
       Rejects fake (if attacker lacks key)
       Accepts real messages only
```

### Advanced Spoofing (Meaconing)

**Theory:** Record real signals, replay with time offset.

```
ATTACKER:
  - Records legitimate GPS messages from iteration N
  - Replays at iteration N+10 with same NMEA sentences
  - Drone thinks it's at old position
  - Causes drift accumulation

DEFENSE:
  - Check GPS time vs system time
  - Reject messages with old timestamps
  - Cross-reference with INS (inertial navigation)
```

---

## GPS Jamming Zones

### Zone-Based Jamming Model

**Theory:** Jamming intensity decreases with distance from jammer.

**Jamming Zone Object:**
```
JammingZone:
  - center: (x, y) position of jammer
  - radius: Maximum affected distance
  - intensity: 0-100% (at center)
  - frequency: Target frequency (L1, L2, or wideband)
  - active: Boolean (can pause/resume)
```

**Distance-Based Calculation:**
```
For drone at position (x, y):
  For each jamming_zone:
    distance = sqrt((x - zone.center[0])² + (y - zone.center[1])²)
    
    IF distance > zone.radius:
      jamming_effect = 0%
    
    ELSE:
      # Linear falloff from center
      jamming_effect = zone.intensity * (1 - distance / zone.radius)
  
  total_jamming = sum of all jamming_effects
  total_jamming = min(100%, total_jamming)  # Cap at 100%
```

**Application to Satellite Messages:**
```
For each satellite attempting to transmit to drone:
  jamming_level = calculate_jamming(drone_position)
  
  IF jamming_level > random_threshold:
    BLOCK MESSAGE (satellite not posted to board)
  
  ELSE:
    DEGRADE SIGNAL:
      msg.payload["snr"] *= (1 - jamming_level/100)
```

---

## Multi-Constellation Support

### Theory: Diversified GPS Sources

**Benefit:** Harder to jam all constellations simultaneously.

**Implementation:**
```
Active Constellations:
  - GPS (32 sats, L1 frequency 1575.42 MHz)
  - GLONASS (24 sats, L1 frequency 1602 MHz)
  - Galileo (30 sats, E1 frequency 1575.42 MHz)

Jamming Resistance:
  - Wideband jammer: Affects all frequencies equally
  - Narrowband jammer: Targets specific frequency
    → GPS and Galileo jammed (same L1 freq)
    → GLONASS still available (different freq)

Drone Processing:
  - Receives messages from all constellations
  - Combines for position fix
  - IF GPS jammed but GLONASS clear:
      Still has 5-10 satellites for fix
      Fix quality degrades slightly but remains functional
```

**Message Board Impact:**
```
ITERATION N:
  GPS satellites post: 8 messages
  GLONASS satellites post: 6 messages
  Galileo satellites post: 7 messages
  
  Total GPS messages on board: 21

  Jamming attack targets L1 (GPS + Galileo):
    GPS messages: 8 → 2 (75% blocked)
    Galileo messages: 7 → 2 (75% blocked)
    GLONASS messages: 6 → 6 (unaffected, different freq)
  
  Drone still has 10 messages total → Fix maintained
```

---

## RTK Base Station as Radio Source

### Differential Corrections via Radio

**Theory:** RTK base station broadcasts correction data to improve accuracy.

**Base Station Message:**
```
RTKCorrectionMessage:
  - sender_id: "base_station_1001"
  - receiver_id: "broadcast"
  - msg_type: "rtk_correction"
  - payload: {
      "rtcm_messages": [1005, 1077, 1087, 1097, 1230],
      "base_position": {"lat": 40.7128, "lon": -74.0060},
      "age_of_corrections": 2.5  # seconds
    }
  - frequency: 915 MHz (ISM band, separate from GPS)
  - signature: Base station signature
```

**Drone Processing:**
```
IF drone receives RTK corrections:
  IF age_of_corrections < 30 seconds:
    Apply corrections to GPS position
    Improve fix_quality to 6 (RTK fixed)
    Reduce position error to 2-5 cm
  ELSE:
    Ignore stale corrections
    Maintain GPS-only fix
```

**Attack Surface:**
```
ATTACKER can:
  1. Jam RTK frequency (915 MHz) → Drones lose RTK, fall back to GPS
  2. Spoof RTK corrections → Inject false correction data → Position offset
  3. Replay old corrections → Stale data → Position drift
```

---

## GPS Requirements Integration

### Requirements Tracker Monitoring

**From requirements_config.json:**

**Thresholds:**
```
Fix Quality:
  - Critical: < 1 (no fix)
  - Warning: < 2 (GPS only, not DGPS)

Satellite Count:
  - Critical: < 4 (insufficient for fix)
  - Warning: < 6 (marginal)

Signal Strength:
  - Critical: < 30 dB-Hz (too weak)
  - Warning: < 35 dB-Hz (degraded)

Jamming Level:
  - Critical: > 70% (severe interference)
  - Warning: > 50% (moderate interference)
```

**Detection Logic:**
```
EACH ITERATION:
  For each drone:
    gps_messages = [msg for msg in board if msg.msg_type == "gps_nmea"]
    
    satellite_count = len(set(msg.payload["satellite_prn"] for msg in gps_messages))
    avg_snr = mean(msg.payload["snr"] for msg in gps_messages)
    jamming_level = calculate_jamming(drone.position)
    
    IF satellite_count < 4 OR avg_snr < 30:
      fix_quality = 0
      LOG ERROR to PostgreSQL
    
    Update requirements_tracker:
      - Fix Quality Level
      - Active Satellites
      - Signal Strength
      - Jamming Level
    
    IF any threshold violated:
      Notification Dashboard shows CRITICAL/WARNING
```

---

## Attack Scenarios

### Scenario 1: Simple GPS Spoofing

**Setup:**
```
Normal operation:
  - 10 real satellites visible
  - Fix quality: 6 (RTK)
  - Position: Accurate

Attacker activates:
  - Generates 12 fake satellite messages
  - Fake position offset: +50 meters east
  - Posts to message board
```

**Outcome:**
```
Drone reads 22 total messages (10 real + 12 fake)
Fake messages dominate
Drone computes position from fake data
Moves 50 meters east of true position
Formation breaks
```

**Defense:**
```
Enable signature verification:
  - Real satellites have valid signatures
  - Fake messages fail verification
  - Drone rejects all 12 fake messages
  - Accepts only 10 real messages
  - Position remains accurate
```

### Scenario 2: Selective Jamming

**Setup:**
```
Attacker places jammer at (0, 0) with radius 5
Intensity: 90%
Frequency: L1 (GPS + Galileo)
GLONASS unaffected
```

**Outcome:**
```
Drones inside radius 5:
  - GPS messages: 10 → 1 (90% blocked)
  - GLONASS messages: 6 → 6 (unaffected)
  - Total satellites: 7
  - Fix quality: 4 (DGPS, degraded but functional)

Drones outside radius 5:
  - GPS messages: 10 → 10 (normal)
  - GLONASS messages: 6 → 6 (normal)
  - Total satellites: 16
  - Fix quality: 6 (RTK, normal)
```

**Detection:**
```
Requirements tracker for affected drones:
  - Signal Strength: 28 dB-Hz (WARNING)
  - Jamming Level: 90% (CRITICAL)
  - Dashboard shows red tile
  - PostgreSQL logs error
```

### Scenario 3: Meaconing (Replay Attack)

**Setup:**
```
Attacker records GPS messages from iteration 100
At iteration 200, replays those messages
Messages contain position from iteration 100
```

**Outcome:**
```
Drone at iteration 200:
  - Should be at position (10, 10)
  - Receives replayed GPS showing position (5, 5)
  - Thinks it teleported backwards
  - Attempts to move forward again
  - Oscillates between real and fake position
```

**Defense:**
```
Check GPS timestamp in NMEA:
  GGA sentence contains time: "123519" (12:35:19 UTC)
  
  IF time_difference(gps_time, system_time) > 5 seconds:
    REJECT message (too old or desync)
  
  Attacker's replayed messages have old timestamps
  Drone rejects them
```

---

## Integration with Radio Message Board

### Unified Message Processing

**Theory:** GPS and radio messages coexist on same board, processed differently.

**Message Board Contents (Example Iteration):**
```
[
  GPSRadioMessage(sender="sat_05", type="gps_nmea", payload=GGA),
  GPSRadioMessage(sender="sat_12", type="gps_nmea", payload=GGA),
  ... (10 GPS messages total)
  
  RadioMessage(sender="controller", type="command", payload=move_to),
  RadioMessage(sender="drone_3", type="telemetry", payload=position),
  RadioMessage(sender="attacker", type="gps_nmea", payload=FAKE_GGA),  # Spoof attempt
]
```

**Drone Processing Loop:**
```
gps_messages = []
radio_messages = []

for msg in message_board:
  IF msg.msg_type == "gps_nmea":
    IF verify_signature(msg):
      gps_messages.append(msg)
    ELSE:
      LOG ERROR: "Spoofed GPS message detected"
  
  ELSE:
    IF verify_signature(msg) AND relevant_to_me(msg):
      radio_messages.append(msg)

# Process GPS separately
position = calculate_position(gps_messages)
fix_quality = determine_fix_quality(gps_messages)

# Process radio commands
for msg in radio_messages:
  handle_command(msg)
```

---

## Logging Strategy

### GPS-Specific Logging

**Qdrant (High Volume):**
```
For each GPS message:
  qdrant.add_nmea_message(
    agent_id=receiver_drone,
    nmea_sentence=msg.payload["nmea_sentence"],
    metadata={
      "satellite_prn": msg.payload["satellite_prn"],
      "snr": msg.payload["snr"],
      "elevation": msg.payload["elevation"],
      "azimuth": msg.payload["azimuth"],
      "jamming_level": calculate_jamming(receiver_position),
      "iteration": current_iteration,
      "spoofed": not verify_signature(msg)
    }
  )
```

**PostgreSQL (Events Only):**
```
IF fix_quality drops below threshold:
  postgresql.add_log(
    text=f"{drone_id} lost GPS fix (satellites: {count}, jamming: {level}%)",
    metadata={
      "source": drone_id,
      "message_type": "error",
      "fix_quality": fix_quality,
      "satellite_count": count,
      "jamming_level": level
    }
  )

IF spoofed message detected:
  postgresql.add_log(
    text=f"{drone_id} detected GPS spoofing attempt",
    metadata={
      "source": drone_id,
      "message_type": "error",
      "attack_type": "gps_spoofing",
      "spoofed_satellite": msg.sender_id
    }
  )
```

---

## GUI Visualization

### GPS-Specific Visual Elements

**Satellite Visibility (Optional):**
```
For each visible satellite:
  Draw small circle at edge of map
  Label with PRN number
  Color by SNR:
    - Green: SNR > 40 (strong)
    - Yellow: SNR 30-40 (moderate)
    - Red: SNR < 30 (weak)
```

**Jamming Zone Overlay:**
```
Already implemented:
  - Red circles for jamming zones
  - Radius shown
  - Agents turn red inside zone

Add:
  - Gradient fill (darker red at center)
  - Label with intensity %
```

**GPS Status Indicator Per Drone:**
```
Next to each agent:
  - Show satellite count as small number
  - Show fix quality as icon:
    ✓ = RTK (6)
    ± = DGPS (4)
    ? = GPS (1)
    ✗ = No Fix (0)
```

---

## Performance Considerations

### Message Volume

**GPS Messages Per Iteration:**
```
Per drone:
  - Visible satellites: ~8-12
  - NMEA types: GGA (1), RMC (1), GSV (3-4)
  - Total GPS messages: ~15 per drone

For 10 drones:
  - GPS messages: 150
  - Radio messages: 10
  - Total: 160 messages on board
```

**Processing Time:**
```
Each drone:
  - Reads 160 messages
  - Filters to ~15 GPS messages relevant to it
  - Processes in ~2ms (signature verification + parsing)

Total for 10 drones: ~20ms
Leaves 980ms for other operations (movement, rendering)
```

**Optimization:**
```
Current: Each drone gets unique GPS messages
Better: All drones share same GPS messages (broadcast nature)

Implementation:
  - Satellites post GPS once to board
  - All drones read same messages
  - Reduces board size from 150 to 15 messages
```

---

## Testing GPS Attacks

### Test Cases

**1. Normal GPS Operation**
```
Expected:
  - 8-12 satellites visible
  - Fix quality: 6
  - Position accuracy: 2-5 cm (RTK)

Test:
  - Run simulation for 100 iterations
  - Verify fix never drops below 6
  - Log position error vs ground truth
```

**2. Jamming Attack**
```
Setup:
  - Place jammer at (0, 0), radius 5, intensity 90%
  - Drone starts at (2, 2) (inside zone)

Expected:
  - Satellite count drops to 0-2
  - Fix quality drops to 0-1
  - Requirements dashboard shows CRITICAL
  - Drone activates recovery mode

Test:
  - Verify fix drops within 1 iteration
  - Verify error logged to PostgreSQL
  - Verify drone backtracks
```

**3. GPS Spoofing**
```
Setup:
  - Attacker generates fake GPS at +10 meters offset
  - Attacker lacks valid satellite keys

Expected:
  - Drone rejects spoofed messages (signature fail)
  - Position remains accurate
  - Error logged: "Spoofing detected"

Test:
  - Count rejected messages in logs
  - Verify position error < 10 cm
```

**4. Multi-Constellation Resilience**
```
Setup:
  - Jam GPS L1 frequency (blocks GPS + Galileo)
  - GLONASS unaffected

Expected:
  - GPS satellites: 10 → 2
  - GLONASS satellites: 6 → 6
  - Total: 8 satellites (still enough for fix)
  - Fix quality: 4 (DGPS, degraded but functional)

Test:
  - Verify fix_quality >= 1
  - Verify position error < 1 meter
  - Verify no GPS loss error logged
```

---

## Future Enhancements

### Phase 1: Realistic Signal Propagation
- Ionospheric delay modeling
- Tropospheric delay modeling
- Multipath effects (urban canyon simulation)

### Phase 2: Advanced Attacks
- Slow position drift attacks
- Time offset attacks
- Constellation-specific spoofing

### Phase 3: Defense Mechanisms
- IMU/INS integration for cross-validation
- RAIM (Receiver Autonomous Integrity Monitoring)
- Visual odometry for GPS-independent positioning