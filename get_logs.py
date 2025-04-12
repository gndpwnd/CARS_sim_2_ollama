# get_logs.py

from rag_store import get_log_data

def print_all_logs():
    try:
        logs = get_log_data()
        if logs:
            print(f"Fetched {len(logs)} logs:")
            for log in logs:
                log_id = log.get("log_id", "Unknown ID")
                log_text = log.get("text", "No text available")
                timestamp = log.get("metadata", {}).get("timestamp", "No timestamp")
                agent_id = log.get("metadata", {}).get("agent_id", "Unknown agent")
                comm_quality = log.get("metadata", {}).get("comm_quality", "Unknown quality")
                position = log.get("metadata", {}).get("position", "Unknown position")
                
                # Printing all details on a single line
                print(f"{log_id} | {timestamp} | {agent_id} | {comm_quality} | {position} | {log_text}")
        else:
            print("No logs found.")
    except Exception as e:
        print(f"ERROR fetching logs: {e}")

if __name__ == '__main__':
    print_all_logs()
