#!/usr/bin/env python3
"""
Enhanced LLM Agent with LIVE API data access
Adds Simulation API as primary source for current state
"""
import json
import httpx
from typing import Dict, List, Any, Optional
from datetime import datetime

try:
    from llm_config import chat_with_retry, get_ollama_client, get_model_name
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

try:
    from rag import get_known_agent_ids
    from postgresql_store import get_messages_by_source, get_agent_errors
    from qdrant_store import get_agent_position_history, search_telemetry
    from core.config import SIMULATION_API_URL, MISSION_END, X_RANGE, Y_RANGE
    DATA_AVAILABLE = True
except ImportError:
    DATA_AVAILABLE = False


# ENHANCED DATA SCHEMA WITH LIVE API
ENHANCED_DATA_SCHEMA = """
=== AVAILABLE DATA SOURCES (PRIORITY ORDER) ===

1. **LIVE SIMULATION API** [PRIMARY - MOST CURRENT]
   - Source: HTTP API at sim_api.py (in-memory state)
   - Returns: Real-time agent positions, jamming status, communication quality
   - Latency: <50ms
   - Use for: "What is happening NOW?", "Current status", "Where are agents?"
   - Request type: "live_agent_status"
   - Example: {"type": "live_agent_status", "agents": "all"}
   - ✅ ALWAYS USE THIS FOR CURRENT STATE QUESTIONS

2. **QDRANT TELEMETRY HISTORY** [SECONDARY - HISTORICAL]
   - Source: Qdrant vector database (logged telemetry)
   - Returns: Past positions, movement history, trends
   - Latency: ~100ms
   - Use for: "What happened in past 5 minutes?", "Movement trajectory", "Did X reach Y?"
   - Request type: "agent_history"
   - Example: {"type": "agent_history", "agent": "agent1", "limit": 30}

3. **POSTGRESQL LOGS** [TERTIARY - EVENTS & MESSAGES]
   - Source: PostgreSQL (structured logs)
   - Returns: Errors, notifications, user/LLM conversation
   - Use for: "What errors occurred?", "What did I ask before?"
   - Request type: "agent_errors" or "conversation_history"

=== DECISION TREE FOR DATA REQUESTS ===

User asks: "Where is agent1?"
→ Use: live_agent_status (most current)

User asks: "What agents are jammed?"
→ Use: live_agent_status (real-time status)

User asks: "What happened to agent2 in the last few minutes?"
→ Use: agent_history from Qdrant (historical telemetry)

User asks: "Has agent3 reached the endpoint?"
→ Use: live_agent_status + check if position == (10.0, 10.0)

User asks: "What errors did agent1 have?"
→ Use: agent_errors from PostgreSQL

=== CRITICAL RULES ===
1. For "current", "now", "status" → ALWAYS use live_agent_status
2. For "past", "history", "recently" → Use agent_history
3. Endpoint is at (10.0, 10.0)
4. Always check actual data, never guess
"""


class EnhancedLLMAgent:
    """LLM Agent with live API access"""
    
    def __init__(self):
        self.ollama_client = get_ollama_client() if LLM_AVAILABLE else None
        self.model_name = get_model_name() if LLM_AVAILABLE else None
        self.api_url = SIMULATION_API_URL
        
    async def answer_question(self, user_query: str) -> str:
        """Answer with live data priority"""
        if not LLM_AVAILABLE or not DATA_AVAILABLE:
            return "❌ LLM or data sources not available"
        
        print(f"\n{'='*60}")
        print(f"[LLM_AGENT] Processing: {user_query}")
        
        # Step 1: LLM decides what data it needs
        data_requests = await self._get_data_requests(user_query)
        
        if not data_requests:
            return await self._answer_without_data(user_query)
        
        # Step 2: Fetch data (with live API priority)
        print(f"[LLM_AGENT] Fetching {len(data_requests)} data sources...")
        fetched_data = await self._fetch_requested_data(data_requests)
        
        # Step 3: Generate answer
        answer = await self._generate_final_answer(user_query, fetched_data)
        
        print(f"[LLM_AGENT] ✓ Answer ready ({len(answer)} chars)")
        print(f"{'='*60}\n")
        
        return answer
    
    async def _get_data_requests(self, user_query: str) -> List[Dict[str, Any]]:
        """Ask LLM what data it needs"""
        
        prompt = f"""{ENHANCED_DATA_SCHEMA}

USER QUESTION: "{user_query}"

TASK: Determine what data sources you need to answer accurately.

PRIORITY RULES:
- For "current", "now", "status" → ALWAYS request live_agent_status
- For "past", "history", "recently" → Request agent_history
- For "errors" → Request agent_errors

Respond with ONLY a JSON array (no markdown):
[
  {{"type": "live_agent_status", "agents": "all"}},
  {{"type": "agent_history", "agent": "agent1", "limit": 20}}
]

If no data needed, return: []

YOUR JSON RESPONSE:"""
        
        response = chat_with_retry(
            self.ollama_client,
            self.model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        
        if response is None:
            return []
        
        llm_response = response['message']['content'].strip()
        
        try:
            # Clean markdown if present
            if llm_response.startswith("```"):
                lines = llm_response.split('\n')
                llm_response = '\n'.join([l for l in lines if not l.startswith('```')])
            
            data_requests = json.loads(llm_response)
            
            if not isinstance(data_requests, list):
                return []
            
            print(f"[LLM_AGENT] Parsed {len(data_requests)} data requests:")
            for req in data_requests:
                print(f"[LLM_AGENT]   - {req.get('type')}")
            
            return data_requests
            
        except json.JSONDecodeError as e:
            print(f"[LLM_AGENT] ⚠️ JSON parse error: {e}")
            return []
    
    async def _fetch_requested_data(self, requests: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Fetch data with LIVE API priority"""
        fetched = {}
        
        for req in requests:
            req_type = req.get('type')
            print(f"[LLM_AGENT]   Fetching: {req_type}")
            
            try:
                if req_type == "live_agent_status":
                    # NEW: Fetch from live API
                    agents = req.get('agents', [])
                    live_data = await self._fetch_live_api_data(agents)
                    fetched['live_agent_status'] = live_data
                    print(f"[LLM_AGENT]     ✓ Got live data for {len(live_data)} agents")
                
                elif req_type == "agent_history":
                    agent = req.get('agent')
                    limit = req.get('limit', 20)
                    history = get_agent_position_history(agent, limit=limit)
                    fetched[f'history_{agent}'] = history
                    print(f"[LLM_AGENT]     ✓ Got {len(history)} history entries")
                
                elif req_type == "agent_errors":
                    agent = req.get('agent')
                    limit = req.get('limit', 10)
                    errors = get_agent_errors(agent, limit=limit)
                    fetched[f'errors_{agent}'] = errors
                    print(f"[LLM_AGENT]     ✓ Got {len(errors)} errors")
                
                elif req_type == "telemetry_search":
                    query = req.get('query', '')
                    limit = req.get('limit', 20)
                    results = search_telemetry(query, limit=limit)
                    fetched['telemetry_search'] = results
                    print(f"[LLM_AGENT]     ✓ Got {len(results)} search results")
                
            except Exception as e:
                print(f"[LLM_AGENT]     ✗ Error fetching {req_type}: {e}")
        
        return fetched
    
    async def _fetch_live_api_data(self, agents: Any) -> Dict[str, Any]:
        """
        NEW: Fetch current state from live Simulation API
        This is the SOURCE OF TRUTH for current positions
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_url}/agents",
                    timeout=2.0
                )
                
                if response.status_code != 200:
                    print(f"[API] ✗ HTTP {response.status_code}")
                    return {}
                
                api_data = response.json().get("agents", {})
                
                # Filter if specific agents requested
                if agents != "all" and isinstance(agents, list):
                    api_data = {k: v for k, v in api_data.items() if k in agents}
                
                # Format for LLM
                formatted = {}
                for agent_id, data in api_data.items():
                    formatted[agent_id] = {
                        'position': data.get('position', [0, 0]),
                        'jammed': data.get('jammed', False),
                        'communication_quality': data.get('communication_quality', 0),
                        'timestamp': datetime.now().isoformat(),
                        'source': 'LIVE_API'
                    }
                    print(f"[API] ✓ {agent_id}: pos={formatted[agent_id]['position']}, jammed={formatted[agent_id]['jammed']}")
                
                return formatted
                
        except httpx.TimeoutException:
            print("[API] ✗ Timeout - is sim_api.py running?")
            return {}
        except Exception as e:
            print(f"[API] ✗ Error: {e}")
            return {}
    
    async def _generate_final_answer(self, user_query: str, fetched_data: Dict[str, Any]) -> str:
        """Generate answer with fetched data"""
        
        # Format data summary
        data_summary = []
        
        for key, value in fetched_data.items():
            if key == 'live_agent_status':
                data_summary.append("\n=== LIVE AGENT STATUS (MOST CURRENT) ===")
                for agent_id, data in value.items():
                    pos = data['position']
                    jammed = "JAMMED" if data['jammed'] else "CLEAR"
                    comm = data['communication_quality']
                    data_summary.append(
                        f"{agent_id}: position=({pos[0]:.2f}, {pos[1]:.2f}), "
                        f"status={jammed}, comm_quality={comm:.2f}"
                    )
            
            elif key.startswith('history_'):
                agent = key.replace('history_', '')
                data_summary.append(f"\n=== HISTORY: {agent} ({len(value)} entries) ===")
                for i, item in enumerate(value[:10]):  # Show first 10
                    pos = item.get('position', [0, 0])
                    jammed = "JAMMED" if item.get('jammed') else "CLEAR"
                    ts = item.get('timestamp', 'unknown')
                    data_summary.append(
                        f"  [{i}] pos=({pos[0]:.2f}, {pos[1]:.2f}), {jammed}, time={ts}"
                    )
            
            elif key.startswith('errors_'):
                agent = key.replace('errors_', '')
                data_summary.append(f"\n=== ERRORS: {agent} ({len(value)} errors) ===")
                for item in value[:5]:
                    data_summary.append(f"  - {item.get('text', '')[:100]}")
        
        prompt = f"""You are answering a question about a multi-agent GPS simulation.

MISSION CONTEXT:
- Mission Endpoint: {MISSION_END}
- Boundaries: X: {X_RANGE}, Y: {Y_RANGE}
- Agents navigate from origin to endpoint
- Position {MISSION_END} = mission complete

USER QUESTION: "{user_query}"

LIVE DATA (fetched from running simulation):
{"".join(data_summary)}

TASK: Answer accurately using ONLY the data above.

RULES:
1. Use LIVE_API data for current state (highest priority)
2. Reference actual agent IDs and their data
3. Check if position == {MISSION_END} for completion
4. Be specific with numbers from the data
5. 2-4 sentences max

YOUR ANSWER:"""
        
        response = chat_with_retry(
            self.ollama_client,
            self.model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        
        if response is None:
            return "❌ Error generating answer"
        
        return response['message']['content'].strip()
    
    async def _answer_without_data(self, user_query: str) -> str:
        """Answer conceptual questions without data"""
        
        prompt = f"""You are an expert on a multi-agent GPS simulation system.

USER QUESTION: "{user_query}"

Answer briefly about the system itself (2-3 sentences).

YOUR ANSWER:"""
        
        response = chat_with_retry(
            self.ollama_client,
            self.model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        
        if response is None:
            return "❌ Error"
        
        return response['message']['content'].strip()


# Global instance
_enhanced_agent = None

def get_enhanced_agent() -> EnhancedLLMAgent:
    """Get or create enhanced agent"""
    global _enhanced_agent
    if _enhanced_agent is None:
        _enhanced_agent = EnhancedLLMAgent()
    return _enhanced_agent


async def answer_with_enhanced_agent(user_query: str) -> str:
    """Answer using enhanced agent with live API"""
    agent = get_enhanced_agent()
    return await agent.answer_question(user_query)