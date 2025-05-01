# Filename: llm_loader.py

import os
import json
import logging
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# Configure logging for the loader module
logging.basicConfig(level=logging.INFO, format='%(asctime)s - LOADER - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Default values
DEFAULT_MODEL = "meta-llama/Meta-Llama-3.1-70B-Instruct"
DEFAULT_TIMEOUT = 60
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = None
DEFAULT_TOP_P = None
DEFAULT_PRESENCE_PENALTY = 0.0
DEFAULT_FREQUENCY_PENALTY = 0.0
DEFAULT_PROMPT_DIR = "prompts"
DEFAULT_FALLBACK_PROMPT = "You are a helpful AI assistant." # Fallback if specific prompt file is missing


def load_llm_config_for_persona(persona_name: str, mode: str = 'philosophy', config_path="llm_config.json"):
    """
    Loads configuration for a specific persona and mode, constructs the
    prompt filename dynamically, initializes and returns a ChatOpenAI instance
    and the system prompt text.

    Args:
        persona_name (str): The name of the persona section (e.g., "socrates").
        mode (str): The conversation mode (e.g., "philosophy", "bio"). Used to find the prompt file.
        config_path (str): Path to the JSON configuration file.

    Returns:
        tuple: (ChatOpenAI instance or None, system_prompt string or None)
    """
    load_dotenv() # Load .env file for API keys

    api_key = os.getenv("NEBIUS_API_KEY")
    base_url = os.getenv("NEBIUS_API_BASE")

    if not api_key or not base_url:
        logger.error("NEBIUS_API_KEY and NEBIUS_API_BASE must be set in the .env file.")
        return None, None

    # --- Load Parameters from JSON Config ---
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        logger.error(f"LLM config file not found at {config_path}. Cannot load persona settings.")
        return None, None
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {config_path}: {e}")
        return None, None

    persona_config = config.get(persona_name, {})
    defaults = config.get("defaults", {})
    # Note: We ignore "prompt_file" in config now, filename is constructed dynamically
    merged = {**defaults, **persona_config}

    # --- Construct Prompt Filename Dynamically ---
    # Use lowercase mode consistent with st.radio options mapping
    mode_suffix = mode.lower() # e.g., 'philosophy', 'bio'
    prompt_filename = f"{persona_name}_{mode_suffix}.txt"
    # Assume prompts are in a 'prompts' subdirectory relative to the config file
    prompt_dir = os.path.join(os.path.dirname(config_path) or '.', DEFAULT_PROMPT_DIR)
    prompt_path = os.path.join(prompt_dir, prompt_filename)

    system_prompt = None
    try:
        with open(prompt_path, "r", encoding="utf-8") as pf:
            system_prompt = pf.read().strip()
        logger.info(f"Successfully loaded prompt for '{persona_name}' in mode '{mode}' from {prompt_path}")
    except FileNotFoundError:
        logger.error(f"Prompt file not found for persona '{persona_name}' in mode '{mode}' at: {prompt_path}. Using fallback prompt.")
        system_prompt = DEFAULT_FALLBACK_PROMPT
    except Exception as e:
        logger.error(f"Error reading prompt file {prompt_path}: {e}. Using fallback prompt.")
        system_prompt = DEFAULT_FALLBACK_PROMPT


    # --- Determine Final LLM Parameters ---
    final_params = merged
    model_name = final_params.get("model_name", DEFAULT_MODEL)
    temperature = final_params.get("temperature", DEFAULT_TEMPERATURE)
    max_tokens = final_params.get("max_tokens", DEFAULT_MAX_TOKENS)
    top_p = final_params.get("top_p", DEFAULT_TOP_P)
    presence_penalty = final_params.get("presence_penalty", DEFAULT_PRESENCE_PENALTY)
    frequency_penalty = final_params.get("frequency_penalty", DEFAULT_FREQUENCY_PENALTY)
    request_timeout = final_params.get("request_timeout", DEFAULT_TIMEOUT)

    # --- Prepare LLM Arguments ---
    llm_kwargs = {
        "model": model_name,
        "api_key": api_key,
        "base_url": base_url,
        "request_timeout": request_timeout,
        "temperature": temperature,
    }
    if max_tokens is not None: llm_kwargs["max_tokens"] = max_tokens
    if top_p is not None: llm_kwargs["top_p"] = top_p
    # Add penalties only if they are explicitly set and not None/0? Check API behavior.
    # Assuming OpenAI API defaults if not provided or 0.0
    if presence_penalty != 0.0: llm_kwargs["presence_penalty"] = presence_penalty
    if frequency_penalty != 0.0: llm_kwargs["frequency_penalty"] = frequency_penalty

    logger.info(f"LLM '{persona_name}' (mode: {mode}): Model='{model_name}', Temp={temperature}, MaxTokens={max_tokens}, Timeout={request_timeout}")

    # --- Initialize LLM ---
    try:
        llm = ChatOpenAI(**llm_kwargs)
        return llm, system_prompt # Return LLM and the loaded prompt text
    except Exception as e:
        logger.error(f"Error initializing ChatOpenAI for {persona_name}: {e}", exc_info=True)
        logger.error("Check API key, base URL, model name, and parameters.")
        return None, None

# Example usage (optional, for testing llm_loader.py directly)
if __name__ == "__main__":
    print("Testing LLM Loader...")
    # Test loading default mode (philosophy)
    socrates_llm_p, socrates_prompt_p = load_llm_config_for_persona("socrates", mode='philosophy')
    if socrates_llm_p:
        print(f"\nSocrates (Philosophy) LLM OK. Prompt start: '{socrates_prompt_p[:60]}...'")
    else: print("\nSocrates (Philosophy) LLM failed.")

    # Test loading bio mode
    socrates_llm_b, socrates_prompt_b = load_llm_config_for_persona("socrates", mode='bio')
    if socrates_llm_b:
         print(f"\nSocrates (Bio) LLM OK. Prompt start: '{socrates_prompt_b[:60]}...'")
    else: print("\nSocrates (Bio) LLM failed.")

    # Test fallback
    print("\nTesting non-existent persona/mode fallback...")
    _, fallback_prompt = load_llm_config_for_persona("no_such_persona", mode='philosophy')
    print(f"Fallback prompt received: '{fallback_prompt}'")
    _, fallback_prompt_m = load_llm_config_for_persona("socrates", mode='no_such_mode')
    print(f"Fallback prompt received for missing mode: '{fallback_prompt_m}'")