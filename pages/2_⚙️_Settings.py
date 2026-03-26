# pages/2_Settings.py — Persona prompt override management.
# UI: "Warm Study" theme.

import os
import sys
import logging

import streamlit as st

# Bridge Streamlit Cloud secrets into os.environ
try:
    for _key in ("NEBIUS_API_KEY", "NEBIUS_API_BASE"):
        if _key in st.secrets and _key not in os.environ:
            os.environ[_key] = st.secrets[_key]
except Exception:
    pass

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
    from core.registry import get_display_names, get_philosopher
    from core.config import load_llm_params
    import gui
except ImportError as e:
    st.error(f"Import error: {e}")
    st.stop()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Inject Warm Study CSS
# ---------------------------------------------------------------------------
gui.inject_chat_css()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(
    '<div class="ws-header-bar">'
    '  <div class="ws-header-left">'
    '    <div class="ws-header-icon">&#x2699;</div>'
    '    <div>'
    '      <h1 class="ws-title">Prompt Settings</h1>'
    '      <p class="ws-subtitle">View and override system prompts for each persona</p>'
    '    </div>'
    '  </div>'
    '</div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PERSONAS = get_display_names() + ["Moderator"]
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
    if st.button("Save Override", key=f"save_{selection_key}", icon=":material/save:"):
        current_text = st.session_state.get(text_area_key, "")
        st.session_state.prompt_overrides[selection_key] = current_text
        st.session_state.editor_content_state[selection_key] = current_text
        st.toast(f"Override saved for {selected_persona} ({selected_mode}).")
        st.rerun()

with col_b:
    if st.button("Load Default", key=f"load_{selection_key}", icon=":material/restart_alt:"):
        default_prompt = load_default_prompt_text(persona_key, mode_key)
        loaded = default_prompt if default_prompt is not None else FALLBACK_TEXT
        st.session_state.editor_content_state[selection_key] = loaded
        st.toast("Default prompt loaded into editor.")
        st.rerun()

with col_c:
    has_override = selection_key in st.session_state.prompt_overrides
    if st.button("Clear Override", key=f"clear_{selection_key}", disabled=not has_override, icon=":material/delete:"):
        if has_override:
            del st.session_state.prompt_overrides[selection_key]
            default_prompt = load_default_prompt_text(persona_key, mode_key)
            st.session_state.editor_content_state[selection_key] = (
                default_prompt if default_prompt is not None else FALLBACK_TEXT
            )
            st.toast(f"Override cleared for {selected_persona} ({selected_mode}).")
            st.rerun()

# ---------------------------------------------------------------------------
# Effective Configuration Viewer
# ---------------------------------------------------------------------------
with st.expander(f"View Effective Configuration — {selected_persona}"):
    # LLM parameters
    params = load_llm_params(persona_key)
    if params:
        st.markdown("**LLM Parameters**")
        param_display = {
            "Model": params.get("model_name", "—"),
            "Temperature": params.get("temperature", "—"),
            "Max Tokens": params.get("max_tokens", "—"),
            "Top P": params.get("top_p", "—"),
            "Presence Penalty": params.get("presence_penalty", 0.0),
            "Frequency Penalty": params.get("frequency_penalty", 0.0),
            "Timeout": f"{params.get('request_timeout', '—')}s",
        }
        for label, val in param_display.items():
            st.caption(f"**{label}:** {val}")
    else:
        st.caption("No LLM parameters found.")

    # Voice profile
    pcfg = get_philosopher(persona_key)
    if pcfg and pcfg.voice_profile:
        st.markdown("**Voice Profile**")
        vp = pcfg.voice_profile
        if vp.get("sentence_range"):
            st.caption(f"**Sentence Range:** {vp['sentence_range']}")
        if vp.get("style_keywords"):
            st.caption(f"**Style:** {', '.join(vp['style_keywords'])}")
        if vp.get("personality_summary"):
            st.caption(f"**Personality:** {vp['personality_summary']}")
        if vp.get("example_utterances"):
            st.caption("**Example Utterances:**")
            for ex in vp["example_utterances"]:
                st.caption(f'  — "{ex}"')

    # Active user personality notes
    notes_key = None
    p1 = st.session_state.get("philosopher_1", "")
    p2 = st.session_state.get("philosopher_2", "")
    if selected_persona == p1:
        notes_key = "personality_notes_p1"
    elif selected_persona == p2:
        notes_key = "personality_notes_p2"
    if notes_key:
        notes = st.session_state.get(notes_key, "")
        if notes and notes.strip():
            st.markdown("**Active Character Notes**")
            st.caption(notes.strip())

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
st.caption("Changes persist for this session and affect both the main dialogue and Direct Chat.")

with st.expander("View All Overrides"):
    overrides = st.session_state.get("prompt_overrides", {})
    if overrides:
        for k, v in overrides.items():
            st.markdown(f"**{k}:** `{v[:80]}...`" if len(v) > 80 else f"**{k}:** `{v}`")
    else:
        st.caption("No overrides set.")
