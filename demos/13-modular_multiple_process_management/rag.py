#!/usr/bin/env python3
"""
Improved RAG System - Informed by Streaming Fix Insights
CRITICAL LEARNINGS:
- Qdrant: Use point IDs for deduplication, iterations for sorting
- Don't rely on Qdrant timestamps for filtering
- Use scroll() with limit, then sort/filter in Python
- Simulation API still useful as source of truth for "NOW"
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from collections import deque
import traceback

# Import storage backends
try:
    from qdrant_store import (
        qdrant_client,
        TELEMETRY_COLLECTION,
        NMEA_COLLECTION
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

try:
    import httpx
    from core.config import SIMULATION_API_URL, MISSION_END, X_RANGE, Y_RANGE
    API_AVAILABLE = True
except ImportError:
    print("[RAG] Warning: Simulation API not available")
    API_AVAILABLE = False


class ImprovedRAG:
    """
    RAG system that uses lessons learned from streaming fixes:
    1. Qdrant: Point IDs for deduplication, iterations for sorting
    2. API: Source of truth for current positions
    3. PostgreSQL: Reliable for structured logs
    """
    
    def __init__(self, default_history_limit: int = 20):
        self.default_history_limit = default_history_limit
        self._model = None
        
        # Track what we've seen (like streaming does)
        self._seen_point_ids = deque(maxlen=500)
        
        print(f"[RAG] Initialized with history limit: {default_history_limit}")
    
    def _get_model(self):
        """Lazy load sentence transformer model"""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
        return self._model
    
    def get_live_agent_positions(self) -> Dict[str, Any]:
        """
        Get CURRENT agent positions from Simulation API (source of truth)
        Falls back to Qdrant if API unavailable
        
        Returns:
            Dict of agent_id -> current state
        """
        if not API_AVAILABLE:
            print("[RAG] API unavailable, falling back to Qdrant")
            return self._get_positions_from_qdrant()
        
        try:
            import asyncio
            
            async def fetch_api():
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{SIMULATION_API_URL}/agents",
                        timeout=2.0
                    )
                    if response.status_code == 200:
                        return response.json().get("agents", {})
                return {}
            
            # Run async in sync context
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            api_data = loop.run_until_complete(fetch_api())
            
            if api_data:
                print(f"[RAG] Got live data from API for {len(api_data)} agents")
                return api_data
            
        except Exception as e:
            print(f"[RAG] API fetch failed: {e}, falling back to Qdrant")
        
        return self._get_positions_from_qdrant()
    
    def _get_positions_from_qdrant(self) -> Dict[str, Any]:
        """
        Fallback: Get positions from Qdrant using streaming-proven method
        Uses point IDs and iteration sorting (NOT timestamp filtering)
        """
        if not QDRANT_AVAILABLE or not qdrant_client:
            return {}
        
        try:
            # Use same approach as streaming: fetch more, sort by iteration
            results = qdrant_client.scroll(
                collection_name=TELEMETRY_COLLECTION,
                limit=200,  # Fetch extra to ensure we get latest
                with_payload=True,
                with_vectors=False
            )[0]
            
            # Group by agent, sort by iteration (like streaming does)
            agent_latest = {}
            
            for point in results:
                payload = point.payload
                agent_id = payload.get('agent_id')
                iteration = payload.get('iteration') or 0
                
                if not agent_id:
                    continue
                
                # Keep only latest iteration per agent
                if agent_id not in agent_latest:
                    agent_latest[agent_id] = {
                        'iteration': iteration,
                        'data': payload
                    }
                elif iteration > agent_latest[agent_id]['iteration']:
                    agent_latest[agent_id] = {
                        'iteration': iteration,
                        'data': payload
                    }
            
            # Format for output
            formatted = {}
            for agent_id, info in agent_latest.items():
                data = info['data']
                formatted[agent_id] = {
                    'position': [
                        float(data.get('position_x', 0)),
                        float(data.get('position_y', 0))
                    ],
                    'jammed': bool(data.get('jammed', False)),
                    'communication_quality': float(data.get('communication_quality', 0)),
                    'iteration': info['iteration'],
                    'timestamp': data.get('timestamp', ''),
                    'source': 'QDRANT'
                }
            
            print(f"[RAG] Got Qdrant data for {len(formatted)} agents")
            return formatted
            
        except Exception as e:
            print(f"[RAG] Qdrant fetch failed: {e}")
            traceback.print_exc()
            return {}
    
    def get_agent_position_history(
        self, 
        agent_id: str, 
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get position history from Qdrant using streaming-proven approach
        CRITICAL: Uses iteration sorting, not timestamp filtering
        
        Args:
            agent_id: Agent identifier
            limit: Number of history entries
            
        Returns:
            List of position records, newest first
        """
        if not QDRANT_AVAILABLE or not qdrant_client:
            return []
        
        try:
            # Fetch more than needed (like streaming does)
            results = qdrant_client.scroll(
                collection_name=TELEMETRY_COLLECTION,
                scroll_filter={
                    "must": [
                        {"key": "agent_id", "match": {"value": agent_id}}
                    ]
                },
                limit=limit * 3,  # Overfetch to ensure we get recent data
                with_payload=True,
                with_vectors=False
            )[0]
            
            # Convert to history records
            history = []
            for point in results:
                payload = point.payload
                
                try:
                    history.append({
                        'position': (
                            float(payload.get('position_x', 0)),
                            float(payload.get('position_y', 0))
                        ),
                        'jammed': bool(payload.get('jammed', False)),
                        'communication_quality': float(payload.get('communication_quality', 0)),
                        'iteration': payload.get('iteration') or 0,
                        'timestamp': payload.get('timestamp', ''),
                        'point_id': str(point.id)
                    })
                except (ValueError, TypeError) as e:
                    print(f"[RAG] Warning: Could not parse position data: {e}")
                    continue
            
            # Sort by iteration (most reliable), then limit
            history.sort(key=lambda x: x.get('iteration', 0), reverse=True)
            history = history[:limit]
            
            print(f"[RAG] Got {len(history)} history entries for {agent_id}")
            return history
            
        except Exception as e:
            print(f"[RAG] Error getting history for {agent_id}: {e}")
            traceback.print_exc()
            return []
    
    def get_documentation_context(
        self, 
        query: Optional[str] = None, 
        max_docs: int = 3
    ) -> str:
        """
        Retrieve relevant documentation snippets from PostgreSQL
        (This works fine - timestamps are reliable here)
        """
        if not POSTGRESQL_AVAILABLE:
            return ""
        
        try:
            with psycopg2.connect(**DB_CONFIG) as conn:
                with conn.cursor() as cur:
                    if query:
                        # Vector search for relevant docs
                        model = self._get_model()
                        query_vec = model.encode([query])[0].tolist()
                        
                        cur.execute(f"""
                            SELECT text, metadata
                            FROM logs
                            WHERE metadata->>'message_type' = 'documentation'
                            ORDER BY embedding <-> %s::vector
                            LIMIT %s;
                        """, (query_vec, max_docs))
                    else:
                        # Get high-priority docs
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
                        return ""
                    
                    # Format documentation
                    doc_text = "=== SYSTEM DOCUMENTATION ===\n\n"
                    for text, metadata in docs:
                        doc_type = metadata.get('doc_type', 'general')
                        if len(text) > 1000:
                            text = text[:1000] + "\n... (truncated)"
                        doc_text += f"[{doc_type.upper()}]\n{text}\n\n"
                    
                    return doc_text
                    
        except Exception as e:
            print(f"[RAG] Error retrieving documentation: {e}")
            return ""
    
    def get_agent_errors_and_events(
        self, 
        agent_id: str, 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recent errors from PostgreSQL (timestamps work here)
        """
        if not POSTGRESQL_AVAILABLE:
            return []
        
        try:
            # Get errors
            errors = get_agent_errors(agent_id, limit=limit)
            
            # Normalize timestamps
            for error in errors:
                if 'created_at' in error:
                    if isinstance(error['created_at'], datetime):
                        error['created_at'] = error['created_at'].isoformat()
                    elif not isinstance(error['created_at'], str):
                        error['created_at'] = str(error['created_at'])
            
            return errors
            
        except Exception as e:
            print(f"[RAG] Error getting events for {agent_id}: {e}")
            return []
    
    def assemble_context_for_llm(
        self, 
        query: str,
        agent_ids: List[str],
        include_documentation: bool = True,
        include_history: bool = False,
        history_limit: int = 5
    ) -> str:
        """
        Assemble complete context using proven data access patterns
        
        Args:
            query: User's question
            agent_ids: Agents to include
            include_documentation: Include system docs
            include_history: Include position history (slower)
            history_limit: How many history entries per agent
            
        Returns:
            Formatted context string
        """
        context_parts = []
        
        # 1. DOCUMENTATION (if relevant)
        if include_documentation:
            needs_docs = any(word in query.lower() for word in [
                'how', 'what is', 'explain', 'why', 'works', 'system'
            ])
            
            if needs_docs:
                docs = self.get_documentation_context(query, max_docs=2)
                if docs:
                    context_parts.append(docs)
                    context_parts.append("="*60 + "\n")
        
        # 2. LIVE AGENT DATA (source of truth)
        if agent_ids:
            live_data = self.get_live_agent_positions()
            
            if live_data:
                context_parts.append("=== CURRENT AGENT STATUS (LIVE) ===\n")
                
                for agent_id in agent_ids:
                    if agent_id not in live_data:
                        continue
                    
                    data = live_data[agent_id]
                    pos = data['position']
                    jammed = data['jammed']
                    comm = data['communication_quality']
                    source = data.get('source', 'API')
                    
                    status_emoji = "🔴" if jammed else "🟢"
                    context_parts.append(
                        f"{status_emoji} **{agent_id}**: Position ({pos[0]:.2f}, {pos[1]:.2f}) | "
                        f"{'JAMMED' if jammed else 'CLEAR'} | Comm: {comm:.2f} | Source: {source}\n"
                    )
                
                context_parts.append("\n")
            else:
                context_parts.append("⚠️ No live agent data available\n\n")
        
        # 3. POSITION HISTORY (if requested)
        if include_history and agent_ids:
            context_parts.append("=== RECENT MOVEMENT HISTORY ===\n")
            
            for agent_id in agent_ids[:3]:  # Limit to 3 agents for context size
                history = self.get_agent_position_history(agent_id, limit=history_limit)
                
                if history:
                    context_parts.append(f"\n**{agent_id}** (last {len(history)} positions):\n")
                    for i, entry in enumerate(history[:3]):  # Show only 3
                        pos = entry['position']
                        jammed = "JAMMED" if entry['jammed'] else "CLEAR"
                        iter_num = entry.get('iteration', '?')
                        context_parts.append(
                            f"  [{i}] Iter {iter_num}: ({pos[0]:.2f}, {pos[1]:.2f}) - {jammed}\n"
                        )
            
            context_parts.append("\n")
        
        # 4. RECENT ERRORS (if any)
        if agent_ids:
            any_errors = False
            for agent_id in agent_ids[:2]:  # Check first 2 agents
                events = self.get_agent_errors_and_events(agent_id, limit=2)
                if events:
                    if not any_errors:
                        context_parts.append("=== RECENT ERRORS ===\n")
                        any_errors = True
                    
                    for event in events[:2]:
                        text = event.get('text', '')[:100]
                        context_parts.append(f"[{agent_id}] {text}\n")
            
            if any_errors:
                context_parts.append("\n")
        
        return "".join(context_parts)
    
    def get_quick_status_summary(self, agent_ids: List[str]) -> str:
        """
        Quick status using live API data only (fastest)
        """
        live_data = self.get_live_agent_positions()
        
        if not live_data:
            return "⚠️ No agent data available"
        
        summary = []
        jammed_count = 0
        
        for agent_id in agent_ids:
            if agent_id in live_data:
                data = live_data[agent_id]
                pos = data['position']
                jammed = data['jammed']
                comm = data['communication_quality']
                source = data.get('source', 'API')
                
                if jammed:
                    jammed_count += 1
                
                status = "JAMMED" if jammed else "CLEAR"
                summary.append(
                    f"{agent_id}: ({pos[0]:.1f}, {pos[1]:.1f}) {status} "
                    f"[comm:{comm:.2f}] ({source})"
                )
            else:
                summary.append(f"{agent_id}: No data")
        
        result = "\n".join(summary)
        
        if jammed_count > 0:
            result = f"⚠️ {jammed_count} agent(s) jammed\n\n" + result
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


# Convenience functions for LLM agent
def format_for_llm(
    query: str, 
    agent_ids: List[str], 
    minimal: bool = False,
    include_history: bool = False
) -> str:
    """
    Format context for LLM with options
    
    Args:
        query: User's question
        agent_ids: Agents to include
        minimal: Quick status only (no docs/history)
        include_history: Include movement history
    """
    rag = get_rag()
    
    if minimal:
        return rag.get_quick_status_summary(agent_ids)
    else:
        return rag.assemble_context_for_llm(
            query,
            agent_ids,
            include_documentation=True,
            include_history=include_history
        )


def get_known_agent_ids(limit: int = 50) -> List[str]:
    """
    Discover agent IDs from live API or Qdrant
    API is source of truth, Qdrant is fallback
    """
    agent_ids = set()
    
    # Try API first (source of truth)
    if API_AVAILABLE:
        try:
            import asyncio
            
            async def get_agents_from_api():
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{SIMULATION_API_URL}/agents",
                        timeout=2.0
                    )
                    if response.status_code == 200:
                        return list(response.json().get("agents", {}).keys())
                return []
            
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            api_agents = loop.run_until_complete(get_agents_from_api())
            if api_agents:
                agent_ids.update(api_agents)
                print(f"[RAG] Found {len(api_agents)} agents from API")
                return sorted(list(agent_ids))
        except Exception as e:
            print(f"[RAG] Could not get agents from API: {e}")
    
    # Fallback: Qdrant
    if QDRANT_AVAILABLE and qdrant_client:
        try:
            results = qdrant_client.scroll(
                collection_name=TELEMETRY_COLLECTION,
                limit=limit * 2,
                with_payload=True,
                with_vectors=False
            )[0]
            
            for point in results:
                agent_id = point.payload.get('agent_id')
                if agent_id:
                    agent_ids.add(agent_id)
            
            if agent_ids:
                print(f"[RAG] Found {len(agent_ids)} agents from Qdrant")
        except Exception as e:
            print(f"[RAG] Error scanning Qdrant: {e}")
    
    if not agent_ids:
        print("[RAG] ⚠️ No agents found")
    
    return sorted(list(agent_ids))


if __name__ == "__main__":
    print("Testing Improved RAG System...")
    
    rag = ImprovedRAG()
    
    # Test 1: Get live positions
    print("\n1. Testing live agent positions...")
    positions = rag.get_live_agent_positions()
    print(f"   Got data for {len(positions)} agents")
    for agent_id, data in list(positions.items())[:2]:
        print(f"   - {agent_id}: {data['position']} (source: {data.get('source')})")
    
    # Test 2: Get agent IDs
    print("\n2. Testing agent discovery...")
    agents = get_known_agent_ids()
    print(f"   Found agents: {agents}")
    
    # Test 3: Get history
    if agents:
        print(f"\n3. Testing position history for {agents[0]}...")
        history = rag.get_agent_position_history(agents[0], limit=5)
        print(f"   Got {len(history)} history entries")
        for i, entry in enumerate(history[:3]):
            print(f"   [{i}] Iter {entry.get('iteration')}: {entry['position']}")
    
    # Test 4: Full context assembly
    print("\n4. Testing context assembly...")
    if agents:
        context = rag.assemble_context_for_llm(
            "What's happening with the agents?",
            agents,
            include_documentation=False,
            include_history=True
        )
        print(f"   Assembled {len(context)} characters of context")
        print("\n" + "="*60)
        print(context[:500] + "...")
        print("="*60)
    
    print("\n✅ Improved RAG test complete")