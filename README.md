# CARS_sim_2_ollama
> <a href="https://github.com/Swarm-Squad" target="_blank" rel="noopener noreferrer">Swarm-Squad</a>

> using python 3.11

## Setup For Demos

clone the repo

```
git clone https://github.com/gndpwnd/CARS_sim_2_ollama.git; cd CARS_sim_2_ollama
```

setup venv

```
python3.11 -m venv venv; source venv/bin/activate
```

install requirements

```
pip install --upgrade pip; pip install -r requirements.txt
```

in a separate terminal, start the ollama server

```
ollama run llama3.2:1b 
```

### Linear Waypoints Mission Simulation

files in ***basic_lin_demos*** can stand on their own
```
python3 demos/basic_lin/1-jam_return_safe_coords.py
```

### Basic RAG Dmemo

need a chatapp interface with ollama/LLM and data generator running at same time
```
python3 demos/basic_rag_demo/chatapp.py
python3 demos/basic_rag_demo/demo_rag_data.py
```

### Handling Automatically Downloaded Files

the rag demo will download files to your system and create files for storage. All of these files should be accounted for in the [.gitignore](./.gitignore){:target="_blank"}, to view your file tree, but exclude directories that have lots of "noisy files"
```
tree -I 'venv|__pycache__|.git'
```

these files can get large, so if you want to remove them, you can run the following command to see what would be removed. In case you don't want to remove the venv, you can exclude it.
```
git clean -xdn
git clean -xdn -e venv/
```

and then run the following command to remove them. however if you don't want to remove ***venv/*** you can exclude it
```
git clean -xdf
git clean -xdf -e venv/
```


# TODO

## Basic Simulation

- [x] Agents exist on a plot
- [x] Agent Parameters
	- [x] Location (x,y)
	- [x] Communication Quality
- [x] Agents follow mission path
	- [x] Linear path from spawn point to (MAX x, MAX y)
- [x] Jamming Locations

## Algorithmic-Agent Interaction

- [x] Agent Jammed
	- [x] Identify Jamming (communication quality threshold)
	- [x] Return to last known non-jammed coordinates
		- [x] Return to last known non-jammed coordinates before promptin llm for new coordinates
- [x] Agent Recovered
	- [x] Agent previously jammed, but is no longer jammed, do not need to prompt LLM
	- [x] Based on current location and mission end state, find new path to get mission end state

## LLM-Agent Interaction

- [x] Agent Recovery
	- [x] Based on known mission path and known jammed coordinates, calculate "next coordinates"
	- [x] Return "next coordinates" and agent move to "next coordinates"
- [ ] Agent Mission Plannning
	- [ ] Given start and end and known jamming, calculate plot function and generate waypoints
	- [ ] Return waypoints and agent moves along waypoints
	- [ ] Update future waypoints based on new jamming coordinates
- [ ] Swarm Mission Planning
	- [ ] swarm idle movements controlled by algorithm
		- [ ] agents cannot intersect other agents
	- [ ] calculate center of swarm, treat as a meta-agent
	- [ ] calculate waypoints for center of swarm given start area and end area
	- [ ] Update future waypoints based on new jamming coordinates


## GPS-Denied Surveying Rover Location Relay (Real World Application #1)

- [ ] Rover exists on plot with 3 LLM-agents
	- [ ] LLM-agents triangulate position of rover
- [ ] Rover moves across plot
	- [ ] LLM-agents update rover location
	- [ ] LLM-agents must be within max-distance of rover (roughly follow rover, LLM control)
- [ ] Rover moves through a jammed area
	- [ ] LLM-Agents maintain non-jammed status
	- [ ] LLM-Agents also maintain max-distance of rover (adapt to rover location and stay outside of jammed area)


## User-LLM-Agent Interaction (Highest Abstraction)

- [x] User can query info on agents from LLM context
	- [x] Agent status, position
	- [ ] Progress of mission
- [ ] User-LLM-Agent Control
	- [ ] User can control agent through llm (override)
		- [ ] move agent from current position to new coordinates
		- [ ] user can specify for agent to rejoin swarm?
	- [ ] User can make a mission plan for an agent that LLM executes
- [ ] User can define swarm of agents and prompt control
	- [ ] move swarm from current position to new coordinates
	- [ ] user can specify adding agents to swarm? "Move AgentX to join SwarmX"
	- [ ] User can make a mission plan for a swarm that LLM executes
