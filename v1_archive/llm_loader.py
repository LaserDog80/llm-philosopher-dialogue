# Filename: llm_loader.py

import os
import json
import logging
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
import streamlit as st # Import streamlit to access session state

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

# --- Function to load ONLY the default prompt text ---
# Use Streamlit caching for default prompt text
@st.cache_data(ttl=3600) # Cache for 1 hour
def load_default_prompt_text(persona_name: str, mode: str) -> str | None:
    """
    Loads and returns the text content of the default prompt file for a given
    persona and mode. Returns None if the file cannot be read. Caches result.
    """
    logger.info(f"Attempting to load default prompt text for '{persona_name}' mode '{mode}'")
    # Construct prompt filename dynamically
    mode_suffix = mode.lower()
    prompt_filename = f"{persona_name}_{mode_suffix}.txt"
    # Assume prompts are in a 'prompts' subdirectory relative to this script's dir
    # Adjust if your prompts dir is elsewhere relative to where app is run
    try:
        # Try finding prompts relative to current working directory first
        cwd = os.getcwd()
        prompt_dir_path = os.path.join(cwd, DEFAULT_PROMPT_DIR)
        prompt_path = os.path.join(prompt_dir_path, prompt_filename)
        logger.debug(f"Checking for prompt at: {prompt_path}")
        if not os.path.exists(prompt_path):
             # Fallback: Try finding prompts relative to the script's directory
             script_dir = os.path.dirname(__file__) or '.'
             prompt_dir_path = os.path.join(script_dir, DEFAULT_PROMPT_DIR)
             prompt_path = os.path.join(prompt_dir_path, prompt_filename)
             logger.debug(f"Checking for prompt at fallback path: {prompt_path}")


        with open(prompt_path, "r", encoding="utf-8") as pf:
            system_prompt = pf.read().strip()
        logger.info(f"Successfully loaded default prompt text for '{persona_name}' mode '{mode}' from {prompt_path}")
        return system_prompt
    except FileNotFoundError:
        logger.error(f"Default prompt file not found for persona '{persona_name}' mode '{mode}' at expected paths.")
        return None
    except Exception as e:
        logger.error(f"Error reading default prompt file {prompt_path}: {e}.")
        return None

# --- Modified function to load LLM config AND check for prompt overrides ---
# Consider caching the LLM instance + config loading part
# Use cache_resource for non-hashable objects like LLM clients
# Key needs to include things that change the LLM object: persona_name, model params, API key info indirectly
# Caching LLM might be complex if parameters change frequently or per-persona significantly.
# For now, let's focus on caching prompts and config read.

@st.cache_data(ttl=3600)
def _load_llm_params(persona_name: str, config_path="llm_config.json") -> dict:
    """Loads and caches parameters from JSON config."""
    logger.info(f"Loading LLM params for {persona_name} from {config_path}")
    try:
        with open(config_path, "r", encoding="utf-8") as f: config = json.load(f)
    except Exception as e:
        logger.error(f"Error loading/parsing LLM config {config_path}: {e}")
        return {} # Return empty dict on failure

    persona_config = config.get(persona_name, {})
    defaults = config.get("defaults", {})
    merged = {**defaults, **persona_config}
    return merged

def load_llm_config_for_persona(persona_name: str, mode: str = 'philosophy', config_path="llm_config.json"):
    """
    Loads LLM config, loads the DEFAULT system prompt text, checks session state
    for an OVERRIDDEN prompt, and returns the LLM instance and the
    effective (default or overridden) system prompt text.

    Args:
        persona_name (str): The name of the persona section (e.g., "socrates").
        mode (str): The conversation mode (e.g., "philosophy", "bio").
        config_path (str): Path to the JSON configuration file.

    Returns:
        tuple: (ChatOpenAI instance or None, effective_system_prompt string or None)
    """
    # load_dotenv() # Called once in app.py now

    api_key = os.getenv("NEBIUS_API_KEY")
    base_url = os.getenv("NEBIUS_API_BASE")

    if not api_key or not base_url:
        logger.error("NEBIUS_API_KEY and NEBIUS_API_BASE must be set.")
        return None, None

    # --- Load LLM Parameters using cached function ---
    merged_params = _load_llm_params(persona_name, config_path)
    if not merged_params: # Handle failure in loading params
        return None, None

    # --- Load DEFAULT System Prompt Text (uses caching internally) ---
    default_system_prompt = load_default_prompt_text(persona_name, mode)
    if default_system_prompt is None:
        logger.warning(f"Using fallback prompt for '{persona_name}' mode '{mode}' due to missing/unreadable default file.")
        default_system_prompt = DEFAULT_FALLBACK_PROMPT

    # --- Check for User Override in Session State ---
    effective_system_prompt = default_system_prompt # Start with the default
    override_key = f"{persona_name}_{mode.lower()}"
    # Initialize prompt_overrides in session state if it doesn't exist
    # setdefault needed here in case Settings page hasn't run yet
    st.session_state.setdefault('prompt_overrides', {})

    if override_key in st.session_state.prompt_overrides:
        # Ensure override is not empty string, otherwise use default
        override_text = st.session_state.prompt_overrides[override_key]
        if isinstance(override_text, str) and override_text.strip():
            effective_system_prompt = override_text
            logger.info(f"Using OVERRIDDEN prompt for {override_key}")
        else:
            logger.info(f"Ignoring empty override, using DEFAULT prompt for {override_key}")
            effective_system_prompt = default_system_prompt # Fallback to default if override is empty
    else:
        logger.info(f"Using DEFAULT prompt for {override_key}")


    # --- Determine Final LLM Parameters ---
    final_params = merged_params # Use loaded params
    model_name = final_params.get("model_name", DEFAULT_MODEL)
    temperature = final_params.get("temperature", DEFAULT_TEMPERATURE)
    max_tokens = final_params.get("max_tokens", DEFAULT_MAX_TOKENS)
    top_p = final_params.get("top_p", DEFAULT_TOP_P)
    presence_penalty = final_params.get("presence_penalty", DEFAULT_PRESENCE_PENALTY)
    frequency_penalty = final_params.get("frequency_penalty", DEFAULT_FREQUENCY_PENALTY)
    request_timeout = final_params.get("request_timeout", DEFAULT_TIMEOUT)

    # --- Prepare LLM Arguments ---
    llm_kwargs = {
        "model": model_name, "api_key": api_key, "base_url": base_url,
        "request_timeout": request_timeout, "temperature": temperature,
    }
    # Only add parameters if they are not None, to allow API defaults if preferred
    if max_tokens is not None: llm_kwargs["max_tokens"] = max_tokens
    if top_p is not None: llm_kwargs["top_p"] = top_p
    # Penalties usually default to 0.0, only add if explicitly non-zero
    if presence_penalty != 0.0: llm_kwargs["presence_penalty"] = presence_penalty
    if frequency_penalty != 0.0: llm_kwargs["frequency_penalty"] = frequency_penalty

    logger.info(f"LLM '{persona_name}' (mode: {mode}): Model='{model_name}', Temp={temperature}, MaxTokens={max_tokens}, Timeout={request_timeout}")

    # --- Initialize LLM ---
    # TODO: Consider caching the LLM instance if beneficial (using st.cache_resource)
    # Cache key would need to combine relevant parts of llm_kwargs
    try:
        llm = ChatOpenAI(**llm_kwargs)
        # Return LLM and the effective prompt (default or overridden)
        return llm, effective_system_prompt
    except Exception as e:
        logger.error(f"Error initializing ChatOpenAI for {persona_name}: {e}", exc_info=True)
        logger.error("Check API key, base URL, model name, and parameters.")
        return None, None

# --- Example Usage ---
# (Keep __main__ block unchanged if needed for testing)
if __name__ == "__main__":
     # This block won't have Streamlit context (caching, session_state)
     # It will test basic loading logic without overrides/caching active
     print("Testing LLM Loader (without Streamlit session state)...")
     # Test loading default mode (philosophy)
     s_llm_p, s_prompt_p = load_llm_config_for_persona("socrates", mode='philosophy')
     if s_llm_p: print(f"\nSocrates (Philosophy) LLM OK.")
     else: print("\nSocrates (Philosophy) LLM failed.")
     print(f"Prompt loaded: '{s_prompt_p[:80]}...'")

     # Test loading default text directly
     print("\nTesting direct default prompt loading...")
     default_s_bio = load_default_prompt_text("socrates", "bio")
     if default_s_bio: print(f"Default Socrates Bio prompt fetched: '{default_s_bio[:80]}...'")
     else: print("Fetching default Socrates Bio prompt FAILED.")

     default_m_phil = load_default_prompt_text("moderator", "philosophy")
     if default_m_phil: print(f"Default Moderator Phil prompt fetched: '{default_m_phil[:80]}...'")
     else: print("Fetching default Moderator Phil prompt FAILED.")