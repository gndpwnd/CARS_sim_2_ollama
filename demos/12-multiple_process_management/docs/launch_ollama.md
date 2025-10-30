# Ollama GPU Manager

A bash script to manage Ollama models on a remote GPU server through an SSH jump host, with automatic port forwarding and multi-model support.

## Problem It Solves

Running Ollama on a GPU server that:
- Requires SSH jump host access (vegaln1 → gpu02)
- Has no internet connection (requires pulling models via vega node)
- Needs port forwarding to local machine
- Requires managing multiple models simultaneously

## Quick Start

```bash
# Start the default model (llama3:8b)
./launch_ollama.sh

# Start a different model
./launch_ollama.sh --model gemma2:2b

# Check what's running
./launch_ollama.sh --status

# Stop a specific model
./launch_ollama.sh --stop 1

# Stop everything
./launch_ollama.sh --stop
```

## What It Does

1. **Auto-starts Ollama service** on GPU if not running (port 11435)
2. **Launches model runners** as persistent background processes
3. **Auto-pulls missing models** via vega (GPU has no internet)
4. **Sets up port forwarding** (localhost:11434 → gpu02:11435)
5. **Manages multiple models** simultaneously with indexed control

## Architecture

```
Local Machine (11434) → SSH Jump (vegaln1) → GPU Server (11435)
                                          ↓
                                    Vega (for pulling models)
```

## Commands

### Start Models
```bash
./launch_ollama.sh                    # Start serve + default model
./launch_ollama.sh --model llama3:8b  # Start specific model
```

### Check Status
```bash
./launch_ollama.sh --status
```

Output:
```
=================================
OLLAMA STATUS
=================================

--- Ollama Service (GPU) ---
Status: RUNNING
PID: 58619
Port: 11435

--- Running Model Runners ---
[1] llama3:8b (PID: 60049)
[2] gemma2:2b (PID: 61620)

--- Available Models ---
NAME                            ID              SIZE      MODIFIED
llama3:8b                       365c0bd3c000    4.7 GB    20 minutes ago
gemma2:2b                       8ccf136fdd52    1.6 GB    28 minutes ago

--- Local Port Forward ---
Status: ACTIVE
Local: localhost:11434 -> GPU:11435
PID: 52935
=================================
```

### Stop Models
```bash
./launch_ollama.sh --stop 1   # Stop model [1] from status list
./launch_ollama.sh --stop     # Stop everything (models + serve + port forward)
```

## How It Works

### Model Runner Architecture
- Each model runs as `ollama run MODEL` in a persistent loop
- Models stay loaded in GPU memory, ready to handle requests
- Multiple models can run simultaneously
- Each gets its own PID for individual control

### Model Pulling (GPU has no internet)
When a model doesn't exist:
1. Stops Ollama on GPU
2. Starts Ollama on vega (has internet)
3. Pulls model to shared storage
4. Stops Ollama on vega
5. Restarts Ollama on GPU
6. Model now available on GPU

### Port Forwarding
Automatic SSH tunnel: `localhost:11434 → gpu02:11435`
- Persists across model starts/stops
- Only killed when running `--stop` without arguments

## Configuration

Edit these variables at the top of the script:
```bash
JUMP_HOST="nelsg10@vegaln1.erau.edu"
GPU_HOST="nelsg10@gpu02"
VEGA_HOST="nelsg10@vegaln1.erau.edu"
LOCAL_PORT=11434
REMOTE_PORT=11435
DEFAULT_MODEL="llama3:8b"
OLLAMA_BIN="/home2/nelsg10/.local/bin/ollama/bin/ollama"
```

## Prerequisites

- SSH key authentication configured for jump host and GPU
- Ollama installed at the configured `OLLAMA_BIN` path
- `lsof` command available on local machine (for port checking)

## Usage Examples

### Running Multiple Models
```bash
./launch_ollama.sh --model llama3:8b
./launch_ollama.sh --model gemma2:2b
./launch_ollama.sh --model llama3.3:70b-instruct-q5_K_M
./launch_ollama.sh --status  # See all running models
```

### Selective Stopping
```bash
./launch_ollama.sh --status   # Check which is [1], [2], [3]
./launch_ollama.sh --stop 2   # Stop only gemma2:2b
# Other models keep running
```

### Full Cleanup
```bash
./launch_ollama.sh --stop     # Stops all models, serve, and port forward
```

## Debugging

```bash
./launch_ollama.sh --verbose --status  # See detailed SSH commands
```

Check logs on GPU:
```bash
ssh -J nelsg10@vegaln1.erau.edu nelsg10@gpu02
tail -f /tmp/ollama_serve.log
tail -f /tmp/ollama_run_llama3_8b.log
```

## Notes

- Status always reflects real-time GPU server state
- Model indices in `--status` may change if models are stopped
- Always run `--status` before using `--stop [N]` to get current indices
- Port forward persists until explicitly stopped with `--stop`