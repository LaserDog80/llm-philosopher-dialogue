# pages/1_Direct_Chat.py — Debug page for chatting with individual personas.

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
# Inject chat CSS for consistent styling
# ---------------------------------------------------------------------------
gui.inject_chat_css()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PERSONAS = ["Socrates", "Confucius", "Moderator"]
MODES = ["Philosophy", "Bio"]

# ---------------------------------------------------------------------------
# Page Layout
# ---------------------------------------------------------------------------
st.markdown(
    '<div class="phd-header">'
    '  <h1 class="phd-title">Direct AI Chat</h1>'
    '  <p class="phd-subtitle">Chat directly with an individual philosopher persona</p>'
    '</div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------
col1, col2 = st.columns(2)
with col1:
    selected_persona = st.radio(
        "Persona:",
        PERSONAS,
        key="debug_chat_persona",
        horizontal=True,
    )
with col2:
    selected_mode = st.radio(
        "Mode:",
        MODES,
        key="debug_local_conversation_mode",
        horizontal=True,
    )

persona_key = selected_persona.lower()
config_key = f"{persona_key}_{selected_mode.lower()}"

show_thinking = st.checkbox("Show Thinking", key="debug_show_thinking", value=False)

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
# System prompt viewer
# ---------------------------------------------------------------------------
with st.expander("View System Prompt", expanded=False):
    prompt_text = st.session_state.get("debug_system_prompt", "")
    if prompt_text:
        st.text_area("System Prompt:", value=prompt_text, height=200, disabled=True, key=f"sp_{config_key}")
    else:
        st.caption("No prompt loaded.")

st.divider()

# ---------------------------------------------------------------------------
# Chat display — using the new styled HTML
# ---------------------------------------------------------------------------
st.session_state.debug_messages.setdefault(config_key, [])
history = st.session_state.debug_messages[config_key]

# Get the speaker style for the AI persona
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
                f'    <div class="phd-card" style="border-left-color:{user_style["color"]}; background:{user_style["bg"]};">'
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
                f'    <div class="phd-card" style="border-left-color:{style["color"]}; background:{style["bg"]};">'
                f'      <div class="phd-content">{gui._esc(content)}</div>'
                f'    </div>'
                f'  </div>'
                f'</div>'
            )
            if thinking and show_thinking:
                html_parts.append(
                    f'<div class="phd-mod-ctx" style="margin-left:48px;">'
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
        # Store user message
        st.session_state.debug_messages[config_key].append(
            {"type": "human", "content": prompt, "thinking": None}
        )

        # Build history for the chain
        history_for_chain: List[BaseMessage] = []
        for msg in st.session_state.debug_messages[config_key][:-1]:
            if msg["type"] == "human":
                history_for_chain.append(HumanMessage(content=msg["content"]))
            elif msg["type"] == "ai":
                history_for_chain.append(AIMessage(content=msg["content"]))

        try:
            with st.spinner(f"{selected_persona} is thinking..."):
                raw = st.session_state.debug_chain.invoke({
                    "input": prompt,
                    "chat_history": history_for_chain,
                })
            thinking_text = extract_think_block(raw)
            cleaned = clean_response(raw)
            st.session_state.debug_messages[config_key].append(
                {"type": "ai", "content": cleaned, "thinking": thinking_text}
            )
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")
            logger.exception(f"Chain invocation failed for {config_key}")
            # Remove the user message we just added
            if st.session_state.debug_messages.get(config_key):
                st.session_state.debug_messages[config_key].pop()
            st.rerun()

# ---------------------------------------------------------------------------
# Transcript and controls
# ---------------------------------------------------------------------------
st.divider()

with st.expander("View Full Transcript", expanded=False):
    if history:
        lines = []
        for msg in history:
            if msg["type"] == "human":
                lines.append(f"YOU: {msg['content']}")
            elif msg["type"] == "ai":
                if msg.get("thinking") and show_thinking:
                    lines.append(f"  [Thinking]: {msg['thinking']}")
                lines.append(f"{selected_persona.upper()}: {msg['content']}")
            lines.append("-" * 30)
        st.text_area("Transcript:", value="\n".join(lines), height=300, disabled=True, key=f"transcript_{config_key}")
    else:
        st.caption("No messages yet.")

if st.button("Clear Chat History", disabled=not history):
    st.session_state.debug_messages[config_key] = []
    st.rerun()
