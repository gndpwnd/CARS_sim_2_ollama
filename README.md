# CARS_sim_2_ollama

## Setup Demos

clone the repo
```
git clone https://github.com/gndpwnd/CARS_sim_2_ollama.git; cd CARS_sim_2_ollama
```

setup venv and install dependencies
```
python3 -m venv venv; source venv/bin/activate; python -m pip install --upgrade pip; pip install -r requirements.txt
```

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
	- [ ] Return to last known non-jammed coordinates
		- [ ] Return to last known non-jammed coordinates before promptin llm for new coordinates
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

- [ ] User can query info on agents from LLM context
	- [ ] Agent status, position
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
