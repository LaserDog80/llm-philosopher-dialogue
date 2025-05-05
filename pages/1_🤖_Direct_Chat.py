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
DEFAULT_CONVERSATION_MODE = 'Philosophy' # Match default in app.py
SHOW_THINKING_OPTIONS = ["Show Thinking", "Hide Thinking"]
DEFAULT_SHOW_THINKING = SHOW_THINKING_OPTIONS[0] # Default to Show

# --- Regex for extracting <think> blocks ---
THINK_BLOCK_REGEX = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)

# --- Helper functions for text processing ---
def extract_think_block(text: str | None) -> str | None:
    """Extracts content from the first <think> block found."""
    if not text:
        return None
    match = THINK_BLOCK_REGEX.search(text)
    if match:
        return match.group(1).strip()
    return None

def clean_response(text: str | None) -> str:
    """Removes <think> blocks and surrounding tags."""
    if not text:
        return ""
    return THINK_BLOCK_REGEX.sub('', text).strip()

# --- Get Current Mode from Main App State ---
current_mode = st.session_state.get('conversation_mode', DEFAULT_CONVERSATION_MODE)
st.info(f"Using AI configurations for **{current_mode} Mode** (selected on main page sidebar).")

# --- Persona Selection ---
selected_persona = st.radio(
    "Select AI Persona to chat with:",
    PERSONAS,
    key="debug_chat_persona_select",
    horizontal=True,
    index=PERSONAS.index(st.session_state.get("debug_chat_persona", DEFAULT_PERSONA)) # Remember selection
)

# Update session state for persona
st.session_state.debug_chat_persona = selected_persona
persona_key = selected_persona.lower() # e.g., "socrates"

# --- State Initialization for this page ---
st.session_state.setdefault('debug_messages', {})
st.session_state.setdefault('debug_llm', None)
st.session_state.setdefault('debug_system_prompt', "")
st.session_state.setdefault('current_debug_config_key', None)
st.session_state.setdefault('debug_chain', None)
# Initialize state for the new radio button
st.session_state.setdefault('debug_show_thinking_radio', DEFAULT_SHOW_THINKING)


# --- Load LLM, Prompt, and Chain based on selection ---
debug_config_key = f"{persona_key}_{current_mode.lower()}"

if st.session_state.current_debug_config_key != debug_config_key:
    logger.info(f"Config changed to: {debug_config_key}. Loading LLM, prompt, and creating chain.")
    st.session_state.debug_messages.setdefault(debug_config_key, []) # Ensure list exists
    st.session_state.debug_llm = None
    st.session_state.debug_system_prompt = "Loading..."
    st.session_state.debug_chain = None # Reset chain

    with st.spinner(f"Loading {selected_persona} ({current_mode} mode)..."):
        try:
            llm, system_prompt_text = load_llm_config_for_persona(persona_key, mode=current_mode)
            if llm and system_prompt_text:
                st.session_state.debug_llm = llm
                st.session_state.debug_system_prompt = system_prompt_text
                st.session_state.current_debug_config_key = debug_config_key

                # Create and store the chain
                chat_prompt_template = ChatPromptTemplate.from_messages([
                    ("system", system_prompt_text),
                    MessagesPlaceholder(variable_name="chat_history"),
                    ("user", "{input}")
                ])
                output_parser = StrOutputParser()
                st.session_state.debug_chain = chat_prompt_template | llm | output_parser
                logger.info(f"Successfully loaded LLM/Prompt and created Chain for {debug_config_key}")
            else:
                st.error(f"Failed to load LLM or system prompt for {selected_persona} in {current_mode} mode.")
                st.session_state.debug_system_prompt = "Error: Could not load configuration."
                st.session_state.current_debug_config_key = None
        except Exception as e:
            st.error(f"An error occurred while loading configuration: {e}")
            logger.error(f"Error loading LLM/Prompt/Chain for {debug_config_key}", exc_info=True)
            st.session_state.debug_system_prompt = f"Error loading: {e}"
            st.session_state.current_debug_config_key = None


# --- Display System Prompt & Controls ---
with st.expander("View System Prompt", expanded=False):
    current_prompt_display = st.session_state.get("debug_system_prompt", "")
    if current_prompt_display and not current_prompt_display.startswith("Error") and not current_prompt_display == "Loading...":
        st.text_area("System Prompt:", value=current_prompt_display, height=200, disabled=True, key=f"sp_{debug_config_key}")
    else:
        st.warning(current_prompt_display or "System prompt not loaded.")

# --- Add Show/Hide Thinking Radio Button ---
st.radio(
    "Display Options:",
    SHOW_THINKING_OPTIONS,
    key='debug_show_thinking_radio', # Session state key
    horizontal=True,
    index=SHOW_THINKING_OPTIONS.index(st.session_state.debug_show_thinking_radio) # Set index from state
)
# --- End Radio Button ---

st.divider()

# --- Chat Interface ---
# Ensure message history storage for the current config exists
st.session_state.debug_messages.setdefault(debug_config_key, [])

# Display chat messages from history
st.subheader(f"Chat with {selected_persona}")
current_message_history = st.session_state.debug_messages[debug_config_key]
# Get the current state of the radio button
show_thinking = st.session_state.debug_show_thinking_radio == SHOW_THINKING_OPTIONS[0] # True if "Show Thinking" is selected

for idx, message_data in enumerate(current_message_history):
    message_type = message_data.get("type")
    content = message_data.get("content", "")
    thinking = message_data.get("thinking") # Will be None for humans

    if message_type == "human":
        avatar = "👤"
        with st.chat_message("human", avatar=avatar):
            st.markdown(content)
    elif message_type == "ai":
        avatar = "🤖"
        with st.chat_message("ai", avatar=avatar):
            # <<< CHANGE: Conditionally display thinking text FIRST >>>
            if thinking and show_thinking: # Check flag here
                st.caption(f"Thinking: {thinking}") # Display thinking above
            # Display main content AFTER thinking
            st.markdown(content)
    else:
        # Fallback for potentially malformed data
        with st.chat_message("system"):
             st.warning(f"Unknown message format at index {idx}: {message_data}")


# React to user input
if prompt := st.chat_input(f"What do you want to ask {selected_persona}?"):
    if not st.session_state.debug_chain or st.session_state.current_debug_config_key != debug_config_key:
        st.error("Cannot chat. AI Chain is not loaded correctly.")
    else:
        user_message_data = {"type": "human", "content": prompt, "thinking": None}
        st.session_state.debug_messages[debug_config_key].append(user_message_data)

        with st.chat_message("human", avatar="👤"):
            st.markdown(prompt)

        # Prepare chat history for Langchain prompt
        history_for_prompt: List[BaseMessage] = []
        for msg_data in st.session_state.debug_messages[debug_config_key][:-1]:
            msg_type = msg_data.get("type")
            msg_content = msg_data.get("content", "")
            if msg_type == "human":
                history_for_prompt.append(HumanMessage(content=msg_content))
            elif msg_type == "ai":
                history_for_prompt.append(AIMessage(content=msg_content))

        # Invoke the stored chain
        try:
            chain = st.session_state.debug_chain
            with st.spinner(f"{selected_persona} is thinking..."):
                input_data = {
                    "input": prompt,
                    "chat_history": history_for_prompt
                 }
                logger.info(f"Invoking stored chain for {selected_persona} ({debug_config_key}) with input: '{prompt[:50]}...'")
                raw_response_content = chain.invoke(input_data)
                logger.info(f"{selected_persona} responded.")

            # Process Response
            thinking_text = extract_think_block(raw_response_content)
            cleaned_response_content = clean_response(raw_response_content)

            # Add AI response to history
            ai_message_data = {"type": "ai", "content": cleaned_response_content, "thinking": thinking_text}
            st.session_state.debug_messages[debug_config_key].append(ai_message_data)
            st.rerun()

        except Exception as e:
            st.error(f"An error occurred during chat invocation: {e}")
            logger.error(f"Error invoking chain for {debug_config_key}: {e}", exc_info=True)
            if st.session_state.debug_messages[debug_config_key]:
                 st.session_state.debug_messages[debug_config_key].pop()
            st.rerun()


# --- Transcript Display ---
st.divider()
with st.expander("View/Copy Full Transcript", expanded=False):
    if st.session_state.current_debug_config_key == debug_config_key \
       and st.session_state.get("debug_system_prompt") \
       and not st.session_state.debug_system_prompt.startswith("Error") \
       and not st.session_state.debug_system_prompt == "Loading...":

        transcript_list = []
        system_prompt = st.session_state.debug_system_prompt
        persona_name = st.session_state.debug_chat_persona
        message_history = st.session_state.debug_messages.get(debug_config_key, [])
        # Use the same flag for transcript visibility
        show_thinking_in_transcript = st.session_state.debug_show_thinking_radio == SHOW_THINKING_OPTIONS[0]

        transcript_list.append(f"--- System Prompt ({persona_name} - {current_mode} Mode) ---")
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
                    # <<< CHANGE: Conditionally add thinking BEFORE main AI content >>>
                    if thinking and show_thinking_in_transcript: # Check flag
                        transcript_list.append(f"  THINKING: {thinking}")
                    transcript_list.append(f"AI ({persona_name}): {msg_content}")
                else:
                    transcript_list.append(f"UNKNOWN_TYPE ({msg_type}): {msg_content}")
                transcript_list.append("-" * 20)

        full_transcript = "\n".join(transcript_list)
        st.text_area("Full Transcript:", value=full_transcript, height=400, disabled=True, key=f"transcript_{debug_config_key}")
    elif st.session_state.get("debug_system_prompt", "").startswith("Error"):
         st.warning("Cannot show transcript because the AI configuration failed to load.")
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