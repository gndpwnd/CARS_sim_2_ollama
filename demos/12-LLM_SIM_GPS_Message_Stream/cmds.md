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

# 🚀 Complete Startup Commands with Full Paths

## **Step 1: Connect to VPN**
```bash
# Start OpenVPN (adjust path to your .ovpn file)
sudo openvpn /path/to/your/config.ovpn
```

---

## **Step 2: Start Ollama Server (Remote GPU)**
```bash
# On remote GPU machine (gpu02)
OLLAMA_HOST=127.0.0.1:11435 ollama serve
```

---

## **Step 3: SSH Tunnel to Ollama (Local Machine)**
```bash
# Forward Ollama port from remote GPU to local machine
ssh -L 11434:127.0.0.1:11435 -J nelsg10@vegaln1.erau.edu nelsg10@gpu02
```

### **Verify Ollama Connection:**
```bash
# Test local connection
curl localhost:11434

# List available models
OLLAMA_HOST=127.0.0.1:11435 ollama list

# Test model (optional)
OLLAMA_HOST=127.0.0.1:11435 ollama run llama3:8b
```

---

## **Step 4: Start PostgreSQL Database**
```bash
cd ~/CARS_sim_2_ollama/demos/12-LLM_SIM_GPS_Message_Stream
docker compose up -d
```

### **Stop Database (when done):**
```bash
cd ~/CARS_sim_2_ollama/demos/12-LLM_SIM_GPS_Message_Stream
docker compose down -v
```

---

## **Step 5: Start Backend Services (GPS + MCP Chatapp)**
### **Terminal 1:**
```bash
[ -z "$VIRTUAL_ENV" ] && source ~/CARS_sim_2_ollama/venv/bin/activate
cd ~/CARS_sim_2_ollama/demos/12-LLM_SIM_GPS_Message_Stream
python startup.py
```
**Expected Output:**
```
[GPS] Server listening on 0.0.0.0:12345
[MCP] Server starting...
Visit http://0.0.0.0:5000
```

---

## **Step 6: Start Main GUI Simulation**
### **Terminal 2:**
```bash
[ -z "$VIRTUAL_ENV" ] && source ~/CARS_sim_2_ollama/venv/bin/activate
cd ~/CARS_sim_2_ollama/demos/12-LLM_SIM_GPS_Message_Stream
python main_gui.py
```
**Expected Output:**
```
[GUI] Initializing GPS Simulation GUI...
[GUI] Window visible: True
[SIM] GUI window should be visible now - simulation running...
```

---

## **Access Points**

| Component | URL/Interface |
|-----------|---------------|
| **GUI Simulation** | PyQt5 Window (appears automatically) |
| **Web Dashboard** | http://localhost:5000 |
| **GPS Constellation** | tcp://localhost:12345 (backend only) |
| **Ollama API** | http://localhost:11434 |
| **PostgreSQL** | localhost:5432 (user: postgres, pass: password) |

---

## **🛑 Shutdown Sequence**

```bash
# 1. Close GUI (Terminal 2)
# Close PyQt5 window or press Ctrl+C

# 2. Stop Backend Services (Terminal 1)
# Press Ctrl+C in startup.py terminal

# 3. Stop Database
cd ~/CARS_sim_2_ollama/demos/12-LLM_SIM_GPS_Message_Stream
docker compose down -v

# 4. Close SSH tunnel (Terminal with ssh command)
# Press Ctrl+C or exit

# 5. Stop Ollama on GPU (if you started it)
# Press Ctrl+C on gpu02
```

---

## **⚡ Quick Checklist**

- [ ] VPN connected
- [ ] Ollama server running on gpu02
- [ ] SSH tunnel established (port 11434 forwarded)
- [ ] `curl localhost:11434` returns Ollama response
- [ ] PostgreSQL container running (`docker ps`)
- [ ] Virtual environment activated
- [ ] Backend services running (startup.py)
- [ ] GUI window visible (main_gui.py)

---

## **🔧 Troubleshooting**

### **Can't connect to Ollama:**
```bash
# Check if tunnel is active
netstat -an | grep 11434

# Test connection
curl localhost:11434
```

### **Database not starting:**
```bash
# Check container status
docker ps -a

# View logs
docker compose logs
```

### **GUI not showing:**
```bash
# Test PyQt5 display
python test_gui_display.py
```