# core/persona.py — Single chain factory replacing socrates.py, confucius.py, moderator.py.

import logging
from typing import Optional, Any, Dict

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser

from core.config import load_llm_config_for_persona

logger = logging.getLogger(__name__)


def create_chain(
    persona_id: str,
    mode: str = "philosophy",
    prompt_overrides: Optional[Dict[str, str]] = None,
) -> Optional[Any]:
    """
    Create a LangChain chain for any persona/mode combination.

    This single factory replaces the three identical files
    (socrates.py, confucius.py, moderator.py).

    Args:
        persona_id: Lowercase persona name (e.g. "socrates", "confucius", "moderator").
        mode: Conversation mode (e.g. "philosophy", "bio").
        prompt_overrides: Optional dict of override prompts keyed by "persona_mode".

    Returns:
        A LangChain chain, or None on failure.
    """
    logger.info(f"Creating chain for '{persona_id}' mode '{mode}'")
    llm, system_prompt = load_llm_config_for_persona(
        persona_id, mode=mode, prompt_overrides=prompt_overrides
    )

    if not llm or not system_prompt:
        logger.error(f"Failed to load LLM/prompt for '{persona_id}' mode '{mode}'")
        return None

    try:
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("user", "{input}"),
        ])
        chain = prompt_template | llm | StrOutputParser()
        logger.info(f"Chain created for '{persona_id}' mode '{mode}'")
        return chain
    except Exception as e:
        logger.error(f"Error creating chain for '{persona_id}' mode '{mode}': {e}", exc_info=True)
        return None
