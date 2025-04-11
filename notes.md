i would now like to create a nearly identical simulation in triangulate.py where 3 agents are positioned at random coordinate, and a rover agent (explicitly different than all other agents and of blue color) is also placed randomly on the xy plane. After placement, use the agents to triangulate the position of the rover and draw dotted lines between the agents to the rover with a visable distance value so that the view can see what is going on. Print out the current rover position and to make things simpler, remove all llm functionality and round all calculationns to the nearest hundreth. 


Ollama’s chat endpoint supports persistent conversation through the messages array:

[
  {"role": "system", "content": "You are a helpful assistant."},
  {"role": "user", "content": "Start a simulation with 5 agents."},
  {"role": "assistant", "content": "Simulation with 5 agents started."},
  ...
]


You need to store and maintain this message history so both your chat and simulation can append and read from it.