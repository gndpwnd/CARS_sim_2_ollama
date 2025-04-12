# rag_store.py (FAISS version)
import faiss
import os
import pickle
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")

# Store the FAISS index and mapping of vectors to logs
index_file = "faiss_index.bin"
logs_file = "log_data.pkl"

if os.path.exists(index_file):
    index = faiss.read_index(index_file)
    with open(logs_file, "rb") as f:
        log_data = pickle.load(f)
else:
    index = faiss.IndexFlatL2(384)  # 384 is the dimension for MiniLM
    log_data = []

def save_state():
    """Save the current state of the index and log data"""
    faiss.write_index(index, index_file)
    with open(logs_file, "wb") as f:
        pickle.dump(log_data, f)


def convert_numpy_coords(obj):
    """
    Convert numpy data types to standard Python types for JSON serialization.
    
    Args:
        obj: Any Python object that might contain numpy data types
        
    Returns:
        Object with numpy types converted to standard Python types
    """
    
    # Handle numpy arrays
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    
    # Handle numpy scalars
    if isinstance(obj, (np.int_, np.intc, np.intp, np.int8, np.int16, np.int32, np.int64,
                       np.uint8, np.uint16, np.uint32, np.uint64)):
        return int(obj)
    
    if isinstance(obj, (np.float_, np.float16, np.float32, np.float64)):
        return float(obj)
    
    if isinstance(obj, (np.complex_, np.complex64, np.complex128)):
        return complex(obj)
    
    if isinstance(obj, np.bool_):
        return bool(obj)
    
    # Handle tuples containing numpy types
    if isinstance(obj, tuple):
        return tuple(convert_numpy_coords(item) for item in obj)
        
    # Handle lists containing numpy types
    if isinstance(obj, list):
        return [convert_numpy_coords(item) for item in obj]
        
    # Handle dictionaries containing numpy types
    if isinstance(obj, dict):
        return {key: convert_numpy_coords(value) for key, value in obj.items()}
        
    # Return other types unchanged
    return obj

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
    
    save_state()

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

def clear_store():
    """
    Clear the FAISS index and all stored logs.
    Useful for development or resetting the RAG store.
    """
    global log_data, index
    log_data = []
    index = faiss.IndexFlatL2(384)
    save_state()

def get_log_data():
    try:
        return log_data
    except Exception as e:
        print(f"Error retrieving log data: {e}")
        return []