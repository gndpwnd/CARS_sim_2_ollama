#!/usr/bin/env python3
"""
Test all connections for the simulation system
"""
import sys
import subprocess
import socket
import time

def check_ssh_tunnel():
    """Check if SSH tunnel is active"""
    print("Checking SSH tunnel...")
    try:
        result = subprocess.run(
            ["lsof", "-ti:11434"],
            capture_output=True,
            text=True
        )
        if result.stdout.strip():
            print("✓ SSH tunnel is active (PID: {})".format(result.stdout.strip()))
            return True
        else:
            print("✗ SSH tunnel not found on port 11434")
            print("  Run: ./launch_ollama.sh")
            return False
    except Exception as e:
        print(f"✗ Error checking tunnel: {e}")
        return False

def check_ollama_connection():
    """Check if Ollama is accessible"""
    print("\nChecking Ollama connection...")
    try:
        import ollama
        client = ollama.Client(host="http://localhost:11434")
        
        # Get models list
        models_response = client.list()
        
        # Handle different response formats
        if isinstance(models_response, dict):
            models_list = models_response.get('models', [])
        else:
            models_list = []
        
        # Extract model names
        model_names = []
        for model in models_list:
            if isinstance(model, dict):
                # Handle both 'name' and 'model' keys
                name = model.get('name') or model.get('model', 'unknown')
                model_names.append(name)
        
        print("✓ Ollama is accessible")
        if model_names:
            print(f"  Available models: {model_names}")
        else:
            print("  Available models: (none found)")
        
        return True
        
    except Exception as e:
        print(f"✗ Ollama not accessible: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_postgresql():
    """Check PostgreSQL connection"""
    print("\nChecking PostgreSQL...")
    try:
        import psycopg2
        conn = psycopg2.connect(
            dbname="rag_db",
            user="postgres",
            password="password",
            host="localhost",
            port="5432"
        )
        conn.close()
        print("✓ PostgreSQL is accessible")
        return True
    except Exception as e:
        print(f"✗ PostgreSQL not accessible: {e}")
        print("  Run: docker compose up -d")
        return False

def check_qdrant():
    """Check Qdrant connection"""
    print("\nChecking Qdrant...")
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(host="localhost", port=6333)
        collections = client.get_collections()
        print("✓ Qdrant is accessible")
        print(f"  Collections: {[c.name for c in collections.collections]}")
        return True
    except Exception as e:
        print(f"✗ Qdrant not accessible: {e}")
        print("  Run: docker compose up -d")
        return False

def test_ollama_chat():
    """Test actual Ollama chat functionality with sample prompt"""
    print("\nTesting Ollama chat...")
    print("="*60)
    try:
        import ollama
        client = ollama.Client(host="http://localhost:11434")
        
        # Test prompt
        test_prompt = "Hello, how are you doing?"
        print(f"  📤 Sending: '{test_prompt}'")
        print(f"  ⏳ Waiting for response (this may take a moment)...")
        
        start_time = time.time()
        
        response = client.chat(
            model="llama3:8b",
            messages=[{"role": "user", "content": test_prompt}],
            options={"timeout": 30}
        )
        
        elapsed = time.time() - start_time
        
        reply = response.get('message', {}).get('content', '')
        
        print(f"\n  📥 Response (received in {elapsed:.2f}s):")
        print("  " + "-"*56)
        
        # Format the response nicely
        for line in reply.split('\n'):
            print(f"  {line}")
        
        print("  " + "-"*56)
        print("✓ Ollama chat working")
        print("="*60)
        return True
        
    except Exception as e:
        print(f"\n✗ Ollama chat failed: {e}")
        print("="*60)
        import traceback
        traceback.print_exc()
        return False

def main():
    print("="*60)
    print("CONNECTION TEST")
    print("="*60)
    
    results = {
        "SSH Tunnel": check_ssh_tunnel(),
        "Ollama API": check_ollama_connection(),
        "PostgreSQL": check_postgresql(),
        "Qdrant": check_qdrant()
    }
    
    # Add visual separator before chat test
    print("\n" + "="*60)
    print("OLLAMA CHAT TEST")
    print("="*60)
    
    chat_result = test_ollama_chat()
    results["Ollama Chat"] = chat_result
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for name, status in results.items():
        symbol = "✓" if status else "✗"
        print(f"{symbol} {name}")
    
    if all(results.values()):
        print("\n✓ All systems ready!")
        print("\n💡 TIP: You can now run:")
        print("   python startup.py    # Start backend services")
        print("   python main_gui.py   # Start GUI simulation")
        return 0
    else:
        print("\n✗ Some systems need attention")
        
        if not results.get("SSH Tunnel"):
            print("\n🔧 Fix: Run ./launch_ollama.sh")
        if not results.get("PostgreSQL") or not results.get("Qdrant"):
            print("🔧 Fix: Run docker compose up -d")
        
        return 1

if __name__ == "__main__":
    sys.exit(main())