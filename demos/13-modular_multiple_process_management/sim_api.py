#!/usr/bin/env python3
"""
Simulation API Service
Provides HTTP API for agent simulation state
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

def init_agents():
    """Initialize agent states"""
    for agent_id in get_agent_ids(NUM_AGENTS):
        agent_states[agent_id] = {
            "position": [0.0, 0.0],  # Start at origin
            "jammed": False,
            "communication_quality": 1.0,
            "last_update": datetime.now().isoformat()
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

# Initialize on startup
init_agents()

if __name__ == "__main__":
    print("Starting Simulation API...")
    uvicorn.run(app, host="0.0.0.0", port=5001)