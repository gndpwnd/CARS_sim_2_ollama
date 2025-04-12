from flask import Flask, render_template, request, jsonify, Response
import sys
import traceback
import hashlib
from datetime import datetime
import time

LLM_MODEL = "llama3.2:1b"

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
            model=LLM_MODEL,
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

@app.route("/log_count")
def log_count():
    """
    Return the current number of logs in the system.
    """
    try:
        logs = get_log_data()
        return jsonify({"log_count": len(logs)})
    except Exception as e:
        print("Error in /log_count route:", e)
        return jsonify({"error": "Internal server error"}), 500

@app.route("/stream_logs")
def stream_logs():
    """
    Stream live logs as they are added to the system.
    """
    def generate():
        while True:
            logs = get_log_data()
            logs_sorted = sorted(
                logs,
                key=lambda x: x.get("metadata", {}).get("timestamp", x.get("log_id", "")),
                reverse=True
            )
            latest_log = logs_sorted[0] if logs_sorted else None
            if latest_log:
                yield f"data: {latest_log}\n\n"
            time.sleep(1)  # Adjust the delay between streams if needed

    return Response(generate(), content_type='text/event-stream')

@app.route("/log_chunk/<int:chunk_num>")
def get_log_chunk(chunk_num):
    """
    Get a specific chunk of logs by chunk number.
    Each chunk will be 20 logs by default, but you can adjust this if needed.
    """
    try:
        logs = get_log_data()
        start_index = chunk_num * 20
        end_index = start_index + 20
        logs_sorted = sorted(
            logs,
            key=lambda x: x.get("metadata", {}).get("timestamp", x.get("log_id", "")),
            reverse=True
        )
        chunk = logs_sorted[start_index:end_index]

        return jsonify({
            "logs": chunk,
            "has_more": len(logs_sorted) > end_index
        })
    except Exception as e:
        print("Error in /log_chunk route:", e)
        return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    print("Starting Flask app...")
    print(f"Python version: {sys.version}")
    print("Visit http://127.0.0.1:5000")
    app.run(debug=True)
