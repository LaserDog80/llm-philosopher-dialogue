import os
import langchain
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from llm_loader import load_llm_config_for_persona

# --- Define Persona ---
persona_name = "moderator"

# --- Load LLM and System Prompt using the loader ---
llm, system_prompt = load_llm_config_for_persona(persona_name)

# --- Global Chain Variable ---
moderator_chain = None

if llm and system_prompt:
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "{input}")
    ])
    output_parser = StrOutputParser()
    moderator_chain = prompt | llm | output_parser
    print(f"-> Moderator chain created successfully for '{persona_name}'.")
else:
    print(f"Error: Failed to initialize Moderator chain for '{persona_name}'. Check config and loader.")
    # The moderator_chain variable remains None

# --- No __main__ block needed ---
# This script now only defines the chain when imported.
