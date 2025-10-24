#!/usr/bin/env python3
"""
Simple RAG System - Retrieval Augmented Generation
Orchestrates data retrieval from Qdrant (telemetry) and PostgreSQL (messages)
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import traceback

# Import storage backends
try:
    from qdrant_store import (
        get_agent_position_history,
        get_nmea_messages,
        search_telemetry
    )
    QDRANT_AVAILABLE = True
except ImportError:
    print("[RAG] Warning: Qdrant store not available")
    QDRANT_AVAILABLE = False

try:
    from postgresql_store import (
        get_messages_by_source,
        get_agent_errors,
        get_conversation_history,
        retrieve_relevant
    )
    POSTGRESQL_AVAILABLE = True
except ImportError:
    print("[RAG] Warning: PostgreSQL store not available")
    POSTGRESQL_AVAILABLE = False


class SimpleRAG:
    """
    Simple RAG system that retrieves context for LLM queries
    
    Data Flow:
    - Telemetry (positions, NMEA, GPS metrics) → Qdrant
    - Messages (user, LLM, agent notifications) → PostgreSQL
    """
    
    def __init__(self, default_history_limit: int = 5):
        self.default_history_limit = default_history_limit
        print(f"[RAG] Initialized with history limit: {default_history_limit}")
    
    def get_agent_context(self, agent_id: str, history_limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Get comprehensive context for a specific agent
        
        Args:
            agent_id: Agent identifier (e.g., "agent_1")
            history_limit: Number of historical records to retrieve
        
        Returns:
            Dictionary with telemetry, messages, and status
        """
        limit = history_limit or self.default_history_limit
        context = {
            'agent_id': agent_id,
            'timestamp': datetime.now().isoformat(),
            'telemetry': {},
            'messages': {},
            'errors': []
        }
        
        # Get position history from Qdrant
        if QDRANT_AVAILABLE:
            try:
                positions = get_agent_position_history(agent_id, limit=limit)
                context['telemetry']['position_history'] = positions
                
                if positions:
                    context['telemetry']['current_position'] = positions[0]['position']
                    context['telemetry']['jammed'] = positions[0]['jammed']
                    context['telemetry']['communication_quality'] = positions[0]['communication_quality']
            except Exception as e:
                print(f"[RAG] Error getting position history: {e}")
                context['telemetry']['error'] = str(e)
        
        # Get agent messages from PostgreSQL
        if POSTGRESQL_AVAILABLE:
            try:
                messages = get_messages_by_source(agent_id, limit=limit)
                context['messages']['history'] = messages
                
                # Get errors specifically
                errors = get_agent_errors(agent_id, limit=limit)
                context['errors'] = errors
            except Exception as e:
                print(f"[RAG] Error getting messages: {e}")
                context['messages']['error'] = str(e)
        
        return context
    
    def get_all_agents_status(self, agent_ids: List[str]) -> Dict[str, Any]:
        """
        Get current status for all agents (lightweight, latest data only)
        
        Args:
            agent_ids: List of agent identifiers
        
        Returns:
            Dictionary mapping agent_id to current status
        """
        status = {}
        
        for agent_id in agent_ids:
            try:
                agent_status = {
                    'agent_id': agent_id,
                    'position': None,
                    'jammed': False,
                    'communication_quality': 0.0,
                    'error_count': 0
                }
                
                # Get latest position from Qdrant (just 1 record)
                if QDRANT_AVAILABLE:
                    positions = get_agent_position_history(agent_id, limit=1)
                    if positions:
                        latest = positions[0]
                        agent_status['position'] = latest['position']
                        agent_status['jammed'] = latest['jammed']
                        agent_status['communication_quality'] = latest['communication_quality']
                
                # Get error count from PostgreSQL
                if POSTGRESQL_AVAILABLE:
                    errors = get_agent_errors(agent_id, limit=10)
                    agent_status['error_count'] = len(errors)
                
                status[agent_id] = agent_status
                
            except Exception as e:
                print(f"[RAG] Error getting status for {agent_id}: {e}")
                status[agent_id] = {'error': str(e)}
        
        return status
    
    def get_nmea_context(self, agent_id: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent NMEA messages for analysis
        
        Args:
            agent_id: Optional agent filter
            limit: Number of messages
        
        Returns:
            List of NMEA message records
        """
        if not QDRANT_AVAILABLE:
            return []
        
        try:
            return get_nmea_messages(agent_id, limit=limit)
        except Exception as e:
            print(f"[RAG] Error getting NMEA messages: {e}")
            return []
    
    def semantic_search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """
        Perform semantic search across both databases
        
        Args:
            query: Natural language query
            limit: Max results per source
        
        Returns:
            Combined results from Qdrant and PostgreSQL
        """
        results = {
            'query': query,
            'telemetry_results': [],
            'message_results': []
        }
        
        # Search telemetry in Qdrant
        if QDRANT_AVAILABLE:
            try:
                telemetry = search_telemetry(query, limit=limit)
                results['telemetry_results'] = telemetry
            except Exception as e:
                print(f"[RAG] Error searching telemetry: {e}")
        
        # Search messages in PostgreSQL
        if POSTGRESQL_AVAILABLE:
            try:
                messages = retrieve_relevant(query, k=limit)
                results['message_results'] = messages
            except Exception as e:
                print(f"[RAG] Error searching messages: {e}")
        
        return results
    
    def get_conversation_context(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get recent conversation history (user/LLM messages only)
        
        Args:
            limit: Number of messages
        
        Returns:
            List of conversation messages
        """
        if not POSTGRESQL_AVAILABLE:
            return []
        
        try:
            return get_conversation_history(limit=limit)
        except Exception as e:
            print(f"[RAG] Error getting conversation: {e}")
            return []
    
    def format_agent_context_for_llm(self, agent_id: str, history_limit: Optional[int] = None) -> str:
        """
        Format agent context into a readable string for LLM consumption
        
        Args:
            agent_id: Agent identifier
            history_limit: Number of historical records
        
        Returns:
            Formatted string with all relevant context
        """
        context = self.get_agent_context(agent_id, history_limit)
        
        output = f"=== AGENT CONTEXT: {agent_id} ===\n\n"
        
        # Current Status
        if context['telemetry'].get('current_position'):
            pos = context['telemetry']['current_position']
            jammed = context['telemetry'].get('jammed', False)
            comm = context['telemetry'].get('communication_quality', 0)
            
            output += f"CURRENT STATUS:\n"
            output += f"  Position: ({pos[0]:.2f}, {pos[1]:.2f})\n"
            output += f"  Status: {'JAMMED' if jammed else 'CLEAR'}\n"
            output += f"  Communication Quality: {comm:.2f}\n\n"
        
        # Position History
        if context['telemetry'].get('position_history'):
            output += f"POSITION HISTORY (last {len(context['telemetry']['position_history'])} positions):\n"
            for i, pos_data in enumerate(context['telemetry']['position_history']):
                pos = pos_data['position']
                status = 'JAMMED' if pos_data['jammed'] else 'CLEAR'
                output += f"  {i+1}. ({pos[0]:.2f}, {pos[1]:.2f}) - {status}\n"
            output += "\n"
        
        # Recent Errors
        if context['errors']:
            output += f"RECENT ERRORS ({len(context['errors'])}):\n"
            for error in context['errors'][:3]:  # Show max 3
                output += f"  - {error.get('text', 'Unknown error')}\n"
            output += "\n"
        
        # Recent Messages
        if context['messages'].get('history'):
            output += f"RECENT MESSAGES:\n"
            for msg in context['messages']['history'][:3]:  # Show max 3
                output += f"  - {msg.get('text', 'No text')}\n"
            output += "\n"
        
        return output
    
    def format_all_agents_for_llm(self, agent_ids: List[str]) -> str:
        """
        Format status for all agents into LLM-friendly format
        
        Args:
            agent_ids: List of agent identifiers
        
        Returns:
            Formatted string with all agents' status
        """
        status = self.get_all_agents_status(agent_ids)
        
        output = "=== ALL AGENTS STATUS ===\n\n"
        
        for agent_id, data in status.items():
            if 'error' in data:
                output += f"{agent_id}: ERROR - {data['error']}\n"
                continue
            
            pos = data.get('position')
            jammed = data.get('jammed', False)
            comm = data.get('communication_quality', 0)
            errors = data.get('error_count', 0)
            
            status_emoji = "🔴" if jammed else "🟢"
            
            if pos:
                output += f"{status_emoji} {agent_id}: "
                output += f"({pos[0]:.2f}, {pos[1]:.2f}) "
                output += f"Comm: {comm:.2f} "
                if errors > 0:
                    output += f"[{errors} errors]"
                output += "\n"
            else:
                output += f"{agent_id}: No data available\n"
        
        return output


# Global RAG instance
_rag_instance = None

def get_rag() -> SimpleRAG:
    """Get or create global RAG instance"""
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = SimpleRAG()
    return _rag_instance


# Convenience functions
def get_agent_context(agent_id: str, history_limit: Optional[int] = None) -> Dict[str, Any]:
    """Convenience function to get agent context"""
    return get_rag().get_agent_context(agent_id, history_limit)

def get_all_agents_status(agent_ids: List[str]) -> Dict[str, Any]:
    """Convenience function to get all agents status"""
    return get_rag().get_all_agents_status(agent_ids)

def format_for_llm(agent_id: str, history_limit: Optional[int] = None) -> str:
    """Convenience function to format context for LLM"""
    return get_rag().format_agent_context_for_llm(agent_id, history_limit)

def format_all_agents_for_llm(agent_ids: List[str]) -> str:
    """Convenience function to format all agents for LLM"""
    return get_rag().format_all_agents_for_llm(agent_ids)


if __name__ == "__main__":
    print("Testing Simple RAG System...")
    
    rag = SimpleRAG(default_history_limit=5)
    
    # Test getting agent context
    print("\n1. Testing get_agent_context()...")
    context = rag.get_agent_context("agent_1")
    print(f"   Context keys: {list(context.keys())}")
    
    # Test formatting for LLM
    print("\n2. Testing format_agent_context_for_llm()...")
    formatted = rag.format_agent_context_for_llm("agent_1", history_limit=3)
    print(formatted)
    
    # Test all agents status
    print("\n3. Testing get_all_agents_status()...")
    status = rag.get_all_agents_status(["agent_1", "agent_2", "agent_3"])
    print(f"   Status for {len(status)} agents")
    
    # Test formatting all agents
    print("\n4. Testing format_all_agents_for_llm()...")
    all_formatted = rag.format_all_agents_for_llm(["agent_1", "agent_2"])
    print(all_formatted)
    
    print("\n✅ RAG system test complete")