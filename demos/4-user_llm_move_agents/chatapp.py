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

# Define the tools available to the model
tools = [
    {
        "type": "function",
        "function": {
            "name": "move_agent",
            "description": "Moves an agent to the specified coordinates within the simulation",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_id": {
                        "type": "string",
                        "description": "The ID of the agent to move (e.g., 'agent1', '1')",
                    },
                    "target_x": {
                        "type": "number",
                        "description": "The target x-coordinate (-10 to 10)",
                    },
                    "target_y": {
                        "type": "number",
                        "description": "The target y-coordinate (-10 to 10)",
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
            "description": "Returns the current positions of all agents in the simulation",
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
    
    # Try the move pattern first
    match = re.search(move_pattern, user_message, re.IGNORECASE)
    if not match:
        # Try the send pattern
        match = re.search(send_pattern, user_message, re.IGNORECASE)
    
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

        # Fetch relevant logs for context
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
        
        # Get current agent positions for better context
        current_positions = get_agent_positions()
        positions_text = "\n".join([f"Agent {agent_id} is currently at position {pos}" 
                                   for agent_id, pos in current_positions.items()])

        # Create a clearer prompt for the LLM with stronger guidance
        prompt = f"""
You are an assistant for a Multi-Agent Simulation system. Users can ask you about the current state of the simulation 
and request you to move agents to new coordinates.

CURRENT SIMULATION STATE:
{positions_text}

RECENT LOG HISTORY:
{context_text}

IMPORTANT: When the user wants to move an agent, you MUST use the move_agent function to do so.
DO NOT respond with code snippets or explanations. Simply call the function with the appropriate parameters.

The move_agent function requires:
- agent_id: The ID of the agent (format: "agent1", "1", etc.)
- target_x: The target x-coordinate (between -10 and 10)
- target_y: The target y-coordinate (between -10 and 10)

If the user asks about agent positions, use the get_agent_positions function.

USER QUERY: {user_message}

Respond directly to the user's query based on the simulation state. If they ask to move an agent, call the appropriate function.
"""

        # First, check for a direct move command to handle it immediately if present
        move_command = parse_move_command(user_message)
        if move_command:
            agent_id, target_x, target_y = move_command
            print(f"[DEBUG] Direct parse of move command: {agent_id} to ({target_x}, {target_y})")
            try:
                result = move_agent(agent_id, target_x, target_y)
                return jsonify({
                    'response': f"Moving {agent_id} to ({target_x}, {target_y}).\n\n{result['message']}"
                })
            except Exception as e:
                print(f"Error moving agent directly: {e}")
                return jsonify({'response': f"Failed to move agent: {e}"})

        # If not a direct move command, try using the LLM with function calling
        response = ollama.chat(
            model=LLM_MODEL,
            messages=[{"role": "system", "content": prompt}],
            tools=tools
        )
        
        # Extract the message and any tool calls
        message = response.get('message', {})
        tool_calls = message.get('tool_calls', [])
        
        print(f"[DEBUG] LLM response: {message}")
        print(f"[DEBUG] Tool calls detected: {tool_calls}")
        
        # Process any function calls first
        if tool_calls:
            results = []
            for tool_call in tool_calls:
                function_name = tool_call.get('function', {}).get('name')
                arguments = json.loads(tool_call.get('function', {}).get('arguments', '{}'))
                
                print(f"[DEBUG] Function call: {function_name} with args: {arguments}")
                
                if function_name == "move_agent":
                    try:
                        result = move_agent(
                            arguments.get('agent_id'), 
                            arguments.get('target_x'), 
                            arguments.get('target_y')
                        )
                        results.append(result)
                    except Exception as e:
                        print(f"Error executing move_agent: {e}")
                        results.append({"success": False, "message": f"Error: {str(e)}"})
                
                elif function_name == "get_agent_positions":
                    try:
                        positions = get_agent_positions()
                        results.append({"success": True, "positions": positions})
                    except Exception as e:
                        print(f"Error getting agent positions: {e}")
                        results.append({"success": False, "message": f"Error: {str(e)}"})
            
            # Format the results for the user
            result_messages = [r.get('message', str(r)) for r in results if r.get('success', False)]
            if result_messages:
                # Lead with the action taken, then provide the LLM's response
                response_content = "Action completed:\n" + "\n".join(result_messages) + "\n\n" + message.get('content', '')
            else:
                response_content = message.get('content', '') + "\n\nI tried to perform an action but encountered an error."
                
            return jsonify({'response': response_content})
        
        # Check if we can still parse a move command from the LLM's response as fallback
        ollama_response = message.get('content', "Sorry, I didn't understand that.")
        move_command = parse_move_command(ollama_response)
        if move_command:
            agent_id, target_x, target_y = move_command
            print(f"[DEBUG] Parsed move command from LLM text: {agent_id} to ({target_x}, {target_y})")
            try:
                result = move_agent(agent_id, target_x, target_y)
                return jsonify({'response': f"Moving {agent_id} to ({target_x}, {target_y}).\n\n{result['message']}"})
            except Exception as e:
                print(f"Error moving agent: {e}")
                return jsonify({'response': ollama_response + f"\n\nFailed to move agent: {e}"})

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