# LLM configuration (shared between all components)
LLM_MODEL = "llama3:8b"
OLLAMA_HOST = "http://localhost:11434"

import ollama

def get_ollama_client():
    """
    Returns an Ollama client with consistent configuration
    """
    # Configure the client to use the correct host
    client = ollama.Client(host=OLLAMA_HOST)
    return client

def get_model_name():
    """
    Returns the configured model name
    """
    return LLM_MODEL