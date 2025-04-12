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

@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        error_msg = f"ERROR: Could not render template 'index.html': {e}"
        print(error_msg)
        return error_msg, 500

@app.route('/test')
def test():
    return "Flask server is running correctly!"

@app.route('/chat', methods=['POST'])
def chat():
    try:
        user_message = request.json.get('message')
        if not user_message:
            return jsonify({'error': 'No message provided'}), 400

        # Get RAG context
        relevant_logs = retrieve_relevant(user_message, k=3)
        context = "\n".join(log.get("text", "") for log in relevant_logs)

        prompt = f"Context:\n{context}\n\nUser: {user_message}"
        response = ollama.chat(
            model="tinyllama:1.1b",
            messages=[{"role": "user", "content": prompt}]
        )
        ollama_response = response.get('message', {}).get('content', "Sorry, I didn't understand that.")

        # Log both user message and bot response
        timestamp = datetime.now().isoformat()

        user_hash = hashlib.md5(user_message.encode()).hexdigest()[:8]
        response_hash = hashlib.md5(ollama_response.encode()).hexdigest()[:8]

        add_log(f"user-{user_hash}", user_message, {"role": "user", "timestamp": timestamp})
        add_log(f"ollama-{response_hash}", ollama_response, {"role": "ollama", "timestamp": timestamp})

        return jsonify({'response': ollama_response})

    except Exception as e:
        print(f"ERROR: {e}")
        return jsonify({'error': str(e)}), 500

@app.route("/logs")
def get_logs():
    try:
        logs = get_log_data()
        logs_sorted = sorted(
            logs,
            key=lambda x: x.get("metadata", {}).get("timestamp", x.get("log_id", "")),
            reverse=True
        )

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
    print("Visit http://127.0.0.1:5000")
    app.run(debug=True)
