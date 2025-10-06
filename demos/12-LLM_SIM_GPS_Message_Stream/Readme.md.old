# Integrating MCP with RAG for LLM and Agent Jamming Simulation

> using llama3.3:70b-instruct-q5_K_M

### Run the Simulation and Chatapp

```
docker compose down -v; sudo chown -R $USER:$USER ./pgdata; rm -rf ./pgdata; docker compose up -d; python sim.py
```

```
python3 mcp_chatapp.py
```

**A Quick Note on the Simulation and MCP Chatapp:**

The mcp_rag_chatapp and the simulation need to be in the same memory space so that the mcp can actually influence the agents in the simulation. OR the simulation needs to be open to allow for other programs to influence it. in a real world hardware setup, you would simply interact with a hardware api and not have to jerry rig a simulation to do this.


---

# Simulation Code Breakdown

## Imports
The code imports several Python libraries for various functionalities:
- math and random for basic mathematical operations and randomization
- numpy (as np) for numerical operations
- matplotlib.pyplot (as plt) for visualization
- matplotlib.widgets.Button for interactive buttons
- matplotlib.animation.FuncAnimation for animation
- datetime for timestamp generation
- threading for running the API server in parallel
- FastAPI components for building the web API (uvicorn, FastAPI, HTTPException, Request, CORSMiddleware)
- Pydantic's BaseModel for data validation
- json for JSON handling
- typing components for type hints
- time for timing operations

## Configuration Section
- The code uses a toggle (USE_LLM) to switch between LLM-based and algorithm-based control
- Simulation parameters include:
  - update_freq: How often the simulation updates (2.5 seconds)
  - communication quality thresholds (high_comm_qual and low_comm_qual)
  - Coordinate ranges (x_range and y_range)
  - Number of agents (num_agents)
  - Mission endpoint (mission_end)
  - Jamming zone parameters (jamming_center and jamming_radius)
  - RAG update frequency (RAG_UPDATE_FREQUENCY)
  - LLM prompt constraints (MAX_CHARS_PER_AGENT, LLM_PROMPT_TIMEOUT, MAX_RETRIES)

## Global Variables
The simulation maintains several global state variables:
- swarm_pos_dict: Tracks each agent's position and communication quality
- position_history: Records the path history of each agent
- jammed_positions: Tracks which agents are in the jamming zone
- last_safe_position: Stores the last known safe position for each agent
- Various tracking variables for simulation state (iteration_count, animation_running, etc.)
- agent_targets: Stores manual movement targets for agents

## Core Functions

### initialize_agents()
- Creates agents with random starting positions near the origin
- Initializes all tracking dictionaries with default values
- Sets up initial paths toward the mission endpoint
- Prepares state tracking for the two-step jamming recovery process

### update_swarm_data(frame)
The main simulation update function that:
1. Handles manual movement targets if set
2. Manages the two-step jamming recovery process:
   - First returns to last safe position
   - Then gets new movement coordinates (from LLM or algorithm)
3. Updates normal movement when not jammed
4. Tracks communication quality based on position
5. Updates path history and current positions

### Plotting Functions
- init_plot(): Sets up the initial visualization with:
  - Coordinate grid
  - Jamming zone visualization
  - Mission endpoint marker
  - Movement step size indicator
- update_plot(frame): Updates the visualization each frame by:
  - Drawing agent paths
  - Showing current positions (color-coded by status)
  - Plotting communication quality over time
  - Handling data logging to RAG store

### Button Callbacks
- pause_simulation(): Pauses the animation
- continue_simulation(): Resumes the animation
- stop_simulation(): Stops and closes the simulation

### run_simulation_with_plots()
Main function that:
1. Sets up the matplotlib figure with two subplots
2. Creates control buttons
3. Initializes agents
4. Starts the animation

## API Implementation
The FastAPI app provides endpoints for:
- Getting simulation status (/status)
- Moving agents manually (/move_agent)
- Listing all agents (/agents)
- Getting and updating simulation parameters (/simulation_params)
- Controlling simulation state (/control/pause, /control/continue)

### API Models
Pydantic models for request/response validation:
- MoveAgentRequest: For manual movement requests
- AgentPosition: Current agent state
- SimulationStatus: Overall simulation state
- SimulationSettings: For parameter updates

## Execution Flow
1. When run as __main__, the code:
   - Prints the control mode (LLM or Algorithm)
   - Starts the API server in a background thread
   - Initializes agents
   - Runs the simulation with visualization

## Key Features
- Dual control modes (LLM vs algorithm)
- Jamming zone detection and recovery process
- Manual agent movement via API
- Real-time visualization
- Communication quality tracking
- Data logging for RAG
- Interactive controls
- Configurable parameters

--- 

# MCP Server Code Breakdown

## Imports
The code imports several Python libraries for various functionalities:
- FastAPI components for building the web server (FastAPI, Request, Response, etc.)
- CORS middleware for cross-origin requests
- Static file serving and Jinja2 templating
- FastMCP for multi-agent control
- Database connectors (psycopg2 for PostgreSQL)
- HTTP client (httpx) for API calls
- Logging and error handling utilities
- RAG and LLM configuration from other modules

## Configuration Section
- Database configuration (DB_CONFIG) for PostgreSQL connection
- Ollama client initialization for LLM interactions
- Simulation API endpoint configuration (SIMULATION_API_URL)
- FastAPI app and MCP server instantiation
- CORS middleware setup to allow all origins (for development)
- Templates and static files configuration

## Core Components

### Database Functions
- fetch_logs_from_db(): Retrieves logs from PostgreSQL database with optional limit
  - Handles JSON metadata parsing
  - Returns formatted log entries with timestamps

### Agent Movement Functionality
- move_agent(): The primary tool for moving agents
  - Makes API calls to simulation server
  - Handles success/failure cases
  - Logs movements to RAG store
  - Provides detailed feedback about jamming status

### LLM Command Processing
- llm_command(): Processes natural language commands
  - Gets current agent status from simulation
  - Formats prompt with live agent data
  - Uses Ollama LLM to interpret commands
  - Validates and executes movement commands
  - Handles non-movement commands appropriately

### Chat Interface
- chat(): The main conversational endpoint
  - Combines RAG (logs) with live simulation data
  - Detects duplicate commands
  - Creates rich context for LLM responses
  - Handles error cases gracefully
  - Maintains conversation history

## API Endpoints

### Simulation Control
- /simulation_info: Gets current simulation parameters
- /control/pause: Pauses the simulation
- /control/continue: Resumes the simulation

### Log Management
- /logs: Retrieves recent logs (with pagination option)
- /log_count: Returns total log count

### System Management
- /health: Comprehensive health check
  - Verifies simulation API connectivity
  - Returns server status
- /test: Simple connectivity test

### User Interface
- /: Serves the main HTML interface
- /static: Serves static assets

## Key Features

### Integration Capabilities
- Seamless connection between MCP and simulation
- Real-time data synchronization
- Unified logging system

### Natural Language Processing
- Advanced command interpretation
- Context-aware responses
- Duplicate command detection

### Monitoring and Control
- Comprehensive status reporting
- Fine-grained simulation control
- Health monitoring

### User Experience
- Web-based interface
- Interactive controls
- Clear status feedback

## Execution Flow
1. On startup:
   - Initializes all components
   - Starts FastAPI server
   - Verifies connections
2. During operation:
   - Processes user commands
   - Maintains real-time sync with simulation
   - Updates interface
3. Shutdown:
   - Cleanly terminates connections

## Error Handling
- Comprehensive exception catching
- Meaningful error messages
- Graceful degradation
- Detailed logging

## Data Flow
1. User input → API endpoint
2. Context gathering (logs + live data)
3. LLM processing
4. Action execution
5. Result reporting
6. Logging

## Security Considerations
- CORS configuration
- Input validation
- Error sanitization
- Secure database access