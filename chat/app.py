from flask import Flask, render_template, request, jsonify
import ollama
from rag.rag_store import add_log, retrieve_relevant

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get('message')
    if not user_message:
        return jsonify({'error': 'No message provided'}), 400

    try:
        # Retrieve relevant logs from ChromaDB
        relevant_logs = retrieve_relevant(user_message, k=3)
        context = "\n".join(relevant_logs)

        # Send the user's message and context to Ollama
        prompt = f"Context:\n{context}\n\nUser: {user_message}"
        response = ollama.chat(
            model="llama3.2:1b",
            messages=[{"role": "user", "content": prompt}]
        )
        ollama_response = response.get('message', {}).get('content', 'Sorry, I didn’t understand that.')

        # Add the user message and response to ChromaDB
        add_log(log_id=f"log-{user_message[:10]}", log_text=user_message, metadata={"role": "user"})
        add_log(log_id=f"log-{ollama_response[:10]}", log_text=ollama_response, metadata={"role": "ollama"})

    except Exception as e:
        ollama_response = f"Error: {str(e)}"

    return jsonify({'response': ollama_response})

if __name__ == '__main__':
    app.run(debug=True)