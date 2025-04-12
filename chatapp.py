# The chatapp

from flask import Flask, render_template, request, jsonify
import sys
import traceback
import hashlib
from datetime import datetime

try:
    from rag_store import get_log_data, add_log, retrieve_relevant
    print("Successfully imported rag_store")
except Exception as e:
    print(f"ERROR importing rag_store: {e}")
    traceback.print_exc()

try:
    import ollama
    print("Successfully imported ollama")
except Exception as e:
    print(f"ERROR importing ollama: {e}")
    traceback.print_exc()
    print("Note: If ollama isn't installed, run: pip install ollama")

try:
    import numpy as np
    print("Successfully imported numpy")
except Exception as e:
    print(f"ERROR importing numpy: {e}")
    traceback.print_exc()

app = Flask(__name__)

# Route for serving the HTML template
@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        error_msg = f"ERROR: Could not render template 'index.html': {e}"
        print(error_msg)
        return error_msg, 500

# Add a test route to verify the server is running
@app.route('/test')
def test():
    return "Flask server is running correctly!"

@app.route('/chat', methods=['POST'])
def chat():
    try:
        user_message = request.json.get('message')
        if not user_message:
            return jsonify({'error': 'No message provided'}), 400

        # Retrieve relevant logs from RAG
        relevant_logs = retrieve_relevant(user_message, k=3)
        context = "\n".join(relevant_logs)

        # Send the user message and context to Ollama
        prompt = f"Context:\n{context}\n\nUser: {user_message}"
        response = ollama.chat(
            model="tinyllama:1.1b",
            messages=[{"role": "user", "content": prompt}]
        )
        ollama_response = response.get('message', {}).get('content', "Sorry, I didn't understand that.")

        # Add both user message and Ollama response to the RAG store
        current_timestamp = datetime.now().isoformat()
        message_hash = hashlib.md5(user_message.encode()).hexdigest()[:8]
        add_log(
            log_id=f"user-{message_hash}",
            log_text=user_message,
            metadata={"role": "user", "timestamp": current_timestamp}
        )
        response_hash = hashlib.md5(ollama_response.encode()).hexdigest()[:8]
        add_log(
            log_id=f"ollama-{response_hash}",
            log_text=ollama_response,
            metadata={"role": "ollama", "timestamp": current_timestamp}
        )

        return jsonify({'response': ollama_response})
    
    except Exception as e:
        print(f"ERROR: {e}")
        return jsonify({'error': str(e)}), 500

@app.route("/logs")
def get_logs():
    try:
        logs = get_log_data()
        print("Fetched logs:", logs)

        # Provide a fallback timestamp if missing
        logs_sorted = sorted(
            logs,
            key=lambda x: x.get("metadata", {}).get("timestamp", x.get("log_id", "")),
            reverse=True
        )

        print("Sorted logs:", logs_sorted)

        return jsonify({
            "logs": logs_sorted[:20],
            "has_more": len(logs_sorted) > 20
        })
    except Exception as e:
        print("Error in /logs route:", e)
        return jsonify({"error": "Internal server error"}), 500




if __name__ == '__main__':
    print("Starting Flask app...")
    print(f"Python version: {sys.version}")
    print("Make sure you have created an 'index.html' file in the 'templates' folder")
    print("Access the web interface at http://127.0.0.1:5000")
    print("To test if the server is running correctly, visit http://127.0.0.1:5000/test")
    app.run(debug=True)