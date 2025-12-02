# Radio Communication Simulation Theory

## Overview

Event-driven message board system for inter-drone and drone-to-controller radio communication with cybersecurity attack simulation.

---

## Core Concept: Message Board Architecture

### Iteration-Based Processing Model

**Theory:** All communication happens via a **shared message board** that exists for one iteration, then clears.

```
ITERATION N:
  [Message Board] = Empty List
  
  WRITE PHASE:
    - Drones write messages to board
    - Controller writes commands to board
    - Attackers inject malicious messages to board
  
  READ PHASE:
    - Each drone reads entire board
    - Filters messages (signature, relevance, timestamp)
    - Updates internal state based on valid messages
  
  CLEAR PHASE:
    - Board is emptied
    - All messages logged to Qdrant
  
ITERATION N+1:
  [Message Board] = Empty List
  ...
```

**Key Principle:** Write-then-read ensures no race conditions. All entities write simultaneously, then all read simultaneously.

---

## Message Structure

### RadioMessage Data Model

**Components:**
```
RadioMessage:
  - msg_id: UUID (unique identifier)
  - cmd_id: Sequential counter per sender
  - sender_id: Agent/controller/attacker ID
  - receiver_id: Target agent ID or "broadcast"
  - timestamp: Unix timestamp when sent
  - msg_type: "command", "telemetry", "ack", "query", "response"
  - payload: Encrypted data (JSON serializable)
  - signature: Cryptographic signature (validates sender)
  - power: Transmit power (future: affects range)
  - frequency: Radio frequency MHz (future: for jamming simulation)
```

**Message Types:**
1. **Command:** Controller → Drone (movement orders, mission updates)
2. **Telemetry:** Drone → Controller (position, status reports)
3. **ACK:** Drone → Sender (acknowledgment of received message)
4. **Query:** Drone → Drone (request neighbor info)
5. **Response:** Drone → Drone (answer to query)

---

## Drone Communication Protocol

### Per-Iteration Behavior

**Phase 1: Receive (Read from Board)**
```
1. Read all messages from message board
2. For each message:
   a. Verify signature (check against drone_keys dict)
   b. Check if addressed to me (receiver_id == my_id OR "broadcast")
   c. Verify timestamp (reject if older than X iterations)
   d. Check for replay (have I seen this cmd_id from this sender?)
3. Store valid messages in received_messages list
```

**Phase 2: Process (Think)**
```
1. Update internal state based on received messages:
   - Commands: Update mission parameters
   - Telemetry: Update neighbor positions
   - Queries: Prepare response
   - ACKs: Mark message as delivered

2. Run decision logic:
   - Formation control algorithm
   - Collision avoidance
   - Mission progress check
   - Communication need assessment

3. Decide if need to send message:
   - Need to report position? → Send telemetry
   - Need to acknowledge? → Send ACK
   - Need neighbor data? → Send query
   - Received query? → Send response
```

**Phase 3: Send (Write to Board)**
```
IF need_to_send:
  1. Create RadioMessage
  2. Populate fields (sender_id, receiver_id, payload)
  3. Sign message with my private key
  4. Write to message board (ONE message max per iteration)
ELSE:
  Do nothing (saves bandwidth)
```

**Constraint:** One message per drone per iteration prevents spam.

---

## Message Board Data Structure

### Python Implementation Theory

**Shared State:**
```
RadioEnvironment:
  - message_board: List[RadioMessage] (cleared each iteration)
  - drone_keys: Dict[str, str] (drone_id → public key)
  - message_history: List[List[RadioMessage]] (archive for replay)
  - current_iteration: int (iteration counter)
```

**Access Pattern:**
- All drones have **read access** to message_board
- All drones have **write access** to message_board
- No locking needed (single-threaded, write-then-read)

**Logging:**
After read phase, entire message_board is logged to Qdrant:
```
for msg in message_board:
  qdrant.add_radio_message(
    msg_id=msg.msg_id,
    sender=msg.sender_id,
    receiver=msg.receiver_id,
    type=msg.msg_type,
    timestamp=msg.timestamp,
    vector=embed(msg.payload)  # Vectorize for semantic search
  )
```

---

## Attack Simulation

### Attack as External Entity

**Theory:** Attackers are **independent entities** that write to message board just like drones.

**Attack Types:**

### 1. Jamming Attack
**Mechanism:** Flood message board with noise messages

**Implementation:**
```
JammingAttacker:
  - position: (x, y) on map
  - radius: Affected area
  - intensity: Messages per iteration (0-100)
  
  Per Iteration:
    - Generate N random noise messages (N = intensity)
    - Set receiver_id = "broadcast"
    - Invalid signature (garbage bytes)
    - Write all to message board
  
  Effect:
    - Drones waste CPU verifying bad signatures
    - Board fills up, legitimate messages harder to find
    - If intensity > 50, drones may miss critical commands
```

### 2. GPS Spoofing Attack
**Mechanism:** Inject fake GPS NMEA messages

**Implementation:**
```
GPSSpoofingAttacker:
  - target_agent: Which drone to mislead
  - fake_position: False lat/lon
  
  Per Iteration:
    - Create GPS message (special msg_type = "gps_nmea")
    - Payload = fake NMEA sentence with wrong position
    - Signature = valid (if attacker has compromised GPS key)
    - Write to message board
  
  Effect:
    - Target drone reads fake GPS
    - Updates position incorrectly
    - Moves to wrong location
    - Formation breaks
```

### 3. Message Injection Attack
**Mechanism:** Send fake commands pretending to be controller

**Implementation:**
```
InjectionAttacker:
  - target_agent: Which drone to control
  - malicious_command: E.g., "move to -100, -100" (out of bounds)
  
  Per Iteration:
    - Create command message
    - sender_id = "controller" (spoofed)
    - signature = forged (if attacker lacks valid key, fails)
    - Write to message board
  
  Effect:
    - If signature invalid → Drone rejects (attack fails)
    - If attacker has controller key → Drone accepts (attack succeeds)
    - Demonstrates importance of key security
```

### 4. Replay Attack
**Mechanism:** Re-send old valid messages

**Implementation:**
```
ReplayAttacker:
  - captured_message: Previously recorded valid message
  
  Per Iteration:
    - Copy old message
    - Update timestamp to current iteration
    - Signature is still valid (attacker didn't forge it)
    - Write to message board
  
  Effect:
    - Without timestamp validation → Attack succeeds
    - With timestamp validation → Drone rejects (too old)
    - Demonstrates need for nonce/timestamp checks
```

### 5. Man-in-the-Middle (MITM) Attack
**Mechanism:** Intercept, modify, re-send messages

**Implementation:**
```
MITMAttacker:
  - intercept_from: sender_id to monitor
  - modify_function: How to alter payload
  
  READ PHASE:
    - Read all messages from message_board
    - Find messages from intercept_from
    - Store original messages
  
  WRITE PHASE:
    - For each intercepted message:
      - Modify payload (e.g., change position by 10 meters)
      - Re-sign with compromised key (if available)
      - Write modified message to board
    - Original message may still exist on board
  
  Effect:
    - If attacker can't re-sign → Drones see invalid signature, reject
    - If attacker has key → Drones accept modified message
    - Demonstrates need for end-to-end encryption
```

---

## Attack Injection API

### Dynamic Attack Control

**Theory:** Attacks are controlled via configuration objects that simulation reads each iteration.

**Attack Configuration Object:**
```
AttackConfig:
  - attack_id: Unique identifier
  - attack_type: "jamming" | "spoofing" | "injection" | "replay" | "mitm"
  - active: Boolean (can pause/resume attack)
  - target_area: (x, y, radius) or "all"
  - target_agents: List[agent_id] or "all"
  - intensity: 0-100 (messages per iteration or effect strength)
  - start_iteration: When to begin
  - end_iteration: When to stop (None = indefinite)
  - parameters: Dict (attack-specific settings)
```

**GUI Integration:**
```
User clicks "Start Jamming Attack"
  ↓
GUI creates AttackConfig:
  - attack_type = "jamming"
  - target_area = selected_zone
  - intensity = 75
  - active = True
  ↓
AttackConfig added to active_attacks list
  ↓
EACH ITERATION:
  for attack in active_attacks:
    if attack.active:
      attack.execute(message_board)
  ↓
Attack writes messages to board
  ↓
Drones process (and suffer from) attack messages
```

**Pause/Resume:**
- User clicks "Pause Simulation" → Set attack.active = False
- User clicks "Resume" → Set attack.active = True
- Attack state persists across pauses

---

## Message Filtering and Validation

### Drone Receive Logic (Detailed)

**Step 1: Signature Verification**
```
Theory: Only accept messages from known/trusted sources

for msg in message_board:
  expected_key = drone_keys.get(msg.sender_id)
  if not expected_key:
    REJECT (unknown sender)
  
  if not verify_signature(msg.payload, msg.signature, expected_key):
    REJECT (invalid signature, possible forgery)
  
  ACCEPT (proceed to next check)
```

**Step 2: Relevance Check**
```
Theory: Only process messages meant for me

if msg.receiver_id == "broadcast":
  ACCEPT (everyone should see this)
elif msg.receiver_id == my_id:
  ACCEPT (directly addressed to me)
else:
  IGNORE (not my business)
```

**Step 3: Timestamp Validation**
```
Theory: Reject old messages (replay attack prevention)

msg_age = current_iteration - msg.timestamp
if msg_age > MAX_MESSAGE_AGE:
  REJECT (too old, possible replay)

if msg_age < 0:
  REJECT (future timestamp, clock desync or attack)

ACCEPT (timestamp reasonable)
```

**Step 4: Replay Detection**
```
Theory: Have I seen this exact message before?

seen_key = (msg.sender_id, msg.cmd_id)
if seen_key in received_history:
  REJECT (replay attack detected)

received_history.add(seen_key)
ACCEPT (first time seeing this message)
```

**Result:** Only valid, relevant, recent, non-replayed messages are processed.

---

## Communication Patterns

### 1. Broadcast (Controller → All Drones)
```
Controller writes:
  RadioMessage(
    sender_id="controller",
    receiver_id="broadcast",
    msg_type="command",
    payload={"action": "return_to_base"}
  )

All drones read and process (if signature valid)
```

### 2. Unicast (Drone → Drone)
```
Drone A queries Drone B:
  RadioMessage(
    sender_id="drone_a",
    receiver_id="drone_b",
    msg_type="query",
    payload={"request": "position"}
  )

Drone B responds (next iteration):
  RadioMessage(
    sender_id="drone_b",
    receiver_id="drone_a",
    msg_type="response",
    payload={"position": [5.2, 3.8]}
  )
```

### 3. Acknowledgment (Drone → Controller)
```
Controller sends command:
  RadioMessage(receiver_id="drone_x", msg_type="command", ...)

Drone X acknowledges:
  RadioMessage(
    sender_id="drone_x",
    receiver_id="controller",
    msg_type="ack",
    payload={"ack_msg_id": original_msg.msg_id}
  )
```

---

## Performance Analysis

### Message Volume Calculations

**Normal Operation (10 drones):**
```
Per Iteration:
- Controller: 1 broadcast (mission update) = 1 message
- Each drone: 1 telemetry report = 10 messages
- Total: 11 messages per iteration

At 1 Hz: 11 messages/second
At 10 Hz: 110 messages/second
```

**Under Attack (Jamming at 50% intensity):**
```
Per Iteration:
- Normal: 11 messages
- Jamming: 50 noise messages
- Total: 61 messages per iteration

Processing:
- Each drone reads 61 messages
- 50 fail signature check (fast rejection)
- 11 pass to relevance check
- ~2-3 relevant per drone (broadcast + direct)
```

**Scalability (100 drones):**
```
Per Iteration:
- Controller: 1 broadcast
- Each drone: 1 telemetry
- Total: 101 messages

Each drone reads 101 messages
Processes ~3-5 relevant messages
Time per drone: ~1ms (signature checks are fast)
Total processing: ~100ms for all drones (sequential)
```

**Bottleneck:** Signature verification is O(N × M) where N = drones, M = messages.
**Optimization:** Use bloom filter to quickly reject non-relevant messages before signature check.

---

## Logging Strategy

### What to Log to Qdrant

**All Messages (Vectorized for Search):**
```
For each message on board:
  text = f"{msg.sender_id} → {msg.receiver_id}: {msg.msg_type}"
  vector = embed(text + str(msg.payload))
  
  qdrant.add(
    collection="radio_messages",
    vector=vector,
    payload={
      "msg_id": msg.msg_id,
      "sender": msg.sender_id,
      "receiver": msg.receiver_id,
      "type": msg.msg_type,
      "timestamp": msg.timestamp,
      "iteration": current_iteration,
      "signature_valid": was_verified,
      "payload_summary": truncate(msg.payload)
    }
  )
```

**Benefits:**
- Semantic search: "Find messages about formation"
- Attack analysis: "Find spoofed messages"
- LLM context: "What happened during jamming?"

### What to Log to PostgreSQL

**Critical Events Only:**
```
IF message causes state change:
  - Command accepted → Log as notification
  - Signature failed → Log as error
  - Replay detected → Log as error
  - Attack successful → Log as error
```

**Example:**
```
Agent drone_5 received invalid command (signature mismatch)
→ PostgreSQL with metadata:
  {
    "source": "drone_5",
    "message_type": "error",
    "attack_type": "injection",
    "timestamp": ...
  }
```

---

## GUI Visualization

### Radio Transmission Arrows

**Theory:** Show active message flow each iteration

**Rendering:**
```
For each message on board:
  IF msg.receiver_id != "broadcast":
    sender_pos = get_position(msg.sender_id)
    receiver_pos = get_position(msg.receiver_id)
    
    ax.arrow(
      sender_pos[0], sender_pos[1],
      receiver_pos[0] - sender_pos[0],
      receiver_pos[1] - sender_pos[1],
      color="blue" if signature_valid else "red",
      width=0.05,  # Thin arrow
      alpha=0.3    # Semi-transparent
    )
  
  ELSE (broadcast):
    sender_pos = get_position(msg.sender_id)
    ax.add_patch(Circle(
      sender_pos, radius=2.0,
      fill=False, color="green", linewidth=1
    ))
```

**Color Coding:**
- Blue arrow: Valid unicast message
- Red arrow: Invalid/attack message
- Green circle: Broadcast (expanding ring)

**Performance:** Clear arrows each iteration (don't accumulate).

---

## Security Model

### Cryptographic Operations (Theory)

**Key Distribution:**
```
On initialization:
  - Generate keypair for each drone (Ed25519)
  - Controller has master keypair
  - All public keys stored in drone_keys dict
  - Private keys stored per-drone
```

**Message Signing:**
```
msg.signature = sign(
  data=serialize(msg.payload),
  private_key=my_private_key
)
```

**Signature Verification:**
```
is_valid = verify(
  data=serialize(msg.payload),
  signature=msg.signature,
  public_key=drone_keys[msg.sender_id]
)
```

**Attack Scenarios:**
1. **No compromised keys:** Attacker can't forge signatures → All attacks fail
2. **One drone key compromised:** Attacker can impersonate that drone only
3. **Controller key compromised:** Attacker can issue valid commands → Full compromise

**Defense:** Key rotation, threshold signatures (require 3 of 5 controllers to sign critical commands).

---

## Integration with Existing System

### Modifications Needed

**1. Add to main_gui.py:**
```
class RadioEnvironment:
  def __init__(self):
    self.message_board = []
    self.drone_keys = load_keys()
    self.current_iteration = 0

def update_swarm_data():
  # EXISTING CODE...
  
  # NEW: Radio communication phase
  radio_env.clear_board()
  
  # Drones write messages
  for agent_id in agents:
    msg = agent_decide_message(agent_id)
    if msg:
      radio_env.post_message(msg)
  
  # Attacks inject messages
  for attack in active_attacks:
    attack_msgs = attack.generate_messages(radio_env)
    for msg in attack_msgs:
      radio_env.post_message(msg)
  
  # Drones read and process
  for agent_id in agents:
    agent_process_messages(agent_id, radio_env.message_board)
  
  # Log to Qdrant
  for msg in radio_env.message_board:
    qdrant.add_radio_message(msg)
```

**2. Add attack_simulator.py (new file):**
```
Contains AttackConfig and attack classes:
- JammingAttack
- SpoofingAttack
- InjectionAttack
- ReplayAttack
- MITMAttack

Each has generate_messages(radio_env) method
```

**3. Add to GUI controls:**
```
[Attack Menu]
  - Attack Type dropdown
  - Intensity slider
  - [Start Attack] button
  - [Stop Attack] button

On button click:
  - Create AttackConfig
  - Add to active_attacks list
```

---

## Testing and Validation

### Test Scenarios

**1. Normal Communication:**
- All drones send telemetry
- Controller sends broadcast command
- All drones receive and ACK
- Verify: 100% message delivery

**2. Jamming Attack:**
- Activate 75% intensity jamming
- Verify: Drones detect invalid signatures
- Verify: Telemetry still gets through
- Measure: Message processing time increases

**3. Replay Attack:**
- Capture valid message
- Replay 10 iterations later
- Verify: Drones reject (timestamp too old)

**4. Key Compromise:**
- Give attacker drone_5's private key
- Attacker sends fake telemetry as drone_5
- Verify: Other drones accept (attack succeeds)
- Verify: System logs show drone_5 position mismatch

---

## Future Enhancements

### Phase 1 Extensions
- Distance-based receive zones (only hear nearby drones)
- Signal strength decay model
- Collision detection (two drones transmit simultaneously)

### Phase 2 Extensions
- Multi-hop mesh routing (relay through intermediaries)
- Frequency hopping (FHSS anti-jamming)
- Beamforming (directional antennas)

### Phase 3 Extensions
- Real-time timing (sub-second iterations)
- Hardware-in-the-loop (real radios)
- Distributed simulation (multiple processes)