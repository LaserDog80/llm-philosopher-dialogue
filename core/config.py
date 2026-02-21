# core/config.py — LLM configuration loading with zero Streamlit dependency.

import os
import json
import logging
from functools import lru_cache
from typing import Optional, Tuple, Any, Dict

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "meta-llama/Meta-Llama-3.1-70B-Instruct"
DEFAULT_TIMEOUT = 60
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = None
DEFAULT_TOP_P = None
DEFAULT_PRESENCE_PENALTY = 0.0
DEFAULT_FREQUENCY_PENALTY = 0.0
DEFAULT_PROMPT_DIR = "prompts"
DEFAULT_FALLBACK_PROMPT = "You are a helpful AI assistant."


@lru_cache(maxsize=32)
def load_default_prompt_text(persona_name: str, mode: str) -> Optional[str]:
    """Load the default prompt text file for a persona/mode combination."""
    mode_suffix = mode.lower()
    prompt_filename = f"{persona_name}_{mode_suffix}.txt"

    # Try CWD first, then script-relative
    for base in [os.getcwd(), os.path.dirname(os.path.dirname(__file__)) or '.']:
        prompt_path = os.path.join(base, DEFAULT_PROMPT_DIR, prompt_filename)
        if os.path.exists(prompt_path):
            try:
                with open(prompt_path, "r", encoding="utf-8") as f:
                    text = f.read().strip()
                logger.info(f"Loaded prompt for '{persona_name}' mode '{mode}' from {prompt_path}")
                return text
            except Exception as e:
                logger.error(f"Error reading prompt file {prompt_path}: {e}")
                return None

    logger.error(f"Prompt file not found for '{persona_name}' mode '{mode}'")
    return None


@lru_cache(maxsize=16)
def load_llm_params(persona_name: str, config_path: str = "llm_config.json") -> Dict:
    """Load and merge LLM parameters from JSON config."""
    try:
        # Try CWD first, then script-relative
        for base in [os.getcwd(), os.path.dirname(os.path.dirname(__file__)) or '.']:
            full_path = os.path.join(base, config_path)
            if os.path.exists(full_path):
                with open(full_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                defaults = config.get("defaults", {})
                persona_config = config.get(persona_name, {})
                return {**defaults, **persona_config}
        logger.error(f"Config file not found: {config_path}")
        return {}
    except Exception as e:
        logger.error(f"Error loading LLM config: {e}")
        return {}


def load_llm_config_for_persona(
    persona_name: str,
    mode: str = "philosophy",
    config_path: str = "llm_config.json",
    prompt_overrides: Optional[Dict[str, str]] = None,
) -> Tuple[Optional[Any], Optional[str]]:
    """
    Load LLM instance and effective prompt for a persona.

    Returns (ChatOpenAI instance, effective_system_prompt) or (None, None).
    """
    load_dotenv()

    api_key = os.getenv("NEBIUS_API_KEY")
    base_url = os.getenv("NEBIUS_API_BASE")
    if not api_key or not base_url:
        logger.error("NEBIUS_API_KEY and NEBIUS_API_BASE must be set.")
        return None, None

    params = load_llm_params(persona_name, config_path)
    if not params:
        return None, None

    # Load prompt
    default_prompt = load_default_prompt_text(persona_name, mode)
    if default_prompt is None:
        logger.warning(f"Using fallback prompt for '{persona_name}' mode '{mode}'")
        default_prompt = DEFAULT_FALLBACK_PROMPT

    # Check overrides
    effective_prompt = default_prompt
    if prompt_overrides:
        override_key = f"{persona_name}_{mode.lower()}"
        override_text = prompt_overrides.get(override_key, "")
        if isinstance(override_text, str) and override_text.strip():
            effective_prompt = override_text
            logger.info(f"Using overridden prompt for {override_key}")

    # Build LLM kwargs
    model_name = params.get("model_name", DEFAULT_MODEL)
    llm_kwargs = {
        "model": model_name,
        "api_key": api_key,
        "base_url": base_url,
        "request_timeout": params.get("request_timeout", DEFAULT_TIMEOUT),
        "temperature": params.get("temperature", DEFAULT_TEMPERATURE),
    }
    max_tokens = params.get("max_tokens", DEFAULT_MAX_TOKENS)
    if max_tokens is not None:
        llm_kwargs["max_tokens"] = max_tokens
    top_p = params.get("top_p", DEFAULT_TOP_P)
    if top_p is not None:
        llm_kwargs["top_p"] = top_p
    pp = params.get("presence_penalty", DEFAULT_PRESENCE_PENALTY)
    if pp != 0.0:
        llm_kwargs["presence_penalty"] = pp
    fp = params.get("frequency_penalty", DEFAULT_FREQUENCY_PENALTY)
    if fp != 0.0:
        llm_kwargs["frequency_penalty"] = fp

    try:
        llm = ChatOpenAI(**llm_kwargs)
        return llm, effective_prompt
    except Exception as e:
        logger.error(f"Error initializing ChatOpenAI for {persona_name}: {e}", exc_info=True)
        return None, None
