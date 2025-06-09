> [basic discord bot](https://github.com/akshay56789/discord-weather-bot)
## Run [litellm](https://github.com/BerriAI/litellm) locally

```bash
ollama run llama3.2:1b
```

in a separate terminal 

```bash
sudo apt update

sudo apt install -y python3.9 python3.9-venv python3.9-dev

curl -sSL https://install.python-poetry.org | python3 -

curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

python3.9 -m venv venv

source venv/bin/activate

pip3 install litellm 'litellm[proxy]'

litellm --config litellm_config_ollama.yaml --detailed_debug
```

in a separate terminal

```
source venv/bin/activate

python tmp1.py
```


## Run litellm in docker along side ollama in docker


command for [ollama](https://hub.docker.com/r/ollama/ollama) to run the smallest 3.2 model


```bash
docker run \
	-d \
	--rm \
	-v ollama:/root/.ollama \
	-p 11434:11434 \
	--name ollama ollama/ollama \
	&& docker exec \
	-d ollama \
		ollama run llama3.2:1b
```

command to run litellm in docker

```bash
docker run \
	-d \
	--rm \
	-v $(pwd)/litellm_config_ollama.yaml:/app/config.yaml \
	-p 4000:4000 \
	--name litellm ghcr.io/berriai/litellm:main-latest \
	--config /app/config.yaml \
	--detailed_debug
```


some curl commands to test [lightllm api](http://localhost:4000)


simple whoami

``` bash
curl --location 'http://127.0.0.1:4000/chat/completions' \
--header 'Content-Type: application/json' \
--data '{
  "model": "llama3.2:1b",
  "messages": [
    {
      "role": "user",
      "content": "what llm are you"
    }
  ]
}'
```

math tutor
```
curl -X POST 'http://0.0.0.0:4000/chat/completions' \
-H 'Content-Type: application/json' \
-H 'Authorization: Bearer sk-1234' \
-d '{
    "model": "llama3.2:1b",
    "messages": [
      {
        "role": "system",
        "content": "You are a helpful math tutor. Guide the user through the solution step by step."
      },
      {
        "role": "user",
        "content": "how can I solve 8x + 7 = -23"
      }
    ]
}'
```


start into function calls

```bash
curl -X POST 'http://0.0.0.0:4000/chat/completions' \
-H 'Content-Type: application/json' \
-H 'Authorization: Bearer sk-1234' \
-d '{
    "model": "llama3.2:1b",
  "messages": [
    {
      "role": "user",
      "content": "What'\''s the weather like in Boston today?"
    }
  ],
  "tools": [
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
              "description": "The city and state, e.g. San Francisco, CA"
            },
            "unit": {
              "type": "string",
              "enum": ["celsius", "fahrenheit"]
            }
          },
          "required": ["location"]
        }
      }
    }
  ],
  "tool_choice": "auto",
  "stream": true
}'
```