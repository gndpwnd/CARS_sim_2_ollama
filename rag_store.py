import faiss
import os
import pickle
from sentence_transformers import SentenceTransformer
from pathlib import Path

# Initialize the model and global variables
model = SentenceTransformer("all-MiniLM-L6-v2")
LOG_DIR = "logs/"
FILE_SIZE_LIMIT_MB = 5  # in MB
FILE_PREFIX = "log_chunk_"
index_file = "faiss_index.bin"
logs_file = "log_data.pkl"

# Convert MB to bytes
FILE_SIZE_LIMIT = FILE_SIZE_LIMIT_MB * 1024 * 1024  # size limit in bytes

# Initialize FAISS index and log data
if os.path.exists(index_file):
    index = faiss.read_index(index_file)
    with open(logs_file, "rb") as f:
        log_data = pickle.load(f)
else:
    index = faiss.IndexFlatL2(384)  # 384 is the dimension for MiniLM
    log_data = []

# Helper functions for chunking logs
def get_chunk_path(index):
    """Return the path to a specific log chunk file."""
    return Path(LOG_DIR) / f"{FILE_PREFIX}{index}.pkl"

def get_latest_chunk_index():
    """Return the index of the most recent log chunk."""
    files = sorted(Path(LOG_DIR).glob(f"{FILE_PREFIX}*.pkl"))
    if not files:
        return 0
    return max(int(f.stem.split("_")[-1]) for f in files)

def current_chunk_path():
    """Return the path to the current chunk."""
    return get_chunk_path(get_latest_chunk_index())

def is_current_chunk_full():
    """Check if the current chunk file has exceeded the size limit."""
    path = current_chunk_path()
    return path.exists() and path.stat().st_size >= FILE_SIZE_LIMIT

def append_log_to_chunk(log_entry):
    """Append a log entry to the current chunk or create a new chunk if needed."""
    # Ensure the logs directory exists
    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)

    if is_current_chunk_full():
        # Move to the next chunk index if the current one is full
        latest_index = get_latest_chunk_index()
        new_index = latest_index + 1
    else:
        # Use the current chunk if not full
        new_index = get_latest_chunk_index()

    # Get the path of the chunk we're writing to
    path = get_chunk_path(new_index)
    
    # Load the current logs from the chunk if it exists, otherwise start with an empty list
    logs = []
    if path.exists():
        with open(path, "rb") as f:
            logs = pickle.load(f)
    
    # Append the new log entry
    logs.append(log_entry)
    
    # Save the updated logs back to the chunk file
    with open(path, "wb") as f:
        pickle.dump(logs, f)

        
# Save the state of the FAISS index and log data
def save_state():
    """Save the current state of the index and log data"""
    faiss.write_index(index, index_file)
    with open(logs_file, "wb") as f:
        pickle.dump(log_data, f)

# Function to add a log with semantic indexing
def add_log(log_id: str, log_text: str, metadata: dict, agent_id=None):
    """
    Add a log entry for a single agent with semantic indexing.
    
    Parameters:
    - log_id: Unique identifier for the log
    - log_text: Text content of the log
    - metadata: Dictionary of metadata (should contain agent_id, comm_quality, position if available)
    - agent_id: Optional, only needed if not already in metadata
    """
    global log_data, index
    
    if agent_id and 'agent_id' not in metadata:
        metadata['agent_id'] = agent_id
    
    # Ensure log_id is in metadata
    metadata['log_id'] = log_id
    
    # Embed the log text
    vec = model.encode([log_text])
    index.add(vec)
    
    log_data.append({
        "log_id": log_id,
        "text": log_text,
        "metadata": metadata
    })
    
    # Append the log to the chunked logs
    append_log_to_chunk({
        "log_id": log_id,
        "text": log_text,
        "metadata": metadata
    })
    
    save_state()

# Retrieve relevant logs based on a query
def retrieve_relevant(query: str, k: int = 3):
    """
    Retrieve relevant log entries based on a query
    """
    if len(log_data) == 0:
        return []
    query_vec = model.encode([query])
    D, I = index.search(query_vec, k)
    return [
        {
            "text": log_data[i]["text"],
            "metadata": log_data[i]["metadata"],
            "comm_quality": log_data[i]["metadata"].get("comm_quality"),
            "position": log_data[i]["metadata"].get("position")
        }
        for i in I[0] if i < len(log_data)
    ]

# Retrieve metadata for relevant log entries
def get_metadata(query: str, k: int = 3):
    """
    Retrieve metadata for relevant log entries
    
    Parameters:
    - query: Query text
    - k: Number of results to return
    
    Returns:
    - List of metadata dictionaries
    """
    if len(log_data) == 0:
        return []
    query_vec = model.encode([query])
    D, I = index.search(query_vec, k)
    return [log_data[i]["metadata"] for i in I[0] if i < len(log_data)]

# Filter logs based on jammed status
def filter_logs_by_jammed(jammed=True):
    """
    Filter logs where jammed status matches the given value.
    
    Parameters:
    - jammed: Boolean value to match jammed status
    
    Returns:
    - List of matching log entries (each with text and metadata)
    """
    return [
        {"text": log["text"], "metadata": log["metadata"]}
        for log in log_data
        if log["metadata"].get("jammed") == jammed
    ]

# Clear the FAISS index and all stored logs
def clear_store():
    """
    Clear the FAISS index and all stored logs.
    Useful for development or resetting the RAG store.
    """
    global log_data, index
    log_data = []
    index = faiss.IndexFlatL2(384)
    save_state()

# Get the log data from the chunked logs
def get_log_data():
    """Retrieve all log data, including chunked logs"""
    all_log_data = []
    chunk_index = get_latest_chunk_index()
    for i in range(chunk_index + 1):
        chunk_path = get_chunk_path(i)
        if chunk_path.exists():
            with open(chunk_path, "rb") as f:
                all_log_data.extend(pickle.load(f))
    return all_log_data
