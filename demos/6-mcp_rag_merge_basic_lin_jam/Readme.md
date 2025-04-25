# Integrating MCP with RAG for LLM and Agent Jamming Simulation


### Run the simulation

```
docker compose down -v; sudo chown -R $USER:$USER ./pgdata; rm -rf ./pgdata; docker compose up -d; python 4-llm_return_to_safe_coords.py
```

### Run the MCP and RAG enabled chatapp

```
python3 mcp_chatapp.py
```
