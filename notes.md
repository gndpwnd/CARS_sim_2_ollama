lmm is to slow for path finding - when dojg a jammed enviornment mission, have a path funding alorigthm to do low level manuevers but also allow llm injection, the llm is a massiv permoance bottleneck for path finding.


have lmm choose what movement functikns and what pathfinding functions to run, or given data give new coordinates.


text gen models : unsupervised learning more or less on the contents of the dataset

instruct models: text gen models that have undergone supervised fine tuning to ensure that the llm responds in a Q+A style format


k models, km vs ks


k_s models for whatever reason are a little slower than k_m models. k models are k-quant models and generally have less perplexity loss relative to size. A q4_K_M model will have much less perplexity loss than a q4_0 or even a q4_1 model.

q4_k_m vs q4_k_s

k_m vs k_s vs k_l - level of optimization of quantization of model - the idea is to reduce the size of the model without losing quality/precision - k_l is the largest "least optimized for size" and k_s is the small "more optimized for siz". "more optimized" does not mean better for what you are doing though.


https://www.reddit.com/r/LocalLLaMA/comments/159nrh5/the_difference_between_quantization_methods_for/

https://github.com/ggerganov/llama.cpp/pull/1684#issuecomment-1579252501

https://github.com/ggml-org/llama.cpp/pull/1684


https://huggingface.co/spaces/Krisseck/IFEval-Leaderboard


The agents should move way faster than the rover. have the agents try to be equidistant from the rover (center of the rover's max distance from agents radius). then add the logic for triangulating the rover's position. Overall the agents should not just stay on the edge of the rover's radius unless the rover is completely encompassed by the jamming zone, the the agents should try to be equidistant from the rover as close as possible while still not in the jamming zone. the agents not being jammed takes priority over being equidistant. due to the agents moving faster than the rover, they should move to the rover until they meet the too close distance to other agents, then the agents should simply move in unison with the rover, not all agents should be moving behind the rover, ideally all agents would be equidistant round the rover as it is travelling, and only break away when the rover is jammed. Agents need to find where in the rover's radius they will not be too close to each other, then the agent that has the greatest number in their id is the first one to move to fix the agents to close together issue.




I have the following python script. It currently is a series of agents on a waypoint mission from one corder of the grid to the other. I want to modify it to have a special rover agent apart from the normal agents. This rover agent moves linearly from the point (-10,5) to (10,5), rather than having the normal agents deploy and follow the mission linear path, i want to deploy them and be able to measure how far each agent is from the rover. as the rover moves, make sure the agents do not stay further than 5 units from the rover, when an agent needs to move closer, plot a new "closer_point" for the agent to move to and use the linear path function to get the agent to move there. I want to control how fast the rover can move and the points that is moves between - effectively keeping the same controls as now except adding the rover speed and having the mission points be for the rover. make sure to plot the rover's communication quality with the other agetns.
a key feature is that when the rover gets jammed, it returns to its safe coordinates, but does not ask the llm for directions, it waits until all agents are within their "AGENT_DIST_TO_ROVER" requirement, then it continues on its path. basically, the rover is moving and the agents stay within their necessary distance to the rover, then when the rover is jammed, then as long as the agents are within their distance, the rover can keep moving. The agents need to stay out of the jamming zone. Make sure that the RAG data logs reflect they are coming from the rover and not the normal agents. Make the rover a blue color and then when it is jammed make it a yellow color.

simply make a new script with helper functions for the rover, and then show me where in my current script i need to adjust for my agent's logic and add the rover logic, show me the full code for the new script, but only the parts of my current script that need to be updated



I want to make a simple simulation using python and matplotlib where a rover (blue dot) moves on a x range -10 to 10 and y range -10 to 10 grid and starts from -10,5 and moves to 10,5. from here i want to have 3 agents (green dots) that only move when they are not within "MAX_DIST_FROM_ROVER" units distance from the rover. if the agents need to move, make a function to finda new coordinate and move to that location. I want every agent to make one move per iteration, with an iteration speed of ITERATION_SPEED = 0.5 in seconds. I want the rover to be slower than the agents, moving at a maximum of ROVER_SPEED = 1.5 units per iteration and the agents moving at a speed of AGENT_SPEED = 3 units per iteration. I would then like to draw black lines between each agent and the rover with the corresponding length (distance between rover and agent) labeled in the center of the line. Do not use classes and keep it as simple as needed


I have the following scripts where i try to have agents follow a rover on an xy plane and store the data for the rover and the agents in RAG. I run into the following issue, could you point out what code i need to fix? you don't need to give me an updated version of the file, just generate the new code to replace the old code.








I have the following python simulation, flask chatapp, and rag store script. I am wanting to make a new simulation based on the old one, but the agents have no objective, there is no jamming zone, there is no automatic movement or linear anything. I simply want to make a version where the user can control agent movements from the chatapp such as a user will type:

"move agent5 to (5,5)"

and then agent with the id of 5 will move to the coordinates 5,5

use the func call ollama script as a base for the LLM ollama to be able to interact with functions in the simulation and manual control rather than the agents prompting for new coordinates and automatically moving



I am trying to make a python agent simulation where the user can control agent movements from the chatapp such as a user will type:

"move agent5 to (5,5)"

and then agent with the id of 5 will move to the coordinates 5,5

use the func call ollama script as a base for the LLM ollama to be able to interact with functions in the simulation and manual control rather than the agents prompting for new coordinates and automatically moving


below are my current sim, chatapp, rag store, html, and javascript nad a refernce file that allows functiona calls with the llm




I am currently trying to integrate user to llm to function call in my agent simulation. I currently have the follwoing code and get the following results. I ultimately want to be able to have the user send a message to the llm and have the llm make a function call to move an agent to a coordinate.



log output from the following conversation. I still don't see the agent on the plot being updated to move across a linear path to the destination and not resume its routine until landing on the desination. Overall the plot is not being managed properly regarding the logs. make sure the agent moves on the plot first before adding to any logs, and can you make a point on the plot for a waypoint when a user makes the agent move to that waypoint? then take that waypoint off the plot when the agent reaches it. overall what if the functionality was changed so that the llm calls a function to plot a waypoint for the agent in order recieved from user, then the python sim takes care of if there are way points, then take the agents current position and make a linear path to the first waypoint. then have the agent follow the linear path to the waypoint before resuming routine.




move agent1 to 5,5
Waypoint (5.0, 5.0) added for agent1. The agent will move to this waypoint.
move agent1 to 5,5
Waypoint (5.0, 5.0) added for agent1. The agent will move to this waypoint.

LOGGING] Logged data for agent agent1 at [1.416, -0.924]
[DEBUG] Updated swarm_pos_dict: {'agent1': [[2.876, -7.861], [2.759, -6.452], [1.427, -6.928], [2.435, -5.936], [1.977, -4.598], [0.565, -4.676], [-0.325, -3.577], [0.76, -2.67], [1.399, -1.409], [1.416, -0.924]]}
[DEBUG] Random move for agent agent1 from [np.float64(1.416), np.float64(-0.924)] to (np.float64(0.255), np.float64(-0.116))
[LOGGING] Logged data for agent agent1 at (0.255, -0.116)
[DEBUG] Updated swarm_pos_dict: {'agent1': [[2.759, -6.452], [1.427, -6.928], [2.435, -5.936], [1.977, -4.598], [0.565, -4.676], [-0.325, -3.577], [0.76, -2.67], [1.399, -1.409], [1.416, -0.924], [0.255, -0.116]]}
[DEBUG] Random move for agent agent1 from [np.float64(0.255), np.float64(-0.116)] to (np.float64(1.075), np.float64(1.036))
[LOGGING] Logged data for agent agent1 at (1.075, 1.036)
[DEBUG] Updated swarm_pos_dict: {'agent1': [[1.427, -6.928], [2.435, -5.936], [1.977, -4.598], [0.565, -4.676], [-0.325, -3.577], [0.76, -2.67], [1.399, -1.409], [1.416, -0.924], [0.255, -0.116], [1.075, 1.036]]}
[DEBUG] Random move for agent agent1 from [np.float64(1.075), np.float64(1.036)] to (np.float64(2.293), np.float64(0.317))
[LOGGING] Logged data for agent agent1 at (2.293, 0.317)
[DEBUG] Updated swarm_pos_dict: {'agent1': [[2.435, -5.936], [1.977, -4.598], [0.565, -4.676], [-0.325, -3.577], [0.76, -2.67], [1.399, -1.409], [1.416, -0.924], [0.255, -0.116], [1.075, 1.036], [2.293, 0.317]]}
[DEBUG] Random move for agent agent1 from [np.float64(2.293), np.float64(0.317)] to (np.float64(3.707), np.float64(0.354))
[LOGGING] Logged data for agent agent1 at (3.707, 0.354)
[DEBUG] Updated swarm_pos_dict: {'agent1': [[1.977, -4.598], [0.565, -4.676], [-0.325, -3.577], [0.76, -2.67], [1.399, -1.409], [1.416, -0.924], [0.255, -0.116], [1.075, 1.036], [2.293, 0.317], [3.707, 0.354]]}
[DEBUG] Random move for agent agent1 from [np.float64(3.707), np.float64(0.354)] to (np.float64(3.497), np.float64(-1.045))
[LOGGING] Logged data for agent agent1 at (3.497, -1.045)
[DEBUG] Updated swarm_pos_dict: {'agent1': [[0.565, -4.676], [-0.325, -3.577], [0.76, -2.67], [1.399, -1.409], [1.416, -0.924], [0.255, -0.116], [1.075, 1.036], [2.293, 0.317], [3.707, 0.354], [3.497, -1.045]]}
Simulation stopped


[DEBUG] Updated swarm_pos_dict: {'agent1': [[-0.869, 1.111], [-0.577, 2.495], [-1.442, 1.376], [-0.154, 2.101], [1.135, 2.826], [2.423, 3.55], [3.712, 4.275], [5.0, 5.0], [5.0, 5.0], [5.0, 5.0]]}
[DEBUG] Direct parse of move command: agent1 to (5.0, 5.0)
[DEBUG] Added waypoint for agent1: (5.0, 5.0)
[DEBUG] Generated linear path with 1 points
127.0.0.1 - - [24/Apr/2025 11:01:48] "POST /chat HTTP/1.1" 200 -
127.0.0.1 - - [24/Apr/2025 11:01:48] "GET /logs HTTP/1.1" 200 -
127.0.0.1 - - [24/Apr/2025 11:01:50] "GET /logs HTTP/1.1" 200 -
[DEBUG] Following path: Agent agent1 moving from [np.float64(5.0), np.float64(5.0)] to (np.float64(5.0), np.float64(5.0))
[DEBUG] Agent agent1 completed its path
[DEBUG] Updated swarm_pos_dict: {'agent1': [[-0.577, 2.495], [-1.442, 1.376], [-0.154, 2.101], [1.135, 2.826], [2.423, 3.55], [3.712, 4.275], [5.0, 5.0], [5.0, 5.0], [5.0, 5.0], [5.0, 5.0]]}
127.0.0.1 - - [24/Apr/2025 11:01:53] "GET /logs HTTP/1.1" 200 -
[DEBUG] Generated new path for agent agent1 with 1 points
[DEBUG] Updated swarm_pos_dict: {'agent1': [[-1.442, 1.376], [-0.154, 2.101], [1.135, 2.826], [2.423, 3.55], [3.712, 4.275], [5.0, 5.0], [5.0, 5.0], [5.0, 5.0], [5.0, 5.0], [5.0, 5.0]]}
127.0.0.1 - - [24/Apr/2025 11:01:56] "GET /logs HTTP/1.1" 200 -
[DEBUG] Generated new path for agent agent1 with 1 points
[DEBUG] Updated swarm_pos_dict: {'agent1': [[-0.154, 2.101], [1.135, 2.826], [2.423, 3.55], [3.712, 4.275], [5.0, 5.0], [5.0, 5.0], [5.0, 5.0], [5.0, 5.0], [5.0, 5.0], [5.0, 5.0]]}
