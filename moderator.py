# Filename: moderator.py

import os
import logging
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI # Direct import might be needed
from llm_loader import load_llm_config_for_persona
from typing import Optional, Any

logger = logging.getLogger(__name__)
persona_name = "moderator"

# --- Chain Creation Function ---
def get_chain(mode: str = 'philosophy') -> Optional[Any]:
    """
    Loads the LLM configuration and prompt for the specified mode,
    then creates and returns a Langchain chain for the Moderator.

    Args:
        mode (str): The conversation mode ('philosophy', 'bio', etc.).
                  This allows the moderator's instructions to potentially
                  differ based on the overall conversation mode.

    Returns:
        A Langchain chain instance or None if creation fails.
    """
    logger.info(f"Creating Moderator chain for mode: {mode}")
    # Pass the mode to the loader - it will load moderator_philosophy.txt or moderator_bio.txt etc.
    llm, system_prompt = load_llm_config_for_persona(persona_name, mode=mode)

    if llm and system_prompt:
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("user", "{input}") # Moderator input usually comes from Director
            ])
            output_parser = StrOutputParser()
            chain = prompt | llm | output_parser
            logger.info(f"Moderator chain created successfully for mode '{mode}'.")
            return chain
        except Exception as e:
            logger.error(f"Error creating Moderator chain for mode '{mode}': {e}", exc_info=True)
            return None
    else:
        logger.error(f"Failed to initialize Moderator chain for mode '{mode}' due to missing LLM or system prompt.")
        return None

# --- No automatic chain creation on import ---

# Example Test (Optional)
if __name__ == "__main__":
    print("Testing Moderator chain creation...")
    philosophy_chain = get_chain(mode='philosophy')
    if philosophy_chain:
        print("Philosophy chain created.")
    else:
        print("Philosophy chain creation FAILED.")

    bio_chain = get_chain(mode='bio')
    if bio_chain:
        print("Bio chain created.")
    else:
        print("Bio chain creation FAILED.")