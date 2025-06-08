check what files are ignored in git or are not checked in

```
git clean -xdn
git clean -xdn -e venv/
```

remove those files and also if you don't want to remove ***venv/*** 

```
git clean -xdf
git clean -xdf -e venv/
```

the big command to run a hybrid-data-enabled system

```
docker compose down -v; sudo chown -R $USER:$USER ./pg_data; sudo chown -R $USER:$USER ./qdrant_data; rm -rf ./pg_data ./qdrant_data; docker compose up -d; python sim.py
```

```
python3 mcp_chatapp.py
```

I have the following python scripts of which i want to create a simulation that shows a rover that conducts a land survey transversing an area in which it would become gps-denied. I then want the rover to stop its movement until it has recieved an accurate position from a "parent drone". In order for the rover to recieve this accurate position, it needs to communicate with at least 4 drones and therefore a COMM_RANGE constraint is fullfilled of the distance between the drones and rover needed for them to communicate. however the drones that help the gps-denied rover need to not be in the jammed area themselves, each drone needs to keep track if it is jammed or not and if it is jammed, then go back to the last position that it was not jammed, each drone keeps track of its last NUM_DRONE_POS_ONBOARD positions so it can recover from being jammed, but will send all telemetry data to the parent drone then that parent drone sends it to a database system as seen in attatched documentation. then each drone when it is within COMM_RANGE of the rover but not GPS-denied or jammed needs to perform a distance measurment - get the distance between a drone and the rover. then each drone will send its distance, measurement and its gps location to a parent drone. this parent drone will then perform multilateration calculations and determine if any drones are not following the constraints in the ToF file. if any drone is not within those constraints, then the parent drone will communicate with that drone and tell it where it should move and move that slave drone until it is within the constrains of the multilateration system. once all constraints of distance measurement and multilateration are met, then the parent drone (also within COMM_RANGE of the rover) should be able to send the final position of the rover to the rover itself, only when the rover recieves a position from the parent drone will it be able to continue on its path when it is gps denied. Overall i want to create the child_drone.py class, the parent_drone.py class, and a rover.py class and make sure the child drone class can communicate with the parent drone class and the rover class. The parent drone class should be able to perform multilateration calculations and send the final position to the rover class. The rover class should be able to receive the position from the parent drone and continue its path when it is gps denied. the child drone class should be able to perform distance measurements and send its telemetry data to the parent drone class. Each child drone should keep track of its last NUM_DRONE_POS_ONBOARD positions and be able to recover from being jammed. this jam recovery should be done by the parent drone class.Dont worry about streaming telemetry data to the database, I will handle that later. 



I want to make sure that my simulation properly incorporates and plots the new vehicle classes of child drone and parent drone and rover. i then want to make sure the user can actually control the gui without losing the quality of the gui. 

the child drones perform distance measurments using ToF with the rover, then they send those to the parent drone and the parent drone performs multilateration so you don't need to worry about distance measurements or multilateration or the constraints associated with them. basically all vehicles should act without user intervention in the simulation but i don't want the simulation dictating vehicle movements if that makes sense only showing the vehicle behaviour by plotting their current locations, jammed area/areas, and current vehicles states if they are jammed or not jammed and then other important information. the only thing i want to control on the vehicles with the simulation is the mission end point for the rover or where the rover is trying to go. then the gui allows the user to interact view whats going on and make necessary intervention with the intention of later hooking up an llm to this system.