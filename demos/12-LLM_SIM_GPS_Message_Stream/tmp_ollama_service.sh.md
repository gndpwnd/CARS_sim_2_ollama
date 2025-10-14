i want to do the ssh jump and command automation, similare to the following:


ssh nelsg10@vegaln1.erau.edu "ssh nelsg10@gpu02 'OLLAMA_HOST=127.0.0.1:11435 ollama serve & sleep 3; ps aux | grep ollama'"


but i want todo the following where i can run it from my local machin (i have already setup ssh keys and can ssh jump automatically)

first command series that i want to make a oneliner and more streamlined:

ssh nelsg10@vegaln1.erau.edu
ssh nelsg10@gpu02
- check if ollama is already running on port 11435
- if not 
OLLAMA_HOST=127.0.0.1:11435 ollama serve &
ps aux | grep ollama
return to local machine

second command to turn into a oneliner

ssh -L 11434:127.0.0.1:11435 -J nelsg10@vegaln1.erau.edu nelsg10@gpu02
OLLAMA_HOST=127.0.0.1:11435 ollama list
OLLAMA_HOST=127.0.0.1:11435 ollama run llama3:8b (i don't know how to background this
return to local machine

or would it be better to have a small bash script on my local machine so that when run with no arguments, it checks if ollama on port 11435 is running, if not it starts it, then checks if model="llama3:8b" is running, if not starts it

- if a argument for a different model (--model) is given to the bash script, then run that model, if the model does not exist on the machine, which can be checked with ollama list, then pull the model:

      - you have to stop ollama on the gpu, start ollama on vega, pull the model, it will be saved to my user's directory and accessible from the gpu, then transition to the gpu, start the ollam service, then the ollama list should inlucde the new model.


- if an argument to stop everything or --stop is given, then stop the model instance, find it through pgrep and use my username to know i am running it as well, then also kill the ollama service. 


- i also want to run the script with --status to see all information, if ollama serve is running, what port it is on, ollama list output, and if an ollama model is running


then also as part of startup and shutdown, i want to have the ssh jump all the way from my local machine from the gpu, and forward port 11435 on the gpu to 11434 on my local machine 


these are the commands i normally use:

Terminal #2

ssh nelsg10@vegaln1.erau.edu
 
ssh nelsg10@gpu02
OLLAMA_HOST=127.0.0.1:11435 ollama serve &
ps aux | grep ollama
kill <PID>

Terminal #3

ssh -L 11434:127.0.0.1:11435 -J nelsg10@vegaln1.erau.edu nelsg10@gpu02
OLLAMA_HOST=127.0.0.1:11435 ollama list
OLLAMA_HOST=127.0.0.1:11435 ollama run llama3.3:70b-instruct-q5_K_M




I would like to be able to manage multiple models. is there a way to, when running status check, see the model runners and classify each model by a number, like the first model is [1] and the second is [2], then if running --stop [1], it will stop the first model. this way numbers can change, but if --stop [x] is run right after a status check, you should have numbers that line up and correspond to the model accurately, i would like a list during status like:

[1] gemma2:2b

[2] llama3:8b

etc... but then when i run --stop by itself, it will stop everything