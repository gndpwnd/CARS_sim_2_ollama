from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import FastMCP
import ollama
import uvicorn
import re
import json

# Initialize Ollama with the local model
client = ollama.Client()
OLLAMA_MODEL = "llama3.2:3b-instruct-q5_K_M"

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
    
    # Prepare the prompt for Ollama
    prompt = f"""You are an AI that controls agents in a 2D simulation.
    
    Command: Move {agent} to coordinates ({x}, {y}).
    
    Please respond only with a JSON object containing:
    1. success: true/false
    2. message: brief description of the action
    3. x: target x coordinate
    4. y: target y coordinate
    """
    
    try:
        response = client.chat(model=OLLAMA_MODEL, messages=[
            {"role": "user", "content": prompt}
        ])
        
        # For logging purposes
        print(f"Ollama response: {response['message']['content']}")
        
        # Return a structured response
        return {
            "success": True,
            "message": f"Moving {agent} to coordinates ({x}, {y})",
            "x": x,
            "y": y
        }
    except Exception as e:
        print(f"Error calling Ollama: {e}")
        return {
            "success": False,
            "message": f"Failed to process command: {str(e)}",
            "x": None,
            "y": None
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
@app.post("/process_command")
async def process_command_endpoint(request: Request):
    data = await request.json()
    command = data.get("command", "")
    
    # Prepare the prompt for Ollama
    prompt = f"""You are an AI that controls agents in a 2D simulation.
    
    Natural language command from user: "{command}"
    
    First, analyze what the user wants to do. If it's about moving an agent,
    extract the agent name and target coordinates.
    
    Return your response as a JSON object with this format:
    {{
        "understood": true/false,
        "action": "move" or "unknown",
        "agent": "agent name if applicable",
        "x": x-coordinate if applicable,
        "y": y-coordinate if applicable,
        "message": "explanation of what you understood"
    }}
    
    Only respond with valid JSON, nothing else.
    """
    
    try:
        # Call Ollama for natural language understanding
        response = client.chat(model=OLLAMA_MODEL, messages=[
            {"role": "user", "content": prompt}
        ])
        
        content = response['message']['content']
        print(f"Ollama response: {content}")
        
        # Try to extract JSON from the response
        # Sometimes LLMs include markdown code blocks or other text
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group(0))
        else:
            # Fallback: try to parse the entire response as JSON
            parsed = json.loads(content)
        
        # If it's a move command and was understood correctly
        if parsed.get("understood", False) and parsed.get("action") == "move":
            # Execute the move
            result = await move_agent(
                parsed.get("agent"),
                float(parsed.get("x")),
                float(parsed.get("y"))
            )
            return {
                "success": result["success"],
                "message": result["message"],
                "x": result["x"],
                "y": result["y"],
                "agent": parsed.get("agent")
            }
        else:
            return {
                "success": False,
                "message": f"Could not understand the command: {parsed.get('message', 'Unknown error')}",
                "x": None,
                "y": None,
                "agent": None
            }
            
    except Exception as e:
        print(f"Error processing command: {e}")
        return {
            "success": False,
            "message": f"Failed to process command: {str(e)}",
            "x": None,
            "y": None,
            "agent": None
        }

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=5000)