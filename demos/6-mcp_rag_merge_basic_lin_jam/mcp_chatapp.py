from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastmcp import FastMCP
import uvicorn
import re
import json
import psycopg2
from datetime import datetime
import traceback
import sys
import httpx
from rag_store import add_log
from llm_config import get_ollama_client, get_model_name

# Database configuration
DB_CONFIG = {
    "dbname": "rag_db",
    "user": "postgres",
    "password": "password",
    "host": "localhost",
    "port": "5432"
}

ollama_client = get_ollama_client()
LLM_MODEL = get_model_name()

# Simulation API endpoint
SIMULATION_API_URL = "http://127.0.0.1:5001"

# Create an MCP server
app = FastAPI()
mcp = FastMCP("Agent Movement and Simulation", app=app)

# Add CORS middleware to allow requests from all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup templates and static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Database functions from chatapp
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

# Define the command to handle agent movement - Updated to use API calls
@mcp.tool()
async def move_agent(agent: str, x: float, y: float) -> dict:
    """Move an agent to specific coordinates"""
    print(f"[ACTION] Move agent '{agent}' to ({x}, {y})")
    
    # Call the simulation API to move the agent
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{SIMULATION_API_URL}/move_agent",
                json={"agent": agent, "x": x, "y": y}
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Log the movement action to RAG store
                timestamp = datetime.now().isoformat()
                action_text = f"Moving agent {agent} to coordinates ({x}, {y})"
                
                add_log(action_text, {
                    "agent_id": agent,
                    "position": f"({x}, {y})",
                    "timestamp": timestamp,
                    "source": "mcp",
                    "action": "move",
                    "jammed": result.get("jammed", False)
                })
                
                return {
                    "success": True,
                    "message": f"Moving {agent} to coordinates ({x}, {y})",
                    "x": x,
                    "y": y,
                    "jammed": result.get("jammed", False),
                    "communication_quality": result.get("communication_quality", 1.0)
                }
            else:
                error_msg = f"Error moving agent: {response.text}"
                print(f"[API ERROR] {error_msg}")
                return {
                    "success": False,
                    "message": error_msg
                }
        except Exception as e:
            error_msg = f"Failed to connect to simulation API: {str(e)}"
            print(f"[CONNECTION ERROR] {error_msg}")
            return {
                "success": False,
                "message": error_msg
            }

# Direct API endpoint for simulation to call
@app.post("/move_agent_via_ollama")
async def move_agent_endpoint(request: Request):
    data = await request.json()
    agent = data.get("agent")
    x = float(data.get("x"))
    y = float(data.get("y"))
    
    result = await move_agent(agent, x, y)
    return result

# Process natural language commands - Updated to verify agents exist first
@app.post("/llm_command")
async def llm_command(request: Request):
    data = await request.json()
    command = data.get("message", "")

    print(f"[RECEIVED COMMAND] {command}")
    
    # Log the user command
    timestamp = datetime.now().isoformat()
    add_log(command, {
        "role": "user",
        "timestamp": timestamp,
        "agent_id": "user",
        "source": "command"
    })

    # First get the available agents from the simulation
    available_agents = {}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{SIMULATION_API_URL}/agents")
            if response.status_code == 200:
                available_agents = response.json().get("agents", {})
                print(f"[AVAILABLE AGENTS] {list(available_agents.keys())}")
    except Exception as e:
        print(f"[ERROR] Failed to fetch available agents: {e}")
        available_agents = {}

    # Format prompt for the LLM - Initial parsing
    prompt = f"""You are an AI that controls agents in a 2D simulation.

Available agents: {", ".join(available_agents.keys()) if available_agents else "No agents available"}

User command: "{command}"

Determine if the user wants to move one or more agents. For each movement, extract:
- agent name (must be one of the available agents)
- x coordinate
- y coordinate

If the user specifies "agent X" (where X is a number), the actual agent name is "agentX" (no space).

Respond in pure JSON array format:
[
    {{
        "understood": true/false,
        "action": "move" or "unknown",
        "agent": "agent name",
        "x": number,
        "y": number,
        "message": "summary of interpretation"
    }},
    ...
]

Only valid JSON. No extra text or explanations.
"""

    try:
        # Step 1: Initial LLM parsing
        response = ollama_client.chat(model=LLM_MODEL, messages=[
            {"role": "user", "content": prompt}
        ])
        raw_response = response['message']['content']
        print(f"[OLLAMA INITIAL RESPONSE] {raw_response}")

        # Extract clean JSON list
        json_match = re.search(r'\[.*\]', raw_response, re.DOTALL)
        parsed_list = json.loads(json_match.group(0)) if json_match else json.loads(raw_response)

        results = []
        for parsed in parsed_list:
            if parsed.get("understood") and parsed.get("action") == "move":
                # Format the agent name correctly (remove spaces if needed)
                agent_name = parsed["agent"].replace(" ", "")
                
                # Check if agent exists
                if agent_name not in available_agents and available_agents:
                    results.append({
                        "success": False,
                        "action": "unknown",
                        "message": f"Agent '{agent_name}' does not exist in the simulation"
                    })
                    continue
                
                # Step 2: Format the command for a function call
                x_coord = parsed["x"]
                y_coord = parsed["y"]
                
                # Log the interpreted command
                print(f"[INTERPRETED COMMAND] Move {agent_name} to ({x_coord}, {y_coord})")
                
                # Step 3: Have the LLM generate a function call
                function_prompt = f"""You are an AI that controls agents in a 2D simulation.
                
You need to generate a function call to move an agent.

The available function is:
```python
move_agent(agent: str, x: float, y: float) -> dict
```

Parameters:
- agent: The name of the agent to move (e.g. "agent1", "agent2")
- x: The x-coordinate to move to
- y: The y-coordinate to move to

Please generate a proper function call to move {agent_name} to coordinates ({x_coord}, {y_coord}).
Return only the function call and nothing else.

Example format: move_agent("agent1", 5.0, -3.5)
"""

                # Call LLM to generate function call
                func_response = ollama_client.chat(model=LLM_MODEL, messages=[
                    {"role": "user", "content": function_prompt}
                ])
                func_text = func_response['message']['content'].strip()
                print(f"[FUNCTION CALL] {func_text}")
                
                # Extract the function call parameters
                func_match = re.search(r'move_agent\s*\(\s*["\']([^"\']+)["\']?\s*,\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\)', func_text)
                
                if func_match:
                    agent_param = func_match.group(1)
                    x_param = float(func_match.group(2))
                    y_param = float(func_match.group(3))
                    
                    # Step 4: Execute the actual function call
                    move_result = await move_agent(agent_param, x_param, y_param)
                    
                    results.append({
                        "success": move_result.get("success", False),
                        "action": "move",
                        "agent": agent_param,
                        "x": x_param,
                        "y": y_param,
                        "message": move_result.get("message", f"Moving {agent_param} to ({x_param}, {y_param})")
                    })
                else:
                    results.append({
                        "success": False,
                        "action": "unknown",
                        "message": "Failed to generate valid function call"
                    })
            else:
                results.append({
                    "success": False,
                    "action": "unknown",
                    "message": parsed.get("message", "Command not understood")
                })
                
                # Log the failure
                add_log(f"Command not understood: {command}", {
                    "role": "system",
                    "timestamp": datetime.now().isoformat(),
                    "source": "command",
                    "success": False
                })

        return {"results": results}

    except Exception as e:
        print(f"[ERROR] {e}")
        traceback.print_exc()
        
        # Log the error
        add_log(f"Error processing command: {e}", {
            "role": "system",
            "timestamp": datetime.now().isoformat(),
            "source": "command",
            "error": str(e)
        })
        
        return {
            "success": False,
            "message": f"Error processing command: {e}"
        }

# Chat endpoint from Flask app now in FastAPI - Updated to incorporate simulation status
@app.post("/chat")
async def chat(request: Request):
    try:
        data = await request.json()
        user_message = data.get('message')
        if not user_message:
            return {"error": "No message provided"}
        
        # Get ALL logs for RAG context without limit
        logs = fetch_logs_from_db()
        print(f"Retrieved {len(logs)} logs for RAG context")
        
        # Get current simulation status
        sim_status = {}
        try:
            async with httpx.AsyncClient() as client:
                status_response = await client.get(f"{SIMULATION_API_URL}/status")
                if status_response.status_code == 200:
                    sim_status = status_response.json()
        except Exception as e:
            print(f"Error fetching simulation status: {e}")
            sim_status = {"error": str(e)}
        
        # Sort logs by timestamp for consistency
        logs_sorted = sorted(
            logs,
            key=lambda x: x.get("metadata", {}).get("timestamp", x.get("created_at", "")),
            reverse=True  # Most recent first
        )
        
        # Format context in a structured way
        simulation_context = []
        for log in logs_sorted:
            metadata = log.get("metadata", {})
            agent_id = metadata.get("agent_id", "Unknown")
            position = metadata.get("position", "Unknown")
            jammed = "JAMMED" if metadata.get("jammed", False) else "CLEAR"
            timestamp = metadata.get("timestamp", "Unknown time")
            text = log.get("text", "")
            
            # Create rich context entries
            entry = f"LOG: Agent {agent_id} at position {position} is {jammed} at {timestamp}: {text}"
            simulation_context.append(entry)
        
        # Add current simulation status
        if sim_status:
            simulation_context.append("\nCURRENT SIMULATION STATUS:")
            simulation_context.append(f"Running: {sim_status.get('running', 'Unknown')}")
            simulation_context.append(f"Iteration Count: {sim_status.get('iteration_count', 'Unknown')}")
            
            # Add current agent positions
            agent_positions = sim_status.get('agent_positions', {})
            if agent_positions:
                simulation_context.append("Current Agent Positions:")
                for agent_id, data in agent_positions.items():
                    jammed_status = "JAMMED" if data.get("jammed", False) else "CLEAR"
                    comm_quality = data.get("communication_quality", 0)
                    simulation_context.append(f"  {agent_id}: Position ({data.get('x', 0)}, {data.get('y', 0)}) - {jammed_status} - Comm Quality: {comm_quality:.2f}")
        
        # Format full context
        context_text = "\n".join(simulation_context)
        
        # Create a clear system prompt for the LLM
        system_prompt = "You are an assistant for a Multi-Agent Simulation system. Provide helpful, accurate information about the simulation based on the logs and current status."
        
        # Call the LLM with all information
        response = ollama_client.chat(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"SIMULATION LOGS AND STATUS:\n{context_text}\n\nUSER QUERY: {user_message}\n\nAnswer based only on information provided above."}
            ]
        )
        
        # Debug response
        print("\n===== LLM RESPONSE =====")
        print(f"Model: {response.model}")
        print("Content:", end=" ")
        if hasattr(response, 'message') and response.message:
            print(response.message.content)
        else:
            print("NO CONTENT")
        print("========================\n")
        
        # Extract response safely
        ollama_response = ""
        if hasattr(response, 'message') and response.message:
            if hasattr(response.message, 'content') and response.message.content:
                ollama_response = response.message.content
        
        # Ensure we got some response
        if not ollama_response.strip():
            ollama_response = "I'm unable to provide an answer based on the available logs and simulation status."
        
        # Log interaction
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
        
        return {"response": ollama_response}
    except Exception as e:
        print(f"ERROR in chat route: {e}")
        traceback.print_exc()
        return {"error": str(e), "error_type": type(e).__name__}

# Added new endpoint to get simulation parameters
@app.get("/simulation_info")
async def get_simulation_info():
    """Get information about the simulation configuration"""
    try:
        async with httpx.AsyncClient() as client:
            params_response = await client.get(f"{SIMULATION_API_URL}/simulation_params")
            agents_response = await client.get(f"{SIMULATION_API_URL}/agents")
            
            if params_response.status_code == 200 and agents_response.status_code == 200:
                params = params_response.json()
                agents = agents_response.json()
                
                return {
                    "simulation_params": params,
                    "agents": agents.get("agents", {})
                }
            else:
                return {
                    "error": "Failed to fetch simulation information",
                    "params_status": params_response.status_code,
                    "agents_status": agents_response.status_code
                }
    except Exception as e:
        print(f"Error fetching simulation info: {e}")
        return {"error": str(e)}

# Added control endpoints to start/pause/continue simulation
@app.post("/control/pause")
async def pause_simulation():
    """Pause the simulation via API"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{SIMULATION_API_URL}/control/pause")
            return response.json()
    except Exception as e:
        return {"error": str(e)}

@app.post("/control/continue")
async def continue_simulation():
    """Continue the simulation via API"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{SIMULATION_API_URL}/control/continue")
            return response.json()
    except Exception as e:
        return {"error": str(e)}

# LOG endpoints
@app.get("/logs")
async def get_logs():
    try:
        logs = fetch_logs_from_db(limit=100)
        return {
            "logs": logs,
            "has_more": False  # You could paginate in future
        }
    except Exception as e:
        print(f"Error in /logs route: {e}")
        return {"error": f"Internal server error: {str(e)}"}

@app.get("/log_count")
async def log_count():
    """
    Return the current number of logs in the system.
    """
    try:
        logs = fetch_logs_from_db()
        return {"log_count": len(logs)}
    except Exception as e:
        print("Error in /log_count route:", e)
        return {"error": "Internal server error"}

# Root endpoint to serve the HTML with Jinja2
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    try:
        return templates.TemplateResponse("index.html", {"request": request})
    except Exception as e:
        error_msg = f"ERROR: Could not render template 'index.html': {e}"
        print(error_msg)
        return HTMLResponse(content=f"<html><body>{error_msg}</body></html>", status_code=500)

@app.get("/test")
async def test():
    return {"message": "FastAPI server is running correctly!"}

# Health check endpoint that also verifies simulation API connectivity
@app.get("/health")
async def health_check():
    """Check if the server and simulation API are reachable"""
    try:
        # Check if simulation API is reachable
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{SIMULATION_API_URL}/")
            simulation_status = "online" if response.status_code == 200 else "offline"
    except Exception as e:
        simulation_status = f"unreachable: {str(e)}"
    
    return {
        "mcp_server": "online",
        "simulation_api": simulation_status,
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    print("Starting integrated MCP server with chat app...")
    print(f"Python version: {sys.version}")
    print("Visit http://127.0.0.1:5000")
    uvicorn.run(app, host="127.0.0.1", port=5000)