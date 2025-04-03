import ollama
import json

# Define the threshold for poor communication quality
COMM_QUALITY_THRESHOLD = 0.2  # Adjust as needed

def send_data_to_llm(swarm_data):
    """
    Sends swarm data to the LLM and retrieves a response.

    Args:
        swarm_data (dict): The current state of the swarm.

    Returns:
        str: The response from the LLM.
    """
    prompt = f"""The following swarm data shows agent positions and communication quality:
{json.dumps(swarm_data, indent=2)}

Some agents may have poor communication quality (below {COMM_QUALITY_THRESHOLD}). 
If necessary, provide movement instructions, such as 'move agent X to center'."""

    response = ollama.chat(
        model="llama3.2:1b",  # Adjust model as needed
        messages=[{"role": "user", "content": prompt}],
    )

    llm_response = response.get("message", {}).get("content", "")
    print(f"LLM Response: {llm_response}")
    return llm_response

def process_llm_response(response, swarm_pos_dict):
    """
    Processes the LLM response and updates agent positions if necessary.

    Args:
        response (str): The response from the LLM.
        swarm_pos_dict (dict): The dictionary containing agent positions.

    Returns:
        bool: True if an agent was moved, False otherwise.
    """
    moved_agent = False
    for agent_id in swarm_pos_dict.keys():
        if f"move agent {agent_id} to center" in response.lower():
            # Move the agent to the center of the formation
            center_x = sum(agent_data[-1][0] for agent_data in swarm_pos_dict.values()) / len(swarm_pos_dict)
            center_y = sum(agent_data[-1][1] for agent_data in swarm_pos_dict.values()) / len(swarm_pos_dict)
            swarm_pos_dict[agent_id].append((center_x, center_y, 1.0))  # Assuming perfect comm quality in center
            print(f"Moved {agent_id} to center at ({center_x}, {center_y})")
            moved_agent = True

    return moved_agent
