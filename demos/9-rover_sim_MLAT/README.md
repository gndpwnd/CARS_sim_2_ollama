### Notice

- currently not connected to MCP enabled chat app
- simulation does not currently stream telemetry to vector databse (qdrant)
- need to fix "sim reset" button functionality
- need to have drones "flock" when rover becomes jammed and use last know rover location as a reference
  - need to make child drones be within COMM_RANGE of rover.
- need to add delays to allow visualization of distance measurements
- need to add verbose logging to show ToF meausurment and MLAT calculations information

### Useful Commands

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
docker compose down -v; sudo chown -R $USER:$USER ./pg_data; sudo chown -R $USER:$USER ./qdrant_data; rm -rf ./pg_data ./qdrant_data; docker compose up -d; python main_gps_sim.py
```

and then run the mcp chatapp

```
python3 mcp_chatapp.py
```