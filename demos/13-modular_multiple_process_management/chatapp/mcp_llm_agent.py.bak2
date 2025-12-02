#!/usr/bin/env python3
"""
LLM Agent with Data Request Capability
FIXED: Better understanding of history queries for "past few minutes" questions
"""
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

try:
    from llm_config import chat_with_retry, get_ollama_client, get_model_name
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    print("[LLM_AGENT] LLM not available")

try:
    from rag import get_known_agent_ids
    from postgresql_store import (
        get_messages_by_source,
        get_agent_errors,
        get_conversation_history
    )
    from qdrant_store import (
        get_agent_position_history,
        search_telemetry
    )
    import httpx
    from core.config import SIMULATION_API_URL, MISSION_END, X_RANGE, Y_RANGE
    DATA_AVAILABLE = True
except ImportError:
    DATA_AVAILABLE = False
    print("[LLM_AGENT] Data sources not available")


# IMPROVED DATA SCHEMA WITH CLEAR HISTORY EXAMPLES
DATA_SCHEMA = """
=== AVAILABLE DATA SOURCES ===

1. AGENT CURRENT STATUS (Real-time from Qdrant - last known position)
   - Source: Qdrant telemetry database (most recent entry per agent)
   - Returns: Current position, jamming status, communication quality
   - Use for: "What is the current status?", "Where is agent X now?", "What agents are jammed?"
   - Request type: "agent_positions"
   - Example: {"type": "agent_positions", "agents": ["agent1", "agent2"]} or {"type": "agent_positions", "agents": "all"}

2. AGENT POSITION HISTORY (Time-series from Qdrant - past movements)
   - Source: Qdrant telemetry database (last N entries per agent)
   - Returns: List of {position: (x,y), jammed: bool, communication_quality: float, timestamp: str}
   - Use for: "What happened in the past few minutes?", "Which agents WERE jammed?", "Movement trajectory", "Did agent X reach Y?"
   - Request type: "agent_history"
   - Example: {"type": "agent_history", "agent": "agent1", "limit": 20}
   - IMPORTANT: Use limit=20-50 for "past few minutes" questions to see recent changes

3. AGENT ERRORS & EVENTS (From PostgreSQL)
   - Source: PostgreSQL logs
   - Returns: List of {text: str, metadata: dict, created_at: timestamp, type: "error"|"notification"}
   - Use for: Understanding problems, jamming incidents, recovery attempts
   - Request type: "agent_errors"
   - Example: {"type": "agent_errors", "agent": "agent1", "limit": 5}

4. SEMANTIC TELEMETRY SEARCH (Vector search in Qdrant)
   - Source: Qdrant vector database
   - Returns: Relevant telemetry matching semantic query
   - Use for: Finding specific situations like "jammed agents", "agents near endpoint"
   - Request type: "telemetry_search"
   - Example: {"type": "telemetry_search", "query": "agents that were jammed recently", "limit": 30}

5. MISSION CONTEXT (Static configuration)
   - Mission Endpoint: (10.0, 10.0)
   - Simulation Boundaries: X: [-50, 50], Y: [-50, 50]
   - Agents start near origin (0, 0)
   - Agents must navigate from origin to endpoint
   - "jammed: true" = Agent is in GPS denial zone (CURRENTLY JAMMED)
   - "jammed: false" = Agent has good GPS signal (CURRENTLY CLEAR)
   - communication_quality < 0.5 = Poor/denied GPS
   - communication_quality >= 0.5 = Good GPS

=== COMMON QUESTIONS & RECOMMENDED DATA ===

Q: "Where is agent X?" or "What agents are jammed NOW?"
→ Request: {"type": "agent_positions", "agents": ["agentX"]} or {"type": "agent_positions", "agents": "all"}

Q: "What agents WERE jammed in the past few minutes?" or "What happened to agent X recently?"
→ Request: {"type": "agent_history", "agent": "agentX", "limit": 30}
→ Then analyze the history to see jamming status changes over time

Q: "What agents have reached the endpoint?"
→ Request: {"type": "agent_positions", "agents": "all"}
→ Then check which are at (10.0, 10.0)

Q: "Show me trajectory of agent X" or "Did agent X move recently?"
→ Request: {"type": "agent_history", "agent": "agentX", "limit": 20}

Q: "What errors occurred?" or "What happened to agent X?"
→ Request: [{"type": "agent_history", "agent": "agentX", "limit": 10}, {"type": "agent_errors", "agent": "agentX", "limit": 5}]

=== CRITICAL NOTES ===
- For "past few minutes" or "recently" questions: ALWAYS use agent_history with limit=20-50
- For "current" or "now" questions: Use agent_positions
- Position (10.0, 10.0) = mission endpoint
- Check ACTUAL data from responses, don't assume or guess
"""


class SimplifiedLLMAgent:
    """
    Simplified LLM Agent that gets schema upfront, requests data once.
    """
    
    def __init__(self):
        self.ollama_client = get_ollama_client() if LLM_AVAILABLE else None
        self.model_name = get_model_name() if LLM_AVAILABLE else None
        
    async def answer_question(self, user_query: str) -> str:
        """
        Answer user question with single data request.
        
        Args:
            user_query: User's question
            
        Returns:
            Final answer
        """
        if not LLM_AVAILABLE or not DATA_AVAILABLE:
            return "❌ LLM or data sources not available"
        
        print(f"\n{'='*60}")
        print(f"[LLM_AGENT] Processing: {user_query}")
        
        # Step 1: Ask LLM what data it needs (with full schema)
        data_requests = await self._get_data_requests(user_query)
        
        if not data_requests:
            print(f"[LLM_AGENT] ⚠️  LLM didn't request data, answering directly")
            return await self._answer_without_data(user_query)
        
        # Step 2: Fetch all requested data
        print(f"[LLM_AGENT] Fetching {len(data_requests)} data items...")
        fetched_data = await self._fetch_requested_data(data_requests)
        
        # Step 3: LLM constructs final answer with data
        print(f"[LLM_AGENT] Generating final answer...")
        answer = await self._generate_final_answer(user_query, fetched_data)
        
        print(f"[LLM_AGENT] ✓ Answer ready ({len(answer)} chars)")
        print(f"{'='*60}\n")
        
        return answer
    
    async def _get_data_requests(self, user_query: str) -> List[Dict[str, Any]]:
        """Ask LLM what data it needs (given full schema)"""
        
        prompt = f"""{DATA_SCHEMA}

USER QUESTION: "{user_query}"

TASK: Based on the question, determine what data you need to answer accurately.

CRITICAL RULES:
- For "past few minutes", "recently", "were jammed", "what happened": Use agent_history with limit=20-50
- For "current", "now", "are jammed": Use agent_positions
- Request ONLY the data needed for THIS specific question
- Use "all" for agents if asking about multiple/all agents

Respond with ONLY a JSON array of data requests (no markdown, no explanation):
[
  {{"type": "agent_positions", "agents": "all"}},
  {{"type": "agent_history", "agent": "agent1", "limit": 30}}
]

If you can answer without any data (e.g., explaining system concepts), return: []

YOUR JSON RESPONSE (array only, no markdown):"""
        
        response = chat_with_retry(
            self.ollama_client,
            self.model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        
        if response is None:
            print("[LLM_AGENT] ❌ LLM connection error")
            return []
        
        llm_response = response['message']['content'].strip()
        print(f"[LLM_AGENT] Data request response: {llm_response[:200]}...")
        
        try:
            # Clean up response
            json_str = llm_response
            if json_str.startswith("```"):
                lines = json_str.split('\n')
                json_str = '\n'.join([l for l in lines if not l.startswith('```')])
            
            data_requests = json.loads(json_str)
            
            if not isinstance(data_requests, list):
                print(f"[LLM_AGENT] ⚠️  Expected list, got: {type(data_requests)}")
                return []
            
            print(f"[LLM_AGENT] Parsed {len(data_requests)} data requests")
            for req in data_requests:
                print(f"[LLM_AGENT]   - {req.get('type')}: {req}")
            
            return data_requests
            
        except json.JSONDecodeError as e:
            print(f"[LLM_AGENT] ⚠️  Could not parse data requests: {e}")
            print(f"[LLM_AGENT] Raw: {llm_response}")
            import re
            match = re.search(r'\[.*\]', llm_response, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except:
                    pass
            return []
    
    async def _fetch_requested_data(self, requests: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Fetch all requested data from Qdrant (primary source)"""
        fetched = {}
        
        for req in requests:
            req_type = req.get('type')
            print(f"[LLM_AGENT]   Fetching: {req_type}")
            
            try:
                if req_type == "agent_positions":
                    # Get current positions from Qdrant (most recent entry)
                    agents = req.get('agents', [])
                    if agents == "all":
                        agents = get_known_agent_ids(limit=100)
                    elif not isinstance(agents, list):
                        agents = [agents]
                    
                    agent_data = {}
                    for agent_id in agents:
                        history = get_agent_position_history(agent_id, limit=1)
                        if history:
                            current = history[0]
                            agent_data[agent_id] = {
                                'position': list(current['position']),
                                'jammed': current['jammed'],
                                'communication_quality': current['communication_quality'],
                                'timestamp': current['timestamp']
                            }
                            print(f"[LLM_AGENT]     ✓ {agent_id}: pos={current['position']}, jammed={current['jammed']}")
                    
                    fetched['agent_positions'] = agent_data
                    print(f"[LLM_AGENT]     ✓ Got data for {len(agent_data)} agents")
                
                elif req_type == "agent_history":
                    # Get position history from Qdrant
                    agent = req.get('agent')
                    limit = req.get('limit', 10)
                    
                    history = get_agent_position_history(agent, limit=limit)
                    fetched[f'history_{agent}'] = history
                    print(f"[LLM_AGENT]     ✓ Got {len(history)} history entries for {agent}")
                
                elif req_type == "agent_errors":
                    agent = req.get('agent')
                    limit = req.get('limit', 10)
                    
                    errors = get_agent_errors(agent, limit=limit)
                    fetched[f'errors_{agent}'] = errors
                    print(f"[LLM_AGENT]     ✓ Got {len(errors)} errors for {agent}")
                
                elif req_type == "telemetry_search":
                    query = req.get('query', '')
                    limit = req.get('limit', 20)
                    
                    results = search_telemetry(query, limit=limit)
                    fetched['telemetry_search'] = results
                    print(f"[LLM_AGENT]     ✓ Got {len(results)} telemetry results")
                
            except Exception as e:
                print(f"[LLM_AGENT]     ✗ Error fetching {req_type}: {e}")
                import traceback
                traceback.print_exc()
        
        return fetched
    
    async def _generate_final_answer(self, user_query: str, fetched_data: Dict[str, Any]) -> str:
        """Generate final answer with fetched data"""
        
        # Format data nicely
        data_summary = []
        for key, value in fetched_data.items():
            if isinstance(value, dict):
                data_summary.append(f"\n=== {key.upper().replace('_', ' ')} ===")
                for k, v in value.items():
                    if isinstance(v, dict):
                        pos = v.get('position', [0, 0])
                        jammed = v.get('jammed', False)
                        comm = v.get('communication_quality', 0)
                        data_summary.append(
                            f"{k}: position={pos}, jammed={jammed}, comm_quality={comm:.2f}"
                        )
                    else:
                        data_summary.append(f"{k}: {v}")
            elif isinstance(value, list):
                data_summary.append(f"\n=== {key.upper().replace('_', ' ')} ({len(value)} items) ===")
                for i, item in enumerate(value[:15]):  # Show first 15 items
                    if isinstance(item, dict):
                        pos = item.get('position', [0, 0])
                        jammed = item.get('jammed', False)
                        ts = item.get('timestamp', 'unknown')
                        data_summary.append(f"  [{i}] pos={pos}, jammed={jammed}, time={ts}")
                    else:
                        data_summary.append(f"  [{i}] {str(item)[:100]}")
                if len(value) > 15:
                    data_summary.append(f"  ... and {len(value) - 15} more entries")
        
        prompt = f"""You are answering a question about a multi-agent GPS simulation.

MISSION CONTEXT:
- Mission Endpoint: {MISSION_END}
- Agents must navigate from origin to endpoint
- Agents at position {MISSION_END} have reached the endpoint
- "jammed: true" = Agent WAS/IS in GPS denial zone at that timestamp
- "jammed: false" = Agent WAS/IS clear at that timestamp
- communication_quality < 0.5 = Poor/denied GPS
- communication_quality >= 0.5 = Good GPS

USER QUESTION: "{user_query}"

LIVE DATA RETRIEVED (from running simulation):
{"".join(data_summary)}

TASK: Answer the user's question accurately using ONLY the data above.

CRITICAL RULES:
1. For "past few minutes" questions: Look at the HISTORY data and identify jamming status CHANGES over time
2. For "current" questions: Look at the POSITIONS data for current status
3. Check ACTUAL positions - agent at {MISSION_END} = reached endpoint
4. Check ACTUAL jammed status in the data - don't guess
5. If history shows jammed=true at any timestamp, that agent WAS jammed at that time
6. Reference specific agent IDs and their ACTUAL data from above
7. Be precise - don't guess or assume

YOUR ANSWER (direct, factual, 2-4 sentences):"""
        
        response = chat_with_retry(
            self.ollama_client,
            self.model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        
        if response is None:
            return "❌ Error generating answer"
        
        return response['message']['content'].strip()
    
    async def _answer_without_data(self, user_query: str) -> str:
        """Answer questions that don't need data (e.g., system explanations)"""
        
        prompt = f"""You are an expert on a multi-agent GPS simulation system.

SYSTEM OVERVIEW:
{DATA_SCHEMA}

USER QUESTION: "{user_query}"

TASK: Answer the user's question about the system itself (not about current agent status).

YOUR ANSWER (2-3 sentences):"""
        
        response = chat_with_retry(
            self.ollama_client,
            self.model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        
        if response is None:
            return "❌ Error generating answer"
        
        return response['message']['content'].strip()


# Global instance
_llm_agent = None

def get_llm_agent() -> SimplifiedLLMAgent:
    """Get or create global LLM agent"""
    global _llm_agent
    if _llm_agent is None:
        _llm_agent = SimplifiedLLMAgent()
    return _llm_agent


async def answer_with_llm_agent(user_query: str) -> str:
    """
    Answer user query using simplified LLM agent.
    
    Args:
        user_query: User's question
        
    Returns:
        Answer string
    """
    agent = get_llm_agent()
    return await agent.answer_question(user_query)