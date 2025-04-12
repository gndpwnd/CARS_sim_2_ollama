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

def add_log(log_id: str, log_text: str, metadata: dict, agent_id: str, comm_quality: float, position: tuple):
    """
    Add a log entry for a single agent with semantic indexing.
    """
    global log_data, index

    # Embed the log text
    vec = model.encode([log_text])
    index.add(vec)

    log_data.append({
        "log_id": log_id,
        "text": log_text,
        "metadata": {
            **metadata,
            "agent_id": agent_id,
            "log_id": log_id,
            "comm_quality": comm_quality,
            "position": position
        }
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
    return log_data