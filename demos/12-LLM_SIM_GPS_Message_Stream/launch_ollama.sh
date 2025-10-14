#!/bin/bash
# Automates Ollama service/model on GPU via jump host

set -euo pipefail

# --- CONFIG ---
JUMP_HOST="nelsg10@vegaln1.erau.edu"
GPU_HOST="nelsg10@gpu02"
VEGA_HOST="nelsg10@vegaln1.erau.edu"
LOCAL_PORT=11434
REMOTE_PORT=11435
DEFAULT_MODEL="llama3:8b"
OLLAMA_BIN="/home2/nelsg10/.local/bin/ollama/bin/ollama"  # Full path to ollama binary

MODEL="$DEFAULT_MODEL"
ACTION="start"
VERBOSE=0

# --- HELPER FUNCTIONS ---
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

OPTIONS:
    --model MODEL    Specify model to run (default: llama3:8b)
    --stop          Stop all Ollama processes
    --status        Show status of Ollama services
    --verbose       Enable verbose debug output
    -h, --help      Show this help message

EXAMPLES:
    $0                           # Start default model
    $0 --model llama3.3:70b      # Start specific model
    $0 --status                  # Check status
    $0 --stop                    # Stop everything
EOF
}

# Execute command on GPU via jump host
run_on_gpu() {
    if [ "${VERBOSE:-0}" = "1" ]; then
        echo "  [GPU] Running: $*" >&2
    fi
    ssh -o ConnectTimeout=10 -J "$JUMP_HOST" "$GPU_HOST" "$@"
}

# Execute command on Vega
run_on_vega() {
    if [ "${VERBOSE:-0}" = "1" ]; then
        echo "  [VEGA] Running: $*" >&2
    fi
    ssh -o ConnectTimeout=10 "$VEGA_HOST" "$@"
}

# Check if ollama serve is running on GPU
is_ollama_running() {
    local count
    count=$(run_on_gpu "ps aux | grep '[o]llama serve' | grep -v grep | wc -l")
    if [ "$count" -gt 0 ]; then
        echo "yes"
    else
        echo "no"
    fi
}

# Get PID of ollama serve
get_ollama_pid() {
    run_on_gpu "ps aux | grep '[o]llama serve' | grep -v grep | awk '{print \$2}' | head -1"
}

# Check if specific model is running
is_model_running() {
    local model="$1"
    local count
    count=$(run_on_gpu "ps aux | grep '[o]llama run $model' | grep -v grep | wc -l")
    if [ "$count" -gt 0 ]; then
        echo "yes"
    else
        echo "no"
    fi
}

# Get PID of model
get_model_pid() {
    local model="$1"
    run_on_gpu "ps aux | grep '[o]llama run $model' | grep -v grep | awk '{print \$2}' | head -1"
}

# Start ollama serve on GPU
start_ollama_serve() {
    if [ "$(is_ollama_running)" = "yes" ]; then
        echo "✓ Ollama serve already running (PID: $(get_ollama_pid))"
        return 0
    fi
    
    echo "Starting ollama serve on GPU..."
    
    # Use setsid to detach the process from the SSH session
    run_on_gpu "setsid bash -c 'OLLAMA_HOST=127.0.0.1:$REMOTE_PORT $OLLAMA_BIN serve > /tmp/ollama_serve.log 2>&1 < /dev/null &' >/dev/null 2>&1"
    
    echo "  Waiting for service to start..."
    sleep 3
    
    if [ "$(is_ollama_running)" = "yes" ]; then
        echo "✓ Ollama serve started (PID: $(get_ollama_pid))"
    else
        echo "✗ Failed to start ollama serve"
        echo ""
        echo "Diagnostics:"
        echo "  Checking log file..."
        run_on_gpu "tail -20 /tmp/ollama_serve.log 2>/dev/null || echo 'No log file found'"
        echo ""
        echo "  Checking if ollama binary exists..."
        run_on_gpu "ls -la $OLLAMA_BIN 2>/dev/null || echo 'Binary not found at $OLLAMA_BIN'"
        echo ""
        return 1
    fi
}

# Check if model exists on system
model_exists() {
    local model="$1"
    local list_output
    
    # Use the port-forwarded connection if available, otherwise direct
    if lsof -ti:$LOCAL_PORT >/dev/null 2>&1; then
        list_output=$(OLLAMA_HOST=127.0.0.1:$LOCAL_PORT $OLLAMA_BIN list 2>/dev/null | grep "^${model%%:*}" || echo "")
    else
        list_output=$(run_on_gpu "$OLLAMA_BIN list 2>/dev/null" | grep "^${model%%:*}" || echo "")
    fi
    
    if [ -n "$list_output" ]; then
        return 0
    fi
    return 1
}

# Pull model via Vega (has better network)
pull_model() {
    local model="$1"
    echo "Model $model not found. Pulling via Vega (this may take a while)..."
    
    # Stop ollama on GPU temporarily
    echo "  Stopping GPU ollama..."
    local gpu_pid
    gpu_pid=$(get_ollama_pid)
    if [ -n "$gpu_pid" ]; then
        run_on_gpu "kill $gpu_pid 2>/dev/null || true"
        sleep 2
    fi
    
    # Start ollama on Vega, pull model, then stop
    echo "  Pulling model on Vega..."
    run_on_vega "OLLAMA_HOST=127.0.0.1:$REMOTE_PORT $OLLAMA_BIN serve > /tmp/ollama_vega_pull.log 2>&1 & VEGA_PID=\$!; sleep 3; OLLAMA_HOST=127.0.0.1:$REMOTE_PORT $OLLAMA_BIN pull $model; kill \$VEGA_PID 2>/dev/null || true"
    
    # Restart on GPU
    echo "  Restarting ollama on GPU..."
    start_ollama_serve
    
    echo "✓ Model $model pulled successfully"
}

# Start model running
start_model() {
    local model="$1"
    
    if [ "$(is_model_running "$model")" = "yes" ]; then
        echo "✓ Model $model already running (PID: $(get_model_pid "$model"))"
        return 0
    fi
    
    # Check if model exists, pull if not
    if ! model_exists "$model"; then
        pull_model "$model"
    fi
    
    echo "Starting model $model..."
    
    # Use setsid to detach the process
    run_on_gpu "setsid bash -c 'OLLAMA_HOST=127.0.0.1:$REMOTE_PORT $OLLAMA_BIN run $model > /tmp/ollama_model_${model//[:\/]/_}.log 2>&1 < /dev/null &' >/dev/null 2>&1"
    
    sleep 3
    
    if [ "$(is_model_running "$model")" = "yes" ]; then
        echo "✓ Model $model started (PID: $(get_model_pid "$model"))"
    else
        echo "✗ Failed to start model $model"
        echo ""
        echo "Diagnostics:"
        run_on_gpu "tail -20 /tmp/ollama_model_${model//[:\/]/_}.log 2>/dev/null || echo 'No log file found'"
        return 1
    fi
}

# Stop all ollama processes
stop_all() {
    echo "Stopping all Ollama processes..."
    
    # Get PIDs
    local serve_pid
    serve_pid=$(get_ollama_pid)
    
    local model_pids
    model_pids=$(run_on_gpu "ps aux | grep '[o]llama run' | grep -v grep | awk '{print \$2}'")
    
    # Kill model processes
    if [ -n "$model_pids" ]; then
        echo "  Stopping model processes: $model_pids"
        for pid in $model_pids; do
            run_on_gpu "kill $pid 2>/dev/null || true"
        done
    fi
    
    # Kill serve process
    if [ -n "$serve_pid" ]; then
        echo "  Stopping ollama serve: $serve_pid"
        run_on_gpu "kill $serve_pid 2>/dev/null || true"
    fi
    
    if [ -z "$serve_pid" ] && [ -z "$model_pids" ]; then
        echo "  No ollama processes found on GPU"
    fi
    
    sleep 1
    
    # Kill local port forward
    if lsof -ti:$LOCAL_PORT >/dev/null 2>&1; then
        echo "  Stopping local port forward..."
        kill $(lsof -ti:$LOCAL_PORT) 2>/dev/null || true
    fi
    
    echo "✓ All processes stopped"
}

# Show status
show_status() {
    echo "==================================="
    echo "OLLAMA STATUS"
    echo "==================================="
    
    echo -e "\n--- Ollama Service (GPU) ---"
    if [ "$(is_ollama_running)" = "yes" ]; then
        local pid
        pid=$(get_ollama_pid)
        echo "Status: RUNNING"
        echo "PID: $pid"
        echo "Port: $REMOTE_PORT"
    else
        echo "Status: NOT RUNNING"
    fi
    
    echo -e "\n--- Available Models ---"
    if [ "$(is_ollama_running)" = "yes" ]; then
        run_on_gpu "OLLAMA_HOST=127.0.0.1:$REMOTE_PORT $OLLAMA_BIN list 2>/dev/null || echo 'Error fetching models'"
    else
        echo "(Ollama serve not running)"
    fi
    
    echo -e "\n--- Running Model Processes ---"
    local model_procs
    model_procs=$(run_on_gpu "ps aux | grep '[o]llama run' | grep -v grep")
    if [ -n "$model_procs" ]; then
        echo "$model_procs" | awk '{print $2, $11, $12, $13, $14, $15}'
    else
        echo "None"
    fi
    
    echo -e "\n--- Local Port Forward ---"
    if lsof -ti:$LOCAL_PORT >/dev/null 2>&1; then
        echo "Status: ACTIVE"
        echo "Local: localhost:$LOCAL_PORT -> GPU:$REMOTE_PORT"
        echo "PID: $(lsof -ti:$LOCAL_PORT)"
    else
        echo "Status: NOT ACTIVE"
    fi
    echo "==================================="
}

# Setup port forwarding
setup_port_forward() {
    # Kill existing forward if present
    if lsof -ti:$LOCAL_PORT >/dev/null 2>&1; then
        echo "Killing existing port forward..."
        kill $(lsof -ti:$LOCAL_PORT) 2>/dev/null || true
        sleep 1
    fi
    
    echo "Setting up port forward: localhost:$LOCAL_PORT -> GPU:$REMOTE_PORT"
    ssh -f -N -L "$LOCAL_PORT:127.0.0.1:$REMOTE_PORT" -J "$JUMP_HOST" "$GPU_HOST"
    sleep 1
    
    if lsof -ti:$LOCAL_PORT >/dev/null 2>&1; then
        echo "✓ Port forward established"
    else
        echo "✗ Failed to establish port forward"
        return 1
    fi
}

# --- ARGUMENT PARSING ---
while [[ $# -gt 0 ]]; do
    case $1 in
        --model)
            MODEL="$2"
            shift 2
            ;;
        --stop)
            ACTION="stop"
            shift
            ;;
        --status)
            ACTION="status"
            shift
            ;;
        --verbose|-v)
            VERBOSE=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Error: Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# --- MAIN ---
case $ACTION in
    start)
        echo "Starting Ollama with model: $MODEL"
        echo "-----------------------------------"
        start_ollama_serve
        start_model "$MODEL"
        setup_port_forward
        echo "-----------------------------------"
        echo "✓ Setup complete!"
        echo "  Connect locally at: http://localhost:$LOCAL_PORT"
        echo "  Model running: $MODEL"
        echo ""
        echo "Test with: curl http://localhost:$LOCAL_PORT/api/generate -d '{\"model\":\"$MODEL\",\"prompt\":\"Hello\"}'"
        ;;
    stop)
        stop_all
        ;;
    status)
        show_status
        ;;
esac