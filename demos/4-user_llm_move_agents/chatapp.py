# This is a Flask app that serves as a chat interface for an LLM to control agents in a simulation
from flask import Flask, render_template, request, jsonify
import sys
import traceback
from datetime import datetime
import psycopg2
import json
import re
from rag_store import retrieve_relevant

# Import simulation functions
from simulation_controller import (
    move_agent, 
    check_simulation_status, 
    swarm_pos_dict,
    initialize_agents,
    start_simulation,
    get_agent_positions
)

from llm_config import get_ollama_client, get_model_name
ollama = get_ollama_client()
LLM_MODEL = get_model_name()

NUM_LOGS_CONTEXT = 30  # Number of logs to fetch from DB
NUM_LOGS_FOR_LLM = 20  # Number of logs to use for LLM context

DB_CONFIG = {
    "dbname": "rag_db",
    "user": "postgres",
    "password": "password",
    "host": "localhost",
    "port": "5432"
}

# Define the tools available to the model with improved descriptions
tools = [
    {
        "type": "function",
        "function": {
            "name": "add_waypoint",
            "description": "Adds a waypoint for an agent. The agent will move to the waypoint autonomously. Once the waypoint is reached, the agent will proceed to the next waypoint or resume random movement.",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_id": {
                        "type": "string",
                        "description": "The ID of the agent to add the waypoint for (e.g., 'agent1', '1').",
                    },
                    "target_x": {
                        "type": "number",
                        "description": "The x-coordinate of the waypoint (-10 to 10).",
                    },
                    "target_y": {
                        "type": "number",
                        "description": "The y-coordinate of the waypoint (-10 to 10).",
                    },
                },
                "required": ["agent_id", "target_x", "target_y"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_agent_positions",
            "description": "Returns the current positions of all agents in the simulation, including their movement status and destination if applicable.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    }
]

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
        # Make sure simulation is active when someone loads the page
        check_simulation_status()
        return render_template('index.html')
    except Exception as e:
        error_msg = f"ERROR: Could not render template 'index.html': {e}"
        print(error_msg)
        return error_msg, 500

@app.route('/test')
def test():
    return "Flask server is running correctly!"

def parse_move_command(user_message):
    """
    Manually parse move commands if the LLM doesn't use function calling.
    Returns agent_id, target_x, target_y if successful, None otherwise.
    """
    # Match patterns like: move agent4 to 5,5 or move agent4 to (5,5)
    move_pattern = r"move (?:agent)?(\d+) to (?:\()?(-?\d+\.?\d*)[,\s]+(-?\d+\.?\d*)(?:\))?"
    
    # Match patterns like: send agent3 to position x=6,y=-7
    send_pattern = r"send (?:agent)?(\d+) to position x=(-?\d+\.?\d*)[,\s]*y=(-?\d+\.?\d*)"
    
    # Match patterns like: agent2 go to coordinates 4,8
    go_pattern = r"(?:agent)?(\d+) go to coordinates (?:\()?(-?\d+\.?\d*)[,\s]+(-?\d+\.?\d*)(?:\))?"
    
    # Try each pattern in sequence
    for pattern in [move_pattern, send_pattern, go_pattern]:
        match = re.search(pattern, user_message, re.IGNORECASE)
        if match:
            agent_num, x_str, y_str = match.groups()
            agent_id = f"agent{agent_num}"
            target_x = float(x_str)
            target_y = float(y_str)
            return agent_id, target_x, target_y
    
    return None

@app.route('/chat', methods=['POST'])
def chat():
    try:
        user_message = request.json.get('message')
        if not user_message:
            return jsonify({'error': 'No message provided'}), 400

        # Check for a direct move command to handle it as adding a waypoint
        move_command = parse_move_command(user_message)
        if move_command:
            agent_id, target_x, target_y = move_command
            print(f"[DEBUG] Direct parse of move command: {agent_id} to ({target_x}, {target_y})")
            try:
                # Add the waypoint for the agent
                from simulation_controller import add_waypoint
                add_waypoint(agent_id, target_x, target_y)
                return jsonify({
                    'response': f"Waypoint ({target_x}, {target_y}) added for {agent_id}. The agent will move to this waypoint."
                })
            except Exception as e:
                print(f"Error adding waypoint: {e}")
                return jsonify({'response': f"Failed to add waypoint: {e}"})

        # Check if the user wants to retrieve agent positions
        if "agent positions" in user_message.lower() or "current positions" in user_message.lower():
            try:
                positions = get_agent_positions()
                positions_text = "\n".join(
                    f"Agent {agent_id} is currently at position {pos}" for agent_id, pos in positions.items()
                )
                return jsonify({'response': f"Current agent positions:\n{positions_text}"})
            except Exception as e:
                print(f"Error retrieving agent positions: {e}")
                return jsonify({'response': f"Failed to retrieve agent positions: {e}"})

        # If not a direct move command or position request, use the LLM for other queries
        try:
            # Fetch relevant logs and context for the LLM
            logs = retrieve_relevant(user_message, k=NUM_LOGS_FOR_LLM)
            simulation_context = []
            for log in logs:
                agent_id = log.get("metadata", {}).get("agent_id", "Unknown")
                position = log.get("metadata", {}).get("position", "Unknown")
                jammed = "JAMMED" if log.get("metadata", {}).get("jammed", False) else "CLEAR"
                timestamp = log.get("metadata", {}).get("timestamp", "Unknown time")
                entry = f"Agent {agent_id} at position {position} is {jammed} at {timestamp}"
                simulation_context.append(entry)

            context_text = "\n".join(simulation_context)
            current_positions = get_agent_positions()
            positions_text = "\n".join(
                f"Agent {agent_id} is currently at position {pos}" for agent_id, pos in current_positions.items()
            )

            # Create a prompt for the LLM
            prompt = f"""
You are an assistant for a Multi-Agent Simulation system. Users can ask you about the current state of the simulation 
and request you to add waypoints for agents. The simulation will handle moving agents to their waypoints.

CURRENT SIMULATION STATE:
{positions_text}

RECENT LOG HISTORY:
{context_text}

USER QUERY: {user_message}

Respond directly to the user's query based on the simulation state. If they ask to move an agent, add a waypoint for the agent.
"""

            # Call the LLM
            response = ollama.chat(
                model=LLM_MODEL,
                messages=[{"role": "system", "content": prompt}],
                tools=tools
            )
            return jsonify({'response': response.get('message', {}).get('content', "Sorry, I didn't understand that.")})

        except Exception as e:
            print(f"Error calling LLM: {e}")
            return jsonify({'response': f"There was an error processing your request with the language model: {str(e)}"})

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
            "has_more": False
        })
    except Exception as e:
        print(f"Error in /logs route: {e}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@app.route("/log_count")
def log_count():
    """Return the current number of logs in the system."""
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
    # Initialize the simulation when the app starts
    app.run(debug=True)