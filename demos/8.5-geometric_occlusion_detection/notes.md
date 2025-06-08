I want to perform multilateration using 3 known points (drones) in an xy plane to determine an unknown position (rover position) when given the distance from the rover to each child drone. I have attatched the math behind multilateration in 2D and 3D for context. what i want to prove or disprove is that when in either 2D or 3D, given the know positions and respective distance measurements, go through the combinations of distance measurements (in meters) and drone x, y coordinates and if there is a distance that is to short or too long within a given tolerance (say 1m) then the target is possibly occluded in the system but how do i know which anchor point the target appears to be occluded from?. please create a simply python script to help visualize this proof using matplotlib and show distance measurements as dotted blue lines, the drones/anchors as green points, and the rover as yellow point. I also want to be able to determine if there is target occlusion from multiple points. i don't want to perform any multilateration in the occlusion checker, this occlusion checking will become part of my multilateration system, i only want to check for possible occlusion based on the distances and positions of the anchor points given a predefined tolerance of 0.1 meter or so. Overall i want to incorporate the occlusion checker file into the main simulation, but also split the main simulation into the main controls (stay in the main sim file) and the vehicle class (put in vehicle.py). please update the main simulation and if needed the utils file. I also don't want to perform multilateration at all, this simulation needs to focus soley on geometric occlusion detection in 2D and if i want to in 3D, keep track of 2D vs 3D usage with SET_3D = false to start in 2D

i want the jammed areas that the user can draw to become the obstacles that create target occlusion and the system should then detect this occlusion. I would then like to begin the logic to determine which drones/anchors are occluded from the target and then start on a system to guide those drones/anchors to move so that they are not occluded from the target. remeber that the rover position is fully unknown during this process and that the position of the occlusion objects/areas are fully unknown and this system simply detects and navigates the occlusions to properly position the drones to get accurate distance measurements, but don't perform multilateration just yet.


I currently have:

(venv) ubuntu@ubuntu:~/Desktop/CARS_sim_2_ollama/demos/8.5-geometric_occlusion_detection$ tree
.
├── main_occ_sim.py
├── notes.md
├── occ_check.py
├── occ_gui.py
├── occ_handler.py
├── occ_utils.py
└── vehicle.py

when switching to 3d, i want matplotlib to plot everything in 3d but if switching directly from 2d, keep every vehicle in the xy plane of z=0, if restarting or starting the simulation in 3d, then put vehicles in positions including variance in Z

also i noticed a bug - when starting the sim and having drawn no obstacles, there exists occlusion being detected, this should not happen. maybe you need to modify the constraint of accuracy to within 0.1m or something but in this simulation i should be able to draw an obstacle and then the occlusion detection system, not knowing the position of the rover or any obstacles, should determine that an anchor point/drone is facing occlusion from the rover.

I just recently split my occlusion checker into occlusion hanlder and occlusion checker, the checker is now a sub class of the handler in which the handler will control higher level actions like movement of anchors/drones when needed and the checker simply perorms geometric analysis so that i can reduce overall file sizes. i want to make sure everything seems to flow together and that no code is redundant.