# pages/1_Direct_Chat.py — Debug page for chatting with individual personas.
# UI: "Warm Study" theme — clean chat interface with popover settings.

import os
import sys
import logging

import streamlit as st
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from typing import List

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
# Imports (ensure parent directory is on path for llm_loader)
# ---------------------------------------------------------------------------
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from llm_loader import load_llm_config_for_persona
    from core.utils import extract_think_block, clean_response
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
# Constants
# ---------------------------------------------------------------------------
PERSONAS = ["Socrates", "Confucius", "Moderator"]
MODES = ["Philosophy", "Bio"]

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(
    '<div class="ws-header-bar">'
    '  <div class="ws-header-left">'
    '    <div class="ws-header-icon">&#x1F916;</div>'
    '    <div>'
    '      <h1 class="ws-title">Direct AI Chat</h1>'
    '      <p class="ws-subtitle">Chat directly with an individual philosopher persona</p>'
    '    </div>'
    '  </div>'
    '</div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Controls — in a popover for clean layout
# ---------------------------------------------------------------------------
col_settings, col_spacer, col_clear = st.columns([1.5, 5, 1.5])

with col_settings:
    with st.popover("Settings", icon=":material/settings:", use_container_width=False):
        st.markdown('<div class="ws-settings-section">Persona</div>', unsafe_allow_html=True)
        selected_persona = st.radio(
            "Persona:",
            PERSONAS,
            key="debug_chat_persona",
            horizontal=True,
        )
        st.markdown('<div class="ws-settings-section">Mode</div>', unsafe_allow_html=True)
        selected_mode = st.radio(
            "Mode:",
            MODES,
            key="debug_local_conversation_mode",
            horizontal=True,
        )
        st.checkbox("Show Thinking", key="debug_show_thinking", value=False)

        with st.expander("View System Prompt", expanded=False):
            prompt_text = st.session_state.get("debug_system_prompt", "")
            if prompt_text:
                _sp_key = f"sp_{selected_persona.lower()}_{selected_mode.lower()}"
                st.text_area("System Prompt:", value=prompt_text, height=200, disabled=True, key=_sp_key)
            else:
                st.caption("No prompt loaded.")

# Resolve keys from session state (set by widgets inside popover)
selected_persona = st.session_state.get("debug_chat_persona", "Socrates")
selected_mode = st.session_state.get("debug_local_conversation_mode", "Philosophy")
persona_key = selected_persona.lower()
config_key = f"{persona_key}_{selected_mode.lower()}"

with col_clear:
    pass  # Clear button placed after history is resolved

st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# State initialization
# ---------------------------------------------------------------------------
st.session_state.setdefault("debug_messages", {})
st.session_state.setdefault("debug_chain", None)
st.session_state.setdefault("debug_system_prompt", "")
st.session_state.setdefault("current_debug_config_key", None)

# ---------------------------------------------------------------------------
# Load chain when config changes
# ---------------------------------------------------------------------------
if st.session_state.current_debug_config_key != config_key:
    st.session_state.debug_chain = None
    st.session_state.debug_system_prompt = ""
    st.session_state.debug_messages.setdefault(config_key, [])

try:
    llm, system_prompt = load_llm_config_for_persona(persona_key, mode=selected_mode)
    if llm and system_prompt:
        prompt_changed = st.session_state.debug_system_prompt != system_prompt
        need_update = (
            st.session_state.current_debug_config_key != config_key
            or prompt_changed
            or st.session_state.debug_chain is None
        )
        if need_update:
            st.session_state.debug_system_prompt = system_prompt
            st.session_state.current_debug_config_key = config_key
            template = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                MessagesPlaceholder(variable_name="chat_history"),
                ("user", "{input}"),
            ])
            st.session_state.debug_chain = template | llm | StrOutputParser()
        else:
            st.session_state.current_debug_config_key = config_key
    else:
        st.error(f"Failed to load config for {selected_persona} ({selected_mode})")
        st.session_state.debug_chain = None
except Exception as e:
    st.error(f"Config loading error: {e}")
    logger.exception("Direct Chat config load failed")
    st.session_state.debug_chain = None

# ---------------------------------------------------------------------------
# Chat display — Warm Study styled HTML
# ---------------------------------------------------------------------------
st.session_state.debug_messages.setdefault(config_key, [])
history = st.session_state.debug_messages[config_key]

style = gui.SPEAKER_STYLES.get(persona_key, gui.SPEAKER_STYLES["system"])

if not history:
    st.markdown(
        '<div class="phd-empty">'
        f'  <div class="phd-empty-icon">&#x1F4AC;</div>'
        f'  <div class="phd-empty-text">Chat with {selected_persona}</div>'
        f'  <div class="phd-empty-hint">Ask a question below to start a direct conversation</div>'
        '</div>',
        unsafe_allow_html=True,
    )
else:
    html_parts = ['<div class="phd-container">']
    for msg in history:
        msg_type = msg.get("type")
        content = msg.get("content", "")
        thinking = msg.get("thinking")

        if msg_type == "human":
            user_style = gui.SPEAKER_STYLES["user"]
            html_parts.append(
                f'<div class="phd-turn">'
                f'  <div class="phd-avatar" style="background:{user_style["color"]};">{user_style["initials"]}</div>'
                f'  <div class="phd-msg-body">'
                f'    <div class="phd-msg-header">'
                f'      <span class="phd-speaker" style="color:{user_style["text_color"]};">You</span>'
                f'    </div>'
                f'    <div class="phd-card" style="border-left-color:{user_style.get("border", user_style["color"])}; background:{user_style["bg"]};">'
                f'      <div class="phd-content">{gui._esc(content)}</div>'
                f'    </div>'
                f'  </div>'
                f'</div>'
            )
        elif msg_type == "ai":
            html_parts.append(
                f'<div class="phd-turn">'
                f'  <div class="phd-avatar" style="background:{style["color"]};">{style["initials"]}</div>'
                f'  <div class="phd-msg-body">'
                f'    <div class="phd-msg-header">'
                f'      <span class="phd-speaker" style="color:{style["text_color"]};">{style["display_name"]}</span>'
                f'    </div>'
                f'    <div class="phd-card" style="border-left-color:{style.get("border", style["color"])}; background:{style["bg"]};">'
                f'      <div class="phd-content">{gui._esc(content)}</div>'
                f'    </div>'
                f'  </div>'
                f'</div>'
            )
            if thinking and st.session_state.get("debug_show_thinking", False):
                html_parts.append(
                    f'<div class="phd-mod-ctx" style="margin-left:54px;">'
                    f'  <details>'
                    f'    <summary class="phd-mod-toggle" style="color:{style["text_color"]};">Thinking</summary>'
                    f'    <div class="phd-mod-body">{gui._esc(thinking)}</div>'
                    f'  </details>'
                    f'</div>'
                )

    html_parts.append('</div>')
    st.markdown("\n".join(html_parts), unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Chat input
# ---------------------------------------------------------------------------
if prompt := st.chat_input(f"Ask {selected_persona} a question..."):
    if not st.session_state.debug_chain:
        st.error("Chain not loaded. Cannot chat.")
    else:
        st.session_state.debug_messages[config_key].append(
            {"type": "human", "content": prompt, "thinking": None}
        )

        history_for_chain: List[BaseMessage] = []
        for msg in st.session_state.debug_messages[config_key][:-1]:
            if msg["type"] == "human":
                history_for_chain.append(HumanMessage(content=msg["content"]))
            elif msg["type"] == "ai":
                history_for_chain.append(AIMessage(content=msg["content"]))

        try:
            thinking_placeholder = st.empty()
            thinking_placeholder.markdown(
                gui.render_thinking_indicator(f"{selected_persona} is reflecting..."),
                unsafe_allow_html=True,
            )
            raw = st.session_state.debug_chain.invoke({
                "input": prompt,
                "chat_history": history_for_chain,
            })
            thinking_placeholder.empty()

            thinking_text = extract_think_block(raw)
            cleaned = clean_response(raw)
            st.session_state.debug_messages[config_key].append(
                {"type": "ai", "content": cleaned, "thinking": thinking_text}
            )
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")
            logger.exception(f"Chain invocation failed for {config_key}")
            if st.session_state.debug_messages.get(config_key):
                st.session_state.debug_messages[config_key].pop()
            st.rerun()

# ---------------------------------------------------------------------------
# Bottom controls — clean minimal
# ---------------------------------------------------------------------------
st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

col_a, col_b = st.columns([1, 1])
with col_a:
    with st.expander("View Full Transcript", expanded=False):
        if history:
            lines = []
            for msg in history:
                if msg["type"] == "human":
                    lines.append(f"YOU: {msg['content']}")
                elif msg["type"] == "ai":
                    if msg.get("thinking") and st.session_state.get("debug_show_thinking", False):
                        lines.append(f"  [Thinking]: {msg['thinking']}")
                    lines.append(f"{selected_persona.upper()}: {msg['content']}")
                lines.append("-" * 30)
            st.text_area("Transcript:", value="\n".join(lines), height=300, disabled=True, key=f"transcript_{config_key}")
        else:
            st.caption("No messages yet.")

with col_b:
    if st.button("Clear Chat History", disabled=not history, icon=":material/delete:"):
        st.session_state.debug_messages[config_key] = []
        st.rerun()
