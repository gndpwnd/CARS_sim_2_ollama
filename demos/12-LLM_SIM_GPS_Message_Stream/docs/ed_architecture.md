# System Architecture Documentation

## Overview

Multi-agent drone swarm simulation with LLM-augmented command and control, GPS constellation, and cybersecurity attack modeling.

---

## System Components

### 1. Simulation Core (`main_gui.py`)
**Purpose:** PyQt5 GUI with matplotlib visualization, drives iteration loop

**Responsibilities:**
- Manages swarm state (positions, jamming status, movement paths)
- Updates agents every iteration (1 Hz default)
- Handles user input (drawing jamming zones, pause/resume)
- Renders agent positions, paths, and mission endpoint

**Key State:**
- `swarm_pos_dict`: Agent positions + communication quality
- `jammed_positions`: Boolean per agent
- `last_safe_position`: Recovery waypoints
- `agent_paths`: Movement queues per agent

**Iteration Loop:**
```
1. Update agent positions based on paths
2. Check jamming status for each agent
3. Update GPS data via constellation
4. Log telemetry to Qdrant
5. Log errors/warnings to PostgreSQL
6. Render visualization
```

---

### 2. GPS Constellation (`sat_constellation.py`)
**Purpose:** Simulates GNSS satellites generating NMEA messages

**Architecture:**
- TCP server on port 12345
- Receives position + jamming level per agent
- Returns NMEA sentences (GGA, RMC, GSV) + metrics

**NMEA Generation:**
- **GGA:** Position fix with lat/lon, satellites, fix quality, HDOP
- **RMC:** Navigation data with speed, heading, validity
- **GSV:** Satellite visibility with PRN, elevation, azimuth, SNR

**Signal Degradation Model:**
```
Jamming Level 0-30%:    6-8 sats, DGPS fix, SNR 35-42 dB-Hz
Jamming Level 30-70%:   3-5 sats, GPS fix, SNR 25-35 dB-Hz
Jamming Level 70-100%:  0 sats, no fix, SNR 0 dB-Hz
```

**Configuration:** `constellation_config.json`
- Satellite counts (GPS: 32, GLONASS: 24, Galileo: 30)
- Signal quality thresholds
- Error injection rates
- NMEA/RTCM message types

---

### 3. MCP Chatapp (`mcp_chatapp.py`)
**Purpose:** FastAPI web interface for LLM interaction with simulation

**Endpoints:**
- `POST /chat` - Natural language commands to LLM
- `GET /startup_menu` - Command menu and simulation bounds
- `GET /data/postgresql` - Fetch messages
- `GET /data/qdrant` - Fetch telemetry
- `GET /stream/postgresql` - SSE stream of messages
- `GET /stream/qdrant` - SSE stream of telemetry

**LLM Integration:**
- Ollama client (localhost:11434)
- Model: `llama3:8b` (preloaded on startup)
- Context: Retrieves from RAG system (PostgreSQL + Qdrant)

**Command Types:**
1. **Movement:** "move agent1 to 5, 5" → parsed and executed
2. **Status:** "status" → generates report from RAG
3. **Report:** "report" → detailed analysis with LLM
4. **General:** Natural language Q&A about simulation

---

### 4. Data Storage

#### PostgreSQL (`postgresql_store.py`)
**Purpose:** Relational storage for messages and events

**Schema:**
```sql
CREATE TABLE logs (
    id UUID PRIMARY KEY,
    text TEXT,
    metadata JSONB,
    embedding VECTOR(384),
    created_at TIMESTAMP
);
```

**Message Types (metadata.message_type):**
- `command` - User commands
- `response` - LLM responses
- `notification` - Status updates
- `error` - Jamming events, GPS loss
- `telemetry` - (legacy, now in Qdrant)

**Indexes:**
- `metadata->>'source'` (user, llm, agent_1, agent_2...)
- `metadata->>'message_type'`
- `metadata->>'timestamp'`

#### Qdrant (`qdrant_store.py`)
**Purpose:** Vector storage for high-volume telemetry

**Collections:**
1. `nmea_messages`
   - Raw NMEA sentences
   - Agent ID, timestamp, position
   - GPS metrics (sats, fix quality, signal)

2. `agent_telemetry`
   - Position (x, y) every iteration
   - Jamming status, comm quality
   - GPS metrics, iteration number

**Vector Embedding:** MiniLM (384 dimensions)
- Enables semantic search over telemetry
- Example: "agents jammed near origin"

---

### 5. RAG System (`rag.py`)
**Purpose:** Orchestrates retrieval from both databases for LLM context

**Key Functions:**
```
get_agent_context(agent_id, history_limit=5)
  → Returns: position history, messages, errors

get_all_agents_status(agent_ids)
  → Returns: current position, jammed status, error count

format_for_llm(agent_id)
  → Returns: Human-readable context string

get_known_agent_ids()
  → Discovers agents from stored data
```

**Data Flow:**
```
LLM Query → RAG → Qdrant (telemetry) + PostgreSQL (messages)
         → Formatted Context → LLM → Response
```

---

### 6. Requirements Tracker (`sim_reqs_tracker.py`)
**Purpose:** Monitors GPS denial detection requirements

**Tracked Metrics (from `requirements_config.json`):**
- **Fix Quality Level:** 0=None, 1=GPS, 2=DGPS, 3=RTK
- **Satellite Count:** Number in solution
- **Signal Strength:** Average C/N0 in dB-Hz
- **Jamming Level:** Estimated intensity (%)

**Thresholds:**
- **Critical:** Fix < 1, Sats < 4, Signal < 30, Jamming > 70
- **Warning:** Fix < 2, Sats < 6, Signal < 35, Jamming > 50

**Logging:**
- Violations → PostgreSQL as errors/notifications
- Raw metrics → Qdrant as telemetry

**GUI Integration:**
- Notification dashboard (`notification_dashboard.py`)
- PyQt5 window with color-coded requirement tiles
- Updates every second

---

### 7. Agent Movement Logic (`sim_helper_funcs.py`)
**Purpose:** Movement algorithms and recovery behaviors

**Algorithms:**
1. **Linear Path to Mission End:** Direct route when clear
2. **Algorithm Recovery:** When jammed, backtrack to last safe position
3. **LLM Recovery (Future):** Request new position via MCP

**Jamming Recovery Flow:**
```
1. Detect jamming (check_if_jammed)
2. Backtrack to last_safe_position
3. If still jammed, try random position within movement limit
4. If still jammed, request LLM help via MCP
5. Resume mission path when clear
```

---

## Data Flow Diagrams

### Normal Operation
```
User → MCP → LLM → Command
                ↓
            main_gui → Agent Movement
                ↓
        GPS Constellation (NMEA)
                ↓
            Telemetry
                ↓
        Qdrant + PostgreSQL
                ↓
            RAG → LLM Context
```

### Attack Scenario
```
Jamming Zone Active
    ↓
Agent Enters Zone
    ↓
GPS Constellation: Signal Degraded
    ↓
Agent: Jammed Status = True
    ↓
Recovery Algorithm: Backtrack
    ↓
PostgreSQL: Log Error
Qdrant: Log Telemetry
    ↓
Requirements Tracker: Violation Detected
    ↓
GUI: Show Agent as Red
Dashboard: Show CRITICAL status
```

---

## Security Architecture

### Current Implementation
1. **Encryption:** AES-128 (planned, not yet active)
2. **Authentication:** CMD_ID + SENDER_ID deduplication
3. **Replay Protection:** Timestamp validation
4. **Signature Verification:** (planned, not yet active)

### Attack Surface (Simulated)
- **GPS Spoofing:** Fake NMEA injection
- **Jamming:** Signal degradation zones
- **Message Injection:** (planned with radio system)
- **Replay Attacks:** (planned with radio system)

---

## Configuration Files

### `requirements_config.json`
Defines GPS requirement thresholds for monitoring

### `constellation_config.json`
Configures satellite counts, signal parameters, error injection rates

### `docker-compose.yml`
Launches PostgreSQL (pgvector) and Qdrant containers

---

## Startup Sequence

### Backend Services (`startup.py`)
```
1. Check dependencies (fastapi, psycopg2, qdrant-client)
2. Verify database connectivity
3. Start sat_constellation.py (port 12345)
4. Start mcp_chatapp.py (port 5000)
5. Wait for Ctrl+C
```

### Frontend GUI (`main_gui.py`)
```
1. Initialize PyQt5 application
2. Create matplotlib canvas
3. Connect to GPS constellation
4. Initialize requirements monitor
5. Spawn agents in non-jammed positions
6. Start iteration timer (1 Hz)
7. Launch notification dashboard (optional)
```

---

## Performance Characteristics

### Scale (Current)
- **Agents:** 5-10 (tested)
- **Target:** Up to 100
- **Iteration Rate:** 1 Hz (1 second per step)
- **Message Volume:** 1 per agent per iteration

### Bottlenecks
- **GPS Constellation:** TCP roundtrip (~10ms per agent)
- **Database Logging:** Batch inserts to Qdrant/PostgreSQL
- **GUI Rendering:** Matplotlib redraw (~50ms with 10 agents)

### Optimization Paths
- Use async database clients
- Batch GPS requests
- Optimize matplotlib blitting for partial updates

---

## Extension Points

### Adding New Agent Behaviors
- Modify `sim_helper_funcs.py::algorithm_make_move()`
- Add new movement strategy functions
- Integrate with `main_gui.py::update_swarm_data()`

### Adding New Requirements
- Edit `requirements_config.json`
- Update `sim_reqs_tracker.py::_get_metric_value()`
- GUI updates automatically from config

### Adding New LLM Commands
- Add endpoint to `mcp_chatapp.py`
- Update startup menu generation
- Implement handler function

---

## Dependencies

### Core
- Python 3.11+
- PyQt5 (GUI)
- matplotlib (visualization)
- numpy (math operations)

### Databases
- psycopg2 (PostgreSQL client)
- qdrant-client (Qdrant vector DB)
- sentence-transformers (embeddings)

### LLM
- httpx (HTTP client)
- ollama (local LLM server)

### GPS
- pynmea2 (NMEA parsing)
- socket (TCP client)

---

## Known Limitations

1. **Single-threaded simulation:** All agents update sequentially
2. **No collision detection:** Agents can overlap
3. **Simplified GPS model:** No ionospheric delays, multipath
4. **No cryptographic validation:** Messages not yet signed/encrypted
5. **No distributed deployment:** All runs on one machine

---

## Future Roadmap

### Phase 1: Radio Communication (Current)
- Implement message board architecture
- Add inter-drone messaging
- Enable attack injection

### Phase 2: Enhanced GPS
- Multi-constellation support
- RTK corrections
- Realistic signal propagation

### Phase 3: Advanced Security
- Implement encryption/signatures
- Add MITM attack simulation
- Blockchain-style message validation

### Phase 4: Scalability
- Distributed simulation (multiple processes)
- Redis message broker
- 1000+ agent support