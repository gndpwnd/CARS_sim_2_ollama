# change simulation that feeds data into the RAG to send agent x,y coordinates and an is_jammed "jammed" or "not jammed" through RAG

I have the following files, chatapp.py provides a chat interface with an llm, rag store helps with storage using RAG, and demo_rag_data simply generates RAG data for a basic demo of RAG. now I want to swap out the demo rag data with an actual simulation llm_return_safe_coords. can you make all necessary changes to chatapp, rat_store, and llm_return_safe_coords for the llm_return_safe_coords to properly send agent x,y ccoordinates and an is_jammed "jammed" or "not jammed" through RAG? Do not use classes and provide the code for all three files. I will provide the code for the three files below.


# live rag data feed

I have the following chatapp that I use to interact with an LLM in conjunction with a simple RAG python script. I also have a simulation script feeding data into the RAG so i can ask the LLM questions about it through the chat. I want to add to my chat app. To the left of the chat window, I would like a live view of all RAG data being recorded, like viewing a livestream of all data going back and forth. If the data reaches a certain amount, you can start lazy loading it. I would like the most recent data at the top of the feed, and then lazy load the rest as the user scrolls down.


I have the following code for a chat app to integrate talking to an LLM with RAG. Currently i can load all rag messages into a rag feed and be able to interact with the llm though a chat, but the logs do not update automatically every 3 second to include the most recent logs. the most recent logs are only loaded when i refresh the page.