# This is a simple Flask app that serves as a chat interface for an LLM (Large Language Model) and displaying logs.
from flask import Flask, render_template, request, jsonify, Response
import sys
import traceback
import hashlib
from datetime import datetime
import time
import pickle

from llm_config import get_ollama_client, get_model_name
ollama = get_ollama_client()
LLM_MODEL = get_model_name()

try:
    from rag_store import get_log_data, add_log, retrieve_relevant, get_chunk_path, get_latest_chunk_index
    print("Successfully imported rag_store functions")
except Exception as e:
    print(f"ERROR importing from rag_store: {e}")
    traceback.print_exc()

try:
    import numpy as np
    print("Successfully imported numpy")
except Exception as e:
    print(f"ERROR importing numpy: {e}")
    traceback.print_exc()

app = Flask(__name__)

@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        error_msg = f"ERROR: Could not render template 'index.html': {e}"
        print(error_msg)
        return error_msg, 500

@app.route('/test')
def test():
    return "Flask server is running correctly!"

@app.route('/chat', methods=['POST'])
def chat():
    try:
        user_message = request.json.get('message')
        if not user_message:
            return jsonify({'error': 'No message provided'}), 400

        # Get ALL recent logs for context
        logs = get_log_data()
        print(f"Retrieved {len(logs)} logs for context")
        
        logs_sorted = sorted(
            logs,
            key=lambda x: x.get("metadata", {}).get("timestamp", x.get("log_id", "")),
            reverse=True
        )
        
        # Provide rich context from simulation logs
        context_logs = logs_sorted[:15]  # Use up to 15 logs for better context
        
        # Format the context information in a clean way
        simulation_context = []
        for log in context_logs:
            agent_id = log.get("metadata", {}).get("agent_id", "Unknown")
            position = log.get("metadata", {}).get("position", "Unknown")
            jammed = "JAMMED" if log.get("metadata", {}).get("jammed", False) else "CLEAR"
            timestamp = log.get("metadata", {}).get("timestamp", "Unknown time")
            
            # Create a structured context entry
            entry = f"Agent {agent_id} at position {position} is {jammed} at {timestamp}"
            simulation_context.append(entry)
        
        # Join all context entries
        context_text = "\n".join(simulation_context)

        # Create a structured prompt
        prompt = f"""
You are an assistant for a Multi-Agent Simulation system. Users can ask you about the current state of the simulation.

CURRENT SIMULATION STATE:
{context_text}

USER QUERY: {user_message}

Respond to the user's query based on the simulation state information provided above.
"""

        # Call the LLM with the enhanced prompt
        response = ollama.chat(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}]
        )
        ollama_response = response.get('message', {}).get('content', "Sorry, I didn't understand that.")

        # Log both user message and bot response
        timestamp = datetime.now().isoformat()

        user_hash = hashlib.md5(user_message.encode()).hexdigest()[:8]
        response_hash = hashlib.md5(ollama_response.encode()).hexdigest()[:8]

        add_log(f"user-{user_hash}", user_message, {"role": "user", "timestamp": timestamp})
        add_log(f"ollama-{response_hash}", ollama_response, {"role": "ollama", "timestamp": timestamp})

        return jsonify({'response': ollama_response})

    except Exception as e:
        print(f"ERROR in chat route: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route("/logs")
def get_logs():
    try:
        # Get all logs from the most recent chunk only
        latest_chunk_index = get_latest_chunk_index()
        chunk_path = get_chunk_path(latest_chunk_index)
        
        if chunk_path.exists():
            with open(chunk_path, "rb") as f:
                logs = pickle.load(f)
                
            # Sort by timestamp if available
            logs_sorted = sorted(
                logs,
                key=lambda x: x.get("metadata", {}).get("timestamp", x.get("log_id", "")),
                reverse=True
            )
            
            print(f"Found {len(logs_sorted)} logs in latest chunk")
            
            # Return ALL logs from the chunk
            return jsonify({
                "logs": logs_sorted,
                "has_more": False  # Since we're returning all logs from the current chunk
            })
        else:
            print(f"No logs found at path: {chunk_path}")
            return jsonify({"logs": [], "has_more": False})
    except Exception as e:
        print(f"Error in /logs route: {e}")
        traceback.print_exc()
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@app.route("/log_count")
def log_count():
    """
    Return the current number of logs in the system.
    """
    try:
        logs = get_log_data()
        return jsonify({"log_count": len(logs)})
    except Exception as e:
        print("Error in /log_count route:", e)
        return jsonify({"error": "Internal server error"}), 500

@app.route("/stream_logs")
def stream_logs():
    """
    Stream live logs as they are added to the system.
    """
    def generate():
        while True:
            logs = get_log_data()
            logs_sorted = sorted(
                logs,
                key=lambda x: x.get("metadata", {}).get("timestamp", x.get("log_id", "")),
                reverse=True
            )
            latest_log = logs_sorted[0] if logs_sorted else None
            if latest_log:
                yield f"data: {latest_log}\n\n"
            time.sleep(1)  # Adjust the delay between streams if needed

    return Response(generate(), content_type='text/event-stream')

@app.route("/log_chunk/<int:chunk_index>")
def get_log_chunk(chunk_index):
    try:
        chunk_path = get_chunk_path(chunk_index)
        if not chunk_path.exists():
            return jsonify({"logs": [], "has_more": False})

        with open(chunk_path, "rb") as f:
            logs = pickle.load(f)

        logs_sorted = sorted(logs, key=lambda x: x.get("metadata", {}).get("timestamp", x.get("log_id", "")), reverse=True)
        print(f"Chunk {chunk_index} contains {len(logs_sorted)} logs")

        return jsonify({
            "logs": logs_sorted,
            "has_more": (chunk_index > 0)  # If index > 0, older chunks may exist
        })
    except Exception as e:
        print(f"Error in /log_chunk/{chunk_index}: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    print("Starting Flask app...")
    print(f"Python version: {sys.version}")
    print("Visit http://127.0.0.1:5000")
    app.run(debug=True)
