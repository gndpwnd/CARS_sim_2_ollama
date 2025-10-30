"""
Report generation functions using RAG.
"""
import httpx
from datetime import datetime
from core.config import SIMULATION_API_URL
from integrations import add_log

# Import RAG functions
try:
    from rag import format_for_llm, format_all_agents_for_llm
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    print("[RAG] RAG system not available")

# Import LLM
try:
    from llm_config import chat_with_retry, get_ollama_client, get_model_name
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    print("[LLM] LLM not available")

async def generate_status_report():
    """Generate human-friendly status report using RAG"""
    if not RAG_AVAILABLE:
        return {"response": "❌ RAG system not available"}
    
    try:
        async with httpx.AsyncClient() as client:
            agents_response = await client.get(f"{SIMULATION_API_URL}/agents", timeout=2.0)
            
            if agents_response.status_code != 200:
                return {"response": "❌ Could not retrieve agents list"}
            
            agents_data = agents_response.json().get("agents", {})
            agent_ids = list(agents_data.keys())
            
            # Use RAG to format status
            status_text = format_all_agents_for_llm(agent_ids)
            
            report = "📊 **SIMULATION STATUS REPORT**\n\n"
            report += status_text
            
            return {"response": report}
            
    except Exception as e:
        return {"response": f"❌ Error generating report: {str(e)}"}

async def generate_detailed_report():
    """Generate detailed analysis report using RAG + LLM"""
    if not RAG_AVAILABLE or not LLM_AVAILABLE:
        return {"response": "❌ RAG or LLM not available"}
    
    try:
        # Get all agents
        async with httpx.AsyncClient() as client:
            agents_response = await client.get(f"{SIMULATION_API_URL}/agents", timeout=2.0)
        
        if agents_response.status_code != 200:
            return {"response": "❌ Could not retrieve agents"}
        
        agents_data = agents_response.json().get("agents", {})
        agent_ids = list(agents_data.keys())
        
        # Build context using RAG
        context = "SIMULATION DATA:\n\n"
        
        for agent_id in agent_ids:
            agent_context = format_for_llm(agent_id, history_limit=5)
            context += agent_context + "\n"
        
        # Ask LLM for analysis
        prompt = f"""{context}

Based on the above simulation data, provide a comprehensive human-friendly report including:
1. Overall simulation health
2. Agent performance analysis
3. Jamming impact assessment
4. Recommendations for agent movement
5. Any anomalies or concerns

Keep the report concise but informative."""
        
        ollama_client = get_ollama_client()
        model_name = get_model_name()
        
        response = chat_with_retry(
            ollama_client,
            model_name,
            messages=[{"role": "user", "content": prompt}]
        )

        if response is None:
            return {"response": "✗ LLM connection error. Is Ollama running?"}

        llm_report = response['message']['content']
        
        # Log the report
        add_log(llm_report, {
            "source": "llm",
            "message_type": "response",
            "timestamp": datetime.now().isoformat()
        })
        
        return {"response": f"📋 **DETAILED ANALYSIS REPORT**\n\n{llm_report}"}
        
    except Exception as e:
        return {"response": f"❌ Error generating detailed report: {str(e)}"}

async def list_agents():
    """List all agents with basic info using RAG"""
    if not RAG_AVAILABLE:
        return {"response": "❌ RAG system not available"}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{SIMULATION_API_URL}/agents", timeout=2.0)
            
            if response.status_code != 200:
                return {"response": "❌ Could not retrieve agent list"}
            
            agents = response.json().get("agents", {})
            agent_ids = list(agents.keys())
            
            if not agent_ids:
                return {"response": "⚠️ No agents currently in simulation"}
            
            # Use RAG to format list
            agent_list = format_all_agents_for_llm(agent_ids)
            
            report = "🤖 **AGENT LIST**\n\n" + agent_list
            
            return {"response": report}
            
    except Exception as e:
        return {"response": f"❌ Error listing agents: {str(e)}"}

async def get_agent_info(agent_name: str):
    """Get detailed info for a specific agent using RAG"""
    if not RAG_AVAILABLE:
        return {"response": "❌ RAG system not available"}
    
    try:
        # Use RAG to get comprehensive context
        context_text = format_for_llm(agent_name, history_limit=5)
        
        if "No data available" in context_text or not context_text:
            return {"response": f"❌ Agent '{agent_name}' not found or no data available"}
        
        report = f"🤖 **{agent_name.upper()} DETAILS**\n\n"
        report += context_text
        
        return {"response": report}
        
    except Exception as e:
        return {"response": f"❌ Error getting agent info: {str(e)}"}