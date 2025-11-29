#!/usr/bin/env python3
"""
Diagnostic: Check what data sources show
"""
from qdrant_store import get_agent_position_history
from rag import get_known_agent_ids
import httpx
import asyncio

async def diagnose():
    print("="*60)
    print("DIAGNOSTIC: What does the LLM see?")
    print("="*60)
    
    # 1. Check agent discovery
    print("\n1. Agent Discovery:")
    agent_ids = get_known_agent_ids(limit=100)
    print(f"   Found agents: {agent_ids}")
    
    # 2. Check Qdrant telemetry
    print("\n2. Qdrant Telemetry (what LLM SHOULD use):")
    for agent_id in agent_ids[:5]:
        history = get_agent_position_history(agent_id, limit=1)
        if history:
            current = history[0]
            print(f"   {agent_id}: pos={current['position']}, jammed={current['jammed']}, comm={current['communication_quality']:.2f}")
        else:
            print(f"   {agent_id}: NO DATA")
    
    # 3. Check Simulation API
    print("\n3. Simulation API (OLD/STALE method):")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:5001/agents", timeout=2.0)
            if response.status_code == 200:
                api_agents = response.json().get("agents", {})
                for agent_id, data in list(api_agents.items())[:5]:
                    print(f"   {agent_id}: pos={data['position']}, jammed={data['jammed']}")
            else:
                print(f"   ERROR: HTTP {response.status_code}")
    except Exception as e:
        print(f"   ERROR: {e}")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    asyncio.run(diagnose())