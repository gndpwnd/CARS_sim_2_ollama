# Project Structure and Modularity Guide

## Overview

Organized architecture for maintaining separation between radio communication, GPS systems, swarm control, and existing infrastructure.

---

## Directory Structure

```
project_root/
│
├── config/                          # Configuration files
│   ├── requirements_config.json     # GPS requirement thresholds
│   ├── constellation_config.json    # Satellite parameters
│   ├── drone_config.json            # Drone IDs, keys, capabilities
│   └── attack_scenarios.json        # Predefined attack configurations
│
├── core/                            # Core simulation modules
│   ├── __init__.py
│   ├── radio_environment.py         # Message board system
│   ├── gps_radio_layer.py           # GPS as radio implementation
│   ├── drone_agent.py               # Individual drone logic
│   ├── swarm_controller.py          # Formation algorithms
│   └── simulation_engine.py         # Iteration orchestration
│
├── attacks/                         # Attack simulation modules
│   ├── __init__.py
│   ├── base_attack.py               # Abstract attack class
│   ├── jamming_attack.py            # Jamming implementation
│   ├── spoofing_attack.py           # GPS/message spoofing
│   ├── injection_attack.py          # Fake message injection
│   ├── replay_attack.py             # Message replay
│   └── mitm_attack.py               # Man-in-the-middle
│
├── storage/                         # Database interfaces
│   ├── __init__.py
│   ├── postgresql_store.py          # Message/event storage
│   ├── qdrant_store.py              # Telemetry/vector storage
│   └── rag.py                       # RAG orchestration
│
├── gps/                             # GPS constellation system
│   ├── __init__.py
│   ├── sat_constellation.py         # Satellite server
│   ├── gps_client_lib.py            # Client library
│   └── nmea_generator.py            # NMEA sentence creation
│
├── requirements/                    # Requirements tracking
│   ├── __init__.py
│   ├── vehicle_requirements_tracker.py
│   └── sim_reqs_tracker.py
│
├── gui/                             # User interface components
│   ├── __init__.py
│   ├── main_gui.py                  # Primary simulation window
│   ├── notification_dashboard.py    # Requirements monitor
│   └── attack_control_panel.py      # Attack configuration UI
│
├── llm/                             # LLM integration
│   ├── __init__.py
│   ├── mcp_chatapp.py               # FastAPI MCP server
│   ├── llm_config.py                # Ollama client setup
│   └── templates/                   # Web UI templates
│       └── index.html
│
├── utils/                           # Helper functions
│   ├── __init__.py
│   ├── sim_helper_funcs.py          # Movement algorithms
│   ├── crypto_utils.py              # Signature/encryption
│   └── logging_utils.py             # Centralized logging
│
├── tests/                           # Test suite
│   ├── test_radio_environment.py
│   ├── test_gps_radio.py
│   ├── test_attacks.py
│   └── test_integration.py
│
├── docker-compose.yml               # Database containers
├── startup.py                       # Backend launcher
├── requirements.txt                 # Python dependencies
└── README.md                        # Project documentation
```

---

## Module Responsibilities

### Core Modules

#### `radio_environment.py`
**Purpose:** Message board and radio communication infrastructure

**Classes:**
- `RadioMessage`: Data model for messages
- `RadioEnvironment`: Message board management
- `DroneRegistry`: Key storage and drone metadata

**Key Methods:**
```
RadioEnvironment:
  - post_message(msg: RadioMessage)
  - get_messages() -> List[RadioMessage]
  - clear_board()
  - filter_messages(receiver_id, msg_type)
```

**Dependencies:** None (pure data structure)

---

#### `gps_radio_layer.py`
**Purpose:** GPS constellation as radio broadcast system

**Classes:**
- `GPSRadioMessage`: Extends RadioMessage for GPS
- `SatelliteTransmitter`: Posts GPS NMEA to board
- `GPSJammingSimulator`: Applies jamming to GPS messages

**Key Methods:**
```
SatelliteTransmitter:
  - broadcast_nmea(drone_positions, jamming_zones)
  - calculate_visibility(drone_pos, sat_pos)
  - apply_jamming(message, jamming_level)
```

**Dependencies:**
- `radio_environment.py`
- `gps_client_lib.py`
- `sat_constellation.py`

---

#### `drone_agent.py`
**Purpose:** Individual drone state and decision logic

**Classes:**
- `DroneAgent`: Single drone entity
- `DroneState`: Position, velocity, status
- `DroneMemory`: Message history, received CMD_IDs

**Key Methods:**
```
DroneAgent:
  - receive_messages(message_board) -> List[RadioMessage]
  - process_messages(messages)
  - decide_action() -> Optional[RadioMessage]
  - update_position()
```

**Dependencies:**
- `radio_environment.py`
- `gps_radio_layer.py`
- `crypto_utils.py`

---

#### `swarm_controller.py`
**Purpose:** Formation control algorithms (optional centralized logic)

**Classes:**
- `FormationController`: Hexagonal lattice, line, etc.
- `FormationState`: Current geometry, spacing

**Key Methods:**
```
FormationController:
  - calculate_target_positions(drones)
  - adjust_formation(constraints)
  - handle_failures(failed_drones)
```

**Dependencies:**
- `drone_agent.py`

---

#### `simulation_engine.py`
**Purpose:** Orchestrates iteration loop, ties all modules together

**Classes:**
- `SimulationEngine`: Main coordinator
- `IterationState`: Current iteration number, time

**Key Methods:**
```
SimulationEngine:
  - run_iteration()
    1. Clear message board
    2. GPS phase (satellites post)
    3. Attack phase (attackers post)
    4. Radio phase (drones post)
    5. Processing phase (drones read/act)
    6. Movement phase (drones update positions)
    7. Logging phase (telemetry to Qdrant)
  - start(), stop(), pause(), resume()
```

**Dependencies:** All core modules + attacks + storage

---

### Attack Modules

#### `base_attack.py`
**Purpose:** Abstract base class for all attacks

**Classes:**
- `BaseAttack`: Interface for attacks
- `AttackConfig`: Configuration object

**Key Methods:**
```
BaseAttack (abstract):
  - generate_messages(radio_env, iteration) -> List[RadioMessage]
  - is_active(iteration) -> bool
  - get_targets(drones) -> List[DroneAgent]
```

---

#### Attack Implementations

**Each attack inherits from `BaseAttack`:**

**`jamming_attack.py`:**
- Floods board with noise messages
- Parameters: intensity, frequency, radius

**`spoofing_attack.py`:**
- Generates fake GPS NMEA
- Parameters: fake_position, target_drone

**`injection_attack.py`:**
- Injects fake command messages
- Parameters: command_type, target_drone

**`replay_attack.py`:**
- Replays captured old messages
- Parameters: captured_message, delay_iterations

**`mitm_attack.py`:**
- Intercepts and modifies messages
- Parameters: target_sender, modification_function

---

### Storage Modules

**Separation of Concerns:**

#### `postgresql_store.py`
**Stores:** User messages, LLM responses, agent notifications, errors

**When to Use:**
- Important events (jamming detected, GPS loss)
- Conversational data (user ↔ LLM)
- Structured queries (get errors for agent_5)

---

#### `qdrant_store.py`
**Stores:** Telemetry, radio messages, GPS NMEA (vectorized)

**When to Use:**
- High-frequency data (position every iteration)
- Semantic search (find similar situations)
- Time-series analysis (position history)

---

#### `rag.py`
**Orchestrates:** Retrieval from both databases for LLM

**Key Functions:**
```
get_agent_context(agent_id)
  → PostgreSQL: Recent messages/errors
  → Qdrant: Position history, telemetry
  → Returns: Unified context for LLM

format_for_llm(agent_id)
  → Human-readable string for LLM prompt
```

---

### GPS Modules

**Keep Existing Structure:**

#### `sat_constellation.py`
- TCP server on port 12345
- Maintains satellite positions
- Generates NMEA on request

**Integration with Radio:**
- Wrapper class `GPSSatelliteWrapper` in `gps_radio_layer.py`
- Calls `sat_constellation` TCP endpoint
- Converts NMEA to `GPSRadioMessage`
- Posts to message board

---

#### `gps_client_lib.py`
**No changes needed**
- Still used for direct GPS queries
- Used by `gps_radio_layer.py` to get NMEA
- Fallback for when constellation unavailable

---

### GUI Modules

#### `main_gui.py`
**Responsibilities:**
- Matplotlib rendering
- User input (jamming zones, pause/resume)
- Iteration timer
- Attack control integration

**Integration Points:**
```
Calls:
  - simulation_engine.run_iteration()
  - attack_control_panel.get_active_attacks()
  - notification_dashboard.update()

Receives:
  - Position updates from drones
  - Message board state for arrow rendering
```

---

#### `notification_dashboard.py`
**No changes needed**
- Still monitors requirements
- Reads from `sim_reqs_tracker.py`

---

#### `attack_control_panel.py` (NEW)
**Purpose:** GUI for configuring attacks

**Components:**
- Attack type dropdown
- Intensity slider
- Target area selector (click map)
- Start/Stop buttons

**Methods:**
```
create_attack(type, params) -> AttackConfig
add_to_simulation(attack_config)
remove_attack(attack_id)
```

---

## Data Flow Diagrams

### Iteration Flow

```
ITERATION N START
    ↓
simulation_engine.run_iteration()
    ↓
┌─────────────────────────────────┐
│ 1. CLEAR MESSAGE BOARD          │
│    radio_environment.clear()     │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ 2. GPS PHASE                    │
│    gps_radio_layer.broadcast()  │
│    → Posts NMEA to board        │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ 3. ATTACK PHASE                 │
│    for attack in attacks:       │
│      msgs = attack.generate()   │
│      board.post(msgs)            │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ 4. RADIO PHASE                  │
│    for drone in drones:         │
│      msg = drone.decide()       │
│      board.post(msg)             │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ 5. PROCESSING PHASE             │
│    for drone in drones:         │
│      msgs = board.get_messages()│
│      drone.process(msgs)        │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ 6. MOVEMENT PHASE               │
│    for drone in drones:         │
│      drone.update_position()    │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ 7. LOGGING PHASE                │
│    qdrant.log_telemetry(drones) │
│    qdrant.log_messages(board)   │
│    postgresql.log_errors()      │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ 8. GUI UPDATE                   │
│    main_gui.render(drones)      │
│    dashboard.update()           │
└─────────────────────────────────┘
    ↓
ITERATION N+1 START
```

---

### Message Flow

```
USER COMMAND:
  User → MCP Chatapp → LLM → Command Parsed
    ↓
  RadioMessage created (sender="controller")
    ↓
  Posted to message_board
    ↓
  Logged to PostgreSQL (source="user", type="command")


DRONE TELEMETRY:
  Drone → RadioMessage (sender="drone_5", type="telemetry")
    ↓
  Posted to message_board
    ↓
  Logged to Qdrant (vectorized telemetry)


GPS BROADCAST:
  Satellite → GPSRadioMessage (sender="sat_12", type="gps_nmea")
    ↓
  Posted to message_board
    ↓
  Logged to Qdrant (NMEA collection)


ATTACK INJECTION:
  Attacker → RadioMessage (sender="attacker", signature=invalid)
    ↓
  Posted to message_board
    ↓
  Drone rejects (signature fail)
    ↓
  Logged to PostgreSQL (source="drone_5", type="error")
```

---

## Integration Strategy

### Phase 1: Add Radio System (Minimal Changes)

**Step 1:** Create `core/radio_environment.py`
- Implement `RadioMessage` dataclass
- Implement `RadioEnvironment` class
- No external dependencies

**Step 2:** Modify `main_gui.py`
```python
# ADD:
from core.radio_environment import RadioEnvironment

# IN __init__:
self.radio_env = RadioEnvironment()

# IN update_swarm_data (before movement):
self.radio_env.clear_board()
for agent_id in agents:
    msg = self._drone_decide_message(agent_id)
    if msg:
        self.radio_env.post_message(msg)

for agent_id in agents:
    self._drone_process_messages(agent_id, self.radio_env.get_messages())
```

**Step 3:** Test with simple messages
- One drone posts telemetry
- Other drones receive and ignore (not relevant)
- Verify message board clears each iteration

---

### Phase 2: Add GPS Radio Layer

**Step 1:** Create `core/gps_radio_layer.py`
- Wrapper around existing `sat_constellation.py`
- Converts NMEA to `GPSRadioMessage`
- Posts to message board

**Step 2:** Modify `main_gui.py`
```python
# REPLACE:
gps_data = self.gps_manager.update_agent_gps(...)

# WITH:
self.gps_radio_layer.broadcast_gps(
    agents, self.radio_env, jamming_zones
)
```

**Step 3:** Modify `drone_agent.py`
```python
# ADD:
def process_gps_messages(self, messages):
    gps_msgs = [m for m in messages if m.msg_type == "gps_nmea"]
    self.position = calculate_position_from_nmea(gps_msgs)
    self.fix_quality = determine_fix_quality(gps_msgs)
```

---

### Phase 3: Add Attack System

**Step 1:** Create `attacks/` module
- Implement `base_attack.py`
- Implement attack subclasses

**Step 2:** Create `gui/attack_control_panel.py`
- Qt widget with attack controls
- Returns `AttackConfig` objects

**Step 3:** Integrate in `main_gui.py`
```python
# ADD:
self.active_attacks = []

# IN update_swarm_data (after GPS phase):
for attack in self.active_attacks:
    if attack.is_active(self.iteration_count):
        attack_msgs = attack.generate_messages(
            self.radio_env, self.iteration_count
        )
        for msg in attack_msgs:
            self.radio_env.post_message(msg)
```

---

### Phase 4: Enhanced Logging

**Step 1:** Add radio message logging to `qdrant_store.py`
```python
def add_radio_message(msg: RadioMessage):
    vector = embed(msg.payload)
    qdrant.upsert(
        collection="radio_messages",
        vector=vector,
        payload={...}
    )
```

**Step 2:** Add attack logging to `postgresql_store.py`
```python
if signature_verification_failed:
    add_log(
        text=f"{drone_id} rejected message from {sender}",
        metadata={"message_type": "error", "attack_type": "injection"}
    )
```

---

## Configuration Management

### `drone_config.json` (NEW)
```json
{
  "drones": [
    {
      "id": "agent_1",
      "public_key": "base64_encoded_key",
      "initial_position": [0, 0],
      "capabilities": ["gps", "radio", "camera"]
    },
    ...
  ],
  "controller": {
    "id": "controller",
    "public_key": "base64_encoded_key"
  }
}
```

### `attack_scenarios.json` (NEW)
```json
{
  "scenarios": [
    {
      "name": "GPS Jamming",
      "attack_type": "jamming",
      "parameters": {
        "center": [0, 0],
        "radius": 5,
        "intensity": 80,
        "frequency": "L1"
      }
    },
    ...
  ]
}
```

---

## Testing Strategy

### Unit Tests

**`test_radio_environment.py`:**
```python
def test_post_and_retrieve():
    env = RadioEnvironment()
    msg = RadioMessage(sender_id="test", ...)
    env.post_message(msg)
    assert len(env.get_messages()) == 1

def test_clear_board():
    env = RadioEnvironment()
    env.post_message(msg)
    env.clear_board()
    assert len(env.get_messages()) == 0
```

**`test_gps_radio.py`:**
```python
def test_gps_to_radio_conversion():
    nmea = "$GPGGA,123519,..."
    gps_msg = convert_nmea_to_radio_message(nmea)
    assert gps_msg.msg_type == "gps_nmea"
```

**`test_attacks.py`:**
```python
def test_jamming_attack():
    attack = JammingAttack(intensity=50)
    messages = attack.generate_messages(env, iteration=1)
    assert len(messages) == 50
```

---

### Integration Tests

**`test_integration.py`:**
```python
def test_full_iteration():
    engine = SimulationEngine()
    engine.add_drone(DroneAgent("agent_1"))
    engine.run_iteration()
    
    # Verify message board was populated and cleared
    assert len(engine.radio_env.message_board) == 0
    
    # Verify telemetry logged
    assert qdrant.count("agent_telemetry") > 0

def test_attack_injection():
    engine = SimulationEngine()
    attack = SpoofingAttack(fake_position=(10, 10))
    engine.add_attack(attack)
    engine.run_iteration()
    
    # Verify attack message posted
    messages = engine.get_message_history(iteration=1)
    assert any(m.sender_id == "attacker" for m in messages)
```

---

## Dependency Graph

```
simulation_engine
    ├── radio_environment (no deps)
    ├── gps_radio_layer
    │   ├── radio_environment
    │   ├── sat_constellation
    │   └── gps_client_lib
    ├── drone_agent
    │   ├── radio_environment
    │   ├── gps_radio_layer
    │   └── crypto_utils
    ├── swarm_controller
    │   └── drone_agent
    ├── attacks/*
    │   ├── base_attack
    │   └── radio_environment
    ├── storage
    │   ├── postgresql_store (no deps)
    │   ├── qdrant_store (no deps)
    │   └── rag (both stores)
    └── gui
        ├── main_gui (calls simulation_engine)
        ├── notification_dashboard (reads sim_reqs_tracker)
        └── attack_control_panel (creates attack configs)
```

**Key Principle:** Core modules have minimal dependencies. GUI depends on core, not vice versa.

---

## Migration Path from Current Codebase

### Existing Files → New Structure

**Keep As-Is:**
- `sat_constellation.py` → `gps/sat_constellation.py`
- `gps_client_lib.py` → `gps/gps_client_lib.py`
- `postgresql_store.py` → `storage/postgresql_store.py`
- `qdrant_store.py` → `storage/qdrant_store.py`
- `rag.py` → `storage/rag.py`
- `mcp_chatapp.py` → `llm/mcp_chatapp.py`
- `vehicle_requirements_tracker.py` → `requirements/`
- `sim_reqs_tracker.py` → `requirements/`
- `notification_dashboard.py` → `gui/notification_dashboard.py`

**Refactor:**
- `main_gui.py`:
  - Extract agent logic → `core/drone_agent.py`
  - Extract iteration loop → `core/simulation_engine.py`
  - Keep GUI rendering in `gui/main_gui.py`

- `sim_helper_funcs.py`:
  - Split into:
    - Movement algorithms → `utils/movement_algorithms.py`
    - Jamming checks → `core/environment_checks.py`

**Create New:**
- `core/radio_environment.py`
- `core/gps_radio_layer.py`
- `attacks/*` (all files)
- `gui/attack_control_panel.py`
- `utils/crypto_utils.py`

---

## Development Workflow

### Step-by-Step Implementation

**Week 1: Radio Foundation**
1. Create `core/radio_environment.py`
2. Write unit tests
3. Add simple message posting to `main_gui.py`
4. Test with 2 drones exchanging messages

**Week 2: GPS Integration**
1. Create `core/gps_radio_layer.py`
2. Convert GPS to radio messages
3. Test GPS on message board
4. Verify telemetry logging

**Week 3: Attack Framework**
1. Create `attacks/base_attack.py`
2. Implement `jamming_attack.py`
3. Test jamming in simulation
4. Verify error logging

**Week 4: GUI Integration**
1. Create `gui/attack_control_panel.py`
2. Add attack controls to main GUI
3. Test dynamic attack injection
4. Polish visualization

**Week 5: Full Attacks**
1. Implement remaining attack types
2. Add attack scenarios config
3. Test all attack types
4. Documentation

---

## Performance Monitoring

### Metrics to Track

**Per Iteration:**
```
- Messages on board: Count
- Processing time: Milliseconds
  - GPS phase: X ms
  - Attack phase: X ms
  - Radio phase: X ms
  - Processing phase: X ms
  - Movement phase: X ms
  - Logging phase: X ms
  - GUI phase: X ms
- Memory usage: MB
```

**Per Drone:**
```
- Messages received: Count
- Messages sent: Count
- Signature verifications: Count (success/fail)
- Position updates: Count
```

**Logging:**
```python
@profile_iteration
def run_iteration(self):
    with timer("gps_phase"):
        self.gps_phase()
    with timer("attack_phase"):
        self.attack_phase()
    ...
    log_performance_metrics()
```

---

## Scalability Considerations

### Current Capacity (Target)
- **10 drones:** Comfortable, <100ms per iteration
- **100 drones:** Feasible, optimize signature checks
- **1000 drones:** Requires architectural changes

### Optimization Path (100+ drones)

**Optimization 1: Batch Processing**
```
Instead of: for drone in drones: verify_each_message()
Use: batch_verify_signatures(all_drones, all_messages)
```

**Optimization 2: Message Filtering**
```
Instead of: each drone reads entire board
Use: pre-filter board by receiver_id, broadcast only
```

**Optimization 3: Parallel Processing**
```
Use multiprocessing.Pool to process drones in parallel
Each process handles subset of drones
Synchronize at end of iteration
```

### Beyond 1000 Drones

**Architectural Change: Distributed Message Broker**
```
Replace: In-memory message board
With: Redis Pub/Sub or RabbitMQ
Benefits:
  - True distributed processing
  - Multiple simulation processes
  - Network scalability
```

---

## Summary

### Key Principles

1. **Modularity:** Clear separation between radio, GPS, attacks, storage
2. **Minimal Changes:** Existing code mostly untouched, add wrappers
3. **Incremental:** Add features in phases, test each phase
4. **Performance:** In-memory for speed, optimize later if needed
5. **Testability:** Each module has unit tests, integration tests cover full flow

### Integration Points

- `simulation_engine.py` orchestrates all modules
- `radio_environment.py` is shared state (message board)
- All modules read/write to message board
- Logging is centralized through `qdrant_store.py` and `postgresql_store.py`
- GUI reads from simulation engine, doesn't call modules directly

### Extension Points

- New attack types: Subclass `BaseAttack`
- New message types: Add to `RadioMessage.msg_type` enum
- New formations: Implement in `swarm_controller.py`
- New GUI panels: Inherit from Qt widgets, integrate via `main_gui.py`