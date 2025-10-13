from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, StreamingResponse
from fastmcp import FastMCP
import uvicorn
import json
import psycopg2
from datetime import datetime
import traceback
import sys
import httpx
import asyncio
from rag_store import add_log
from llm_config import get_ollama_client, get_model_name

# Try to import Qdrant
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct
    QDRANT_ENABLED = True
except ImportError:
    QDRANT_ENABLED = False
    print("[WARNING] Qdrant not available. Install with: pip install qdrant-client")

# Database configuration
DB_CONFIG = {
    "dbname": "rag_db",
    "user": "postgres",
    "password": "password",
    "host": "localhost",
    "port": "5432"
}

# Qdrant configuration
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
COLLECTION_NAME = "simulation_logs"

ollama_client = get_ollama_client()
LLM_MODEL = get_model_name()

# Simulation API endpoint
SIMULATION_API_URL = "http://0.0.0.0:5001"

# Create an MCP server
app = FastAPI()
mcp = FastMCP("Agent Movement and Simulation", app=app)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup templates and static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize Qdrant client
qdrant_client = None
if QDRANT_ENABLED:
    try:
        qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        # Create collection if it doesn't exist
        try:
            qdrant_client.get_collection(COLLECTION_NAME)
            print(f"[QDRANT] Connected to collection '{COLLECTION_NAME}'")
        except:
            qdrant_client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE)
            )
            print(f"[QDRANT] Created new collection '{COLLECTION_NAME}'")
    except Exception as e:
        print(f"[QDRANT] Failed to connect: {e}")
        qdrant_client = None

# Database functions
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
                        "created_at": created_at.isoformat(),
                        "source": "postgresql"
                    })
                return logs
    except Exception as e:
        print(f"Error fetching logs from DB: {e}")
        return []

def fetch_logs_from_qdrant(limit=50):
    """Fetch logs from Qdrant vector database"""
    if not qdrant_client:
        return []
    
    try:
        # Search for all points (no vector filtering)
        results = qdrant_client.scroll(
            collection_name=COLLECTION_NAME,
            limit=limit,
            with_payload=True,
            with_vectors=False
        )[0]
        
        logs = []
        for point in results:
            payload = point.payload
            logs.append({
                "log_id": str(point.id),
                "text": payload.get("text", ""),
                "metadata": payload.get("metadata", {}),
                "created_at": payload.get("timestamp", datetime.now().isoformat()),
                "source": "qdrant",
                "vector_score": None
            })
        
        return logs
    except Exception as e:
        print(f"Error fetching from Qdrant: {e}")
        return []

# Move agent tool
@mcp.tool()
async def move_agent(agent: str, x: float, y: float) -> dict:
    """Move an agent to specific coordinates"""
    print(f"[ACTION] Move agent '{agent}' to ({x}, {y})")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{SIMULATION_API_URL}/move_agent",
                json={"agent": agent, "x": x, "y": y}
            )
            
            if response.status_code == 200:
                result = response.json()
                
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
                
                if result.get("jammed", False):
                    message = (f"Agent {agent} is currently jammed (Comm quality: {result.get('communication_quality', 0.2)}). "
                             f"It will first return to its last safe position at {result.get('current_position')} "
                             f"before proceeding to ({x}, {y}).")
                else:
                    message = f"Moving {agent} to coordinates ({x}, {y})."
                
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

# Process natural language commands
@app.post("/llm_command")
async def llm_command(request: Request):
    data = await request.json()
    command = data.get("message", "")

    print(f"[RECEIVED COMMAND] {command}")
    
    timestamp = datetime.now().isoformat()
    add_log(command, {
        "role": "user",
        "timestamp": timestamp,
        "agent_id": "user",
        "source": "command"
    })

    available_agents = {}
    live_agent_data = {}
    try:
        async with httpx.AsyncClient() as client:
            agents_response = await client.get(f"{SIMULATION_API_URL}/agents")
            status_response = await client.get(f"{SIMULATION_API_URL}/status")
            
            if agents_response.status_code == 200:
                available_agents = agents_response.json().get("agents", {})
                print(f"[AVAILABLE AGENTS] {list(available_agents.keys())}")
            
            if status_response.status_code == 200:
                live_agent_data = status_response.json()
                print(f"[LIVE AGENT DATA] Retrieved for {len(live_agent_data.get('agent_positions', {}))} agents")
    except Exception as e:
        print(f"[ERROR] Failed to fetch agent data: {e}")
        available_agents = {}
        live_agent_data = {}

    prompt = f"""You are an AI that controls agents in a 2D simulation.

Available agents: {", ".join(available_agents.keys()) if available_agents else "No agents available"}

User command: "{command}"

LIVE AGENT STATUS:
{format_live_agent_data(live_agent_data)}

If this is a movement command, extract:
1. The agent name (must match an available agent)
2. The x coordinate (number)
3. The y coordinate (number)

Respond ONLY with the agent name and coordinates in this exact format:
agent_name,x,y

If it's not a movement command, respond with: "Not a movement command"
"""

    try:
        response = ollama_client.chat(model=LLM_MODEL, messages=[
            {"role": "user", "content": prompt}
        ])
        
        raw_response = response['message']['content'].strip()
        print(f"[OLLAMA RESPONSE] {raw_response}")

        if "," in raw_response and len(raw_response.split(",")) == 3:
            agent_name, x_str, y_str = raw_response.split(",")
            agent_name = agent_name.strip()
            
            if agent_name not in available_agents:
                return {"response": f"Error: Agent '{agent_name}' not found in simulation"}
            
            try:
                x = float(x_str.strip())
                y = float(y_str.strip())
                
                move_result = await move_agent(agent_name, x, y)
                
                if move_result.get("success"):
                    response_data = {
                        "response": f"Moving {agent_name} to ({x}, {y}). {move_result.get('message', '')}",
                        "live_data": {
                            agent_name: live_agent_data.get('agent_positions', {}).get(agent_name)
                        }
                    }
                    return response_data
                else:
                    return {"response": f"Failed to move {agent_name}: {move_result.get('message', 'Unknown error')}"}
            
            except ValueError:
                return {"response": f"Invalid coordinates: {x_str}, {y_str}"}
        
        return {"response": raw_response if raw_response else "Command not understood"}

    except Exception as e:
        print(f"[ERROR] {e}")
        traceback.print_exc()
        
        add_log(f"Error processing command: {e}", {
            "role": "system",
            "timestamp": datetime.now().isoformat(),
            "source": "command",
            "error": str(e)
        })
        
        return {
            "response": f"Error processing command: {e}"
        }

def format_live_agent_data(live_data):
    """Format live agent data for LLM prompt"""
    if not live_data or not live_data.get('agent_positions'):
        return "No live agent data available"
    
    formatted = []
    for agent_id, data in live_data['agent_positions'].items():
        status = "JAMMED" if data.get('jammed', False) else "CLEAR"
        comm_quality = data.get('communication_quality', 0)
        pos = data.get('position', {})
        formatted.append(
            f"{agent_id}: Position ({pos.get('x', '?')}, {pos.get('y', '?')}) - {status} - Comm: {comm_quality:.2f}"
        )
    
    return "\n".join(formatted)

# Chat endpoint with streaming
@app.post("/chat")
async def chat(request: Request):
    try:
        data = await request.json()
        user_message = data.get('message')
        if not user_message:
            return {"error": "No message provided"}
        
        logs = fetch_logs_from_db()
        print(f"Retrieved {len(logs)} logs for RAG context")
        
        sim_status = {}
        try:
            async with httpx.AsyncClient() as client:
                status_response = await client.get(f"{SIMULATION_API_URL}/status")
                if status_response.status_code == 200:
                    sim_status = status_response.json()
        except Exception as e:
            print(f"Error fetching simulation status: {e}")
            sim_status = {"error": str(e)}
        
        logs_sorted = sorted(
            logs,
            key=lambda x: x.get("metadata", {}).get("timestamp", x.get("created_at", "")),
            reverse=True
        )
        
        simulation_context = []
        for log in logs_sorted:
            metadata = log.get("metadata", {})
            agent_id = metadata.get("agent_id", "Unknown")
            position = metadata.get("position", "Unknown")
            jammed = "JAMMED" if metadata.get("jammed", False) else "CLEAR"
            timestamp = metadata.get("timestamp", "Unknown time")
            text = log.get("text", "")
            
            entry = f"LOG: Agent {agent_id} at position {position} is {jammed} at {timestamp}: {text}"
            simulation_context.append(entry)
        
        if sim_status:
            simulation_context.append("\nCURRENT SIMULATION STATUS:")
            simulation_context.append(f"Running: {sim_status.get('running', 'Unknown')}")
            simulation_context.append(f"Iteration Count: {sim_status.get('iteration_count', 'Unknown')}")
            
            agent_positions = sim_status.get('agent_positions', {})
            if agent_positions:
                simulation_context.append("Current Agent Positions:")
                for agent_id, data in agent_positions.items():
                    jammed_status = "JAMMED" if data.get("jammed", False) else "CLEAR"
                    comm_quality = data.get("communication_quality", 0)
                    simulation_context.append(f"  {agent_id}: Position ({data.get('x', 0)}, {data.get('y', 0)}) - {jammed_status} - Comm Quality: {comm_quality:.2f}")
        
        context_text = "\n".join(simulation_context)
        
        system_prompt = """You are an assistant for a Multi-Agent Simulation system. Provide helpful, accurate information about the simulation based on the logs and current status.

Keep your responses concise and focused on answering the user's questions.
- If the user is asking about agent positions or statuses, give them the current information
- Don't recite all the log history unless specifically asked
- For questions about recent commands, just give a brief status update
"""
        
        response = ollama_client.chat(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"SIMULATION LOGS AND STATUS:\n{context_text}\n\nUSER QUERY: {user_message}\n\nAnswer based only on information provided above."}
            ]
        )
        
        ollama_response = ""
        if hasattr(response, 'message') and response.message:
            if hasattr(response.message, 'content') and response.message.content:
                ollama_response = response.message.content
        
        if not ollama_response.strip():
            ollama_response = "I'm unable to provide an answer based on the available logs and simulation status."
        
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

# Server-Sent Events for real-time streaming
@app.get("/stream/postgresql")
async def stream_postgresql():
    """Stream PostgreSQL logs in real-time"""
    async def event_generator():
        last_check_time = datetime.now()
        
        while True:
            try:
                logs = fetch_logs_from_db(limit=10)
                
                for log in logs:
                    log_time = datetime.fromisoformat(log.get("created_at", datetime.now().isoformat()))
                    if log_time > last_check_time:
                        yield f"data: {json.dumps(log)}\n\n"
                
                last_check_time = datetime.now()
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"Error in PostgreSQL stream: {e}")
                await asyncio.sleep(1)
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/stream/qdrant")
async def stream_qdrant():
    """Stream Qdrant logs in real-time"""
    async def event_generator():
        last_count = 0
        
        while True:
            try:
                if qdrant_client:
                    logs = fetch_logs_from_qdrant(limit=10)
                    
                    if len(logs) > last_count:
                        for log in logs[:len(logs) - last_count]:
                            yield f"data: {json.dumps(log)}\n\n"
                    
                    last_count = len(logs)
                else:
                    yield f"data: {json.dumps({'error': 'Qdrant not available'})}\n\n"
                
                await asyncio.sleep(2)
                
            except Exception as e:
                print(f"Error in Qdrant stream: {e}")
                await asyncio.sleep(2)
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# Get initial data endpoints
@app.get("/data/postgresql")
async def get_postgresql_data():
    """Get PostgreSQL logs"""
    try:
        logs = fetch_logs_from_db(limit=50)
        return {"logs": logs, "source": "postgresql"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/data/qdrant")
async def get_qdrant_data():
    """Get Qdrant logs"""
    try:
        logs = fetch_logs_from_qdrant(limit=50)
        return {"logs": logs, "source": "qdrant", "enabled": QDRANT_ENABLED}
    except Exception as e:
        return {"error": str(e)}

# Simulation info and control endpoints
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

# Root endpoint to serve the HTML
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    try:
        return templates.TemplateResponse("index.html", {"request": request})
    except Exception as e:
        error_msg = f"ERROR: Could not render template 'index.html': {e}"
        print(error_msg)
        return HTMLResponse(content=f"<html><body>{error_msg}</body></html>", status_code=500)

# Health check endpoint
@app.get("/health")
async def health_check():
    """Check if the server and simulation API are reachable"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{SIMULATION_API_URL}/")
            simulation_status = "online" if response.status_code == 200 else "offline"
    except Exception as e:
        simulation_status = f"unreachable: {str(e)}"
    
    qdrant_status = "available" if qdrant_client else "unavailable"
    
    return {
        "mcp_server": "online",
        "simulation_api": simulation_status,
        "qdrant": qdrant_status,
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    print("Starting integrated MCP server with 3-column chat app...")
    print(f"Python version: {sys.version}")
    print("Visit http://0.0.0.0:5000")
    uvicorn.run(app, host="0.0.0.0", port=5000)