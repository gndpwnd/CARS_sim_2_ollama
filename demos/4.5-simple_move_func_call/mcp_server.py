# mcp-server.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import FastMCP
import ollama
import uvicorn
import re
import json

# Initialize Ollama with the local model
client = ollama.Client()
OLLAMA_MODEL = "llama3.3:70b-instruct-q5_K_M"

# Create an MCP server
app = FastAPI()
mcp = FastMCP("Agent Movement and Simulation", app=app)

# Add CORS middleware to allow requests from the matplotlib application
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define the command to handle agent movement
@mcp.tool()
async def move_agent(agent: str, x: float, y: float) -> dict:
    """Move an agent to specific coordinates"""
    print(f"[ACTION] Move agent '{agent}' to ({x}, {y})")
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
# Add this new endpoint for receiving raw natural language commands
@app.post("/llm_command")
async def llm_command(request: Request):
    data = await request.json()
    command = data.get("message", "")

    print(f"[RECEIVED COMMAND] {command}")

    # Format prompt for the LLM
    prompt = f"""You are an AI that controls agents in a 2D simulation.

User command: "{command}"

Determine if the user wants to move an agent. If so, extract:
- agent name
- x coordinate
- y coordinate

Respond in pure JSON format:
{{
    "understood": true/false,
    "action": "move" or "unknown",
    "agent": "agent name",
    "x": number,
    "y": number,
    "message": "summary of interpretation"
}}

Only valid JSON. No extra text or explanations.
"""

    try:
        response = client.chat(model=OLLAMA_MODEL, messages=[
            {"role": "user", "content": prompt}
        ])

        raw_response = response['message']['content']
        print(f"[OLLAMA RESPONSE] {raw_response}")

        # Try to extract clean JSON (in case Ollama adds markdown)
        json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
        parsed = json.loads(json_match.group(0)) if json_match else json.loads(raw_response)

        if parsed.get("understood") and parsed.get("action") == "move":
            agent = parsed.get("agent")
            x = parsed.get("x")
            y = parsed.get("y")

            return {
                "success": True,
                "action": "move",
                "agent": agent,
                "x": x,
                "y": y,
                "message": parsed.get("message", "Moving agent")
            }
        else:
            return {
                "success": False,
                "action": "unknown",
                "message": parsed.get("message", "Command not understood")
            }

    except Exception as e:
        print(f"[ERROR] {e}")
        return {
            "success": False,
            "message": f"Error processing command: {e}"
        }


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=5000)