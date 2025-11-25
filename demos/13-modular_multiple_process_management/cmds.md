```bash
# 1. Start Ollama on remote GPU
cd ~/CARS_sim_2_ollama/demos/13-modular_multiple_process_management && ./launch_ollama.sh 

# 2. Start PostgreSQL
cd ~/CARS_sim_2_ollama/demos/13-modular_multiple_process_management && docker compose up -d

# 3. Start Backend Services (GPS + MCP Chatapp)
cd ~/CARS_sim_2_ollama/demos/13-modular_multiple_process_management && [ -z "$VIRTUAL_ENV" ] && source ~/CARS_sim_2_ollama/venv/bin/activate 
python startup.py

# 4. Start Main GUI (in new terminal)
cd ~/CARS_sim_2_ollama/demos/13-modular_multiple_process_management && [ -z "$VIRTUAL_ENV" ] && source ~/CARS_sim_2_ollama/venv/bin/activate
python main_gui.py


tree -I "__pycache__" -I "docs" -I "docs_old" -I "pgdata" -I "qdrant_data" | xclip -selection clipboard

```