import os
import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

CHROMA_PATH = "/opt/CARS_sim_2_ollama/chroma_db"

# Ensure the ChromaDB folder exists
if not os.path.exists(CHROMA_PATH):
    os.makedirs(CHROMA_PATH)

# Choose an embedding model (use one from Ollama if preferred)
embedding_function = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

# Initialize ChromaDB client and collection
client = chromadb.Client(Settings(chroma_db_impl="duckdb+parquet", persist_directory=CHROMA_PATH))
collection = client.get_or_create_collection("simulation_logs", embedding_function=embedding_function)

def add_log(log_id, log_text, metadata=None):
    """
    Add a log entry to the ChromaDB collection.
    """
    if not collection.get(ids=[log_id]):  # Avoid duplicate entries
        collection.add(
            documents=[log_text],
            ids=[log_id],
            metadatas=[metadata or {}]
        )

def retrieve_relevant(query, k=3):
    """
    Retrieve the most relevant logs for a given query.
    """
    results = collection.query(
        query_texts=[query],
        n_results=k
    )
    return results['documents'] if results['documents'] else []