from flask import Flask, render_template, request, jsonify
import ollama

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
        # Send the user's message to Ollama
        response = ollama.chat(
            model="llama3.2:1b",  # Updated model
            messages=[{"role": "user", "content": user_message}]
        )
        ollama_response = response.get('message', {}).get('content', 'Sorry, I didn’t understand that.')
    except Exception as e:
        ollama_response = f"Error: {str(e)}"

    return jsonify({'response': ollama_response})

if __name__ == '__main__':
    app.run(debug=True)