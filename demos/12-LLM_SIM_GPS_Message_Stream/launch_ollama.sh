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
OLLAMA_BIN="/home2/nelsg10/.local/bin/ollama/bin/ollama"

MODEL="$DEFAULT_MODEL"
ACTION="start"
VERBOSE=0
STOP_INDEX=""

# --- HELPER FUNCTIONS ---
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

OPTIONS:
    --model MODEL    Start a model runner (default: llama3:8b)
    --stop [N]      Stop all processes, or just runner [N]
    --status        Show status of Ollama services
    --verbose       Enable verbose debug output
    -h, --help      Show this help message

EXAMPLES:
    $0                           # Start serve + default model
    $0 --model gemma2:2b         # Start another model (keeps others running)
    $0 --status                  # Check status with numbered list
    $0 --stop 1                  # Stop model [1] from status list
    $0 --stop                    # Stop everything

HOW IT WORKS:
    - Each model runs as a separate 'ollama run MODEL' background process
    - Models stay loaded and ready to handle requests
    - You can run multiple models simultaneously
    - Stop individual models by their index number
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

# Get all running model processes
# Returns: PID MODEL_NAME (one per line)
get_running_model_processes() {
    # First get PIDs of all ollama processes
    local all_pids=$(run_on_gpu "pgrep -f '$OLLAMA_BIN run' 2>/dev/null || true")
    
    if [ -z "$all_pids" ]; then
        return
    fi
    
    # For each PID, get full command line and extract model name
    for pid in $all_pids; do
        local cmdline=$(run_on_gpu "ps -p $pid -o args= 2>/dev/null || true")
        
        # Skip if it's a runner subprocess (not the main "ollama run" process)
        if echo "$cmdline" | grep -q "ollama runner"; then
            continue
        fi
        
        # Extract model name from "ollama run MODEL" command
        # Preserve the full model name including tag (e.g., llama3:8b)
        if echo "$cmdline" | grep -q "$OLLAMA_BIN run"; then
            # Remove everything before and including "ollama run ", then take first word
            local model=$(echo "$cmdline" | grep -o "$OLLAMA_BIN run [^ ;]*" | awk '{print $NF}')
            if [ -n "$model" ]; then
                echo "$pid $model"
            fi
        fi
    done
}

# Check if specific model process is running
is_model_process_running() {
    local model="$1"
    local count
    count=$(run_on_gpu "ps aux | grep '$OLLAMA_BIN run $model' | grep -v grep | wc -l")
    if [ "$count" -gt 0 ]; then
        echo "yes"
    else
        echo "no"
    fi
}

# Get PID of specific model process
get_model_process_pid() {
    local model="$1"
    run_on_gpu "ps aux | grep '$OLLAMA_BIN run $model' | grep -v grep | awk '{print \$2}' | head -1"
}

# Start ollama serve on GPU
start_ollama_serve() {
    if [ "$(is_ollama_running)" = "yes" ]; then
        echo "✓ Ollama serve already running (PID: $(get_ollama_pid))"
        return 0
    fi
    
    echo "Starting ollama serve on GPU..."
    
    # Use nohup with disown to truly detach
    run_on_gpu "nohup bash -c 'OLLAMA_HOST=127.0.0.1:$REMOTE_PORT $OLLAMA_BIN serve > /tmp/ollama_serve.log 2>&1' >/dev/null 2>&1 & disown"
    
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
        return 1
    fi
}

# Check if model exists on system
model_exists() {
    local model="$1"
    local list_output
    
    # Make sure ollama serve is running first
    if [ "$(is_ollama_running)" != "yes" ]; then
        return 1
    fi
    
    # Check on GPU
    list_output=$(run_on_gpu "OLLAMA_HOST=127.0.0.1:$REMOTE_PORT $OLLAMA_BIN list 2>/dev/null")
    
    # Debug output if verbose
    if [ "${VERBOSE:-0}" = "1" ]; then
        echo "  Model list output:" >&2
        echo "$list_output" >&2
        echo "  Looking for: $model" >&2
    fi
    
    # Check if exact model name (with tag) appears in the list
    # Use word boundary to match exact model names
    if echo "$list_output" | grep -q "^${model}[[:space:]]"; then
        return 0
    fi
    return 1
}

# Pull model via Vega (GPU has no internet)
pull_model() {
    local model="$1"
    echo "Model $model not found. Pulling via Vega (GPU has no internet)..."
    
    # Stop ollama on GPU temporarily
    echo "  Stopping GPU ollama..."
    local gpu_pid
    gpu_pid=$(get_ollama_pid)
    if [ -n "$gpu_pid" ]; then
        run_on_gpu "kill $gpu_pid 2>/dev/null || true"
        sleep 2
    fi
    
    # Start ollama on Vega, pull model, then stop
    echo "  Starting ollama on Vega and pulling model..."
    run_on_vega "OLLAMA_HOST=127.0.0.1:$REMOTE_PORT $OLLAMA_BIN serve > /tmp/ollama_vega_pull.log 2>&1 & VEGA_PID=\$!; sleep 3; OLLAMA_HOST=127.0.0.1:$REMOTE_PORT $OLLAMA_BIN pull $model; kill \$VEGA_PID 2>/dev/null || true"
    
    # Restart on GPU
    echo "  Restarting ollama on GPU..."
    start_ollama_serve
    
    echo "✓ Model $model pulled successfully"
}

# Start a model runner process
start_model_runner() {
    local model="$1"
    
    if [ "$(is_model_process_running "$model")" = "yes" ]; then
        echo "✓ Model $model already running (PID: $(get_model_process_pid "$model"))"
        return 0
    fi
    
    echo "Checking if model exists..."
    # Check if model exists, pull if not
    if ! model_exists "$model"; then
        echo "Model $model not found in ollama list"
        pull_model "$model"
    else
        echo "✓ Model $model found"
    fi
    
    echo "Starting model runner for $model..."
    
    # Start persistent ollama run process in background
    local log_file="/tmp/ollama_run_${model//[:\/]/_}.log"
    
    # Start the runner - it will keep running and handling requests
    run_on_gpu "nohup bash -c 'while true; do OLLAMA_HOST=127.0.0.1:$REMOTE_PORT $OLLAMA_BIN run $model; sleep 1; done > $log_file 2>&1' >/dev/null 2>&1 & disown"
    
    sleep 3
    
    if [ "$(is_model_process_running "$model")" = "yes" ]; then
        local pid=$(get_model_process_pid "$model")
        echo "✓ Model $model runner started (PID: $pid)"
    else
        echo "✗ Failed to start model runner for $model"
        echo ""
        echo "Diagnostics:"
        run_on_gpu "tail -20 $log_file 2>/dev/null || echo 'No log file found'"
        echo ""
        echo "All ollama processes on GPU:"
        run_on_gpu "ps aux | grep ollama | grep -v grep"
        return 1
    fi
}

# Stop specific model runner by index
stop_model_by_index() {
    local index="$1"
    
    echo "Stopping model runner at index [$index]..."
    
    # Get list of running models
    local models=()
    while IFS= read -r line; do
        if [ -n "$line" ]; then
            local pid=$(echo "$line" | awk '{print $1}')
            local model=$(echo "$line" | awk '{print $2}')
            models+=("$pid:$model")
        fi
    done < <(get_running_model_processes)
    
    local array_index=$((index - 1))
    
    if [ "$array_index" -lt 0 ] || [ "$array_index" -ge "${#models[@]}" ]; then
        echo "✗ Invalid index: $index (valid range: 1-${#models[@]})"
        return 1
    fi
    
    local target="${models[$array_index]}"
    local pid=$(echo "$target" | cut -d: -f1)
    local model=$(echo "$target" | cut -d: -f2-)
    
    echo "  Stopping [$index] $model (PID: $pid)"
    run_on_gpu "kill $pid 2>/dev/null || true"
    
    sleep 1
    echo "✓ Model runner stopped"
}

# Stop all ollama processes
stop_all() {
    echo "Stopping all Ollama processes..."
    
    # Get all model runner PIDs
    local model_pids
    model_pids=$(run_on_gpu "ps aux | grep '$OLLAMA_BIN run' | grep -v grep | awk '{print \$2}'")
    
    # Kill model runners
    if [ -n "$model_pids" ]; then
        echo "  Stopping model runners..."
        for pid in $model_pids; do
            run_on_gpu "kill $pid 2>/dev/null || true"
        done
    fi
    
    # Get serve PID
    local serve_pid
    serve_pid=$(get_ollama_pid)
    
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
    
    echo -e "\n--- Running Model Runners ---"
    
    # Get running processes
    local models=()
    while IFS= read -r line; do
        if [ -n "$line" ]; then
            local pid=$(echo "$line" | awk '{print $1}')
            local model_name=$(echo "$line" | awk '{print $2}')
            models+=("$pid:$model_name")
        fi
    done < <(get_running_model_processes)
    
    if [ "${#models[@]}" -eq 0 ]; then
        echo "None"
    else
        local index=1
        for entry in "${models[@]}"; do
            local pid=$(echo "$entry" | cut -d: -f1)
            local model_name=$(echo "$entry" | cut -d: -f2-)
            
            echo "[$index] $model_name (PID: $pid)"
            ((index++))
        done
    fi
    
    echo -e "\n--- Available Models ---"
    if [ "$(is_ollama_running)" = "yes" ]; then
        run_on_gpu "OLLAMA_HOST=127.0.0.1:$REMOTE_PORT $OLLAMA_BIN list 2>/dev/null"
    else
        echo "(Ollama serve not running)"
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
        echo "Port forward already active, keeping existing connection"
        return 0
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
            if [[ $# -gt 1 ]] && [[ "$2" =~ ^[0-9]+$ ]]; then
                STOP_INDEX="$2"
                shift 2
            else
                shift
            fi
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
        echo "Starting Ollama model runner: $MODEL"
        echo "-----------------------------------"
        start_ollama_serve
        start_model_runner "$MODEL"
        setup_port_forward
        echo "-----------------------------------"
        echo "✓ Setup complete!"
        echo "  Connect locally at: http://localhost:$LOCAL_PORT"
        echo "  Model runner active: $MODEL"
        echo ""
        echo "Run './launch_ollama.sh --model <name>' to start more models"
        echo "Run './launch_ollama.sh --status' to see all running models"
        ;;
    stop)
        if [ -n "$STOP_INDEX" ]; then
            stop_model_by_index "$STOP_INDEX"
        else
            stop_all
        fi
        ;;
    status)
        show_status
        ;;
esac