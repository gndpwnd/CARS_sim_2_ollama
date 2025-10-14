1. openvpn vpn command


OLLAMA_HOST=127.0.0.1:11435 ollama serve


2. ssh -L 11434:127.0.0.1:11435 -J nelsg10@vegaln1.erau.edu nelsg10@gpu02

    1. OLLAMA_HOST=127.0.0.1:11435 ollama list
    2. OLLAMA_HOST=127.0.0.1:11435 ollama run llama3:8b

3. curl localhost:11434

3. cd ~/CARS_sim_2_ollama/demos/12-LLM_SIM_GPS_Message_Stream; docker compose up -d

    1. cd ~/CARS_sim_2_ollama/demos/12-LLM_SIM_GPS_Message_Stream; docker compose down -v

4. [ -z "$VIRTUAL_ENV" ] && source ~/CARS_sim_2_ollama/venv/bin/activate; cd ~/CARS_sim_2_ollama/demos/12-LLM_SIM_GPS_Message_Stream && python startup.py


5. [ -z "$VIRTUAL_ENV" ] && source ~/CARS_sim_2_ollama/venv/bin/activate; cd ~/CARS_sim_2_ollama/demos/12-LLM_SIM_GPS_Message_Stream && python main_gui.py
