import faiss
import os
import pickle
from sentence_transformers import SentenceTransformer
from pathlib import Path
import uuid

# Constants and setup
model = SentenceTransformer("all-MiniLM-L6-v2")
LOG_DIR = "logs/"
FILE_SIZE_LIMIT_MB = 5  # in MB
FILE_PREFIX = "log_chunk_"
index_file = "faiss_index.bin"
FILE_SIZE_LIMIT = FILE_SIZE_LIMIT_MB * 1024 * 1024  # size limit in bytes


if os.path.exists(index_file):
    index = faiss.read_index(index_file)
else:
    index = None  # Will be initialized when first vector is added

# ────── Chunk Management ──────

def get_chunk_path(index):
    return Path(LOG_DIR) / f"{FILE_PREFIX}{index}.pkl"

def get_latest_chunk_index():
    files = sorted(Path(LOG_DIR).glob(f"{FILE_PREFIX}*.pkl"))
    if not files:
        return 0
    return max(int(f.stem.split("_")[-1]) for f in files)

def current_chunk_path():
    return get_chunk_path(get_latest_chunk_index())

def is_current_chunk_full():
    path = current_chunk_path()
    return path.exists() and path.stat().st_size >= FILE_SIZE_LIMIT

def append_log_to_chunk(log_entry):
    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
    new_index = get_latest_chunk_index()
    if is_current_chunk_full():
        new_index += 1

    path = get_chunk_path(new_index)
    logs = []
    if path.exists():
        with open(path, "rb") as f:
            logs = pickle.load(f)

    logs.append(log_entry)
    with open(path, "wb") as f:
        pickle.dump(logs, f)

def get_log_data():
    """Load logs from chunk files only"""
    all_log_data = []
    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
    chunk_files = sorted(Path(LOG_DIR).glob(f"{FILE_PREFIX}*.pkl"))
    for chunk_path in chunk_files:
        try:
            with open(chunk_path, "rb") as f:
                all_log_data.extend(pickle.load(f))
        except Exception as e:
            print(f"Failed to load chunk {chunk_path}: {e}")
    return all_log_data

# ────── Main Operations ──────

def add_log(log_id: str = None, log_text: str = "", metadata: dict = None, agent_id=None):
    global index  # <- to avoid the 'local variable referenced before assignment' error

    if metadata is None:
        metadata = {}

    if agent_id is not None:
        metadata['agent_id'] = agent_id

    log_id = log_id or str(uuid.uuid4())  # Always assign unique ID
    metadata['log_id'] = log_id

    try:
        vec = model.encode([log_text])

        if index is None:
            index = faiss.IndexFlatL2(vec.shape[1])

        if not index.is_trained:
            index = faiss.IndexFlatL2(vec.shape[1])  # Safe fallback

        index.add(vec)

        log_entry = {
            "log_id": log_id,
            "text": log_text,
            "metadata": metadata
        }

        append_log_to_chunk(log_entry)
        faiss.write_index(index, index_file)

    except Exception as e:
        print(f"Error adding log: {e}")


def retrieve_relevant(query: str, k: int = 3):
    all_logs = get_log_data()
    if not all_logs:
        return []

    query_vec = model.encode([query])
    D, I = index.search(query_vec, k)

    return [
        {
            "text": all_logs[i]["text"],
            "metadata": all_logs[i]["metadata"],
            "comm_quality": all_logs[i]["metadata"].get("comm_quality"),
            "position": all_logs[i]["metadata"].get("position")
        }
        for i in I[0] if i < len(all_logs)
    ]

def get_metadata(query: str, k: int = 3):
    all_logs = get_log_data()
    if not all_logs:
        return []

    query_vec = model.encode([query])
    D, I = index.search(query_vec, k)
    return [all_logs[i]["metadata"] for i in I[0] if i < len(all_logs)]

def filter_logs_by_jammed(jammed=True):
    return [
        {"text": log["text"], "metadata": log["metadata"]}
        for log in get_log_data()
        if log["metadata"].get("jammed") == jammed
    ]

def clear_store():
    """Clear the FAISS index and all stored logs."""
    global index
    index = faiss.IndexFlatL2(384)
    faiss.write_index(index, index_file)

    # Optionally clear the log chunks (disabled by default)
    # import shutil
    # shutil.rmtree(LOG_DIR, ignore_errors=True)
