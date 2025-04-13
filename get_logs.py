import pickle
import time
from pathlib import Path

LOG_DIR = "logs/"
FILE_PREFIX = "log_chunk_"
OUTPUT_FILE = "logs.txt"

def get_chunk_path(index):
    return Path(LOG_DIR) / f"{FILE_PREFIX}{index}.pkl"

def get_latest_chunk_index():
    files = sorted(Path(LOG_DIR).glob(f"{FILE_PREFIX}*.pkl"))
    if not files:
        return -1
    return max(int(f.stem.split("_")[-1]) for f in files)

def read_latest_logs():
    index = get_latest_chunk_index()
    if index == -1:
        return []
    path = get_chunk_path(index)
    if not path.exists():
        return []
    with open(path, "rb") as f:
        return pickle.load(f)

def write_logs_to_text(logs):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for i, log in enumerate(logs, 1):
            f.write(f"--- Log Entry {i} ---\n")
            f.write(f"Log ID: {log.get('log_id')}\n")
            f.write(f"Text: {log.get('text')}\n")
            f.write(f"Metadata: {log.get('metadata')}\n\n")

if __name__ == "__main__":
    while True:
        logs = read_latest_logs()
        write_logs_to_text(logs)
        time.sleep(3)
