An AI is simply a matrix multiplication program that is designed to make guesses. RAG allows for guesses to be more informed without needing to run a bigger model (the amount of data retrival and baseline model context will change this need so the original claim is a generality). An MCP allows an LLM to "interact with the real world" through function calls.

An llm in simply an AI for language, so it is matrix multiplication that is good at guessing words. you don't use an LLM to perform mathematical operations or anything else outside of language processing, which is why you have an MCP and then use a RAG to make better and more detailed function calls.

llm is to slow for path finding - when doing a jammed enviornment mission, have a path funding alorigthm to do low level manuevers but also allow llm injection, the llm is a massive performance bottleneck for path finding. have llm choose what movement functions and what pathfinding functions to run, or given data give new coordinates.


k models, km vs ks


k_s models for whatever reason are a little slower than k_m models. k models are k-quant models and generally have less perplexity loss relative to size. A q4_K_M model will have much less perplexity loss than a q4_0 or even a q4_1 model.

q4_k_m vs q4_k_s

k_m vs k_s vs k_l - level of optimization of quantization of model - the idea is to reduce the size of the model without losing quality/precision - k_l is the largest "least optimized for size" and k_s is the small "more optimized for siz". "more optimized" does not mean better for what you are doing though.


When you run two different python files (or any files) at the same time, they become two separate processes. Different processes do not share the same memory space. You need to build your data storage system and context retrival to bridge this gap and allow the LLM to be informed about what is occurring in different memory spaces.
