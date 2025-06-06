# This is a simple Flask app that serves as a chat interface for an LLM (Large Language Model) and displaying logs.
from flask import Flask, render_template, request, jsonify
import sys
import traceback
import hashlib
from datetime import datetime
import psycopg2
import json
from datetime import datetime
from rag_store import add_log


from llm_config import get_ollama_client, get_model_name
ollama = get_ollama_client()
LLM_MODEL = get_model_name()

NUM_LOGS_CONTEXT = 30  # Number of logs to fetch from DB
NUM_LOGS_FOR_LLM = 25  # Number of logs to include in LLM context

DB_CONFIG = {
    "dbname": "rag_db",
    "user": "postgres",
    "password": "password",
    "host": "localhost",
    "port": "5432"
}

def fetch_logs_from_db(limit=None):
    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                query = "SELECT id, text, metadata, created_at FROM logs"
                if limit:
                    query += f" ORDER BY created_at DESC LIMIT {limit}"
                else:
                    query += " ORDER BY created_at DESC"
                cur.execute(query)
                rows = cur.fetchall()
                
                logs = []
                for row in rows:
                    log_id, content, metadata_json, created_at = row
                    metadata = json.loads(metadata_json) if isinstance(metadata_json, str) else metadata_json
                    logs.append({
                        "log_id": str(log_id),
                        "text": content,
                        "metadata": metadata,
                        "created_at": created_at.isoformat()
                    })
                return logs
    except Exception as e:
        print(f"Error fetching logs from DB: {e}")
        return []

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
        logs = fetch_logs_from_db(limit=NUM_LOGS_CONTEXT)
        print(f"Retrieved {len(logs)} logs for context")
        
        logs_sorted = sorted(
            logs,
            key=lambda x: x.get("metadata", {}).get("timestamp", x.get("log_id", "")),
            reverse=True
        )
        
        # Provide rich context from simulation logs
        context_logs = logs_sorted[:NUM_LOGS_FOR_LLM]  # use up to this many logs for context
        
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
            messages=[{"role": "system", "content": prompt}]
        )
        ollama_response = response.get('message', {}).get('content', "Sorry, I didn't understand that.")

        # Log both user message and bot response
        timestamp = datetime.now().isoformat()

        add_log(user_message, {
            "role": "user",
            "timestamp": timestamp,
            "agent_id": "user",
            "source": "chat"
        })

        add_log(ollama_response, {
            "role": "assistant",
            "timestamp": timestamp,
            "agent_id": "ollama",
            "source": "chat"
        })


        return jsonify({'response': ollama_response})

    except Exception as e:
        print(f"ERROR in chat route: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route("/logs")
def get_logs():
    try:
        logs = fetch_logs_from_db(limit=100)
        return jsonify({
            "logs": logs,
            "has_more": False  # You could paginate in future
        })
    except Exception as e:
        print(f"Error in /logs route: {e}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@app.route("/log_count")
def log_count():
    """
    Return the current number of logs in the system.
    """
    try:
        logs = fetch_logs_from_db()
        return jsonify({"log_count": len(logs)})
    except Exception as e:
        print("Error in /log_count route:", e)
        return jsonify({"error": "Internal server error"}), 500



if __name__ == '__main__':
    print("Starting Flask app...")
    print(f"Python version: {sys.version}")
    print("Visit http://127.0.0.1:5000")
    app.run(debug=True)
