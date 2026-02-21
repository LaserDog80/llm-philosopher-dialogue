# llm_loader.py — Backward-compatible wrapper around core.config.
#
# The pages (Direct Chat, Settings) import from here. This thin wrapper
# delegates to core.config while still supporting Streamlit session-state
# prompt overrides that the pages rely on.

import logging
import streamlit as st

from core.config import (
    load_default_prompt_text as _core_load_default_prompt_text,
    load_llm_config_for_persona as _core_load_llm_config_for_persona,
)

logger = logging.getLogger(__name__)


def load_default_prompt_text(persona_name: str, mode: str):
    """Load default prompt text (delegates to core.config)."""
    return _core_load_default_prompt_text(persona_name, mode)


def load_llm_config_for_persona(persona_name: str, mode: str = "philosophy", config_path: str = "llm_config.json"):
    """
    Load LLM config with session-state prompt override support.

    This wrapper reads prompt_overrides from st.session_state so that the
    Settings page can inject custom prompts that take effect immediately.
    """
    st.session_state.setdefault("prompt_overrides", {})
    overrides = dict(st.session_state.prompt_overrides)
    return _core_load_llm_config_for_persona(
        persona_name, mode=mode, config_path=config_path, prompt_overrides=overrides
    )
