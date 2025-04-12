# change simulation that feeds data into the RAG to send agent x,y coordinates and an is_jammed "jammed" or "not jammed" through RAG

I have the following files, chatapp.py provides a chat interface with an llm, rag store helps with storage using RAG, and demo_rag_data simply generates RAG data for a basic demo of RAG. now I want to swap out the demo rag data with an actual simulation llm_return_safe_coords. can you make all necessary changes to chatapp, rag_store, and llm_return_safe_coords for the llm_return_safe_coords to properly send agent x,y ccoordinates and an is_jammed "jammed" or "not jammed" through RAG? Do not use classes and provide the code for all three files. I will provide the code for the three files below.


# live rag data feed

I have the following chatapp that I use to interact with an LLM in conjunction with a simple RAG python script. I also have a simulation script feeding data into the RAG so i can ask the LLM questions about it through the chat. I want to add to my chat app. To the left of the chat window, I would like a live view of all RAG data being recorded, like viewing a livestream of all data going back and forth. If the data reaches a certain amount, you can start lazy loading it. I would like the most recent data at the top of the feed, and then lazy load the rest as the user scrolls down.



# current - impement RAG on simulation and make sure logs auto update in RAG feed

I have the following script that is a simulation. i want to incoporate RAG functionality so that agent information is logged into RAG, i want to setup RAG_UPDATE_FREQUENCY = 5 so that every 5 messages, you run a function trigger agent log, and then have agent log function use the following rag_store script (a script that interacts with rag imported to the simulation)


I have the following chat app to interact with llm and corresponding RAG data, I am trying to get the RAG feed to automatically update to show logs every few seconds. the rag feed updates when i refresh the page, but not by itself while i am chatting with the llm. I am able to see logs be populated, but not logs that are new since refreshing the page. please factor in these changes.


