"""
Command parsing and handling for MCP chatapp.
"""
import httpx
from datetime import datetime
from core.config import SIMULATION_API_URL, X_RANGE, Y_RANGE
from integrations import add_log
from .mcp_tools import move_agent
from .mcp_reports import (
    generate_status_report, generate_detailed_report,
    list_agents, get_agent_info
)

# Import LLM
try:
    from llm_config import chat_with_retry, get_ollama_client, get_model_name
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    print("[LLM] LLM not available")

# Import RAG
try:
    from rag import get_known_agent_ids, format_all_agents_for_llm
    from postgresql_store import get_conversation_history
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    print("[RAG] RAG not available")

async def handle_chat_message(message: str):
    """
    Main chat message handler with routing logic.
    
    Args:
        message: User message
        
    Returns:
        Response dictionary
    """
    # Log user message
    timestamp = datetime.now().isoformat()
    add_log(message, {
        "source": "user",
        "message_type": "command",
        "timestamp": timestamp
    })
    
    # Handle special commands (quick responses without LLM)
    lower_msg = message.lower()
    
    if lower_msg in ['help', 'menu', 'commands']:
        from .mcp_menu import generate_startup_menu
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
        return await handle_movement_command(message)
    
    # Otherwise, let LLM handle general conversation
    return await handle_general_chat(message)

async def handle_movement_command(command: str):
    """Handle movement commands with LLM parsing"""
    if not LLM_AVAILABLE:
        return {"response": "❌ LLM not available for command parsing"}
    
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
        
        ollama_client = get_ollama_client()
        model_name = get_model_name()
        
        response = chat_with_retry(
            ollama_client,
            model_name,
            messages=[{"role": "user", "content": prompt}]
        )

        if response is None:
            return {"response": "✗ LLM connection error. Is Ollama running?"}

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
    if not LLM_AVAILABLE or not RAG_AVAILABLE:
        return {"response": "❌ LLM or RAG not available"}
    
    print(f"\n{'='*60}")
    print(f"[CHAT] handle_general_chat() called")
    print(f"[CHAT] Message: {message}")
    print(f"{'='*60}")
    
    try:
        # Discover agents from stored data
        print("[CHAT] Discovering agents from stored data...")
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
        from core.config import MISSION_END
        prompt = f"""Current Simulation State:
{context}

{conversation_text}

User Question: {message}

You are an assistant helping monitor a multi-agent simulation. The agents are trying to reach the mission endpoint at ({MISSION_END[0]}, {MISSION_END[1]}) while avoiding jamming zones.

Provide a helpful, concise response based on the current simulation state. If you need more specific data, suggest what command the user should run (like 'status', 'report', or 'agents')."""
        
        print(f"[CHAT] Prompt built: {len(prompt)} characters")
        
        # Call Ollama
        ollama_client = get_ollama_client()
        model_name = get_model_name()
        
        print(f"[CHAT] Calling Ollama with model: {model_name}")
        
        response = chat_with_retry(
            ollama_client,
            model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        
        if response is None:
            print("[CHAT] ERROR: chat_with_retry returned None")
            return {"response": "❌ LLM connection error. Is Ollama running?"}
        
        print("[CHAT] Received response from Ollama")
        llm_response = response['message']['content']
        print(f"[CHAT] Response length: {len(llm_response)} characters")
        
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
        print(f"[CHAT ERROR] Exception: {str(e)}")
        print(f"{'='*60}")
        import traceback
        traceback.print_exc()
        print(f"{'='*60}\n")
        return {"response": f"❌ Error in conversation: {str(e)}"}