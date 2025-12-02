#!/usr/bin/env python3
"""
Improved RAG System - FIXED vector type casting and agent discovery

FIXES:
1. Proper vector casting for PostgreSQL queries
2. Better agent ID discovery from Qdrant
3. Fallback mechanisms when data is missing
4. Timestamp normalization for sorting
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import traceback

# Import storage backends
try:
    from qdrant_store import (
        get_agent_position_history,
        get_nmea_messages,
        search_telemetry,
        qdrant_client,
        TELEMETRY_COLLECTION
    )
    QDRANT_AVAILABLE = True
except ImportError:
    print("[RAG] Warning: Qdrant store not available")
    QDRANT_AVAILABLE = False
    qdrant_client = None

try:
    from postgresql_store import (
        get_messages_by_source,
        get_agent_errors,
        get_conversation_history,
        retrieve_relevant
    )
    import psycopg2
    from core.config import DB_CONFIG
    POSTGRESQL_AVAILABLE = True
except ImportError:
    print("[RAG] Warning: PostgreSQL store not available")
    POSTGRESQL_AVAILABLE = False


class ImprovedRAG:
    """
    Improved RAG with proper data segregation and fixed queries
    """
    
    def __init__(self, default_history_limit: int = 5):
        self.default_history_limit = default_history_limit
        self._model = None  # Lazy load sentence transformer
        print(f"[RAG] Initialized with history limit: {default_history_limit}")
    
    def _get_model(self):
        """Lazy load sentence transformer model"""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
        return self._model
    
    def get_documentation_context(self, query: Optional[str] = None, max_docs: int = 3) -> str:
        """
        Retrieve relevant documentation snippets.
        FIXED: Proper vector casting for PostgreSQL
        
        Args:
            query: Optional query to find relevant docs
            max_docs: Maximum documentation chunks to retrieve
            
        Returns:
            Formatted documentation string
        """
        if not POSTGRESQL_AVAILABLE:
            return ""
        
        try:
            with psycopg2.connect(**DB_CONFIG) as conn:
                with conn.cursor() as cur:
                    if query:
                        # FIXED: Generate embedding and cast properly
                        model = self._get_model()
                        query_vec = model.encode([query])[0].tolist()
                        
                        # FIXED: Cast the list to vector type explicitly
                        cur.execute(f"""
                            SELECT text, metadata
                            FROM logs
                            WHERE metadata->>'message_type' = 'documentation'
                            ORDER BY embedding <-> %s::vector
                            LIMIT %s;
                        """, (query_vec, max_docs))
                    else:
                        # Get high-priority docs (like system overview)
                        cur.execute("""
                            SELECT text, metadata
                            FROM logs
                            WHERE metadata->>'message_type' = 'documentation'
                            AND (metadata->>'priority' = 'high' 
                                 OR metadata->>'doc_type' = 'system_overview')
                            ORDER BY created_at DESC
                            LIMIT %s;
                        """, (max_docs,))
                    
                    docs = cur.fetchall()
                    
                    if not docs:
                        print("[RAG] No documentation found in database")
                        return ""
                    
                    # Format documentation
                    doc_text = "=== SYSTEM DOCUMENTATION ===\n\n"
                    for text, metadata in docs:
                        doc_type = metadata.get('doc_type', 'general')
                        # Truncate very long docs
                        if len(text) > 1000:
                            text = text[:1000] + "\n... (truncated)"
                        doc_text += f"[{doc_type.upper()}]\n{text}\n\n"
                    
                    return doc_text
                    
        except Exception as e:
            print(f"[RAG] Error retrieving documentation: {e}")
            traceback.print_exc()
            return ""
    
    def get_live_agent_data(self, agent_ids: List[str], history_limit: int = 5) -> Dict[str, Any]:
        """
        Get CURRENT/RECENT telemetry for agents from Qdrant.
        IMPROVED: Better error handling and fallbacks
        
        Args:
            agent_ids: List of agent IDs
            history_limit: How many recent positions to retrieve
            
        Returns:
            Dictionary with current positions and recent history
        """
        if not QDRANT_AVAILABLE:
            print("[RAG] Qdrant not available")
            return {}
        
        agents_data = {}
        
        for agent_id in agent_ids:
            try:
                # Get recent position history
                positions = get_agent_position_history(agent_id, limit=history_limit)
                
                if positions:
                    current = positions[0]  # Most recent
                    
                    agents_data[agent_id] = {
                        'current_position': current['position'],
                        'jammed': current['jammed'],
                        'communication_quality': current['communication_quality'],
                        'timestamp': current['timestamp'],
                        'position_history': [
                            {
                                'position': p['position'],
                                'jammed': p['jammed'],
                                'timestamp': p['timestamp']
                            }
                            for p in positions
                        ]
                    }
                else:
                    print(f"[RAG] No position data for {agent_id}")
            except Exception as e:
                print(f"[RAG] Error getting data for {agent_id}: {e}")
                continue
        
        return agents_data
    
    def get_agent_errors_and_events(self, agent_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent errors and important events for an agent.
        FIXED: Normalize timestamps before sorting
        
        Args:
            agent_id: Agent identifier
            limit: Max events to retrieve
            
        Returns:
            List of error/event records
        """
        if not POSTGRESQL_AVAILABLE:
            return []
        
        try:
            # Get errors
            errors = get_agent_errors(agent_id, limit=limit)
            
            # FIXED: Normalize error timestamps to strings
            for error in errors:
                if 'created_at' in error:
                    if isinstance(error['created_at'], datetime):
                        error['created_at'] = error['created_at'].isoformat()
                    elif not isinstance(error['created_at'], str):
                        error['created_at'] = str(error['created_at'])
            
            # Get notifications (recovery events, etc.)
            with psycopg2.connect(**DB_CONFIG) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT text, metadata, created_at
                        FROM logs
                        WHERE metadata->>'source' = %s
                        AND metadata->>'message_type' = 'notification'
                        ORDER BY created_at DESC
                        LIMIT %s;
                    """, (agent_id, limit))
                    
                    notifications = [
                        {
                            'text': row[0],
                            'metadata': row[1],
                            'created_at': row[2].isoformat() if isinstance(row[2], datetime) else str(row[2]),
                            'type': 'notification'
                        }
                        for row in cur.fetchall()
                    ]
            
            # Combine and sort by time (all timestamps now strings)
            all_events = errors + notifications
            all_events.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            
            return all_events[:limit]
            
        except Exception as e:
            print(f"[RAG] Error getting events for {agent_id}: {e}")
            traceback.print_exc()
            return []
    
    def assemble_context_for_llm(
        self, 
        query: str,
        agent_ids: List[str],
        include_documentation: bool = True,
        include_conversation: bool = True
    ) -> str:
        """
        Assemble complete context for LLM with proper structure.
        IMPROVED: Better empty data handling
        
        Args:
            query: User's question
            agent_ids: List of agents to include
            include_documentation: Whether to include system docs
            include_conversation: Whether to include chat history
            
        Returns:
            Formatted context string for LLM
        """
        context_parts = []
        
        # 1. DOCUMENTATION (if relevant to query)
        if include_documentation:
            # Only include docs if query seems to need system knowledge
            needs_docs = any(word in query.lower() for word in [
                'how', 'what is', 'explain', 'why', 'works', 'system', 'architecture',
                'jamming', 'recovery', 'gps', 'mission'
            ])
            
            if needs_docs:
                docs = self.get_documentation_context(query, max_docs=2)
                if docs:
                    context_parts.append(docs)
                    context_parts.append("="*60 + "\n")
        
        # 2. LIVE AGENT DATA
        if agent_ids:
            live_data = self.get_live_agent_data(agent_ids, history_limit=5)
            
            if live_data:
                context_parts.append("=== CURRENT AGENT STATUS ===\n")
                
                for agent_id, data in live_data.items():
                    pos = data['current_position']
                    jammed = data['jammed']
                    comm = data['communication_quality']
                    
                    status_emoji = "🔴" if jammed else "🟢"
                    context_parts.append(
                        f"{status_emoji} **{agent_id}**: Position ({pos[0]:.2f}, {pos[1]:.2f}) | "
                        f"{'JAMMED' if jammed else 'CLEAR'} | Comm Quality: {comm:.2f}\n"
                    )
                    
                    # Show recent trajectory if agent moved significantly
                    if len(data['position_history']) > 1:
                        prev_pos = data['position_history'][1]['position']
                        if abs(pos[0] - prev_pos[0]) > 1 or abs(pos[1] - prev_pos[1]) > 1:
                            context_parts.append(f"   Recent move: ({prev_pos[0]:.2f}, {prev_pos[1]:.2f}) → ({pos[0]:.2f}, {pos[1]:.2f})\n")
                
                context_parts.append("\n")
            else:
                context_parts.append("⚠️ No live agent data available in telemetry database\n\n")
        
        # 3. RECENT ERRORS/EVENTS (if any)
        if agent_ids:
            any_errors = False
            for agent_id in agent_ids:
                events = self.get_agent_errors_and_events(agent_id, limit=3)
                if events:
                    if not any_errors:
                        context_parts.append("=== RECENT EVENTS/ERRORS ===\n")
                        any_errors = True
                    
                    for event in events:
                        event_type = event.get('metadata', {}).get('message_type', 'unknown')
                        text = event.get('text', '')
                        context_parts.append(f"[{agent_id}] {event_type.upper()}: {text}\n")
            
            if any_errors:
                context_parts.append("\n")
        
        # 4. CONVERSATION HISTORY (brief, if requested)
        if include_conversation:
            try:
                conversation = get_conversation_history(limit=3)
                if conversation:
                    context_parts.append("=== RECENT CONVERSATION ===\n")
                    for msg in conversation[-3:]:  # Last 3 messages
                        role = msg.get('metadata', {}).get('source', 'unknown')
                        text = msg.get('text', '')
                        # Truncate long messages
                        if len(text) > 150:
                            text = text[:150] + "..."
                        context_parts.append(f"{role}: {text}\n")
                    context_parts.append("\n")
            except Exception as e:
                print(f"[RAG] Error getting conversation: {e}")
        
        return "".join(context_parts)
    
    def get_quick_status_summary(self, agent_ids: List[str]) -> str:
        """
        Get a quick, concise status summary.
        IMPROVED: Better handling of missing data
        
        Args:
            agent_ids: List of agents
            
        Returns:
            Brief status string
        """
        live_data = self.get_live_agent_data(agent_ids, history_limit=1)
        
        if not live_data:
            return "⚠️ No agent telemetry data available. Agents may not be running or data not yet recorded."
        
        summary = []
        jammed_count = 0
        
        for agent_id in agent_ids:
            if agent_id in live_data:
                data = live_data[agent_id]
                pos = data['current_position']
                jammed = data['jammed']
                comm = data['communication_quality']
                
                if jammed:
                    jammed_count += 1
                
                status = "JAMMED" if jammed else "CLEAR"
                summary.append(f"{agent_id}: ({pos[0]:.1f}, {pos[1]:.1f}) {status} [{comm:.2f}]")
            else:
                summary.append(f"{agent_id}: No data")
        
        result = "\n".join(summary)
        
        if jammed_count > 0:
            result = f"⚠️  {jammed_count} agent(s) jammed\n\n" + result
        else:
            result = "✅ All agents clear\n\n" + result
        
        return result


# Global RAG instance
_rag_instance = None

def get_rag() -> ImprovedRAG:
    """Get or create global RAG instance"""
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = ImprovedRAG()
    return _rag_instance


def format_for_llm(query: str, agent_ids: List[str], minimal: bool = False) -> str:
    """
    Format context for LLM with proper structure.
    
    Args:
        query: User's question
        agent_ids: Agents to include
        minimal: If True, skip docs and history for quick responses
        
    Returns:
        Formatted context string
    """
    rag = get_rag()
    
    if minimal:
        return rag.get_quick_status_summary(agent_ids)
    else:
        return rag.assemble_context_for_llm(
            query,
            agent_ids,
            include_documentation=True,
            include_conversation=True
        )


def get_known_agent_ids(limit: int = 50) -> List[str]:
    """
    Discover agent IDs from stored telemetry data.
    IMPROVED: Better scanning and fallback to API
    
    Args:
        limit: Number of recent records to scan
        
    Returns:
        List of unique agent IDs
    """
    agent_ids = set()
    
    # Try Qdrant first
    if QDRANT_AVAILABLE and qdrant_client:
        try:
            # Scroll with larger limit to ensure we get all agents
            results = qdrant_client.scroll(
                collection_name=TELEMETRY_COLLECTION,
                limit=limit * 2,  # Get more records
                with_payload=True,
                with_vectors=False
            )[0]
            
            for point in results:
                agent_id = point.payload.get('agent_id')
                if agent_id:
                    agent_ids.add(agent_id)
            
            if agent_ids:
                print(f"[RAG] Found {len(agent_ids)} agents from Qdrant: {sorted(agent_ids)}")
                return sorted(list(agent_ids))
        except Exception as e:
            print(f"[RAG] Error scanning Qdrant for agents: {e}")
    
    # Fallback: Try to get from simulation API
    try:
        import httpx
        from core.config import SIMULATION_API_URL
        
        import asyncio
        async def get_agents_from_api():
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{SIMULATION_API_URL}/agents", timeout=2.0)
                if response.status_code == 200:
                    return list(response.json().get("agents", {}).keys())
            return []
        
        # Run async function
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        api_agents = loop.run_until_complete(get_agents_from_api())
        if api_agents:
            agent_ids.update(api_agents)
            print(f"[RAG] Found {len(api_agents)} agents from API: {sorted(api_agents)}")
    except Exception as e:
        print(f"[RAG] Could not get agents from API: {e}")
    
    # Fallback: Check PostgreSQL messages
    if not agent_ids and POSTGRESQL_AVAILABLE:
        try:
            with psycopg2.connect(**DB_CONFIG) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT DISTINCT metadata->>'source'
                        FROM logs
                        WHERE metadata->>'source' LIKE 'agent%'
                        LIMIT %s;
                    """, (limit,))
                    
                    for row in cur.fetchall():
                        if row[0]:
                            agent_ids.add(row[0])
            
            if agent_ids:
                print(f"[RAG] Found {len(agent_ids)} agents from PostgreSQL: {sorted(agent_ids)}")
        except Exception as e:
            print(f"[RAG] Error scanning PostgreSQL for agents: {e}")
    
    if not agent_ids:
        print("[RAG] ⚠️ No agents found in any data source. Run the simulation first.")
    
    return sorted(list(agent_ids))


# Backward compatibility
def get_agent_context(agent_id: str, history_limit: Optional[int] = None) -> Dict[str, Any]:
    """Get agent context (legacy function)"""
    rag = get_rag()
    live_data = rag.get_live_agent_data([agent_id], history_limit or 5)
    events = rag.get_agent_errors_and_events(agent_id, limit=10)
    
    return {
        'agent_id': agent_id,
        'live_data': live_data.get(agent_id, {}),
        'events': events
    }


if __name__ == "__main__":
    print("Testing Improved RAG System...")
    
    rag = ImprovedRAG()
    
    # Test documentation retrieval
    print("\n1. Testing documentation context...")
    docs = rag.get_documentation_context("How does GPS jamming work?")
    print(f"   Retrieved {len(docs)} characters of documentation")
    if docs:
        print(f"   Preview: {docs[:200]}...")
    
    # Test agent discovery
    print("\n2. Testing agent discovery...")
    agents = get_known_agent_ids(limit=100)
    print(f"   Found agents: {agents}")
    
    # Test live data retrieval
    if agents:
        print("\n3. Testing live agent data...")
        live_data = rag.get_live_agent_data(agents[:3], history_limit=3)
        print(f"   Retrieved data for {len(live_data)} agents")
        for agent_id, data in live_data.items():
            print(f"   - {agent_id}: {data.get('current_position')}")
    
    # Test context assembly
    print("\n4. Testing context assembly...")
    if agents:
        context = rag.assemble_context_for_llm(
            "What's happening with the agents?",
            agents,
            include_documentation=True,
            include_conversation=True
        )
        print(f"   Assembled {len(context)} characters of context")
        print("\n" + "="*60)
        print(context)
        print("="*60)
    
    print("\n✅ Improved RAG test complete")