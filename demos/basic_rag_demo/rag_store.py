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

def add_log(log_id, log_text, metadata=None, agent_id=None):
    """
    Add a log entry to the FAISS index
    
    Parameters:
    - log_id: Unique identifier for the log
    - log_text: Text content of the log
    - metadata: Dictionary containing position, daytime/nighttime percentages, and timestamp
    - agent_id: Optional agent identifier
    """
    if metadata is None:
        metadata = {}
    if agent_id is not None:
        metadata["agent_id"] = agent_id
    
    embedding = model.encode([log_text])
    index.add(embedding)  # Add embedding to FAISS index
    log_data.append({
        "id": log_id,
        "text": log_text,
        "metadata": metadata
    })
    save_state()

def retrieve_relevant(query: str, k: int = 3):
    """
    Retrieve relevant log entries based on a query
    
    Parameters:
    - query: Query text
    - k: Number of results to return
    
    Returns:
    - List of relevant log texts
    """
    if len(log_data) == 0:
        return []
    query_vec = model.encode([query])
    D, I = index.search(query_vec, k)
    return [log_data[i]["text"] for i in I[0] if i < len(log_data)]

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