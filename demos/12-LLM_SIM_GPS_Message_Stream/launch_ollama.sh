#!/bin/bash
# File: launch_ollama_local.sh
# Automates Ollama service/model on GPU via jump host

JUMP_HOST="nelsg10@vegaln1.erau.edu"
GPU_HOST="nelsg10@gpu02"
GPU_USER="nelsg10"
LOCAL_PORT=11434
REMOTE_PORT=11435
DEFAULT_MODEL="llama3:8b"
REMOTE_PID_DIR="~/.ollama"

MODEL="$DEFAULT_MODEL"
ACTION="start"

# --- FUNCTIONS ---
usage() {
    echo "Usage: $0 [--model MODEL] [--stop] [--status]"
}

run_remote() {
    # Single SSH jump to GPU
    ssh -o BatchMode=yes -J "$JUMP_HOST" "$GPU_HOST" "bash -l -c '$1'"
}

start_ollama_service() {
    echo "Checking if Ollama service is running..."
    SERVICE_PID=$(run_remote "pgrep -u $GPU_USER -f 'ollama serve' || true")
    if [ -z "$SERVICE_PID" ]; then
        echo "Ollama service not running. Starting..."
        run_remote "bash -l -c 'mkdir -p $REMOTE_PID_DIR; nohup OLLAMA_HOST=127.0.0.1:$REMOTE_PORT ollama serve >/tmp/ollama_serve.log 2>&1 & disown; echo \$! > $REMOTE_PID_DIR/serve.pid'"
        echo "Ollama service started in background."
        # Wait until the service is actually listening
        for i in {1..5}; do
            run_remote "netstat -tlnp | grep $REMOTE_PORT" && break
            sleep 2
        done
    else
        # Make sure the PID is still valid
        if ! run_remote "ps -p $SERVICE_PID >/dev/null 2>&1"; then
            echo "PID $SERVICE_PID not alive, restarting service..."
            run_remote "bash -l -c 'nohup OLLAMA_HOST=127.0.0.1:$REMOTE_PORT ollama serve >/tmp/ollama_serve.log 2>&1 & disown; echo \$! > $REMOTE_PID_DIR/serve.pid'"
            sleep 3
        else
            echo "Ollama service already running (PID $SERVICE_PID)"
        fi
    fi
}


check_model_exists() {
    MODEL=$1
    EXISTS=$(run_remote "bash -l -c 'OLLAMA_HOST=127.0.0.1:$REMOTE_PORT ollama list | grep -w $MODEL || true'")
    if [ -z "$EXISTS" ]; then
        echo "Model $MODEL not found on GPU. Pulling from Vega..."
        ssh "$JUMP_HOST" "bash -l -c 'OLLAMA_HOST=127.0.0.1:$REMOTE_PORT ollama pull $MODEL'"
        echo "Model $MODEL pulled and should now be available on GPU."
    fi
}

run_model() {
    MODEL=$1
    MODEL_PID=$(run_remote "pgrep -u $GPU_USER -f 'ollama run $MODEL' || true")
    if [ -z "$MODEL_PID" ] || ! run_remote "ps -p $MODEL_PID >/dev/null 2>&1"; then
        echo "Starting model $MODEL on GPU..."
        run_remote "bash -l -c 'nohup OLLAMA_HOST=127.0.0.1:$REMOTE_PORT ollama run $MODEL >/tmp/ollama_$MODEL.log 2>&1 & disown; echo \$! > $REMOTE_PID_DIR/run_$MODEL.pid'"
        echo "Model $MODEL started in background."
    else
        echo "Model $MODEL already running (PID $MODEL_PID)"
    fi
}


stop_all() {
    echo "Stopping all Ollama processes..."
    run_remote "pkill -u $GPU_USER -f 'ollama run'; pkill -u $GPU_USER -f 'ollama serve'; rm -f $REMOTE_PID_DIR/*.pid"
    echo "All Ollama processes stopped."
}

status() {
    echo "=== Ollama Service on GPU ==="
    run_remote 'if [ -f ~/.ollama/serve.pid ]; then echo "Serve PID: $(cat ~/.ollama/serve.pid)"; else echo "Not running"; fi'

    echo "=== Ollama Models on GPU ==="
    run_remote 'shopt -s nullglob; for f in ~/.ollama/run_*.pid; do echo "$(basename "$f" .pid) PID: $(cat "$f")"; done || echo "No models running"'

    echo "=== Available Models ==="
    run_remote "bash -l -c 'OLLAMA_HOST=127.0.0.1:$REMOTE_PORT ollama list || echo \"No models available\"'"

    echo "=== SSH Tunnel Status (local) ==="
    if lsof -iTCP:$LOCAL_PORT -sTCP:LISTEN -t >/dev/null; then
        TUNNEL_PID=$(lsof -tiTCP:$LOCAL_PORT -sTCP:LISTEN)
        echo "Port forwarding active: localhost:$LOCAL_PORT -> GPU:$REMOTE_PORT (PID $TUNNEL_PID)"
    else
        echo "Port forwarding not active"
    fi
}

# --- PARSE ARGUMENTS ---
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --model) MODEL="$2"; shift ;;
        --stop) ACTION="stop" ;;
        --status) ACTION="status" ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1"; usage; exit 1 ;;
    esac
    shift
done

# --- MAIN LOGIC ---
case $ACTION in
    start)
        start_ollama_service
        check_model_exists "$MODEL"
        run_model "$MODEL"

        # Forward port from GPU to local safely
        if lsof -iTCP:$LOCAL_PORT -sTCP:LISTEN -t >/dev/null; then
            echo "Local port $LOCAL_PORT is busy, killing old listener..."
            fuser -k $LOCAL_PORT/tcp
        fi


        echo "Forwarding GPU port $REMOTE_PORT -> local port $LOCAL_PORT..."
        ssh -f -N -L "$LOCAL_PORT":127.0.0.1:"$REMOTE_PORT" -J "$JUMP_HOST" "$GPU_HOST"
        echo "Port forwarding established."
        ;;
    stop)
        stop_all
        ;;
    status)
        status
        ;;
esac
