## Table of Contents
> [TOC Generator](https://www.docstomarkdown.pro/markdown-table-of-contents-generator-free/)

- [CARS_sim_2_ollama](#cars_sim_2_ollama)
  - [Setup Your Ubuntu/Debian System For Demos](#setup-your-ubuntu/debian-system-for-demos)
    - [WSL Setup](#wsl-setup)
  - [Running the Demos](#running-the-demos)
  - [Handling other things in the project](#handling-other-things-in-the-project)
    - [Automatically Downloaded Files](#automatically-downloaded-files)
    - [Setting up a folder to Share Between Host-Machine and VM](#setting-up-a-folder-to-share-between-host-machine-and-vm)
    - [Setting up Docker Compose](#setting-up-docker-compose)
    - [Running docker compose](#running-docker-compose)
- [TODO](#todo)
  - [Basic Simulation](#basic-simulation)
  - [Algorithmic-Agent Interaction](#algorithmic-agent-interaction)
  - [LLM-Agent Interaction](#llm-agent-interaction)
  - [GPS-Denied Surveying Rover Location Relay (Real World Application #1)](#gps-denied-surveying-rover-location-relay-(real-world-application-#1))
  - [User-LLM-Agent Interaction (Highest Abstraction)](#user-llm-agent-interaction-(highest-abstraction))

# CARS_sim_2_ollama
> <a href="https://github.com/Swarm-Squad" target="_blank" rel="noopener noreferrer">Swarm-Squad</a>

> using ubuntu 22.04 LTS and python 3.11
> if using torch, pip install torch --index-url https://download.pytorch.org/whl/cpu

## Setup Your Ubuntu/Debian System For Demos

Install python3.11

```
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.11 python3.11-venv
```

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

install docker

```
sudo apt install -y docker.io docker-compose; sudo groupadd docker; sudo usermod -aG docker $USER; sudo systemctl start docker; sudo systemctl enable docker; newgrp docker
```

install docker compose

```
DOCKER_CONFIG=${DOCKER_CONFIG:-$HOME/.docker}; mkdir -p $DOCKER_CONFIG/cli-plugins; curl -SL https://github.com/docker/compose/releases/download/v2.35.0/docker-compose-linux-x86_64 -o $DOCKER_CONFIG/cli-plugins/docker-compose; chmod +x $DOCKER_CONFIG/cli-plugins/docker-compose; docker compose version
```

install ollama and check if it is started

```
curl -fsSL https://ollama.com/install.sh | sh
```

```
sudo systemctl start ollama
sudo systemctl status ollama
```

in a separate terminal from the terminal you run the python scripts in, run the necessary ollama model

```
ollama run [model_name]
```

### WSL Setup

1) Install WSL and your preferred Linux distribution (e.g., Ubuntu 22.04 LTS).
2) Install Visual Studio Code on Windows.
3) Install the "WSL" extension in VS Code
   - I also like to use the git "source control" extension so I can directly push and pull to a repo
5) Start a new WSL terminal, navigate to the folder you want to open in code and type:

```bash
code .
```

you may get a message similar to the following

```
Installing VS Code Server for Linux x64 (6f17636121051a53c88d3e605c491d22af2ba755)
Downloading: 100%
Unpacking: 100%
Unpacked 2052 files and folders to /home/dev/.vscode-server/bin/6f17636121051a53c88d3e605c491d22af2ba755.
Looking for compatibility check script at /home/dev/.vscode-server/bin/6f17636121051a53c88d3e605c491d22af2ba755/bin/helpers/check-requirements.sh
Running compatibility check script
Compatibility check successful (0)
```

code should open and you might get a message such as ***Do you trust the authors of the files in this folder?***. Make sure to trust the authors.

Your folder should be opened in code. Now when you open a terminal in code it should open a wsl terminal.

**WSL Troubleshooting Operations**

> [developing on top of WSL](https://code.visualstudio.com/docs/remote/wsl)

after starting up the venv, installing pip requirements, and trying to start a demo:

```
qt.qpa.plugin: Could not load the Qt platform plugin "xcb" in "" even though it was found.
This application failed to start because no Qt platform plugin could be initialized. Reinstalling the application may fix this problem.

Available platform plugins are: eglfs, linuxfb, minimal, minimalegl, offscreen, vnc, wayland-egl, wayland, wayland-xcomposite-egl, wayland-xcomposite-glx, webgl, xcb.

Aborted (core dumped)
```

the fix for now:

```bash
sudo apt update; sudo apt install -y libx11-xcb1 libxcb1 libxcb-render0 libxcb-shape0 libxcb-xfixes0 libxcb-render-util0 libxcb-image0 libxcb-keysyms1 libxcb-icccm4 libxcb-sync1 libxcb-xkb1 libxcb-randr0 libxcb-xinerama0 libxkbcommon-x11-0 libxkbcommon0; pip install pyqt5
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
