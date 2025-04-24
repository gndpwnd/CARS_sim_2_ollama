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
    check_simulation_status, 
    get_agent_positions,
    add_waypoint
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

def execute_tool_call(tool_call):
    """
    Execute a tool call from the LLM and return the result
    """
    function_name = tool_call['function']['name']
    arguments = json.loads(tool_call['function']['arguments'])
    
    if function_name == 'add_waypoint':
        agent_id = arguments.get('agent_id')
        target_x = float(arguments.get('target_x', 0))
        target_y = float(arguments.get('target_y', 0))
        
        # Make sure agent_id has the correct format
        if agent_id and not agent_id.startswith('agent') and agent_id.isdigit():
            agent_id = f"agent{agent_id}"
        
        print(f"[DEBUG] Executing add_waypoint with {agent_id}, {target_x}, {target_y}")
        success = add_waypoint(agent_id, target_x, target_y)
        
        if success:
            return f"Waypoint ({target_x}, {target_y}) added for {agent_id}. The agent will move to this waypoint."
        else:
            return f"Failed to add waypoint for {agent_id}. Please check if the agent exists."
            
    elif function_name == 'get_agent_positions':
        positions = get_agent_positions()
        positions_text = "\n".join(
            f"Agent {agent_id} is currently at position {pos}" for agent_id, pos in positions.items()
        )
        return f"Current agent positions:\n{positions_text}"
    
    return f"Unknown tool call: {function_name}"

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
                success = add_waypoint(agent_id, target_x, target_y)
                if success:
                    return jsonify({
                        'response': f"Waypoint ({target_x}, {target_y}) added for {agent_id}. The agent will move to this waypoint."
                    })
                else:
                    return jsonify({
                        'response': f"Failed to add waypoint for {agent_id}. Please check if the agent exists."
                    })
            except Exception as e:
                print(f"Error adding waypoint: {e}")
                return jsonify({'response': f"Failed to add waypoint: {e}"})

        # If not a direct move command, use the LLM
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

            # Create a prompt for the LLM with explicit instructions about function calling
            prompt = f"""
You are an assistant for a Multi-Agent Simulation system. Users can ask you about the current state of the simulation 
and request you to add waypoints for agents. The simulation will handle moving agents to their waypoints.

CURRENT SIMULATION STATE:
{positions_text}

RECENT LOG HISTORY:
{context_text}

USER QUERY: {user_message}

IMPORTANT INSTRUCTIONS FOR FUNCTION CALLING:
- If the user wants to move an agent or add a waypoint, ALWAYS use the add_waypoint function
- The add_waypoint function takes agent_id (string), target_x (number), and target_y (number)
- If the agent ID is a number, format it as "agent{number}" (e.g., "agent1")
- Coordinates must be between -10 and 10 for both x and y

Respond directly to the user's query based on the simulation state. If they ask to move an agent, ALWAYS use the add_waypoint function call.
"""

            # Call the LLM with tools enabled
            response = ollama.chat(
                model=LLM_MODEL,
                messages=[{"role": "system", "content": prompt}],
                tools=tools
            )

            # Process the LLM response
            response_content = response.get('message', {}).get('content', '')
            tool_calls = response.get('message', {}).get('tool_calls', [])
            
            # Execute any tool calls
            tool_call_results = []
            for tool_call in tool_calls:
                try:
                    result = execute_tool_call(tool_call)
                    tool_call_results.append(result)
                except Exception as e:
                    print(f"Error executing tool call: {e}")
                    tool_call_results.append(f"Error: {str(e)}")
            
            # Combine LLM response with tool call results
            final_response = response_content
            if tool_call_results:
                if final_response:
                    final_response += "\n\n" + "\n".join(tool_call_results)
                else:
                    final_response = "\n".join(tool_call_results)
                    
            # If no response and no tool calls, provide a fallback
            if not final_response:
                final_response = "I couldn't understand your request. Please try rephrasing or use more specific instructions."
                
            return jsonify({'response': final_response})

        except Exception as e:
            print(f"Error calling LLM: {e}")
            traceback.print_exc()
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