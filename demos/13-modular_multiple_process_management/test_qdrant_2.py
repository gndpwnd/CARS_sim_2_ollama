# Quick test
from qdrant_store import get_agent_position_history
from datetime import datetime

history = get_agent_position_history("agent1", limit=1)
if history:
    ts = history[0]['timestamp']
    print(f"Raw timestamp: {ts}")
    print(f"Type: {type(ts)}")
    
    # If it's a float (Unix timestamp)
    if isinstance(ts, float):
        print(f"As datetime: {datetime.fromtimestamp(ts)}")
        print(f"Current time: {datetime.now()}")
        print(f"Current Unix: {datetime.now().timestamp()}")



# Check if new data is coming in
from qdrant_store import qdrant_client, TELEMETRY_COLLECTION
from datetime import datetime, timedelta

# Get logs from last 10 seconds
recent = qdrant_client.scroll(
    collection_name=TELEMETRY_COLLECTION,
    limit=10,
    with_payload=True,
    with_vectors=False
)[0]

for point in recent[:5]:
    iteration = point.payload.get('iteration')
    timestamp = point.payload.get('timestamp')
    agent = point.payload.get('agent_id')
    print(f"Agent: {agent}, Iteration: {iteration}, Timestamp: {timestamp}")




# Run while simulation is running
from qdrant_store import qdrant_client, TELEMETRY_COLLECTION
import time

before = qdrant_client.count(collection_name=TELEMETRY_COLLECTION).count
time.sleep(2)
after = qdrant_client.count(collection_name=TELEMETRY_COLLECTION).count

print(f"Before: {before}, After: {after}, New entries: {after - before}")