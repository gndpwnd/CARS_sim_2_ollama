now I need to be tracking all these requirements and constraints for each vehicle, and somehow simulate NMEA sentences and or RTCM messages, please just start with tracking each requirement and constraint for each vehicle, then for the notification dashboard, i want to be able to switch vehicles by using a simple drop down menu above the tabs. make sure to use requirements_config.json so you don't have to blow up file sizes. i want to make this as modular and simple as possible

I want an external program to generate random messages when queried. I basically want to make a "satellite constellation" or a python app that generates NMEA sentences and/or RTCM messages when vehicles ask for them.

please use libraries like

https://github.com/semuconsulting/pyrtcm

and

https://github.com/Knio/pynmea2


python sat_constellation.py

python main_gui.py




dev@DB-78GB094:~/CARS_sim_2_ollama/demos/12-LLM_SIM_GPS_Message_Stream$ tree -I "__pycache__" -I "docs" -I "docs_old"
.
├── Readme.md
├── constellation_config.json
├── docker-compose.yml
├── gps_manager.py
├── llm_config.py
├── mcp_chatapp.py
├── requirements_config.json
├── sat_constellation.py
├── sim.py
├── sim.py.old
├── sim_helper_funcs.py
├── sim_reqs_tracker.py
├── startup.py
├── static
│   ├── css
│   │   └── style.css
│   └── js
│       └── script.js
├── templates
│   └── index.html
├── todo.md
└── vehicle_requirements_tracker.py

4 directories, 18 files
dev@DB-78GB094:~/CARS_sim_2_ollama/demos/12-LLM_SIM_GPS_Message_Stream$ 


I just want to keep track of GPS module messages and IMU on agents

- treat GPS satellites as static positions - they are survey points
- only need to add error to drone/agent for simulation

- sang already has GPS simulation, just need to add plausible NMEA/RTCM messages that look real
 - https://github.com/Swarm-Squad/Swarm-Squad-Ep1/tree/main/lib/old
 - each simulation is standalone, just need main.py and utils.py

- then need to have something to show message streams, like my demo with qdrant and postgresql chat website.

- need to store the following
 - messages between LLM and user, then LLM and agents
 - telemetry (Qdrant)
 - GPS messages between agents and satellites/survey points



i want to make sure all the NMEA messages and RTCM are part of the telemetry for every agent recorded to qdrant along side positioning and more. I would prefer if i could scale the environment/grid system that my agents move on to be similar to the world in terms of making viable coordinates. 
 
also could you make a bash script to start everything in the backgroudn and print out what ports everything is on so i can visit the link in the web browser? then add the functionality to kill the processes using pgrep and kill for the specific script names if the argument stop is passed, so "./run.sh start" starts it and "./run.sh stop" stops it. or should i just keep startup.py? it seems startup.py is more straightforward.


so what is the file structure I should expect now? tell me what files are being used and for what
