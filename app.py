# Filename: app.py

import streamlit as st
import os
import datetime
import json
import logging
from typing import List, Dict, Any, Optional # Added for type hinting

# --- Local Imports ---
try:
    from direction import Director
    import gui
except ImportError as e:
    st.error(f"Critical Error: Failed to import local modules (direction.py or gui.py). Details: {e}")
    logging.exception("Failed to import local modules.") # Log full traceback
    st.stop() # Stop execution if core modules are missing

# --- Configuration ---
LOG_DIR = "logs"
DEFAULT_NUM_ROUNDS = 3

# Configure root logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# Get a logger specific to this app module
logger = logging.getLogger(__name__)

# --- Log File Handling ---
def initialize_log(num_rounds_for_log: int) -> bool:
    """Creates log dir and opens file, stores handle in session state."""
    log_filename = os.path.join(LOG_DIR, f"streamlit_conversation_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        # Use 'a' mode if appending is desired, 'w' to overwrite each time
        handle = open(log_filename, 'w', encoding='utf-8')
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        handle.write(f"Streamlit Conversation Log - {timestamp}\n")
        handle.write(f"Requested Rounds: {num_rounds_for_log}\n")
        handle.write("========================================\n\n")
        st.session_state.log_file_handle = handle
        st.session_state.current_log_filename = log_filename
        logger.info(f"Initialized log file: {log_filename}")
        return True
    except IOError as e:
        st.error(f"Failed to initialize log file: {e}")
        logger.error(f"Failed to initialize log file {log_filename}: {e}")
        st.session_state.log_file_handle = None
        return False

def write_log(message_dict: Dict[str, Any]):
    """Writes message content to the log file."""
    if 'log_file_handle' in st.session_state and st.session_state.log_file_handle and not st.session_state.log_file_handle.closed:
        try:
            role = message_dict.get('role', 'system').upper()
            content = message_dict.get('content', '')
            # Determine prefix based on role for clarity in log
            if role == 'USER':
                 log_line = f"USER: {content}\n"
            elif role == 'SYSTEM':
                 # Don't add SYSTEM prefix if content already indicates it (like MODERATOR CONTEXT)
                 if content.strip().startswith(("MODERATOR CONTEXT", "MODERATOR EVALUATION", "Error:")):
                      log_line = f"{content.strip()}\n"
                 else: # Generic system message
                      log_line = f"SYSTEM: {content}\n"
            else: # Philosophers
                 log_line = f"{role}: {content}\n"

            st.session_state.log_file_handle.write(log_line)
            st.session_state.log_file_handle.write("----------------------------------------\n")
            st.session_state.log_file_handle.flush() # Ensure writes happen immediately
        except Exception as e:
            logger.error(f"Error writing to log file: {e}", exc_info=True)
            # Avoid infinite loops if status update causes issues
            if st.session_state.current_status != "Error writing to log file.":
                 st.session_state.current_status = "Error writing to log file."
                 st.toast("Error writing to log.", icon="⚠️")


def close_log():
    """Closes the log file if open."""
    if 'log_file_handle' in st.session_state and st.session_state.log_file_handle:
        if not st.session_state.log_file_handle.closed:
             log_filename = st.session_state.get('current_log_filename', 'Unknown Log File')
             try:
                 st.session_state.log_file_handle.write("\n--- Log file closed ---\n")
                 st.session_state.log_file_handle.close()
                 logger.info(f"Closed log file: {log_filename}")
             except Exception as e:
                  logger.error(f"Error closing log file {log_filename}: {e}")
        # Reset state variables regardless of close success
        st.session_state.log_file_handle = None
        st.session_state.current_log_filename = None


# --- Initialize Session State ---
# Use keys consistent with widget keys in gui.py
default_values = {
    'messages': [],
    'director_instance': None, # Initialize later with error handling
    'current_status': "Ready.",
    'log_file_handle': None,
    'current_log_filename': None,
    'show_monologue_cb': False,
    'show_moderator_cb': True, # Default to show moderator context
    'bypass_moderator_cb': False, # Default to NOT bypass moderator
    'starting_philosopher': 'Socrates',
    'num_rounds': DEFAULT_NUM_ROUNDS
}
for key, default_value in default_values.items():
    if key not in st.session_state:
        st.session_state[key] = default_value

# Initialize Director instance once
if st.session_state.director_instance is None:
    try:
        st.session_state.director_instance = Director()
        logger.info("Director instance created successfully.")
    except ImportError as e:
        st.error(f"Failed Director init: {e}")
        logger.exception("Director class import failed.")
        st.stop()
    except Exception as e:
        st.error(f"Error initializing Director: {e}")
        logger.exception("Director initialization failed.")
        st.stop()


# --- Render UI ---
try:
    model_info = gui.get_model_info_from_config()
    gui.display_sidebar(model_info) # Contains all sidebar widgets
    gui.display_header()
    gui.display_conversation(st.session_state.messages) # Displays chat history
except Exception as e:
    st.error(f"Error rendering UI components: {e}")
    logger.exception("Error during UI rendering.")


# --- Display Internal Monologue (Conditionally) ---
if st.session_state.get('show_monologue_cb', False):
    with st.expander("Internal Monologue / Debug"):
        monologue_found = False
        # Ensure messages is iterable and contains dicts
        if isinstance(st.session_state.messages, list):
             for message in st.session_state.messages:
                 if isinstance(message, dict):
                      monologue = message.get('monologue')
                      if monologue:
                          monologue_found = True
                          role = message.get('role', 'System')
                          st.markdown(f"**[{role}] Thought:**")
                          # Use st.text or st.code for preformatted display
                          st.text(monologue)
                          st.divider()
        if not monologue_found:
             st.caption("No monologue entries found.")


# Display Status
gui.display_status(st.session_state.current_status)


# --- Handle User Input ---
prompt: Optional[str] = st.chat_input("Enter your initial question...")

if prompt:
    logger.info(f"User input received: '{prompt[:50]}...'") # Log truncated prompt
    st.session_state.current_status = "Processing..."

    # Clear previous messages for a new conversation
    st.session_state.messages = []
    # Close any potentially open log file from a previous run before starting new
    close_log()

    # Get config from session state (set by widgets in gui.py)
    num_rounds_selected = st.session_state.get('num_rounds', DEFAULT_NUM_ROUNDS)
    starting_philosopher_selected = st.session_state.get('starting_philosopher', 'Socrates')

    # Initialize log file for the new conversation
    if not initialize_log(num_rounds_selected):
        st.session_state.current_status = "Log initialization failed. Cannot proceed."
        st.rerun() # Stop processing if log fails

    # Store user message as the first message
    user_message: Dict[str, Any] = {"role": "user", "content": prompt, "monologue": None}
    st.session_state.messages.append(user_message)
    write_log(user_message) # Write user input to the new log

    # Set flag to run conversation after rerun
    st.session_state.run_conversation_flag = True
    st.rerun() # Rerun to display the user's input immediately


# --- Run Conversation if Flag is Set ---
# This block runs *after* the rerun caused by user input submission
if st.session_state.get('run_conversation_flag', False):
    # Reset the flag
    st.session_state.run_conversation_flag = False

    # Retrieve the prompt and config again from session state
    initial_prompt = st.session_state.messages[0]['content'] # First message is user's prompt
    num_rounds_selected = st.session_state.get('num_rounds', DEFAULT_NUM_ROUNDS)
    starting_philosopher_selected = st.session_state.get('starting_philosopher', 'Socrates')
    # Get the bypass moderator setting
    bypass_moderator_mode = st.session_state.get('bypass_moderator_cb', False)
    run_moderated_flag = not bypass_moderator_mode

    director = st.session_state.director_instance

    if director:
        try:
            with st.spinner("Philosophers are conferring..."):
                 logger.info(f"Calling Director: Rounds={num_rounds_selected}, Starter='{starting_philosopher_selected}', Moderated={run_moderated_flag}")
                 # Pass selected options to the director, including the moderation flag
                 generated_messages: List[Dict[str, Any]]
                 final_status: str
                 success: bool
                 generated_messages, final_status, success = director.run_conversation_streamlit(
                     initial_input=initial_prompt,
                     num_rounds=num_rounds_selected,
                     starting_philosopher=starting_philosopher_selected,
                     run_moderated=run_moderated_flag # Pass the flag
                 )
                 logger.info(f"Director finished. Success: {success}. Status: {final_status}")

            # Process results
            st.session_state.current_status = final_status
            # Extend messages only after the initial user message
            st.session_state.messages.extend(generated_messages)

            # Log generated messages
            for msg in generated_messages: write_log(msg)

            # Provide user feedback
            if success: st.toast(f"Conversation completed.", icon="✅")
            else: st.toast(f"Conversation ended: {final_status}", icon="⚠️")

        except Exception as e:
            error_msg = f"An unexpected error occurred during conversation: {e}"
            st.error(error_msg)
            logger.exception(error_msg) # Log full traceback for unexpected errors
            st.session_state.current_status = "Critical error during conversation."
        finally:
            close_log() # Ensure log is closed after run attempt (success, fail, or error)
            st.rerun() # Update display with generated messages or error status
    else:
        st.error("Director instance not available."); logger.error("Director instance is None, cannot run conversation.")
        st.session_state.current_status = "Error: Director not loaded."
        close_log() # Close log if director was never available


# --- Clear History Button ---
st.divider()
if st.button("Clear Conversation History"):
    logger.info("Clear Conversation History button clicked.")
    st.session_state.messages = []
    st.session_state.current_status = "Ready."
    # Close log if clearing history
    close_log()
    # Reset run flag if conversation was interrupted and history cleared
    if 'run_conversation_flag' in st.session_state:
         del st.session_state.run_conversation_flag
    logger.info("Conversation history cleared.")
    st.rerun()