```bash
# 1. Start Ollama on remote GPU
cd ~/CARS_sim_2_ollama/demos/12-LLM_SIM_GPS_Message_Stream && ./launch_ollama.sh --model llama3:8b

# 2. Start PostgreSQL
cd ~/CARS_sim_2_ollama/demos/12-LLM_SIM_GPS_Message_Stream && docker compose up -d

# 4. Start Backend Services (GPS + MCP Chatapp)
cd ~/CARS_sim_2_ollama/demos/12-LLM_SIM_GPS_Message_Stream && [ -z "$VIRTUAL_ENV" ] && source ~/CARS_sim_2_ollama/venv/bin/activate 
python startup.py

# 5. Start Main GUI (in new terminal)
cd ~/CARS_sim_2_ollama/demos/12-LLM_SIM_GPS_Message_Stream && [ -z "$VIRTUAL_ENV" ] && source ~/CARS_sim_2_ollama/venv/bin/activate
python main_gui.py
```