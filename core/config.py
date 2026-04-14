# core/config.py — LLM configuration loading with zero Streamlit dependency.

import os
import json
import logging
from functools import lru_cache
from typing import Optional, Tuple, Any, Dict

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from core.registry import get_philosopher

logger = logging.getLogger(__name__)

# Load .env once at module import time, not on every persona config load
load_dotenv()

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
    """Load the default prompt text file for a persona/mode combination.

    Falls back to the ``philosophy`` prompt if the requested mode-specific file
    is missing — this lets new modes (e.g. ``story``) reuse existing prompts
    for personas that don't yet have a dedicated file.
    """
    mode_suffix = mode.lower()
    candidate_modes = [mode_suffix]
    if mode_suffix != "philosophy":
        candidate_modes.append("philosophy")

    for m in candidate_modes:
        prompt_filename = f"{persona_name}_{m}.txt"
        for base in [os.getcwd(), os.path.dirname(os.path.dirname(__file__)) or '.']:
            prompt_path = os.path.join(base, DEFAULT_PROMPT_DIR, prompt_filename)
            if os.path.exists(prompt_path):
                try:
                    with open(prompt_path, "r", encoding="utf-8") as f:
                        text = f.read().strip()
                    if m != mode_suffix:
                        logger.info(
                            f"Prompt for '{persona_name}' mode '{mode}' missing; "
                            f"fell back to '{m}' ({prompt_path})."
                        )
                    else:
                        logger.info(f"Loaded prompt for '{persona_name}' mode '{mode}' from {prompt_path}")
                    return text
                except Exception as e:
                    logger.error(f"Error reading prompt file {prompt_path}: {e}")
                    return None

    logger.error(f"Prompt file not found for '{persona_name}' mode '{mode}' (tried philosophy fallback)")
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


def _tokens_to_sentence_range(max_tokens: int) -> str:
    """Derive a sentence range from a max_tokens value.

    This is the single source of truth for response length — the verbosity
    slider sets max_tokens and this function translates it into a sentence
    count for the system prompt.
    """
    if max_tokens <= 150:
        return "1"
    elif max_tokens <= 250:
        return "1-2"
    elif max_tokens <= 350:
        return "2-3"
    elif max_tokens <= 500:
        return "3-5"
    elif max_tokens <= 650:
        return "4-6"
    else:
        return "5-8"


def load_llm_config_for_persona(
    persona_name: str,
    mode: str = "philosophy",
    config_path: str = "llm_config.json",
    prompt_overrides: Optional[Dict[str, str]] = None,
    max_tokens_override: Optional[int] = None,
    personality_notes: Optional[str] = None,
    suppress_sentence_range: bool = False,
) -> Tuple[Optional[Any], Optional[str]]:
    """
    Load LLM instance and effective prompt for a persona.

    Returns (ChatOpenAI instance, effective_system_prompt) or (None, None).
    """
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

    # Inject user personality notes BEFORE voice directives so they sit close
    # to the base prompt and carry more weight.  Placed here, even gentle notes
    # like "be cheerful" won't be drowned out by the voice profile examples.
    if personality_notes and personality_notes.strip():
        effective_prompt += (
            f"\n\n--- USER CHARACTER NOTES (HIGHEST PRIORITY) ---\n"
            f"The user has requested the following adjustments to your character.\n"
            f"These OVERRIDE your default speaking style and voice. "
            f"You MUST follow them in every response, even if they conflict "
            f"with the personality description above.\n"
            f">>> {personality_notes.strip()} <<<\n"
        )

    # Append voice directives from philosopher registry.
    # The sentence range is derived from max_tokens (set by the verbosity slider)
    # — this is the single source of truth for response length.
    effective_max_tokens = max_tokens_override or params.get("max_tokens", DEFAULT_MAX_TOKENS)
    pcfg = get_philosopher(persona_name)
    if pcfg and pcfg.voice_profile:
        vp = pcfg.voice_profile
        directives = "\n\n--- VOICE DIRECTIVES ---\n"
        if effective_max_tokens and not suppress_sentence_range:
            sentence_range = _tokens_to_sentence_range(effective_max_tokens)
            directives += f"Respond in {sentence_range} sentences.\n"
        if vp.get("style_keywords"):
            directives += f"Style: {', '.join(vp['style_keywords'])}.\n"
        if vp.get("personality_summary"):
            directives += f"Personality: {vp['personality_summary']}\n"
        if vp.get("example_utterances"):
            directives += "Speak like these examples (adapt these to user character notes if provided):\n"
            for ex in vp["example_utterances"]:
                directives += f'- "{ex}"\n'
        effective_prompt += directives

    # Build LLM kwargs
    model_name = params.get("model_name", DEFAULT_MODEL)
    llm_kwargs = {
        "model": model_name,
        "api_key": api_key,
        "base_url": base_url,
        "request_timeout": params.get("request_timeout", DEFAULT_TIMEOUT),
        "temperature": params.get("temperature", DEFAULT_TEMPERATURE),
    }
    max_tokens = max_tokens_override or params.get("max_tokens", DEFAULT_MAX_TOKENS)
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
