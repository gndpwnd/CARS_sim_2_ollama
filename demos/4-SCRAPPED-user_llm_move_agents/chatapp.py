# This is a Flask app that serves as a chat interface for an LLM to control agents in a simulation
from flask import Flask, render_template, request, jsonify
import sys
import traceback
from datetime import datetime
import psycopg2
import json
import re
from rag_store import retrieve_relevant
from sim import run_simulation_with_plots
import multiprocessing

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
    print(f"[DEBUG] Attempting to parse move command: {user_message}")
    
    # Direct pattern for "move agent1 to 5,5"
    direct_pattern = r"move\s+agent(\d+)\s+to\s+(\d+)\s*,\s*(\d+)"
    match = re.search(direct_pattern, user_message, re.IGNORECASE)
    
    if match:
        agent_num, x_str, y_str = match.groups()
        agent_id = f"agent{agent_num}"
        target_x = float(x_str)
        target_y = float(y_str)
        print(f"[DEBUG] Parsed command: agent_id={agent_id}, x={target_x}, y={target_y}")
        return agent_id, target_x, target_y
    
    print("[DEBUG] Failed to parse move command")
    return None

def process_waypoint_command(agent_id, target_x, target_y):
    """
    Process a waypoint command for an agent, ensuring the same behavior as the button.
    Returns a response message.
    """
    try:
        # Normalize agent_id format (if only number provided)
        if isinstance(agent_id, str) and agent_id.isdigit():
            agent_id = f"agent{agent_id}"
        
        # Make sure coordinates are floats
        target_x = float(target_x)
        target_y = float(target_y)
        
        # Add the waypoint using the same function the button uses
        success = add_waypoint(agent_id, target_x, target_y)
        
        if success:
            return f"Waypoint ({target_x}, {target_y}) added for {agent_id}. The agent will move to this waypoint."
        else:
            return f"Failed to add waypoint for {agent_id}. Please check if the agent exists."
    except Exception as e:
        print(f"[ERROR] Error in process_waypoint_command: {e}")
        return f"Error processing waypoint command: {str(e)}"

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
        
        # Process the waypoint command using the same function for consistency
        return process_waypoint_command(agent_id, target_x, target_y)
            
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

        # Ensure simulation is active
        simulation_status = check_simulation_status()
        print(f"[DEBUG] Simulation status: {simulation_status}")

        # Check for a direct move command to handle it as adding a waypoint
        move_command = parse_move_command(user_message)
        if move_command:
            agent_id, target_x, target_y = move_command
            print(f"[DEBUG] Direct parse of move command: {agent_id} to ({target_x}, {target_y})")

            # Use the process_waypoint_command function for consistent behavior
            response = process_waypoint_command(agent_id, target_x, target_y)
            return jsonify({'response': response})

        # If not a direct move command, use the LLM
        try:
            # Get the current agent positions for context
            current_positions = get_agent_positions()
            positions_text = "\n".join(
                f"Agent {agent_id} is currently at position {pos}" for agent_id, pos in current_positions.items()
            )
            
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
            
            # Create a clearer prompt with explicit instructions
            prompt = f"""
You are an assistant for a Multi-Agent Simulation system. Your main role is to help users control agents by adding waypoints.

CURRENT SIMULATION STATE:
{positions_text}

RECENT LOG HISTORY:
{context_text}

USER QUERY: {user_message}

VERY IMPORTANT INSTRUCTIONS:
1. If the user wants to move an agent to a specific location, you MUST use the `add_waypoint` function call.
2. DO NOT respond with text instructions like "I'll move agent1 to (5,5)" - you MUST use the function call.
3. The `add_waypoint` function requires:
   - `agent_id`: A string like "agent1" or just "1" (will be converted to "agent1").
   - `target_x`: The x-coordinate (must be between -10 and 10).
   - `target_y`: The y-coordinate (must be between -10 and 10).
4. If the user asks for the current positions of agents, you MUST use the `get_agent_positions` function call.
5. Always ensure that the behavior of the `add_waypoint` function matches the behavior of the "Move Agent1" button in the Matplotlib plot.

EXAMPLES OF WHEN TO USE `add_waypoint`:
- "Move agent1 to coordinates (5,5)"
- "Send agent 2 to position (-3,4)"
- "Place agent3 at x=2, y=-7"
- "Can you relocate agent 1 to the point (4,4)?"

EXAMPLES OF WHEN TO USE `get_agent_positions`:
- "Where is agent1 currently?"
- "What are the positions of all agents?"
- "Can you tell me where agent2 is?"

Remember:
- ALWAYS use function calls instead of text-based responses for agent control actions.
- Ensure the function calls are consistent with the behavior of the simulation's UI buttons.
"""

            # Call the LLM with tools enabled and force tool usage when appropriate
            response = ollama.chat(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_message}
                ],
                tools=tools,
                tool_choice={"type": "auto"}
            )

            # Process the LLM response
            response_content = response.get('message', {}).get('content', '')
            tool_calls = response.get('message', {}).get('tool_calls', [])
            
            print(f"[DEBUG] LLM response: {response}")
            print(f"[DEBUG] Tool calls: {tool_calls}")
            
            # Execute any tool calls
            tool_call_results = []
            for tool_call in tool_calls:
                try:
                    result = execute_tool_call(tool_call)
                    tool_call_results.append(result)
                except Exception as e:
                    print(f"Error executing tool call: {e}")
                    tool_call_results.append(f"Error: {str(e)}")
            
            # Check if user asked about agent positions but LLM didn't use tool call
            if not tool_calls and ('position' in user_message.lower() or 
                                  'where' in user_message.lower() and 'agent' in user_message.lower()):
                positions = get_agent_positions()
                positions_text = "\n".join(
                    f"Agent {agent_id} is currently at position {pos}" for agent_id, pos in positions.items()
                )
                if response_content:
                    response_content += f"\n\nCurrent agent positions:\n{positions_text}"
                else:
                    response_content = f"Current agent positions:\n{positions_text}"
            
            # Combine LLM response with tool call results
            final_response = response_content
            if tool_call_results:
                if final_response:
                    final_response += "\n\n" + "\n".join(tool_call_results)
                else:
                    final_response = "\n".join(tool_call_results)
                    
            # If no response and no tool calls, use a fallback response
            if not final_response and not tool_calls:
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
    print(f"Python version: {sys.version}")
    print("Starting Flask app and simulation...")

    # Start the simulation in a separate process
    simulation_process = multiprocessing.Process(target=run_simulation_with_plots)
    simulation_process.start()

    # Start the Flask app in the main process
    try:
        app.run(debug=True, use_reloader=False)  # Disable the auto-reloader so simulation does not start twice
    finally:
        # Ensure the simulation process is terminated when Flask exits
        simulation_process.terminate()
        simulation_process.join()
