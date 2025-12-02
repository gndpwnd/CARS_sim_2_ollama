# test_qdrant_streaming.py
from qdrant_store import qdrant_client, TELEMETRY_COLLECTION
import time

print("Watching Qdrant for new entries...")

# Get initial count
initial_count = qdrant_client.count(collection_name=TELEMETRY_COLLECTION).count
print(f"Initial count: {initial_count}")

time.sleep(5)

# Get count after 5 seconds
after_count = qdrant_client.count(collection_name=TELEMETRY_COLLECTION).count
print(f"After 5 seconds: {after_count}")
print(f"New entries: {after_count - initial_count}")

if after_count == initial_count:
    print("⚠️ NO NEW ENTRIES! GUI might not be logging to Qdrant!")
else:
    print("✅ Qdrant is receiving new data")