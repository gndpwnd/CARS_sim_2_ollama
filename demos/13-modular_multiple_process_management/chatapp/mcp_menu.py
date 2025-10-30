"""
Startup menu generation for MCP chatapp.
"""
from core.config import X_RANGE, Y_RANGE, MISSION_END

def generate_startup_menu():
    """Generate startup menu with simulation info"""
    menu = f"""🚀 **Multi-Agent Simulation Control System**

**SIMULATION BOUNDARIES:**
- X Range: {X_RANGE[0]} to {X_RANGE[1]}
- Y Range: {Y_RANGE[0]} to {Y_RANGE[1]}
- Mission Endpoint: ({MISSION_END[0]}, {MISSION_END[1]}) ⭐

**AVAILABLE COMMANDS:**

🔹 **Movement Commands:**
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