#!/usr/bin/env python3
"""
Simulation API Service
Provides HTTP API for agent simulation state with LLM movement control
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from typing import Dict, Any, List
from datetime import datetime
from core.config import (
    X_RANGE, Y_RANGE, MISSION_END, NUM_AGENTS,
    get_agent_ids
)

# Create FastAPI app
app = FastAPI(title="Simulation API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory state store
agent_states: Dict[str, Dict[str, Any]] = {}

# LLM-commanded targets (takes priority over algorithmic movement)
llm_targets: Dict[str, tuple] = {}

def init_agents():
    """Initialize agent states"""
    for agent_id in get_agent_ids(NUM_AGENTS):
        agent_states[agent_id] = {
            "position": [0.0, 0.0],  # Start at origin
            "jammed": False,
            "communication_quality": 1.0,
            "last_update": datetime.now().isoformat(),
            "llm_target": None  # LLM-commanded target
        }

@app.get("/")
async def root():
    """Root endpoint - health check"""
    return {
        "status": "online",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/status")
async def get_status():
    """Get simulation status"""
    return {
        "running": True,
        "agent_count": len(agent_states),
        "boundaries": {
            "x_range": X_RANGE,
            "y_range": Y_RANGE,
            "mission_end": MISSION_END
        },
        "timestamp": datetime.now().isoformat()
    }

@app.get("/agents")
async def get_agents():
    """Get all agent states"""
    return {"agents": agent_states}

@app.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Get specific agent state"""
    if agent_id not in agent_states:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    return agent_states[agent_id]

@app.put("/agents/{agent_id}")
async def update_agent(agent_id: str, state: Dict[str, Any]):
    """Update agent state"""
    if agent_id not in agent_states:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    
    # Update allowed fields
    for field in ["position", "jammed", "communication_quality"]:
        if field in state:
            agent_states[agent_id][field] = state[field]
    
    agent_states[agent_id]["last_update"] = datetime.now().isoformat()
    return agent_states[agent_id]

@app.post("/move_agent")
async def move_agent(command: Dict[str, Any]):
    """
    LLM-commanded agent movement endpoint.
    
    This takes PRIORITY over algorithmic movement.
    The agent will move to this target, then resume algorithmic behavior.
    
    Args:
        command: {
            "agent": "agent_1",
            "x": 5.0,
            "y": 10.0
        }
    
    Returns:
        Status with agent information
    """
    agent_id = command.get("agent")
    x = command.get("x")
    y = command.get("y")
    
    # Validate inputs
    if not agent_id:
        raise HTTPException(status_code=400, detail="Missing 'agent' field")
    
    if x is None or y is None:
        raise HTTPException(status_code=400, detail="Missing 'x' or 'y' coordinates")
    
    if agent_id not in agent_states:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    
    # Validate coordinates are within bounds
    if not (X_RANGE[0] <= x <= X_RANGE[1] and Y_RANGE[0] <= y <= Y_RANGE[1]):
        raise HTTPException(
            status_code=400, 
            detail=f"Coordinates ({x}, {y}) outside boundaries. X: {X_RANGE}, Y: {Y_RANGE}"
        )
    
    # Store LLM target (GUI will read this and prioritize it)
    agent_states[agent_id]["llm_target"] = [float(x), float(y)]
    agent_states[agent_id]["last_update"] = datetime.now().isoformat()
    
    # Store in global targets dict (for easy access by GUI)
    llm_targets[agent_id] = (float(x), float(y))
    
    current_pos = agent_states[agent_id]["position"]
    is_jammed = agent_states[agent_id]["jammed"]
    comm_quality = agent_states[agent_id]["communication_quality"]
    
    print(f"[SIM API] LLM commanded {agent_id} to move to ({x}, {y})")
    print(f"[SIM API]   Current position: {current_pos}")
    print(f"[SIM API]   Jammed: {is_jammed}, Comm: {comm_quality}")
    
    return {
        "success": True,
        "message": f"LLM command accepted: {agent_id} will move to ({x}, {y})",
        "agent": agent_id,
        "target": [float(x), float(y)],
        "current_position": current_pos,
        "jammed": is_jammed,
        "communication_quality": comm_quality,
        "note": "Target will take priority over algorithmic movement"
    }

@app.get("/llm_targets")
async def get_llm_targets():
    """Get all active LLM-commanded targets"""
    return {"targets": llm_targets}

@app.delete("/llm_targets/{agent_id}")
async def clear_llm_target(agent_id: str):
    """Clear LLM target for an agent (resume algorithmic movement)"""
    if agent_id in llm_targets:
        del llm_targets[agent_id]
    
    if agent_id in agent_states:
        agent_states[agent_id]["llm_target"] = None
    
    return {"success": True, "message": f"Cleared LLM target for {agent_id}"}

@app.post("/llm_targets/clear_all")
async def clear_all_llm_targets():
    """Clear all LLM targets (all agents resume algorithmic movement)"""
    llm_targets.clear()
    
    for agent_id in agent_states:
        agent_states[agent_id]["llm_target"] = None
    
    return {"success": True, "message": "Cleared all LLM targets"}

# Initialize on startup
init_agents()

if __name__ == "__main__":
    print("="*60)
    print("Starting Simulation API with LLM Movement Control")
    print("="*60)
    print(f"Agents: {len(agent_states)}")
    print(f"Boundaries: X={X_RANGE}, Y={Y_RANGE}")
    print(f"Mission Endpoint: {MISSION_END}")
    print("="*60)
    uvicorn.run(app, host="0.0.0.0", port=5001)