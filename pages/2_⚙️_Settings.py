# pages/2_Settings.py — Persona prompt override management.

import os
import sys
import logging

import streamlit as st

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
try:
    import auth
except ImportError:
    st.error("Fatal: `auth.py` not found.")
    st.stop()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if not auth.check_password():
    st.stop()

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from llm_loader import load_default_prompt_text
    import gui
except ImportError as e:
    st.error(f"Import error: {e}")
    st.stop()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Inject CSS
# ---------------------------------------------------------------------------
gui.inject_chat_css()

# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------
st.markdown(
    '<div class="phd-header">'
    '  <h1 class="phd-title">Prompt Settings</h1>'
    '  <p class="phd-subtitle">View and override system prompts for each persona</p>'
    '</div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PERSONAS = ["Socrates", "Confucius", "Moderator"]
MODES = ["Philosophy", "Bio"]
FALLBACK_TEXT = "Default prompt file not found."

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
st.session_state.setdefault("prompt_overrides", {})
st.session_state.setdefault("editor_content_state", {})
st.session_state.setdefault("last_processed_key_settings", None)

# ---------------------------------------------------------------------------
# Selectors
# ---------------------------------------------------------------------------
col1, col2 = st.columns(2)
with col1:
    selected_persona = st.selectbox("Persona:", PERSONAS, key="settings_persona_select")
with col2:
    selected_mode = st.selectbox("Mode:", MODES, key="settings_mode_select")

persona_key = selected_persona.lower()
mode_key = selected_mode.lower()
selection_key = f"{persona_key}_{mode_key}"
text_area_key = f"prompt_editor_{selection_key}"

# ---------------------------------------------------------------------------
# Load editor content when selection changes
# ---------------------------------------------------------------------------
if st.session_state.last_processed_key_settings != selection_key:
    if selection_key in st.session_state.prompt_overrides:
        prompt_for_editor = st.session_state.prompt_overrides[selection_key]
        source = "User Override"
    else:
        default_prompt = load_default_prompt_text(persona_key, mode_key)
        if default_prompt is not None:
            prompt_for_editor = default_prompt
            source = "Default (from file)"
        else:
            prompt_for_editor = FALLBACK_TEXT
            source = "Default (Not Found)"

    st.session_state.editor_content_state[selection_key] = prompt_for_editor
    st.session_state.last_processed_key_settings = selection_key
    st.info(f"**{selected_persona}** ({selected_mode}) — Source: **{source}**")

# ---------------------------------------------------------------------------
# Prompt editor
# ---------------------------------------------------------------------------
st.session_state.editor_content_state.setdefault(selection_key, "")

st.text_area(
    "System Prompt:",
    value=st.session_state.editor_content_state[selection_key],
    height=300,
    key=text_area_key,
    help="Edit the prompt. Click 'Save Override' to apply changes.",
)

# ---------------------------------------------------------------------------
# Action buttons
# ---------------------------------------------------------------------------
col_a, col_b, col_c = st.columns(3)

with col_a:
    if st.button("Save Override", key=f"save_{selection_key}"):
        current_text = st.session_state.get(text_area_key, "")
        st.session_state.prompt_overrides[selection_key] = current_text
        st.session_state.editor_content_state[selection_key] = current_text
        st.toast(f"Override saved for {selected_persona} ({selected_mode}).")
        st.rerun()

with col_b:
    if st.button("Load Default", key=f"load_{selection_key}"):
        default_prompt = load_default_prompt_text(persona_key, mode_key)
        loaded = default_prompt if default_prompt is not None else FALLBACK_TEXT
        st.session_state.editor_content_state[selection_key] = loaded
        st.toast("Default prompt loaded into editor.")
        st.rerun()

with col_c:
    has_override = selection_key in st.session_state.prompt_overrides
    if st.button("Clear Override", key=f"clear_{selection_key}", disabled=not has_override):
        if has_override:
            del st.session_state.prompt_overrides[selection_key]
            default_prompt = load_default_prompt_text(persona_key, mode_key)
            st.session_state.editor_content_state[selection_key] = (
                default_prompt if default_prompt is not None else FALLBACK_TEXT
            )
            st.toast(f"Override cleared for {selected_persona} ({selected_mode}).")
            st.rerun()

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.divider()
st.caption("Changes persist for this session and affect both the main dialogue and Direct Chat.")

with st.expander("View All Overrides"):
    overrides = st.session_state.get("prompt_overrides", {})
    if overrides:
        for k, v in overrides.items():
            st.markdown(f"**{k}:** `{v[:80]}...`" if len(v) > 80 else f"**{k}:** `{v}`")
    else:
        st.caption("No overrides set.")
