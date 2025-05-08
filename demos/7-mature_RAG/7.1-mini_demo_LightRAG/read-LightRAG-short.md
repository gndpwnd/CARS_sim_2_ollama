it is important to note that the LightRAG Server will load the environment variables from .env into the system environment variables each time it starts. Since the LightRAG Server will prioritize the settings in the system environment variables, if you modify the .env file after starting the LightRAG Server via the command line, you need to execute source .env to make the new settings take effect.

By default, Ollama operates with a context window size of 2048 tokens, which can be adjusted to better suit your needs. 

For example, to set the context size to 8000 tokens: 
Code

ollama run llama3 --num_ctx 8000

ollama run llama3.3:70b-instruct-q5_K_M --num_ctx 8000


The LightRAG Server supports two operational modes:

    The simple and efficient Uvicorn mode:

lightrag-server

    The multiprocess Gunicorn + Uvicorn mode (production mode, not supported on Windows environments):

lightrag-gunicorn --workers 4

The .env file must be placed in the startup directory.


Here are some commonly used startup parameters:

    --host: Server listening address (default: 0.0.0.0)
    --port: Server listening port (default: 9621)
    --timeout: LLM request timeout (default: 150 seconds)
    --log-level: Logging level (default: INFO)
    --input-dir: Specifying the directory to scan for documents (default: ./inputs)


### you should run the demo code with project folder
cd LightRAG
### provide your API-KEY for OpenAI
export OPENAI_API_KEY="sk-...your_opeai_key..."
### download the demo document of "A Christmas Carol" by Charles Dickens
curl https://raw.githubusercontent.com/gusye1234/nano-graphrag/main/tests/mock_data.txt > ./book.txt
### run the demo code
python examples/lightrag_openai_demo.py



# updating ollama models locally
 - stop ollama serve on gpu, start ollama serve on vega, then pull models
 - ollama pull gemma:2b
 - ollama pull nomic-embed-text
 - then go back to ollama serve on gpus