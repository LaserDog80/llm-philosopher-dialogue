# Filename: socrates.py

import os
import logging
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI # Direct import might be needed if type hinting chain output
from llm_loader import load_llm_config_for_persona
from typing import Optional, Any # For type hinting

logger = logging.getLogger(__name__)
persona_name = "socrates"

# --- Chain Creation Function ---
def get_chain(mode: str = 'philosophy') -> Optional[Any]:
    """
    Loads the LLM configuration and prompt for the specified mode,
    then creates and returns a Langchain chain for Socrates.

    Args:
        mode (str): The conversation mode ('philosophy', 'bio', etc.).

    Returns:
        A Langchain chain instance or None if creation fails.
    """
    logger.info(f"Creating Socrates chain for mode: {mode}")
    llm, system_prompt = load_llm_config_for_persona(persona_name, mode=mode)

    if llm and system_prompt:
        try:
            # Define prompt template using the loaded system prompt
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("user", "{input}")
            ])
            output_parser = StrOutputParser()
            chain = prompt | llm | output_parser
            logger.info(f"Socrates chain created successfully for mode '{mode}'.")
            return chain
        except Exception as e:
            logger.error(f"Error creating Socrates chain for mode '{mode}': {e}", exc_info=True)
            return None
    else:
        logger.error(f"Failed to initialize Socrates chain for mode '{mode}' due to missing LLM or system prompt.")
        return None

# --- No automatic chain creation on import ---
# The chain is now created on demand by calling get_chain(mode)

# Example Test (Optional)
if __name__ == "__main__":
    print("Testing Socrates chain creation...")
    philosophy_chain = get_chain(mode='philosophy')
    if philosophy_chain:
        print("Philosophy chain created.")
        # test_p = philosophy_chain.invoke({"input": "What is virtue?"})
        # print(f"Test response (Philosophy): {test_p}")
    else:
        print("Philosophy chain creation FAILED.")

    bio_chain = get_chain(mode='bio')
    if bio_chain:
        print("Bio chain created.")
        # test_b = bio_chain.invoke({"input": "Tell me about your trial."})
        # print(f"Test response (Bio): {test_b}")
    else:
        print("Bio chain creation FAILED.")