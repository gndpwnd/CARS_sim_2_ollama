# test_qdrant_freshness.py
from qdrant_store import get_agent_position_history
import httpx
import asyncio

async def check_data_freshness():
    # Get from Qdrant
    qdrant_data = get_agent_position_history("agent1", limit=1)
    
    # Get from Simulation API
    async with httpx.AsyncClient() as client:
        resp = await client.get("http://localhost:5001/agents/agent1")
        api_data = resp.json()
    
    print("Qdrant position:", qdrant_data[0]['position'] if qdrant_data else "NO DATA")
    print("API position:", api_data['position'])
    print("Match:", qdrant_data[0]['position'] == api_data['position'] if qdrant_data else False)

asyncio.run(check_data_freshness())