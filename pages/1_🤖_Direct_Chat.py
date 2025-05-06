# pages/1_🤖_Direct_Chat.py

import streamlit as st
import os
import logging
import re # Import regex module
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
# Import message types required for history conversion
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from typing import List # Import List for type hinting

# --- Authentication Import and Check ---
try:
    import auth # Import the new authentication module
except ImportError:
    st.error("Fatal Error: Authentication module (`auth.py`) not found.")
    st.stop()

# Check authentication status using the auth module
# Initialize session state variable if it doesn't exist
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
# Run check - stops if not authenticated
if not auth.check_password():
    st.stop()
# --- End Authentication Check ---


# Assuming llm_loader.py is in the parent directory or accessible via PYTHONPATH
import sys
# Ensure the parent directory is in the path only once if needed
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)
try:
    from llm_loader import load_llm_config_for_persona
except ImportError:
    st.error("Could not import `llm_loader`. Make sure it's accessible.")
    st.stop()

# Configure logger for this page
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - DirectChat - %(levelname)s - %(message)s')

# --- Page Configuration ---
st.title("🤖 Direct AI Chat (Debug)")
st.caption("Chat directly with an individual AI persona using its configured system prompt for the currently selected mode.")

# --- Constants ---
PERSONAS = ["Socrates", "Confucius", "Moderator"]
DEFAULT_PERSONA = PERSONAS[0]
DEBUG_PAGE_MODES = ["Philosophy", "Bio"]
DEFAULT_DEBUG_PAGE_MODE = DEBUG_PAGE_MODES[0]

SHOW_THINKING_OPTIONS = ["Show Thinking", "Hide Thinking"]
DEFAULT_SHOW_THINKING_VALUE = SHOW_THINKING_OPTIONS[1] # Default to "Hide Thinking" value

# --- Regex for extracting <think> blocks ---
THINK_BLOCK_REGEX = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)

# --- Helper functions for text processing ---
def extract_think_block(text: str | None) -> str | None:
    """Extracts content from the first <think> block found."""
    if not text: return None
    match = THINK_BLOCK_REGEX.search(text)
    return match.group(1).strip() if match else None

def clean_response(text: str | None) -> str:
    """Removes <think> blocks and surrounding tags."""
    if not text: return ""
    return THINK_BLOCK_REGEX.sub('', text).strip()

# --- Persona Selection ---
# <<< FIX: Initialize debug_chat_persona if not present >>>
if 'debug_chat_persona' not in st.session_state:
    st.session_state.debug_chat_persona = DEFAULT_PERSONA

# <<< FIX: Use key="debug_chat_persona" and read from it for index and selected_persona >>>
selected_persona = st.radio(
    "Select AI Persona to chat with:",
    PERSONAS,
    key="debug_chat_persona", # Widget now manages st.session_state.debug_chat_persona
    horizontal=True,
    index=PERSONAS.index(st.session_state.debug_chat_persona) # Read current value for index
)
# selected_persona is now guaranteed to be the value from st.session_state.debug_chat_persona
persona_key = selected_persona.lower()

# --- Local Mode Selection for Direct Chat ---
if 'debug_local_conversation_mode' not in st.session_state:
    st.session_state.debug_local_conversation_mode = DEFAULT_DEBUG_PAGE_MODE

selected_local_mode = st.radio(
    "Select Conversation Mode (for this chat):",
    DEBUG_PAGE_MODES,
    key='debug_local_conversation_mode', # Changed key to directly manage the state
    horizontal=True,
    index=DEBUG_PAGE_MODES.index(st.session_state.debug_local_conversation_mode)
)
# selected_local_mode is now st.session_state.debug_local_conversation_mode
# --- End Local Mode Selection ---

# Update info message to reflect local mode selection
st.info(f"Using AI configurations for **{selected_local_mode} Mode** (selected on this page).")


# --- State Initialization for this page (other states) ---
st.session_state.setdefault('debug_messages', {})
st.session_state.setdefault('debug_llm', None)
st.session_state.setdefault('debug_system_prompt', "")
st.session_state.setdefault('current_debug_config_key', None)
st.session_state.setdefault('debug_chain', None)

# --- Load LLM, Prompt, and Chain based on current selection (Persona AND Local Mode) ---
debug_config_key = f"{persona_key}_{selected_local_mode.lower()}"
logger.debug(f"Running Direct Chat page for config key: {debug_config_key}")

if st.session_state.current_debug_config_key != debug_config_key:
     st.session_state.debug_llm = None
     st.session_state.debug_chain = None
     st.session_state.debug_system_prompt = "Loading..."
     st.session_state.debug_messages.setdefault(debug_config_key, [])

try:
    llm, system_prompt_text = load_llm_config_for_persona(persona_key, mode=selected_local_mode)

    if llm and system_prompt_text:
        prompt_changed = st.session_state.get('debug_system_prompt') != system_prompt_text
        llm_or_chain_missing = not st.session_state.get('debug_llm') or not st.session_state.get('debug_chain')
        config_key_changed = st.session_state.current_debug_config_key != debug_config_key

        if config_key_changed or prompt_changed or llm_or_chain_missing:
            logger.info(f"Configuration requires update for {debug_config_key}. Creating/Updating LLM and Chain.")
            st.session_state.debug_llm = llm
            st.session_state.debug_system_prompt = system_prompt_text
            st.session_state.current_debug_config_key = debug_config_key

            chat_prompt_template = ChatPromptTemplate.from_messages([
                ("system", system_prompt_text),
                MessagesPlaceholder(variable_name="chat_history"),
                ("user", "{input}")
            ])
            output_parser = StrOutputParser()
            st.session_state.debug_chain = chat_prompt_template | llm | output_parser
            logger.info(f"Chain updated successfully for {debug_config_key}.")
        else:
             logger.debug(f"Configuration for {debug_config_key} is up-to-date. No chain update needed.")
             st.session_state.current_debug_config_key = debug_config_key
    else:
        st.error(f"Failed to load LLM or system prompt for {selected_persona} in {selected_local_mode} mode.")
        st.session_state.debug_system_prompt = "Error: Could not load configuration."
        st.session_state.debug_llm = None
        st.session_state.debug_chain = None

except Exception as e:
    st.error(f"An error occurred while loading configuration: {e}")
    logger.error(f"Error loading LLM/Prompt/Chain for {debug_config_key}", exc_info=True)
    st.session_state.debug_system_prompt = f"Error loading: {e}"
    st.session_state.debug_llm = None
    st.session_state.debug_chain = None

# --- Display System Prompt & Controls ---
with st.expander("View System Prompt", expanded=False):
    current_prompt_display = st.session_state.get("debug_system_prompt", "")
    if current_prompt_display and not current_prompt_display.startswith("Error") and not current_prompt_display == "Loading...":
        st.text_area("System Prompt:", value=current_prompt_display, height=200, disabled=True, key=f"sp_{debug_config_key}")
    elif current_prompt_display == "Loading...":
         st.info("Loading system prompt...")
    else:
        st.warning(current_prompt_display or "System prompt not loaded or failed to load.")

st.radio(
    "Display Thinking:",
    SHOW_THINKING_OPTIONS,
    key='debug_show_thinking_radio',
    horizontal=True,
    index=SHOW_THINKING_OPTIONS.index(
        st.session_state.get('debug_show_thinking_radio', DEFAULT_SHOW_THINKING_VALUE)
    )
)
st.divider()

# --- Chat Interface ---
st.session_state.debug_messages.setdefault(debug_config_key, [])
st.subheader(f"Chat with {selected_persona} ({selected_local_mode} Mode)")
current_message_history = st.session_state.debug_messages[debug_config_key]

show_thinking_value = st.session_state.get('debug_show_thinking_radio', DEFAULT_SHOW_THINKING_VALUE)
show_thinking = show_thinking_value == SHOW_THINKING_OPTIONS[0]

for idx, message_data in enumerate(current_message_history):
    message_type = message_data.get("type")
    content = message_data.get("content", "")
    thinking = message_data.get("thinking")

    if message_type == "human":
        avatar = "👤"
        with st.chat_message("human", avatar=avatar):
            st.markdown(content)
    elif message_type == "ai":
        avatar = "🤖"
        with st.chat_message("ai", avatar=avatar):
            if thinking and show_thinking:
                st.caption(f"Thinking: {thinking}")
            st.markdown(content)
    else:
        with st.chat_message("system"):
             st.warning(f"Unknown message format at index {idx}: {message_data}")


if prompt := st.chat_input(f"What do you want to ask {selected_persona}?"):
    if not st.session_state.debug_chain or st.session_state.current_debug_config_key != debug_config_key:
        st.error("Cannot chat. AI Chain is not loaded correctly for the current selection.")
    else:
        user_message_data = {"type": "human", "content": prompt, "thinking": None}
        st.session_state.debug_messages[debug_config_key].append(user_message_data)

        with st.chat_message("human", avatar="👤"):
            st.markdown(prompt)

        history_for_prompt: List[BaseMessage] = []
        for msg_data in st.session_state.debug_messages[debug_config_key][:-1]:
            msg_type = msg_data.get("type")
            msg_content = msg_data.get("content", "")
            if msg_type == "human":
                history_for_prompt.append(HumanMessage(content=msg_content))
            elif msg_type == "ai":
                history_for_prompt.append(AIMessage(content=msg_content))
        try:
            chain = st.session_state.debug_chain
            with st.spinner(f"{selected_persona} is thinking..."):
                input_data = { "input": prompt, "chat_history": history_for_prompt }
                raw_response_content = chain.invoke(input_data)
            thinking_text = extract_think_block(raw_response_content)
            cleaned_response_content = clean_response(raw_response_content)
            ai_message_data = {"type": "ai", "content": cleaned_response_content, "thinking": thinking_text}
            st.session_state.debug_messages[debug_config_key].append(ai_message_data)
            st.rerun()
        except Exception as e:
            st.error(f"An error occurred during chat invocation: {e}")
            logger.error(f"Error invoking chain for {debug_config_key}: {e}", exc_info=True)
            if st.session_state.debug_messages.get(debug_config_key):
                 st.session_state.debug_messages[debug_config_key].pop()
            st.rerun()

# --- Transcript Display ---
st.divider()
with st.expander("View/Copy Full Transcript", expanded=False):
    # <<< FIX: Ensure persona_name is correctly sourced from st.session_state.debug_chat_persona >>>
    if st.session_state.current_debug_config_key == debug_config_key \
       and st.session_state.get("debug_system_prompt") \
       and not st.session_state.debug_system_prompt.startswith("Error") \
       and not st.session_state.debug_system_prompt == "Loading..." \
       and 'debug_chat_persona' in st.session_state: # Ensure the key exists

        transcript_list = []
        system_prompt = st.session_state.debug_system_prompt
        persona_name = st.session_state.debug_chat_persona # This will now be correctly initialized
        transcript_mode_header = selected_local_mode
        message_history = st.session_state.debug_messages.get(debug_config_key, [])
        
        show_thinking_in_transcript_value = st.session_state.get('debug_show_thinking_radio', DEFAULT_SHOW_THINKING_VALUE)
        show_thinking_in_transcript = show_thinking_in_transcript_value == SHOW_THINKING_OPTIONS[0]


        transcript_list.append(f"--- System Prompt ({persona_name} - {transcript_mode_header} Mode) ---")
        transcript_list.append(system_prompt)
        transcript_list.append("-----------------------------------------------\n")

        if not message_history:
            transcript_list.append("No messages in this chat session yet.")
        else:
            for message_data in message_history:
                msg_type = message_data.get("type")
                msg_content = message_data.get("content", "")
                thinking = message_data.get("thinking")
                if msg_type == "human":
                    transcript_list.append(f"USER: {msg_content}")
                elif msg_type == "ai":
                    if thinking and show_thinking_in_transcript:
                        transcript_list.append(f"  THINKING: {thinking}")
                    transcript_list.append(f"AI ({persona_name}): {msg_content}")
                else:
                    transcript_list.append(f"UNKNOWN_TYPE ({msg_type}): {msg_content}")
                transcript_list.append("-" * 20)
        full_transcript = "\n".join(transcript_list)
        st.text_area("Full Transcript:", value=full_transcript, height=400, disabled=True, key=f"transcript_{debug_config_key}")
    elif st.session_state.get("debug_system_prompt", "").startswith("Error"):
         st.warning("Cannot show transcript because the AI configuration failed to load.")
    elif 'debug_chat_persona' not in st.session_state:
        st.warning("Cannot show transcript because persona state is not initialized.")
    else:
        st.caption("Chat with the AI first or ensure configuration is loaded.")

# --- Option to clear debug chat history ---
st.divider()
col1_clear, col2_clear = st.columns([1,3])
with col1_clear:
    can_clear = debug_config_key in st.session_state.debug_messages and st.session_state.debug_messages[debug_config_key]
    if st.button(f"Clear Chat History", disabled=not can_clear):
        st.session_state.debug_messages[debug_config_key] = []
        logger.info(f"Cleared debug chat history for {debug_config_key}")
        st.rerun()
