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

## Running the Demos

Read the Readme.md files in the demo folders for more information on how to run the demos.

## Handling other things in the project 

### Automatically Downloaded Files

the rag demo will download files to your system and create files for storage. All of these files should be accounted for in the [.gitignore](https://github.com/gndpwnd/CARS_sim_2_ollama/blob/main/.gitignore), to view your file tree, but exclude directories that have lots of "noisy files"
```
tree -I 'venv|__pycache__|.git|pgdata'
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

### Setting up a folder to Share Between Host-Machine and VM

> using VMware workstation pro

 - Select your VM
 - go to that VM's settings
	or
 - if your VM is running, go to "VM" in the menu bar
 - select "Settings"
  
 - select "Options" tab
 - select "Shared Folders"
 - select "Always enabled"
 - select "Add" to add a new folder
 - select the folder you want to share
 - click "OK"

The folder should mount to your VM at ***/mnt/hgfs/<folder_name>***. You can use this folder to share files between your host machine and your VM.

Making a symbolic link to that folder so you can access it from your working directory

```
ln -s /mnt/hgfs/<folder_name> <link_name>
ln -s /mnt/hgfs/shared-folder host-share
```

### Setting up Docker Compose

Install the newer docker compose on your system, i am using ubuntu

> [source](https://docs.docker.com/compose/install/linux/)

in one line
```
DOCKER_CONFIG=${DOCKER_CONFIG:-$HOME/.docker}; mkdir -p $DOCKER_CONFIG/cli-plugins; curl -SL https://github.com/docker/compose/releases/download/v2.35.0/docker-compose-linux-x86_64 -o $DOCKER_CONFIG/cli-plugins/docker-compose; chmod +x $DOCKER_CONFIG/cli-plugins/docker-compose; docker compose version
```


the commands being run
```
DOCKER_CONFIG=${DOCKER_CONFIG:-$HOME/.docker}
mkdir -p $DOCKER_CONFIG/cli-plugins
curl -SL https://github.com/docker/compose/releases/download/v2.35.0/docker-compose-linux-x86_64 -o $DOCKER_CONFIG/cli-plugins/docker-compose
chmod +x $DOCKER_CONFIG/cli-plugins/docker-compose
docker compose version
```

### Running docker compose

```
docker compose up
```

running in detatched mode
```
docker compose up -d
```

stopping docker compose
```
docker compose down
```

beginner friendly - remove everything associated with the docker compose, except persistent volumes
```
docker compose down -v
```

to list or remove all unused docker containers linked to the postresql pgvector image

```
docker ps -a --filter "ancestor=ankane/pgvector:latest" -q
```

```
docker rm $(docker ps -a --filter "ancestor=ankane/pgvector:latest" -q)
```

change permissions on pgdata directory so user can use it or remove it
```
sudo chown -R $USER:$USER ./pgdata
```

remove pgdata directory
```
rm -rf ./pgdata
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
