"""
MCP tool definitions for agent control.
"""
import httpx
from datetime import datetime
from fastmcp import FastMCP
from core.config import SIMULATION_API_URL
from integrations import add_log

async def move_agent(agent: str, x: float, y: float) -> dict:
    """
    Move an agent to specific coordinates.
    
    Args:
        agent: Agent identifier
        x: X coordinate
        y: Y coordinate
        
    Returns:
        Result dictionary with success status and message
    """
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
                    message = (
                        f"Agent {agent} is currently jammed (Comm quality: {result.get('communication_quality', 0.2)}). "
                        f"It will first return to its last safe position at {result.get('current_position')} "
                        f"before proceeding to ({x}, {y})."
                    )
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

def register_tools(mcp: FastMCP):
    """
    Register MCP tools.
    
    Args:
        mcp: FastMCP instance
    """
    @mcp.tool()
    async def move_agent_tool(agent: str, x: float, y: float) -> dict:
        """Move an agent to specific coordinates"""
        return await move_agent(agent, x, y)