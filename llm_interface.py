import ollama

def llm_make_move(agent_id: str, last_known_position: list) -> list:
    """
    Requests a new coordinate from the LLM when an agent is jammed.
    Args:
        agent_id (str): The ID of the agent.
        last_known_position (list): The last non-jammed position [x, y].
    Returns:
        list: The new coordinate [x, y] recommended by the LLM.
    """
    tools = [
        {
            "type": "function",
            "function": {
                "name": "llm_make_move",
                "description": "Requests a new coordinate for a jammed agent.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "agent_id": {
                            "type": "string",
                            "description": "The ID of the agent that needs new coordinates."
                        },
                        "last_known_position": {
                            "type": "array",
                            "items": {"type": "number"},
                            "description": "The last non-jammed position as [x, y]."
                        }
                    },
                    "required": ["agent_id", "last_known_position"]
                }
            }
        }
    ]
    
    prompt = f"Agent {agent_id} is jammed. Provide a new coordinate based on its last non-jammed position {last_known_position}."
    
    response = ollama.chat(
        model="llama3.2:1b",  # Replace with the appropriate model
        messages=[{"role": "user", "content": prompt}],
        tools=tools,
    )
    
    message = response.get("message", {})
    tool_calls = message.get("tool_calls", [])
    
    if tool_calls:
        for tool_call in tool_calls:
            function_name = tool_call.get("function", {}).get("name")
            arguments = tool_call.get("function", {}).get("arguments", {})
            
            if function_name == "llm_make_move":
                return arguments.get("new_coordinates", last_known_position)  # Default to last position if missing
    
    print("No valid LLM response received. Retrying with default behavior.")
    return last_known_position
