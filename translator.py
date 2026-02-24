# Filename: translator.py

import logging
from typing import List, Dict, Any
from core.config import load_llm_config_for_persona
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

logger = logging.getLogger(__name__)

def get_translator_chain():
    """
    Loads the LLM configuration and prompt for the translator,
    then creates and returns a Langchain chain.
    """
    logger.info("Creating translator chain.")
    # The mode 'main' will correspond to 'prompts/translator_main.txt'
    llm, system_prompt = load_llm_config_for_persona("translator", mode='main')

    if llm and system_prompt:
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("user", "{conversation_log}")
            ])
            output_parser = StrOutputParser()
            chain = prompt | llm | output_parser
            logger.info("Translator chain created successfully.")
            return chain
        except Exception as e:
            logger.error(f"Error creating translator chain: {e}", exc_info=True)
            return None
    else:
        logger.error("Failed to initialize translator chain due to missing LLM or system prompt.")
        return None

def format_conversation_for_translation(messages: List[Dict[str, Any]]) -> str:
    """
    Formats the conversation history into a single string for the translator.
    """
    transcript = []
    for message in messages:
        role = message.get("role", "system").upper()
        content = message.get("content", "")
        
        # We only want to translate the actual dialogue
        if role not in ["USER", "SOCRATES", "CONFUCIUS"]:
            continue
            
        if role == "USER":
             # The initial prompt from the user
             transcript.append(f"INITIAL PROMPT: {content}")
        else:
             # The philosophers' responses
             transcript.append(f"{role}: {content}")
    
    return "\n\n".join(transcript)


def translate_conversation(messages: List[Dict[str, Any]]) -> str:
    """
    Takes a list of conversation messages, formats them, and uses an LLM
    to translate the dialogue into a more casual style.

    Args:
        messages: The list of message dictionaries from the conversation.

    Returns:
        A string containing the translated conversation.
    """
    logger.info("Beginning conversation translation process.")
    translator_chain = get_translator_chain()
    if not translator_chain:
        return "Error: The translator model could not be loaded."

    # 1. Format the conversation into a single block of text
    conversation_log = format_conversation_for_translation(messages)
    
    if not conversation_log.strip():
        logger.warning("Conversation log for translation is empty. Nothing to translate.")
        return "There was no dialogue to translate."

    # 2. Invoke the translation chain
    try:
        logger.info("Invoking translator chain...")
        translated_text = translator_chain.invoke({
            "conversation_log": conversation_log
        })
        logger.info("Translation successful.")
        return translated_text
    except Exception as e:
        logger.error(f"An error occurred during translation: {e}", exc_info=True)
        return f"An error occurred during translation: {e}"