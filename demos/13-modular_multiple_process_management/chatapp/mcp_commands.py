"""
Enhanced command parsing and handling for MCP chatapp.
Fixed duplicate message logging.
"""
import httpx
import json
import re
from datetime import datetime
from core.config import SIMULATION_API_URL, X_RANGE, Y_RANGE, MISSION_END
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
    from rag import get_known_agent_ids, format_all_agents_for_llm, get_agent_context
    from postgresql_store import get_conversation_history
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    print("[RAG] RAG not available")


async def handle_chat_message(message: str):
    """
    Main chat message handler with improved routing logic.
    
    Args:
        message: User message
        
    Returns:
        Response dictionary
    """
    # Log user message ONCE at the entry point
    timestamp = datetime.now().isoformat()
    add_log(message, {
        "source": "user",
        "message_type": "command",
        "timestamp": timestamp,
        "role": "user"  # Add role for clarity
    })
    
    # Handle special commands (quick responses without LLM)
    lower_msg = message.lower().strip()
    
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
    
    # CRITICAL: Classify intent FIRST before processing
    intent = classify_message_intent(message)
    
    print(f"[INTENT] Classified as: {intent}")
    
    if intent == "movement":
        return await handle_movement_command(message)
    elif intent == "multiple_movements":
        return await handle_multiple_movement_commands(message)
    elif intent == "question":
        return await handle_general_chat(message)
    else:
        # Default to general chat
        return await handle_general_chat(message)


def classify_message_intent(message: str) -> str:
    """
    Classify user message intent to prevent LLM from getting stuck.
    
    Returns:
        "movement" | "multiple_movements" | "question" | "report_request"
    """
    lower_msg = message.lower()
    
    # Movement keywords
    movement_keywords = ['move', 'go to', 'navigate', 'send', 'position', 'relocate', 'direct']
    
    # Question keywords
    question_keywords = ['what', 'why', 'how', 'when', 'where', 'who', 'is', 'are', 'can', 'should', 'tell me', 'explain']
    
    # Report keywords
    report_keywords = ['report', 'status', 'analyze', 'summary', 'overview']
    
    # Check for multiple agent movements
    agent_count = sum(1 for word in lower_msg.split() if 'agent' in word)
    if agent_count > 1 and any(kw in lower_msg for kw in movement_keywords):
        return "multiple_movements"
    
    # Check for single movement
    if any(kw in lower_msg for kw in movement_keywords):
        return "movement"
    
    # Check for explicit report request
    if any(kw in lower_msg for kw in report_keywords):
        return "report_request"
    
    # Check for question
    if any(kw in lower_msg for kw in question_keywords) or message.strip().endswith('?'):
        return "question"
    
    return "question"  # Default to question for safety


async def handle_movement_command(command: str):
    """Handle single agent movement commands with improved LLM parsing"""
    # NOTE: Do NOT log here - already logged in handle_chat_message
    
    if not LLM_AVAILABLE:
        return {"response": "⚠️ LLM not available for command parsing"}
    
    try:
        # Get available agents
        async with httpx.AsyncClient() as client:
            agents_response = await client.get(f"{SIMULATION_API_URL}/agents", timeout=2.0)
            
            available_agents = {}
            if agents_response.status_code == 200:
                available_agents = agents_response.json().get("agents", {})
        
        # IMPROVED PROMPT: More explicit about output format
        prompt = f"""You are a command parser for a GPS agent simulation system.

AVAILABLE AGENTS: {", ".join(available_agents.keys()) if available_agents else "None"}

SIMULATION BOUNDARIES:
- X: {X_RANGE[0]} to {X_RANGE[1]}
- Y: {Y_RANGE[0]} to {Y_RANGE[1]}

USER COMMAND: "{command}"

TASK: Extract movement parameters if this is a movement command.

RESPOND WITH EXACTLY ONE LINE IN THIS FORMAT:
agent_name,x_coordinate,y_coordinate

EXAMPLE RESPONSES:
- Input: "move agent1 to 5, 10" → Output: agent1,5,10
- Input: "send agent2 to coordinates -3.5 and 7.2" → Output: agent2,-3.5,7.2
- Input: "tell me about agent3" → Output: INVALID

RULES:
1. Agent name must exist in available agents
2. Coordinates must be numbers within boundaries
3. If not a movement command, output: INVALID
4. No explanations, just the format above

YOUR RESPONSE (one line only):"""
        
        ollama_client = get_ollama_client()
        model_name = get_model_name()
        
        response = chat_with_retry(
            ollama_client,
            model_name,
            messages=[{"role": "user", "content": prompt}]
        )

        if response is None:
            return {"response": "❌ LLM connection error. Is Ollama running?"}

        raw_response = response['message']['content'].strip()
        print(f"[LLM PARSE] Raw: {raw_response}")
        
        # Clean up response (remove any markdown, extra text)
        lines = raw_response.split('\n')
        parsed_line = None
        for line in lines:
            line = line.strip()
            if ',' in line and not line.startswith('#') and not line.startswith('*'):
                parsed_line = line
                break
        
        if not parsed_line:
            parsed_line = raw_response
        
        if "INVALID" in parsed_line.upper():
            return {"response": "❌ Not a valid movement command. Try: 'move agent1 to 5, 5'"}
        
        # Parse the response
        if "," in parsed_line and len(parsed_line.split(",")) >= 3:
            parts = parsed_line.split(",")
            agent_name = parts[0].strip()
            x_str = parts[1].strip()
            y_str = parts[2].strip()
            
            if agent_name not in available_agents:
                return {"response": f"❌ Agent '{agent_name}' not found. Available: {list(available_agents.keys())}"}
            
            try:
                x = float(x_str)
                y = float(y_str)
                
                # Validate coordinates
                if not (X_RANGE[0] <= x <= X_RANGE[1] and Y_RANGE[0] <= y <= Y_RANGE[1]):
                    return {"response": f"❌ Coordinates ({x}, {y}) outside boundaries. X: {X_RANGE}, Y: {Y_RANGE}"}
                
                # Execute movement
                move_result = await move_agent(agent_name, x, y)
                
                if move_result.get("success"):
                    return {"response": f"✅ {move_result.get('message', 'Movement executed')}"}
                else:
                    return {"response": f"❌ Movement failed: {move_result.get('message', 'Unknown error')}"}
            
            except ValueError:
                return {"response": f"❌ Invalid coordinates: {x_str}, {y_str}"}
        
        return {"response": "❌ Could not parse movement. Format: 'move agent1 to 5, 5'"}
        
    except Exception as e:
        return {"response": f"❌ Error: {str(e)}"}


async def handle_multiple_movement_commands(command: str):
    """
    Handle commands that move multiple agents at once.
    Example: "move agent1 to 5,5 and agent2 to -3,7"
    """
    # NOTE: Do NOT log here - already logged in handle_chat_message
    
    if not LLM_AVAILABLE:
        return {"response": "⚠️ LLM not available"}
    
    try:
        # Get available agents
        async with httpx.AsyncClient() as client:
            agents_response = await client.get(f"{SIMULATION_API_URL}/agents", timeout=2.0)
            available_agents = agents_response.json().get("agents", {}) if agents_response.status_code == 200 else {}
        
        prompt = f"""You are a command parser for multiple agent movements.

AVAILABLE AGENTS: {", ".join(available_agents.keys())}
BOUNDARIES: X: {X_RANGE}, Y: {Y_RANGE}

USER COMMAND: "{command}"

TASK: Extract ALL agent movements from this command.

RESPOND WITH VALID JSON ARRAY ONLY (no markdown, no explanation):
[
  {{"agent": "agent1", "x": 5.0, "y": 10.0}},
  {{"agent": "agent2", "x": -3.0, "y": 7.0}}
]

RULES:
1. Agent names must exist
2. Coordinates must be within boundaries
3. Output ONLY the JSON array
4. If no valid movements, output: []

YOUR JSON RESPONSE:"""
        
        ollama_client = get_ollama_client()
        model_name = get_model_name()
        
        response = chat_with_retry(
            ollama_client,
            model_name,
            messages=[{"role": "user", "content": prompt}]
        )

        if response is None:
            return {"response": "❌ LLM error"}

        raw_response = response['message']['content'].strip()
        
        # Extract JSON array
        json_match = re.search(r'\[.*\]', raw_response, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            movements = json.loads(json_str)
        else:
            movements = json.loads(raw_response)
        
        if not movements:
            return {"response": "❌ No valid movements found in command"}
        
        # Execute all movements
        results = []
        for mov in movements:
            agent = mov.get("agent")
            x = mov.get("x")
            y = mov.get("y")
            
            if agent and x is not None and y is not None:
                result = await move_agent(agent, x, y)
                if result.get("success"):
                    results.append(f"✅ {agent} → ({x}, {y})")
                else:
                    results.append(f"❌ {agent}: {result.get('message')}")
        
        return {"response": "**Multiple Movements Executed:**\n" + "\n".join(results)}
        
    except Exception as e:
        return {"response": f"❌ Error: {str(e)}"}


async def handle_general_chat(message: str):
    """
    Handle general conversation with IMPROVED prompting to avoid report loops.
    """
    # NOTE: Do NOT log here - already logged in handle_chat_message
    
    if not LLM_AVAILABLE or not RAG_AVAILABLE:
        return {"response": "❌ LLM or RAG not available"}
    
    print(f"\n{'='*60}")
    print(f"[CHAT] Processing general question")
    print(f"[CHAT] Message: {message}")
    
    try:
        # Get agent data
        agent_ids = get_known_agent_ids(limit=100)
        
        if agent_ids:
            # Get detailed context for ALL agents
            context = format_all_agents_for_llm(agent_ids)
        else:
            context = "⚠️ No agent data available yet."
        
        # Get recent conversation
        conversation = get_conversation_history(limit=5)
        conversation_text = "\n".join([
            f"{msg.get('metadata', {}).get('source', 'unknown')}: {msg.get('text', '')}"
            for msg in conversation[:3]
        ])
        
        # IMPROVED PROMPT: Explicitly prevent report generation unless asked
        prompt = f"""You are an AI assistant monitoring a multi-agent GPS simulation.

CURRENT SIMULATION STATE:
{context}

RECENT CONVERSATION:
{conversation_text}

USER QUESTION: "{message}"

MISSION CONTEXT:
- Agents must reach endpoint at {MISSION_END}
- Agents may be jammed (GPS denied)
- Jamming degrades communication quality

RESPONSE GUIDELINES:
1. Answer the user's question DIRECTLY and CONCISELY
2. DO NOT generate a full report unless explicitly asked
3. If asked "what's happening?", give a 2-3 sentence summary
4. If asked about specific agents, focus on those agents only
5. If suggesting actions, be specific (e.g., "Move agent1 to -5, 10")
6. Keep responses under 150 words unless more detail is requested

YOUR RESPONSE (be direct and conversational):"""
        
        ollama_client = get_ollama_client()
        model_name = get_model_name()
        
        response = chat_with_retry(
            ollama_client,
            model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        
        if response is None:
            return {"response": "❌ LLM connection error"}
        
        llm_response = response['message']['content']
        
        # Log LLM response (but NOT the user message again)
        add_log(llm_response, {
            "source": "llm",
            "message_type": "response",
            "timestamp": datetime.now().isoformat(),
            "role": "assistant"
        })
        
        print(f"[CHAT] Response generated ({len(llm_response)} chars)")
        print(f"{'='*60}\n")
        
        return {"response": llm_response}
        
    except Exception as e:
        print(f"[CHAT ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return {"response": f"❌ Error: {str(e)}"}