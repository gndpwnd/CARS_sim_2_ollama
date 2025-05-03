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
# In the move_agent tool function:
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
                
                # Format the response message
                if result.get("jammed", False):
                    message = (f"Agent {agent} is currently jammed (Comm quality: {result.get('communication_quality', 0.2)}). "
                             f"It will first return to its last safe position at {result.get('current_position')} "
                             f"before proceeding to ({x}, {y}).")
                else:
                    message = f"Moving {agent} to coordinates ({x}, {y}). Current position: {result.get('current_position')}"
                
                return {
                    "success": True,
                    "message": message,
                    "x": x,
                    "y": y,
                    "jammed": result.get("jammed", False),
                    "communication_quality": result.get("communication_quality", 1.0),
                    "current_position": result.get("current_position")
                }
            else:
                error_msg = f"Error moving agent: {response.text}"
                print(f"[API ERROR] {error_msg}")
                return {
                    "success": False,
                    "message": error_msg
                }
        except Exception as e:
            error_msg = f"Exception occurred while moving agent: {str(e)}"
            print(f"[EXCEPTION] {error_msg}")
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

    # Format prompt for the LLM - now focused on extracting movement commands
    prompt = f"""You are an AI that controls agents in a 2D simulation.

Available agents: {", ".join(available_agents.keys()) if available_agents else "No agents available"}

User command: "{command}"

If this is a movement command, extract:
1. The agent name (must match an available agent)
2. The x coordinate (number)
3. The y coordinate (number)

Respond ONLY with the agent name and coordinates in this exact format:
agent_name,x,y

If it's not a movement command, respond with: "Not a movement command"
"""

    try:
        # Get LLM response
        response = ollama_client.chat(model=LLM_MODEL, messages=[
            {"role": "user", "content": prompt}
        ])
        
        raw_response = response['message']['content'].strip()
        print(f"[OLLAMA RESPONSE] {raw_response}")

        # Check if response matches our expected movement command format
        if "," in raw_response and len(raw_response.split(",")) == 3:
            agent_name, x_str, y_str = raw_response.split(",")
            agent_name = agent_name.strip()
            
            # Validate agent exists
            if agent_name not in available_agents:
                return {"response": f"Error: Agent '{agent_name}' not found in simulation"}
            
            try:
                x = float(x_str.strip())
                y = float(y_str.strip())
                
                # Actually execute the movement
                move_result = await move_agent(agent_name, x, y)
                
                if move_result.get("success"):
                    return {"response": f"Moving {agent_name} to ({x}, {y}). {move_result.get('message', '')}"}
                else:
                    return {"response": f"Failed to move {agent_name}: {move_result.get('message', 'Unknown error')}"}
            
            except ValueError:
                return {"response": f"Invalid coordinates: {x_str}, {y_str}"}
        
        # Not a movement command or invalid format
        return {"response": raw_response if raw_response else "Command not understood"}

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
            "response": f"Error processing command: {e}"
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
        
        # Check for duplicate commands (issued within last 10 seconds)
        for log in logs_sorted[:5]:  # Check most recent 5 logs
            metadata = log.get("metadata", {})
            if metadata.get("role") == "user" and metadata.get("source") == "command":
                recent_time = metadata.get("timestamp")
                recent_text = log.get("text", "")
                if recent_time and (datetime.now() - datetime.fromisoformat(recent_time)).total_seconds() < 10:
                    if recent_text.lower() == user_message.lower():
                        print(f"Detected duplicate command processing: '{user_message}'")
                        return {"response": ""}  # Empty response for duplicates
        
        # Create a clear system prompt for the LLM
        system_prompt = """You are an assistant for a Multi-Agent Simulation system. Provide helpful, accurate information about the simulation based on the logs and current status.

Keep your responses concise and focused on answering the user's questions.
- If the user is asking about agent positions or statuses, give them the current information
- Don't recite all the log history unless specifically asked
- For questions about recent commands, just give a brief status update
"""
        
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