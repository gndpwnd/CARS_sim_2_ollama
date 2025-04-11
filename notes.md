tree -I 'venv|__pycache__|.git'

i would now like to create a nearly identical simulation in triangulate.py where 3 agents are positioned at random coordinate, and a rover agent (explicitly different than all other agents and of blue color) is also placed randomly on the xy plane. After placement, use the agents to triangulate the position of the rover and draw dotted lines between the agents to the rover with a visable distance value so that the view can see what is going on. Print out the current rover position and to make things simpler, remove all llm functionality and round all calculationns to the nearest hundreth. 


Ollama’s chat endpoint supports persistent conversation through the messages array:

[
  {"role": "system", "content": "You are a helpful assistant."},
  {"role": "user", "content": "Start a simulation with 5 agents."},
  {"role": "assistant", "content": "Simulation with 5 agents started."},
  ...
]


You need to store and maintain this message history so both your chat and simulation can append and read from it.



I have a simple chat app with flask to communicate to a local ollama model, and i have a gen_data script to run a basic simulation to update ollama with information. I am trying to implement RAG with chromaDB and i have the following project tree

ok i now have the following tree with the following files:

(venv) ubuntu@ubuntu2004:/opt/CARS_sim_2_ollama$ tree -I 'venv|__pycache__|.git'
.
├── chat
│   ├── app.py
│   ├── static
│   │   └── style.css
│   └── templates
│       └── index.html
├── demos
│   └── basic_lin
│       ├── llm_jam.py
│       ├── llm_jam_return_safe_coords.py
│       └── llm_multi_jam.py
├── diagrams
│   ├── Swarm_Squad_Abstraction_Stack.png
│   └── this_repo_qr.png
├── gen_data.py
├── notes.md
├── README.md
└── requirements.txt

6 directories, 12 files
(venv) ubuntu@ubuntu2004:/opt/CARS_sim_2_ollama$ tree -I 'venv|__pycache__|.git'
.
├── chat
│   ├── app.py
│   ├── static
│   │   └── style.css
│   └── templates
│       └── index.html
├── chroma_db
├── demos
│   └── basic_lin
│       ├── llm_jam.py
│       ├── llm_jam_return_safe_coords.py
│       └── llm_multi_jam.py
├── diagrams
│   ├── Swarm_Squad_Abstraction_Stack.png
│   └── this_repo_qr.png
├── gen_data.py
├── notes.md
├── rag
│   └── rag_store.py
├── README.md
└── requirements.txt

I would like to ensure that if not exists, chromadb fodler and chromadb data will be created and stored. I also want to smooth over the RAG functions for putting data into the rag (from the gen data) and then make sure ollama is pulling from the rag