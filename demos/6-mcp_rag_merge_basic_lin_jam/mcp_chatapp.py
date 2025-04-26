from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastmcp import FastMCP
import ollama
import uvicorn
import re
import json
import psycopg2
from datetime import datetime
import traceback
import sys
import os

# Database configuration
DB_CONFIG = {
    "dbname": "rag_db",
    "user": "postgres",
    "password": "password",
    "host": "localhost",
    "port": "5432"
}

# Import RAG store functionality
from rag_store import add_log

# Initialize Ollama with the local model
client = ollama.Client()
OLLAMA_MODEL = "llama3.3:70b-instruct-q5_K_M"

# Get model from llm_config for chat functionality
from llm_config import get_ollama_client, get_model_name
ollama_client = get_ollama_client()
LLM_MODEL = get_model_name()

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

# Define the command to handle agent movement
@mcp.tool()
async def move_agent(agent: str, x: float, y: float) -> dict:
    """Move an agent to specific coordinates"""
    print(f"[ACTION] Move agent '{agent}' to ({x}, {y})")
    
    # Log the movement action to RAG store
    timestamp = datetime.now().isoformat()
    action_text = f"Moving agent {agent} to coordinates ({x}, {y})"
    
    add_log(action_text, {
        "agent_id": agent,
        "position": f"({x}, {y})",
        "timestamp": timestamp,
        "source": "mcp",
        "action": "move"
    })
    
    return {
        "success": True,
        "message": f"Moving {agent} to coordinates ({x}, {y})",
        "x": x,
        "y": y
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

# Process natural language commands
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

    # Format prompt for the LLM
    prompt = f"""You are an AI that controls agents in a 2D simulation.

User command: "{command}"

Determine if the user wants to move one or more agents. For each movement, extract:
- agent name
- x coordinate
- y coordinate

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
        response = client.chat(model=OLLAMA_MODEL, messages=[
            {"role": "user", "content": prompt}
        ])
        raw_response = response['message']['content']
        print(f"[OLLAMA RESPONSE] {raw_response}")

        # Extract clean JSON list
        json_match = re.search(r'\[.*\]', raw_response, re.DOTALL)
        parsed_list = json.loads(json_match.group(0)) if json_match else json.loads(raw_response)

        results = []
        for parsed in parsed_list:
            if parsed.get("understood") and parsed.get("action") == "move":
                # Execute the move
                agent_name = parsed["agent"]
                x_coord = parsed["x"]
                y_coord = parsed["y"]
                
                # Call the move_agent function to handle the actual movement
                move_result = await move_agent(agent_name, x_coord, y_coord)
                
                results.append({
                    "success": True,
                    "action": "move",
                    "agent": agent_name,
                    "x": x_coord,
                    "y": y_coord,
                    "message": parsed.get("message", f"Moving {agent_name} to ({x_coord}, {y_coord})")
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

# Chat endpoint from Flask app now in FastAPI
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
        
        # Format full context
        context_text = "\n".join(simulation_context)
        
        # Create a clear system prompt for the LLM
        system_prompt = "You are an assistant for a Multi-Agent Simulation system. Provide helpful, accurate information about the simulation based on the logs."
        
        # Call the LLM with all information
        response = ollama_client.chat(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"SIMULATION LOGS:\n{context_text}\n\nUSER QUERY: {user_message}\n\nAnswer based only on information in the logs above."}
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
            ollama_response = "I'm unable to provide an answer based on the available logs."
        
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

if __name__ == "__main__":
    print("Starting integrated MCP server with chat app...")
    print(f"Python version: {sys.version}")
    print("Visit http://127.0.0.1:5000")
    uvicorn.run(app, host="127.0.0.1", port=5000)