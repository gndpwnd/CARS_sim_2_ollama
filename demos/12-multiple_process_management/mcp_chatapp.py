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


# Around line 20-40, replace the LLM initialization:

import llm_config
from llm_config import get_ollama_client, get_model_name, initialize_llm, chat_with_retry

# Initialize LLM with preloading
print("[MCP] Initializing LLM...")
ollama_client, llm_ready = initialize_llm(preload=True)
LLM_MODEL = get_model_name()

if llm_ready:
    print(f"[MCP] ✓ LLM ready: {LLM_MODEL} at {llm_config.OLLAMA_HOST}")
else:
    print(f"[MCP] ⚠ LLM initialization had issues, will retry on first request")


# Import new storage system
from postgresql_store import add_log, get_conversation_history
from rag import get_rag, format_for_llm, format_all_agents_for_llm

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
NMEA_COLLECTION = "nmea_messages"
TELEMETRY_COLLECTION = "agent_telemetry"

# Simulation API endpoint
SIMULATION_API_URL = "http://0.0.0.0:5001"

# Simulation boundaries
X_RANGE = (-10, 10)
Y_RANGE = (-10, 10)
MISSION_END = (10, 10)

# Create MCP server
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
        print(f"[QDRANT] Connected to Qdrant at {QDRANT_HOST}:{QDRANT_PORT}")
    except Exception as e:
        print(f"[QDRANT] Failed to connect: {e}")
        qdrant_client = None

# Initialize RAG system
rag = get_rag()
print("[RAG] Simple RAG system initialized")

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
        # Get from telemetry collection
        results = qdrant_client.scroll(
            collection_name=TELEMETRY_COLLECTION,
            limit=limit,
            with_payload=True,
            with_vectors=False
        )[0]
        
        logs = []
        for point in results:
            payload = point.payload
            
            # Extract metadata - it's stored directly in payload, not nested
            metadata = {
                'agent_id': payload.get('agent_id'),
                'position': (payload.get('position_x', 0), payload.get('position_y', 0)),
                'jammed': payload.get('jammed', False),
                'communication_quality': payload.get('communication_quality', 0),
                'timestamp': payload.get('timestamp'),
                'iteration': payload.get('iteration'),
                'gps_satellites': payload.get('gps_satellites'),
                'gps_signal_quality': payload.get('gps_signal_quality'),
                'gps_fix_quality': payload.get('gps_fix_quality')
            }
            
            logs.append({
                "log_id": str(point.id),
                "text": payload.get("text", f"Telemetry update for {payload.get('agent_id', 'unknown')}"),
                "metadata": metadata,
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
                    "message_type": "command",
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
# REPORT GENERATION FUNCTIONS (Using RAG)
# ============================================================================

async def generate_status_report():
    """Generate human-friendly status report using RAG"""
    try:
        async with httpx.AsyncClient() as client:
            agents_response = await client.get(f"{SIMULATION_API_URL}/agents", timeout=2.0)
            
            if agents_response.status_code != 200:
                return {"response": "❌ Could not retrieve agents list"}
            
            agents_data = agents_response.json().get("agents", {})
            agent_ids = list(agents_data.keys())
            
            # Use RAG to format status
            status_text = format_all_agents_for_llm(agent_ids)
            
            report = "📊 **SIMULATION STATUS REPORT**\n\n"
            report += status_text
            
            return {"response": report}
            
    except Exception as e:
        return {"response": f"❌ Error generating report: {str(e)}"}

async def generate_detailed_report():
    """Generate detailed analysis report using RAG + LLM"""
    try:
        # Get all agents
        async with httpx.AsyncClient() as client:
            agents_response = await client.get(f"{SIMULATION_API_URL}/agents", timeout=2.0)
        
        if agents_response.status_code != 200:
            return {"response": "❌ Could not retrieve agents"}
        
        agents_data = agents_response.json().get("agents", {})
        agent_ids = list(agents_data.keys())
        
        # Build context using RAG
        context = "SIMULATION DATA:\n\n"
        
        for agent_id in agent_ids:
            agent_context = format_for_llm(agent_id, history_limit=5)
            context += agent_context + "\n"
        
        # Ask LLM for analysis
        prompt = f"""{context}

Based on the above simulation data, provide a comprehensive human-friendly report including:
1. Overall simulation health
2. Agent performance analysis
3. Jamming impact assessment
4. Recommendations for agent movement
5. Any anomalies or concerns

Keep the report concise but informative."""
        
        response = chat_with_retry(
            ollama_client,
            LLM_MODEL,
            messages=[{"role": "user", "content": prompt}]
        )

        if response is None:
            return {"response": "✗ LLM connection error. Is Ollama running? Check: ./launch_ollama.sh"}

        llm_response = response['message']['content']
        
        llm_report = response['message']['content']
        
        # Log the report
        add_log(llm_report, {
            "source": "llm",
            "message_type": "response",
            "timestamp": datetime.now().isoformat()
        })
        
        return {"response": f"📋 **DETAILED ANALYSIS REPORT**\n\n{llm_report}"}
        
    except Exception as e:
        return {"response": f"❌ Error generating detailed report: {str(e)}"}


async def list_agents():
    """List all agents with basic info using RAG"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{SIMULATION_API_URL}/agents", timeout=2.0)
            
            if response.status_code != 200:
                return {"response": "❌ Could not retrieve agent list"}
            
            agents = response.json().get("agents", {})
            agent_ids = list(agents.keys())
            
            if not agent_ids:
                return {"response": "⚠️ No agents currently in simulation"}
            
            # Use RAG to format list
            agent_list = format_all_agents_for_llm(agent_ids)
            
            report = "🤖 **AGENT LIST**\n\n" + agent_list
            
            return {"response": report}
            
    except Exception as e:
        return {"response": f"❌ Error listing agents: {str(e)}"}


async def get_agent_info(agent_name: str):
    """Get detailed info for a specific agent using RAG"""
    try:
        # Use RAG to get comprehensive context
        context_text = format_for_llm(agent_name, history_limit=5)
        
        if "No data available" in context_text or not context_text:
            return {"response": f"❌ Agent '{agent_name}' not found or no data available"}
        
        report = f"🤖 **{agent_name.upper()} DETAILS**\n\n"
        report += context_text
        
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
            "source": "user",
            "message_type": "command",
            "timestamp": timestamp
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
        
        response = chat_with_retry(
            ollama_client,
            LLM_MODEL,
            messages=[{"role": "user", "content": prompt}]
        )

        if response is None:
            return {"response": "✗ LLM connection error. Is Ollama running? Check: ./launch_ollama.sh"}

        llm_response = response['message']['content']
        
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
    """Handle general conversation with LLM using RAG"""
    print(f"\n{'='*60}")
    print(f"[CHAT] handle_general_chat() called")
    print(f"[CHAT] Message: {message}")
    print(f"{'='*60}")
    
    try:
        # Discover agents from stored data (no API needed!)
        print("[CHAT] Discovering agents from stored data...")
        from rag import get_known_agent_ids
        
        agent_ids = get_known_agent_ids(limit=100)
        print(f"[CHAT] Found {len(agent_ids)} agents: {agent_ids}")
        
        # Build context using RAG
        print("[CHAT] Building context from RAG...")
        if agent_ids:
            context = format_all_agents_for_llm(agent_ids)
            print(f"[CHAT] Context built: {len(context)} characters")
        else:
            context = "No agent data available yet. The simulation may not have started or no data has been logged."
            print("[CHAT] No agents found in stored data")
        
        # Get recent conversation history
        print("[CHAT] Fetching conversation history...")
        conversation = get_conversation_history(limit=10)
        print(f"[CHAT] Retrieved {len(conversation)} conversation messages")
        
        conversation_text = "\nRecent Conversation:\n"
        for msg in conversation[:5]:  # Last 5 messages
            role = msg.get('metadata', {}).get('source', 'unknown')
            text = msg.get('text', '')
            conversation_text += f"{role}: {text}\n"
        
        print("[CHAT] Building prompt...")
        prompt = f"""Current Simulation State:
{context}

{conversation_text}

User Question: {message}

You are an assistant helping monitor a multi-agent simulation. The agents are trying to reach the mission endpoint at ({MISSION_END[0]}, {MISSION_END[1]}) while avoiding jamming zones.

Provide a helpful, concise response based on the current simulation state. If you need more specific data, suggest what command the user should run (like 'status', 'report', or 'agents')."""
        
        print(f"[CHAT] Prompt built: {len(prompt)} characters")
        print(f"[CHAT] First 200 chars of prompt: {prompt[:200]}...")
        
        # Call Ollama with retry logic
        print(f"[CHAT] Calling Ollama with model: {LLM_MODEL}")
        print(f"[CHAT] Ollama host: {llm_config.OLLAMA_HOST}")
        
        response = chat_with_retry(
            ollama_client,
            LLM_MODEL,
            messages=[{"role": "user", "content": prompt}]
        )
        
        if response is None:
            print("[CHAT] ERROR: chat_with_retry returned None")
            return {"response": "❌ LLM connection error. Is Ollama running? Check: ./launch_ollama.sh"}
        
        print("[CHAT] Received response from Ollama")
        llm_response = response['message']['content']
        print(f"[CHAT] Response length: {len(llm_response)} characters")
        print(f"[CHAT] First 100 chars: {llm_response[:100]}...")
        
        # Log assistant response
        add_log(llm_response, {
            "source": "llm",
            "message_type": "response",
            "timestamp": datetime.now().isoformat()
        })
        
        print(f"[CHAT] Returning response to client")
        print(f"{'='*60}\n")
        return {"response": llm_response}
        
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"[CHAT ERROR] Exception in handle_general_chat()")
        print(f"[CHAT ERROR] Exception type: {type(e).__name__}")
        print(f"[CHAT ERROR] Exception message: {str(e)}")
        print(f"{'='*60}")
        import traceback
        traceback.print_exc()
        print(f"{'='*60}\n")
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
        "rag_system": "initialized",
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    print("="*60)
    print("Starting MCP Chatapp Server with Simple RAG")
    print("="*60)
    print(f"Python version: {sys.version}")
    print("Visit http://0.0.0.0:5000")
    print("="*60)
    uvicorn.run(app, host="0.0.0.0", port=5000)