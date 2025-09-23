now I need to be tracking all these requirements and constraints for each vehicle, and somehow simulate NMEA sentences and or RTCM messages, please just start with tracking each requirement and constraint for each vehicle, then for the notification dashboard, i want to be able to switch vehicles by using a simple drop down menu above the tabs. make sure to use requirements_config.json so you don't have to blow up file sizes. i want to make this as modular and simple as possible

I want an external program to generate random messages when queried. I basically want to make a "satellite constellation" or a python app that generates NMEA sentences and/or RTCM messages when vehicles ask for them.

please use libraries like

https://github.com/semuconsulting/pyrtcm

and

https://github.com/Knio/pynmea2


python sat_constellation.py

python main_gui.py




(venv) dev@DB-78GB094:~/CARS_sim_2_ollama/demos/11-simple_NMEA_RCTM$ tree -I "__pycache__" -I "docs" -I "docs_old"
.
├── constellation_config.json
├── enhanced_notification_gui.py
├── gps_client_lib.py
├── main_gui.py
├── notification_gui.py
├── requirements_config.json
├── run_sim.py
├── sat_constellation.py
├── tmp.md
├── utils_gps_sim.py
├── vehicle.py
└── vehicle_requirements_tracker.py

0 directories, 12 files
(venv) dev@DB-78GB094:~/CARS_sim_2_ollama/demos/11-simple_NMEA_RCTM$ 