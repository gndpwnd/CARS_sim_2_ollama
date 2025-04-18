# RAG Integration with LLM and Agent Jamming Simulation


### Run the simulation

change into the directory

```
cd demos/rag_llm_basic_lin_jam
```

start the database

```
docker compose up -d
```

start the simulation to feed data to the database

```
python3 4-llm_return_to_safe_coords.py
```

start the chatapp to query llm and use rag data

```
python3 chatapp.py
```

### Stop the simulation

stop the database and remove all containers and networks created by the docker compose file

```
docker compose down -v
```

or just stop the database

```
docker compose down
```


change permissions on pgdata directory so user can use it or remove it

```
sudo chown -R $USER:$USER ./pgdata
```

remove pgdata directory

```
rm -rf ./pgdata
```
