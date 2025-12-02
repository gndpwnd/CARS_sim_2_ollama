#!/usr/bin/env python3
"""
MCP Chatapp - Fast startup with proper async handling
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastmcp import FastMCP
import uvicorn
import sys
import httpx
from datetime import datetime

# Import configuration
from core.config import SIMULATION_API_URL

# Import integrations
from integrations import add_log

# Import MCP modules
from chatapp import (
    register_tools,
    handle_chat_message,
    generate_startup_menu,
    stream_postgresql,
    stream_qdrant,
    get_postgresql_data,
    get_qdrant_data
)

# Initialize LLM WITHOUT preloading (fast startup)
print("[MCP] Initializing LLM...")
try:
    import llm_config
    from llm_config import initialize_llm, get_model_name
    
    # DON'T preload - let it load on first request
    ollama_client, llm_ready = initialize_llm(preload=False)
    LLM_MODEL = get_model_name()
    
    if llm_ready:
        print(f"[MCP] ✓ LLM configured: {LLM_MODEL} at {llm_config.OLLAMA_HOST} (will load on first use)")
    else:
        print(f"[MCP] ⚠ LLM not available, will retry on first request")
except ImportError as e:
    print(f"[MCP] ⚠ LLM not available: {e}")
    llm_ready = False

# Initialize RAG system
print("[RAG] Initializing RAG system...")
try:
    from rag import get_rag
    rag = get_rag()
    print("[RAG] Simple RAG system initialized")
except ImportError as e:
    print(f"[RAG] ⚠ RAG not available: {e}")
    rag = None

# Create FastAPI app
app = FastAPI()

# Create MCP server
mcp = FastMCP("Agent Movement and Simulation", app=app)

# Register MCP tools
register_tools(mcp)

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

# ============================================================================
# MAIN ROUTES
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve main HTML page"""
    try:
        return templates.TemplateResponse("index.html", {"request": request})
    except Exception as e:
        error_msg = f"ERROR: Could not render template 'index.html': {e}"
        print(error_msg)
        return HTMLResponse(content=f"<html><body>{error_msg}</body></html>", status_code=500)

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
            from core.config import X_RANGE, Y_RANGE, MISSION_END
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
                "x_range": list(X_RANGE),
                "y_range": list(Y_RANGE),
                "mission_end": list(MISSION_END)
            }
        }
        
    except Exception as e:
        return {
            "menu": generate_startup_menu(),
            "error": str(e)
        }

@app.post("/chat")
async def chat(request: Request):
    """Main chat endpoint with enhanced context handling"""
    try:
        data = await request.json()
        user_message = data.get('message', '').strip()
        request_context = data.get('context', {})
        
        print("\n" + "="*60)
        print("[CHAT] New request received")
        print(f"[CHAT] Message: {user_message}")
        
        # Get current health status
        health = await health_check()
        print(f"[CHAT] Health status: {health}")
        
        if not health['llm'] == 'ready':
            return {"response": "❌ LLM not available. Is Ollama running?"}
        
        # Build request metadata
        metadata = {
            "timestamp": datetime.now().isoformat(),
            "request_id": data.get('request_id', ''),
            "user_id": data.get('user_id', 'anonymous'),
            "client_type": request.headers.get('user-agent', 'unknown'),
            "system_health": health
        }
        
        print(f"[CHAT] Request metadata: {metadata}")
        
        # Get simulation status for context
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{SIMULATION_API_URL}/status", timeout=2.0)
                if response.status_code == 200:
                    metadata['simulation'] = response.json()
                    print("[CHAT] Added simulation status to context")
        except Exception as e:
            print(f"[CHAT] Could not get simulation status: {e}")
        
        # Process command
        result = await handle_chat_message(user_message)
        
        print("[CHAT] Request completed")
        print("="*60 + "\n")
        
        return result
        
    except Exception as e:
        error = f"Error processing chat request: {str(e)}"
        print(f"\n[CHAT ERROR] {error}")
        import traceback
        traceback.print_exc()
        print("="*60 + "\n")
        return {"response": f"❌ {error}"}
        
# ============================================================================
# STREAMING ENDPOINTS
# ============================================================================

@app.get("/stream/postgresql")
async def stream_postgresql_endpoint():
    """Stream PostgreSQL logs in real-time"""
    return await stream_postgresql()

@app.get("/stream/qdrant")
async def stream_qdrant_endpoint():
    """Stream Qdrant logs in real-time"""
    return await stream_qdrant()

@app.get("/data/postgresql")
async def get_postgresql_data_endpoint():
    """Get PostgreSQL logs"""
    return await get_postgresql_data()

@app.get("/data/qdrant")
async def get_qdrant_data_endpoint():
    """Get Qdrant logs"""
    return await get_qdrant_data()

# ============================================================================
# UTILITY ENDPOINTS
# ============================================================================

@app.get("/health")
async def health_check():
    """Check if the server and simulation API are reachable"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{SIMULATION_API_URL}/", timeout=2.0)
            simulation_status = "online" if response.status_code == 200 else "offline"
    except Exception as e:
        simulation_status = f"unreachable: {str(e)}"
    
    return {
        "mcp_server": "online",
        "simulation_api": simulation_status,
        "llm": "ready" if llm_ready else "unavailable",
        "rag": "initialized" if rag else "unavailable",
        "timestamp": datetime.now().isoformat()
    }

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("="*60)
    print("Starting MCP Chatapp Server with Simple RAG")
    print("="*60)
    print(f"Python version: {sys.version}")
    print("Visit http://0.0.0.0:5000")
    print("="*60)
    uvicorn.run(app, host="0.0.0.0", port=5000)