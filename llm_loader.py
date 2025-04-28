import os
import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# Default values (used if not found in config file or if file is missing/invalid)
DEFAULT_MODEL = "meta-llama/Meta-Llama-3.1-70B-Instruct" # Fallback model
DEFAULT_TIMEOUT = 60
DEFAULT_TEMPERATURE = 0.7
DEFAULT_SYSTEM_PROMPT = "You are a helpful AI assistant."
DEFAULT_MAX_TOKENS = None
DEFAULT_TOP_P = None
DEFAULT_PRESENCE_PENALTY = 0.0
DEFAULT_FREQUENCY_PENALTY = 0.0

def load_llm_config_for_persona(persona_name, config_path="llm_config.json"):
    """
    Loads configuration for a specific persona from .env and llm_config.json,
    initializes and returns a ChatOpenAI instance and the system prompt.

    Args:
        persona_name (str): The name of the persona section (e.g., "socrates").
        config_path (str): Path to the JSON configuration file.

    Returns:
        tuple: (ChatOpenAI instance or None, system_prompt string or None)
    """
    load_dotenv() # Load .env file for API keys

    # --- Get Credentials ---
    api_key = os.getenv("NEBIUS_API_KEY")
    base_url = os.getenv("NEBIUS_API_BASE")

    if not api_key or not base_url:
        print("Error: NEBIUS_API_KEY and NEBIUS_API_BASE must be set in the .env file.")
        return None, None # Return None for both LLM and prompt

    # --- Load Parameters from JSON Config ---
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    persona_config = config.get(persona_name, {})
    # Load prompt from file if specified
    prompt_file = persona_config.get("prompt_file")
    if prompt_file:
        prompt_path = os.path.join(os.path.dirname(config_path), prompt_file)
        with open(prompt_path, "r", encoding="utf-8") as pf:
            persona_config["system_prompt"] = pf.read().strip()
    # Remove prompt_file key to avoid confusion downstream
    persona_config.pop("prompt_file", None)
    # Merge with defaults
    defaults = config.get("defaults", {})
    merged = {**defaults, **persona_config}

    # --- Determine Final Parameters (Persona overrides Default) ---
    final_params = merged

    # Extract parameters using .get() with fallback defaults if needed
    model_name = final_params.get("model_name") or DEFAULT_MODEL
    temperature = final_params.get("temperature", DEFAULT_TEMPERATURE)
    max_tokens = final_params.get("max_tokens", DEFAULT_MAX_TOKENS)
    top_p = final_params.get("top_p", DEFAULT_TOP_P)
    presence_penalty = final_params.get("presence_penalty", DEFAULT_PRESENCE_PENALTY)
    frequency_penalty = final_params.get("frequency_penalty", DEFAULT_FREQUENCY_PENALTY)
    request_timeout = final_params.get("request_timeout", DEFAULT_TIMEOUT)
    system_prompt = final_params.get("system_prompt", DEFAULT_SYSTEM_PROMPT) # Get system prompt

    # --- Prepare LLM Arguments ---
    # Filter out None values for optional parameters so they don't override API defaults
    llm_kwargs = {
        "model": model_name,
        "api_key": api_key,
        "base_url": base_url,
        "request_timeout": request_timeout,
        "temperature": temperature, # Temperature always has a value (from config or default)
    }
    if max_tokens is not None:
        llm_kwargs["max_tokens"] = max_tokens
    if top_p is not None:
        llm_kwargs["top_p"] = top_p
    if presence_penalty is not None:
        llm_kwargs["presence_penalty"] = presence_penalty
    if frequency_penalty is not None:
        llm_kwargs["frequency_penalty"] = frequency_penalty

    print(f"Initializing LLM for '{persona_name}' with: Model='{model_name}', Temp={temperature}, MaxTokens={max_tokens}, TopP={top_p}, PresencePenalty={presence_penalty}, FrequencyPenalty={frequency_penalty}, Timeout={request_timeout}")
    # Add prints for other parameters if desired

    # --- Initialize LLM ---
    try:
        llm = ChatOpenAI(**llm_kwargs)
        return llm, system_prompt # Return both the LLM and the prompt
    except Exception as e:
        print(f"Error initializing ChatOpenAI: {e}")
        print("Check API key, base URL, model name, and parameters.")
        return None, None

# Example usage (optional, for testing llm_loader.py directly)
if __name__ == "__main__":
    print("Testing LLM Loader...")
    socrates_llm, socrates_prompt = load_llm_config_for_persona("socrates")
    if socrates_llm:
        print("\nSocrates LLM Instance created successfully.")
        print(f"Socrates System Prompt: '{socrates_prompt[:50]}...'") # Print start of prompt
    else:
        print("\nSocrates LLM Instance creation failed.")

    confucius_llm, confucius_prompt = load_llm_config_for_persona("confucius")
    if confucius_llm:
        print("\nConfucius LLM Instance created successfully.")
        print(f"Confucius System Prompt: '{confucius_prompt[:50]}...'") # Print start of prompt
    else:
        print("\nConfucius LLM Instance creation failed.")

    # Test loading a non-existent persona
    print("\nTesting non-existent persona...")
    _, default_prompt = load_llm_config_for_persona("non_existent_persona")
    print(f"Default prompt for non-existent: '{default_prompt[:50]}...'")