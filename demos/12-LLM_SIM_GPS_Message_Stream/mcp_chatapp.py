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
import math
from rag_store import add_log
from llm_config import get_ollama_client, get_model_name

# Try to import Qdrant
try:
    from qdrant_client import QdrantClient
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

# Simulation boundaries (from your config)
X_RANGE = (-10, 10)
Y_RANGE = (-10, 10)
MISSION_END = (10, 10)

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
        try:
            qdrant_client.get_collection(COLLECTION_NAME)
            print(f"[QDRANT] Connected to collection '{COLLECTION_NAME}'")
        except:
            from qdrant_client.models import Distance, VectorParams
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


# ============================================================================
# STARTUP MENU
# ============================================================================

def generate_startup_menu():
    """Generate startup menu with simulation info"""
    menu = f"""🚀 **Multi-Agent Simulation Control System**

**SIMULATION BOUNDARIES:**
- X Range: {X_RANGE[0]} to {X_RANGE[1]}
- Y Range: {Y_RANGE[0]} to {Y_RANGE[1]}
- Mission Endpoint: ({MISSION_END[0]}, {MISSION_END[1]}) ⭐

**AVAILABLE COMMANDS:**

📍 **Movement Commands:**
- `move [agent] to [x], [y]` - Move agent to coordinates
  Example: "move agent1 to 5, 5"

📊 **Status Commands:**
- `status` - Get full simulation status report
- `report` - Generate detailed agent analysis
- `agents` - List all agents and positions
- `agent [name]` - Get detailed info for specific agent

🎯 **Simulation Control:**
- `pause` - Pause the simulation
- `resume` - Resume the simulation
- `help` or `menu` - Show this menu again

💬 **General Chat:**
- Ask questions about the simulation
- Request analysis of agent behavior
- Get recommendations for agent movement

**Current Status:** Ready to receive commands!
"""
    return menu


@app.get("/startup_menu")
async def get_startup_menu():
    """Get the startup menu with current simulation status"""
    try:
        # Get current simulation status
        async with httpx.AsyncClient() as client:
            try:
                status_response = await client.get(f"{SIMULATION_API_URL}/status", timeout=2.0)
                agents_response = await client.get(f"{SIMULATION_API_URL}/agents", timeout=2.0)
                
                sim_status = {}
                agents_info = {}
                
                if status_response.status_code == 200:
                    sim_status = status_response.json()
                
                if agents_response.status_code == 200:
                    agents_info = agents_response.json().get("agents", {})
            except:
                sim_status = {}
                agents_info = {}
        
        menu = generate_startup_menu()
        
        # Add current agent info if available
        if agents_info:
            menu += "\n**CURRENT AGENTS:**\n"
            for agent_id, data in agents_info.items():
                status = "🔴 JAMMED" if data.get('jammed') else "🟢 CLEAR"
                pos = data.get('position', [0, 0])
                menu += f"• {agent_id}: Position ({pos[0]:.1f}, {pos[1]:.1f}) - {status}\n"
        
        return {
            "menu": menu,
            "simulation_status": sim_status,
            "agents": agents_info,
            "boundaries": {
                "x_range": X_RANGE,
                "y_range": Y_RANGE,
                "mission_end": MISSION_END
            }
        }
        
    except Exception as e:
        return {
            "menu": generate_startup_menu(),
            "error": str(e)
        }


# ============================================================================
# MCP TOOLS
# ============================================================================

@mcp.tool()
async def move_agent(agent: str, x: float, y: float) -> dict:
    """Move an agent to specific coordinates"""
    print(f"[ACTION] Move agent '{agent}' to ({x}, {y})")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{SIMULATION_API_URL}/move_agent",
                json={"agent": agent, "x": x, "y": y},
                timeout=5.0
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


# ============================================================================
# REPORT GENERATION FUNCTIONS
# ============================================================================

async def generate_status_report():
    """Generate human-friendly status report"""
    try:
        async with httpx.AsyncClient() as client:
            status_response = await client.get(f"{SIMULATION_API_URL}/status", timeout=2.0)
            agents_response = await client.get(f"{SIMULATION_API_URL}/agents", timeout=2.0)
            
            if status_response.status_code != 200:
                return {"response": "❌ Could not retrieve simulation status"}
            
            status = status_response.json()
            agents = agents_response.json().get("agents", {})
            
            report = "📊 **SIMULATION STATUS REPORT**\n\n"
            report += f"**Status:** {'🟢 Running' if status.get('running') else '🔴 Paused'}\n"
            report += f"**Iteration:** {status.get('iteration_count', 0)}\n"
            report += f"**Active Agents:** {len(agents)}\n\n"
            
            # Agent summary
            jammed_count = sum(1 for a in agents.values() if a.get('jammed'))
            clear_count = len(agents) - jammed_count
            
            report += f"**Agent Status:**\n"
            report += f"• 🟢 Clear: {clear_count}\n"
            report += f"• 🔴 Jammed: {jammed_count}\n\n"
            
            # Individual agents
            report += "**Individual Agent Status:**\n"
            for agent_id, data in sorted(agents.items()):
                status_icon = "🔴" if data.get('jammed') else "🟢"
                pos = data.get('position', [0, 0])
                comm = data.get('communication_quality', 0)
                
                report += f"{status_icon} **{agent_id}**\n"
                report += f"  Position: ({pos[0]:.2f}, {pos[1]:.2f})\n"
                report += f"  Comm Quality: {comm:.2f}\n"
                
                # Distance to mission endpoint
                dist = math.sqrt((MISSION_END[0] - pos[0])**2 + (MISSION_END[1] - pos[1])**2)
                report += f"  Distance to Goal: {dist:.2f}\n\n"
            
            return {"response": report}
            
    except Exception as e:
        return {"response": f"❌ Error generating report: {str(e)}"}

async def generate_detailed_report():
    """Generate detailed analysis report using LLM"""
    try:
        # Fetch all data
        logs = fetch_logs_from_db(limit=50)
        
        async with httpx.AsyncClient() as client:
            status_response = await client.get(f"{SIMULATION_API_URL}/status", timeout=2.0)
            agents_response = await client.get(f"{SIMULATION_API_URL}/agents", timeout=2.0)
        
        # Compile context
        context = "SIMULATION DATA:\n\n"
        
        if status_response.status_code == 200:
            status = status_response.json()
            context += f"Running: {status.get('running')}\n"
            context += f"Iteration: {status.get('iteration_count')}\n\n"
        
        if agents_response.status_code == 200:
            agents = agents_response.json().get("agents", {})
            context += "AGENTS:\n"
            for agent_id, data in agents.items():
                context += f"{agent_id}: Pos {data.get('position')}, "
                context += f"Jammed: {data.get('jammed')}, "
                context += f"Comm: {data.get('communication_quality')}\n"
        
        # Add recent logs
        context += "\nRECENT EVENTS:\n"
        for log in logs[:20]:
            context += f"- {log.get('text', '')}\n"
        
        # Ask LLM for analysis
        prompt = f"""{context}

Based on the above simulation data, provide a comprehensive human-friendly report including:
1. Overall simulation health
2. Agent performance analysis
3. Jamming impact assessment
4. Recommendations for agent movement
5. Any anomalies or concerns

Keep the report concise but informative."""
        
        response = ollama_client.chat(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}]
        )
        
        llm_report = response['message']['content']
        
        return {"response": f"📋 **DETAILED ANALYSIS REPORT**\n\n{llm_report}"}
        
    except Exception as e:
        return {"response": f"❌ Error generating detailed report: {str(e)}"}


async def list_agents():
    """List all agents with basic info"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{SIMULATION_API_URL}/agents", timeout=2.0)
            
            if response.status_code != 200:
                return {"response": "❌ Could not retrieve agent list"}
            
            agents = response.json().get("agents", {})
            
            if not agents:
                return {"response": "⚠️ No agents currently in simulation"}
            
            report = "🤖 **AGENT LIST**\n\n"
            for agent_id, data in sorted(agents.items()):
                icon = "🔴" if data.get('jammed') else "🟢"
                pos = data.get('position', [0, 0])
                report += f"{icon} **{agent_id}**: ({pos[0]:.2f}, {pos[1]:.2f})\n"
            
            return {"response": report}
            
    except Exception as e:
        return {"response": f"❌ Error listing agents: {str(e)}"}


async def get_agent_info(agent_name: str):
    """Get detailed info for a specific agent"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{SIMULATION_API_URL}/agents", timeout=2.0)
            
            if response.status_code != 200:
                return {"response": "❌ Could not retrieve agent information"}
            
            agents = response.json().get("agents", {})
            
            if agent_name not in agents:
                return {"response": f"❌ Agent '{agent_name}' not found"}
            
            data = agents[agent_name]
            
            report = f"🤖 **{agent_name.upper()} DETAILS**\n\n"
            report += f"**Position:** ({data.get('position', [0, 0])[0]:.2f}, {data.get('position', [0, 0])[1]:.2f})\n"
            report += f"**Status:** {'🔴 JAMMED' if data.get('jammed') else '🟢 CLEAR'}\n"
            report += f"**Comm Quality:** {data.get('communication_quality', 0):.2f}\n"
            
            pos = data.get('position', [0, 0])
            dist = math.sqrt((MISSION_END[0] - pos[0])**2 + (MISSION_END[1] - pos[1])**2)
            report += f"**Distance to Goal:** {dist:.2f}\n"
            
            # Get recent logs for this agent
            logs = fetch_logs_from_db(limit=100)
            agent_logs = [l for l in logs if l['metadata'].get('agent_id') == agent_name][:5]
            
            if agent_logs:
                report += f"\n**Recent Activity:**\n"
                for log in agent_logs:
                    report += f"• {log.get('text', '')[:100]}...\n"
            
            return {"response": report}
            
    except Exception as e:
        return {"response": f"❌ Error getting agent info: {str(e)}"}


# ============================================================================
# CHAT ENDPOINT
# ============================================================================

@app.post("/chat")
async def chat(request: Request):
    """Main chat endpoint with LLM interpretation"""
    try:
        data = await request.json()
        user_message = data.get('message', '').strip()
        
        # Log user message
        timestamp = datetime.now().isoformat()
        add_log(user_message, {
            "role": "user",
            "timestamp": timestamp,
            "source": "chat"
        })
        
        # Handle special commands (quick responses without LLM)
        lower_msg = user_message.lower()
        
        if lower_msg in ['help', 'menu', 'commands']:
            menu = generate_startup_menu()
            return {"response": menu}
        
        if lower_msg == 'status':
            return await generate_status_report()
        
        if lower_msg == 'report':
            return await generate_detailed_report()
        
        if lower_msg == 'agents':
            return await list_agents()
        
        if lower_msg.startswith('agent '):
            agent_name = lower_msg.replace('agent ', '').strip()
            return await get_agent_info(agent_name)
        
        # Check if it's a movement command
        if any(word in lower_msg for word in ['move', 'go to', 'navigate', 'send']):
            return await handle_movement_command(user_message)
        
        # Otherwise, let LLM handle general conversation
        return await handle_general_chat(user_message)
        
    except Exception as e:
        print(f"[CHAT ERROR] {e}")
        traceback.print_exc()
        return {"response": f"❌ Error: {str(e)}"}


async def handle_movement_command(command: str):
    """Handle movement commands with LLM parsing"""
    try:
        # Get available agents
        async with httpx.AsyncClient() as client:
            agents_response = await client.get(f"{SIMULATION_API_URL}/agents", timeout=2.0)
            
            available_agents = {}
            if agents_response.status_code == 200:
                available_agents = agents_response.json().get("agents", {})
        
        prompt = f"""You are an AI that controls agents in a 2D simulation.

Available agents: {", ".join(available_agents.keys()) if available_agents else "No agents available"}

Simulation boundaries:
- X Range: {X_RANGE[0]} to {X_RANGE[1]}
- Y Range: {Y_RANGE[0]} to {Y_RANGE[1]}

User command: "{command}"

If this is a movement command, extract:
1. The agent name (must match an available agent)
2. The x coordinate (number within range)
3. The y coordinate (number within range)

Respond ONLY with the agent name and coordinates in this exact format:
agent_name,x,y

If it's not a valid movement command, respond with: "Not a movement command"
"""
        
        response = ollama_client.chat(model=LLM_MODEL, messages=[
            {"role": "user", "content": prompt}
        ])
        
        raw_response = response['message']['content'].strip()
        print(f"[LLM RESPONSE] {raw_response}")
        
        if "," in raw_response and len(raw_response.split(",")) == 3:
            agent_name, x_str, y_str = raw_response.split(",")
            agent_name = agent_name.strip()
            
            if agent_name not in available_agents:
                return {"response": f"❌ Agent '{agent_name}' not found in simulation"}
            
            try:
                x = float(x_str.strip())
                y = float(y_str.strip())
                
                # Validate coordinates
                if not (X_RANGE[0] <= x <= X_RANGE[1] and Y_RANGE[0] <= y <= Y_RANGE[1]):
                    return {"response": f"❌ Coordinates ({x}, {y}) are outside simulation boundaries"}
                
                move_result = await move_agent(agent_name, x, y)
                
                if move_result.get("success"):
                    return {"response": move_result.get('message', '')}
                else:
                    return {"response": f"❌ Failed to move {agent_name}: {move_result.get('message', 'Unknown error')}"}
            
            except ValueError:
                return {"response": f"❌ Invalid coordinates: {x_str}, {y_str}"}
        
        return {"response": "❌ Could not parse movement command. Use format: 'move agent1 to 5, 5'"}
        
    except Exception as e:
        return {"response": f"❌ Error processing movement: {str(e)}"}


async def handle_general_chat(message: str):
    """Handle general conversation with LLM"""
    try:
        # Get current simulation context
        logs = fetch_logs_from_db(limit=30)
        
        async with httpx.AsyncClient() as client:
            status_response = await client.get(f"{SIMULATION_API_URL}/status", timeout=2.0)
            agents_response = await client.get(f"{SIMULATION_API_URL}/agents", timeout=2.0)
        
        context = "Current Simulation State:\n\n"
        
        if status_response.status_code == 200:
            status = status_response.json()
            context += f"Status: {'Running' if status.get('running') else 'Paused'}\n"
            context += f"Iteration: {status.get('iteration_count', 0)}\n\n"
        
        if agents_response.status_code == 200:
            agents = agents_response.json().get("agents", {})
            context += "Agents:\n"
            for agent_id, data in agents.items():
                context += f"- {agent_id}: Position {data.get('position')}, "
                context += f"{'JAMMED' if data.get('jammed') else 'CLEAR'}\n"
        
        # Add recent activity
        context += "\nRecent Activity:\n"
        for log in logs[:10]:
            context += f"- {log.get('text', '')}\n"
        
        prompt = f"""{context}

User Question: {message}

You are an assistant helping monitor a multi-agent simulation. The agents are trying to reach the mission endpoint at ({MISSION_END[0]}, {MISSION_END[1]}) while avoiding jamming zones.

Provide a helpful, concise response based on the current simulation state. If you need more specific data, suggest what command the user should run (like 'status', 'report', or 'agents')."""
        
        response = ollama_client.chat(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}]
        )
        
        llm_response = response['message']['content']
        
        # Log assistant response
        add_log(llm_response, {
            "role": "assistant",
            "timestamp": datetime.now().isoformat(),
            "source": "chat"
        })
        
        return {"response": llm_response}
        
    except Exception as e:
        return {"response": f"❌ Error in conversation: {str(e)}"}


# ============================================================================
# STREAMING ENDPOINTS
# ============================================================================

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


# ============================================================================
# UTILITY ENDPOINTS
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    try:
        return templates.TemplateResponse("index.html", {"request": request})
    except Exception as e:
        error_msg = f"ERROR: Could not render template 'index.html': {e}"
        print(error_msg)
        return HTMLResponse(content=f"<html><body>{error_msg}</body></html>", status_code=500)


@app.get("/health")
async def health_check():
    """Check if the server and simulation API are reachable"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{SIMULATION_API_URL}/", timeout=2.0)
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
    print("="*60)
    print("Starting MCP Chatapp Server")
    print("="*60)
    print(f"Python version: {sys.version}")
    print("Visit http://0.0.0.0:5000")
    print("="*60)
    uvicorn.run(app, host="0.0.0.0", port=5000)