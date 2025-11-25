"""
Enhanced report generation with better RAG context utilization.
Leverages hybrid PostgreSQL + Qdrant data for rich reports.
"""
import httpx
from datetime import datetime
from core.config import SIMULATION_API_URL, MISSION_END
from integrations import add_log

# Import RAG
try:
    from rag import (
        format_for_llm, 
        format_all_agents_for_llm, 
        get_agent_context,
        get_all_agents_status,
        get_rag
    )
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    print("[RAG] RAG not available")

# Import storage directly for deep analysis
try:
    from postgresql_store import (
        get_messages_by_source,
        get_agent_errors,
        get_conversation_history
    )
    from qdrant_store import (
        get_agent_position_history,
        get_nmea_messages,
        search_telemetry
    )
    STORAGE_AVAILABLE = True
except ImportError:
    STORAGE_AVAILABLE = False
    print("[STORAGE] Direct storage access not available")

# Import LLM
try:
    from llm_config import chat_with_retry, get_ollama_client, get_model_name
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    print("[LLM] LLM not available")


async def generate_status_report():
    """Quick status overview without LLM (fast)"""
    if not RAG_AVAILABLE:
        return {"response": "❌ RAG system not available"}
    
    try:
        async with httpx.AsyncClient() as client:
            agents_response = await client.get(f"{SIMULATION_API_URL}/agents", timeout=2.0)
            
            if agents_response.status_code != 200:
                return {"response": "❌ Could not retrieve agents"}
            
            agents_data = agents_response.json().get("agents", {})
            agent_ids = list(agents_data.keys())
            
            # Use RAG for formatted status
            status_text = format_all_agents_for_llm(agent_ids)
            
            report = "📊 **SIMULATION STATUS**\n\n"
            report += status_text
            report += f"\n🎯 **Mission Endpoint:** {MISSION_END}\n"
            report += f"⏰ **Report Time:** {datetime.now().strftime('%H:%M:%S')}\n"
            
            return {"response": report}
            
    except Exception as e:
        return {"response": f"❌ Error: {str(e)}"}


async def generate_detailed_report():
    """
    Enhanced detailed report leveraging BOTH PostgreSQL and Qdrant.
    Provides rich analysis with historical context.
    """
    if not RAG_AVAILABLE or not LLM_AVAILABLE or not STORAGE_AVAILABLE:
        return {"response": "❌ Required systems not available"}
    
    try:
        # Get all agents
        async with httpx.AsyncClient() as client:
            agents_response = await client.get(f"{SIMULATION_API_URL}/agents", timeout=2.0)
        
        if agents_response.status_code != 200:
            return {"response": "❌ Could not retrieve agents"}
        
        agents_data = agents_response.json().get("agents", {})
        agent_ids = list(agents_data.keys())
        
        # Build RICH context from multiple sources
        context_parts = []
        
        # 1. Current agent status (from RAG)
        context_parts.append("=== CURRENT AGENT STATUS ===")
        for agent_id in agent_ids:
            agent_ctx = get_agent_context(agent_id, history_limit=5)
            formatted = format_for_llm(agent_id, history_limit=5)
            context_parts.append(formatted)
        
        # 2. Position history (from Qdrant)
        context_parts.append("\n=== MOVEMENT HISTORY ===")
        for agent_id in agent_ids:
            history = get_agent_position_history(agent_id, limit=10)
            if history:
                context_parts.append(f"\n{agent_id} recent positions:")
                for i, pos_data in enumerate(history[:5]):
                    pos = pos_data['position']
                    status = 'JAMMED' if pos_data['jammed'] else 'CLEAR'
                    context_parts.append(f"  {i+1}. ({pos[0]:.2f}, {pos[1]:.2f}) - {status}")
        
        # 3. Error analysis (from PostgreSQL)
        context_parts.append("\n=== ERROR ANALYSIS ===")
        total_errors = 0
        for agent_id in agent_ids:
            errors = get_agent_errors(agent_id, limit=5)
            if errors:
                total_errors += len(errors)
                context_parts.append(f"\n{agent_id} errors ({len(errors)}):")
                for err in errors[:3]:
                    context_parts.append(f"  - {err.get('text', 'Unknown')}")
        
        if total_errors == 0:
            context_parts.append("No errors reported.")
        
        # 4. GPS/NMEA data (from Qdrant)
        context_parts.append("\n=== GPS TELEMETRY ===")
        for agent_id in agent_ids:
            nmea_msgs = get_nmea_messages(agent_id, limit=3)
            if nmea_msgs:
                latest = nmea_msgs[0]
                context_parts.append(f"\n{agent_id} latest GPS:")
                context_parts.append(f"  Fix Quality: {latest.get('fix_quality', 'unknown')}")
                context_parts.append(f"  Satellites: {latest.get('satellites', 'unknown')}")
        
        full_context = "\n".join(context_parts)
        
        # Ask LLM for STRUCTURED analysis
        prompt = f"""{full_context}

SIMULATION GOAL: Agents must reach mission endpoint at {MISSION_END} while avoiding jamming zones.

Generate a comprehensive analysis report with these sections:

1. **Executive Summary** (2-3 sentences)
2. **Agent Performance**
   - Which agents are making progress?
   - Which agents are struggling?
3. **Jamming Impact**
   - Which areas are jammed?
   - How is it affecting mission?
4. **Movement Recommendations**
   - Specific actionable commands (e.g., "move agent1 to X, Y")
5. **Risk Assessment**
   - Critical issues requiring immediate attention

Keep each section concise (2-4 sentences). Focus on actionable insights."""
        
        ollama_client = get_ollama_client()
        model_name = get_model_name()
        
        response = chat_with_retry(
            ollama_client,
            model_name,
            messages=[{"role": "user", "content": prompt}]
        )

        if response is None:
            return {"response": "❌ LLM connection error"}

        llm_report = response['message']['content']
        
        # Log the report
        add_log(llm_report, {
            "source": "llm",
            "message_type": "response",
            "report_type": "detailed_analysis",
            "timestamp": datetime.now().isoformat()
        })
        
        return {"response": f"📋 **DETAILED ANALYSIS REPORT**\n\n{llm_report}"}
        
    except Exception as e:
        return {"response": f"❌ Error: {str(e)}"}


async def generate_agent_trajectory_report(agent_id: str):
    """
    Generate trajectory analysis for a specific agent.
    Uses Qdrant position history.
    """
    if not STORAGE_AVAILABLE or not LLM_AVAILABLE:
        return {"response": "❌ Required systems not available"}
    
    try:
        # Get extensive position history
        history = get_agent_position_history(agent_id, limit=50)
        
        if not history:
            return {"response": f"❌ No trajectory data for {agent_id}"}
        
        # Analyze trajectory
        jammed_count = sum(1 for p in history if p['jammed'])
        jammed_percentage = (jammed_count / len(history)) * 100
        
        # Get position changes
        positions = [p['position'] for p in history]
        if len(positions) >= 2:
            start = positions[-1]  # Oldest
            end = positions[0]     # Newest
            distance = ((end[0] - start[0])**2 + (end[1] - start[1])**2)**0.5
        else:
            distance = 0
        
        # Calculate progress toward mission endpoint
        current_pos = positions[0]
        mission_distance = ((MISSION_END[0] - current_pos[0])**2 + 
                           (MISSION_END[1] - current_pos[1])**2)**0.5
        
        # Build context
        context = f"""TRAJECTORY ANALYSIS FOR {agent_id}

Total positions tracked: {len(history)}
Jammed positions: {jammed_count} ({jammed_percentage:.1f}%)
Distance traveled: {distance:.2f} units
Current distance to mission endpoint: {mission_distance:.2f} units

RECENT PATH (last 10 positions):
"""
        for i, pos_data in enumerate(history[:10]):
            pos = pos_data['position']
            status = 'JAMMED' if pos_data['jammed'] else 'CLEAR'
            context += f"{i+1}. ({pos[0]:.2f}, {pos[1]:.2f}) - {status}\n"
        
        prompt = f"""{context}

MISSION ENDPOINT: {MISSION_END}

Analyze this agent's trajectory and provide:
1. Movement pattern assessment
2. Jamming impact on progress
3. Recommended next waypoint to reach mission endpoint
4. Predicted time to endpoint (if current pattern continues)

Keep analysis concise and actionable."""
        
        ollama_client = get_ollama_client()
        model_name = get_model_name()
        
        response = chat_with_retry(
            ollama_client,
            model_name,
            messages=[{"role": "user", "content": prompt}]
        )

        if response is None:
            return {"response": "❌ LLM error"}

        analysis = response['message']['content']
        
        return {"response": f"🛰️ **{agent_id} TRAJECTORY ANALYSIS**\n\n{analysis}"}
        
    except Exception as e:
        return {"response": f"❌ Error: {str(e)}"}


async def list_agents():
    """List all agents with basic info"""
    if not RAG_AVAILABLE:
        return {"response": "❌ RAG not available"}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{SIMULATION_API_URL}/agents", timeout=2.0)
            
            if response.status_code != 200:
                return {"response": "❌ Could not retrieve agents"}
            
            agents = response.json().get("agents", {})
            agent_ids = list(agents.keys())
            
            if not agent_ids:
                return {"response": "⚠️ No agents in simulation"}
            
            agent_list = format_all_agents_for_llm(agent_ids)
            
            return {"response": f"🤖 **AGENT LIST**\n\n{agent_list}"}
            
    except Exception as e:
        return {"response": f"❌ Error: {str(e)}"}


async def get_agent_info(agent_name: str):
    """Get detailed info for specific agent"""
    if not RAG_AVAILABLE:
        return {"response": "❌ RAG not available"}
    
    try:
        context_text = format_for_llm(agent_name, history_limit=10)
        
        if "No data available" in context_text:
            return {"response": f"❌ {agent_name} not found"}
        
        return {"response": f"🤖 **{agent_name.upper()} DETAILS**\n\n{context_text}"}
        
    except Exception as e:
        return {"response": f"❌ Error: {str(e)}"}