from flask import Flask, render_template, request, jsonify
import sys
import traceback
import datetime
import hashlib

# Try importing the modules with error handling
try:
    from demos.basic_rag_demo.rag_store import add_log, retrieve_relevant
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
        print("Received chat request")
        user_message = request.json.get('message')
        if not user_message:
            print("No message provided in request")
            return jsonify({'error': 'No message provided'}), 400

        print(f"Processing message: {user_message}")
        
        try:
            # Check if RAG functions are available
            if 'retrieve_relevant' in globals():
                # Retrieve relevant logs from FAISS
                print("Retrieving relevant logs...")
                relevant_logs = retrieve_relevant(user_message, k=3)
                context = "\n".join(relevant_logs)
                print(f"Retrieved {len(relevant_logs)} relevant logs")
            else:
                context = "RAG retrieval not available"
                print("WARNING: RAG functions not available")
                
            # Get current timestamp for logging
            current_timestamp = datetime.datetime.now().isoformat()
            print(f"Current timestamp: {current_timestamp}")

            # Check if ollama is available
            if 'ollama' in globals():
                # Send the user's message and context to Ollama
                print("Sending request to Ollama...")
                prompt = f"Context:\n{context}\n\nUser: {user_message}"
                response = ollama.chat(
                    model="tinyllama:1.1b",
                    messages=[{"role": "user", "content": prompt}]
                )
                ollama_response = response.get('message', {}).get('content', "Sorry, I didn't understand that.")
                print("Received response from Ollama")
            else:
                ollama_response = "Ollama model not available. This is a test response."
                print("WARNING: Ollama not available, returning test response")

            # Store response in RAG if available
            if 'add_log' in globals():
                try:
                    print("Adding log entries to RAG...")
                    # Add the user message to FAISS
                    message_hash = hashlib.md5(user_message.encode()).hexdigest()[:8]
                    add_log(
                        log_id=f"user-{message_hash}",
                        log_text=user_message,
                        metadata={
                            "role": "user",
                            "timestamp": current_timestamp
                        }
                    )
                    
                    # Add the ollama response to FAISS
                    response_hash = hashlib.md5(ollama_response.encode()).hexdigest()[:8]
                    add_log(
                        log_id=f"ollama-{response_hash}",
                        log_text=ollama_response,
                        metadata={
                            "role": "ollama",
                            "timestamp": current_timestamp
                        }
                    )
                    print("Successfully added logs to RAG")
                except Exception as e:
                    print(f"ERROR adding logs to RAG: {e}")
                    traceback.print_exc()

        except Exception as e:
            print(f"ERROR in processing: {e}")
            traceback.print_exc()
            ollama_response = f"Error processing your request: {str(e)}"

        print(f"Returning response: {ollama_response[:50]}...")
        return jsonify({'response': ollama_response})
        
    except Exception as e:
        print(f"CRITICAL ERROR in chat endpoint: {e}")
        traceback.print_exc()
        return jsonify({'error': f"An error occurred: {str(e)}"}), 500

if __name__ == '__main__':
    print("Starting Flask app...")
    print(f"Python version: {sys.version}")
    print("Make sure you have created an 'index.html' file in the 'templates' folder")
    print("Access the web interface at http://127.0.0.1:5000")
    print("To test if the server is running correctly, visit http://127.0.0.1:5000/test")
    app.run(debug=True)