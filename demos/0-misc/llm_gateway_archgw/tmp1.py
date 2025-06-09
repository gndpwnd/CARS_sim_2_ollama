import litellm
from litellm import completion

print(litellm.supports_function_calling(model="ollama/llama3.2:1b"))
#print(litellm.supports_parallel_function_calling(model="ollama/llama3.2:1b"))
#litellm._turn_on_debug()

prompt = "Hi how are you"

response = completion(
            model="ollama/llama3.2:1b",
            messages = [{ "content": prompt,"role": "user"}],
            api_base="http://localhost:11434",
            format = "json",
)

print(response)

# Accessing the content of the message
message_content = response.choices[0].message.content

# Output the content
print(message_content)


messages = [{"role": "user", "content": "What's the weather like in San Francisco, Tokyo, and Paris?"}]

tools = [
	{
	    "type": "function",
	    "function": {
	        "name": "get_current_weather",
	        "description": "Get the current weather in a given location",
	        "parameters": {
	            "type": "object",
	            "properties": {
	                "location": {
	                    "type": "string",
	                    "description": "The city and state, e.g. San Francisco, CA",
	                },
	                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
	            },
	            "required": ["location"],
	        },
	    },
	}
]

response = completion(
	model="ollama/llama3.2:1b",
	messages=messages,
	tools=tools,
	api_base="http://localhost:11434",
)

print(response)