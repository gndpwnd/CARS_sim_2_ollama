# func_call_ollama.py
import ollama

def generate_file(filename: str, content: str) -> str:
    """
    Generates a file with the given filename and content.
    Args:
        filename (str): The name of the file to create.
        content (str): The content to write to the file.
    Returns:
        str: A message indicating the file creation status.
    """
    try:
        with open(filename, "w") as f:
            f.write(content)
        return f"File '{filename}' created successfully."
    except Exception as e:
        return f"Error creating file '{filename}': {e}"

# Define the tools available to the model
tools = [
    {
        "type": "function",
        "function": {
            "name": "generate_file",
            "description": "Generates a file with the given filename and content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "The name of the file to create.",
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to write to the file.",
                    },
                },
                "required": ["filename", "content"],
            },
        },
    }
]

# Create a prompt for the model to use the function
prompt = "Create a file named 'example.txt' with the following content: 'This is an example file.'"

# Call the Ollama API with the prompt and tools
response = ollama.chat(
    model="llama3.2:1b",  # Replace with your model
    messages=[{"role": "user", "content": prompt}],
    tools=tools,
)

# Extract the tool calls from the response
message = response.get("message", {})
tool_calls = message.get("tool_calls", [])

if tool_calls:
    # Execute the function call
    for tool_call in tool_calls:
        # Directly access the function name and arguments (already a dict)
        function_name = tool_call.get("function", {}).get("name")
        arguments = tool_call.get("function", {}).get("arguments", {})
        
        if function_name == "generate_file":
            result = generate_file(**arguments)
            print(result)
else:
    print("No tool call was made. Model response:")
    print(message.get("content", "No content"))