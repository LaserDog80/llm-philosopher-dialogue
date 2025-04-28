import os
import langchain
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from llm_loader import load_llm_config_for_persona # Assuming llm_loader.py is in the same directory

# --- Define Persona ---
persona_name = "confucius"

# --- Load LLM and System Prompt using the loader ---
# This runs when the module is imported
llm, system_prompt = load_llm_config_for_persona(persona_name)

# --- Global Chain Variable ---
# Initialize chain as None in case loading fails
confucius_chain = None

if llm and system_prompt:
    # Prompt Template: Uses the system prompt loaded from config
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "{input}")
    ])

    output_parser = StrOutputParser()

    # Create the chain and make it accessible when imported
    confucius_chain = prompt | llm | output_parser
    print(f"-> Confucius chain created successfully for '{persona_name}'.")
else:
    # This message will appear when importing if loading failed
    print(f"Error: Failed to initialize Confucius chain for '{persona_name}'. Check config and loader.")
    # The confucius_chain variable remains None

# --- No __main__ block needed ---
# This script now only defines the chain when imported.