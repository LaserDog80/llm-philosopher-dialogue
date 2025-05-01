# Filename: app.py

import streamlit as st
import os
import datetime
import json
import logging
from typing import List, Dict, Any, Optional

# --- Local Imports ---
try:
    # Ensure Director can be initialized without pre-loading chains now
    from direction import Director
    import gui
except ImportError as e:
    st.error(f"Critical Error: Failed to import local modules (direction.py or gui.py). Details: {e}")
    logging.exception("Failed to import local modules.")
    st.stop()
except Exception as e:
    # Catch potential errors in the new Director.__init__ if any
    st.error(f"Critical Error during initial imports or Director init: {e}")
    logging.exception("Failed during initial imports or Director init.")
    st.stop()


# --- Configuration ---
LOG_DIR = "logs"
DEFAULT_NUM_ROUNDS = 3
DEFAULT_CONVERSATION_MODE = 'Philosophy' # Default mode matches gui.py default

# Configure root logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Log File Handling ---
# (initialize_log, write_log, close_log functions remain the same as previous version)
# (Kept for brevity - ensure they are present in your actual file)
def initialize_log(num_rounds_for_log: int) -> bool:
    """Creates log dir and opens file, stores handle in session state."""
    log_filename = os.path.join(LOG_DIR, f"streamlit_conversation_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        handle = open(log_filename, 'w', encoding='utf-8')
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        handle.write(f"Streamlit Conversation Log - {timestamp}\n")
        handle.write(f"Requested Rounds: {num_rounds_for_log}\n")
        # Log the mode? Get it from session state here too
        selected_mode = st.session_state.get('conversation_mode', DEFAULT_CONVERSATION_MODE)
        handle.write(f"Conversation Mode: {selected_mode}\n")
        handle.write("========================================\n\n")
        st.session_state.log_file_handle = handle
        st.session_state.current_log_filename = log_filename
        logger.info(f"Initialized log file: {log_filename} for mode '{selected_mode}'")
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
            role = message_dict.get('role', 'system').upper(); content = message_dict.get('content', '')
            if role == 'USER': log_line = f"USER: {content}\n"
            elif role == 'SYSTEM':
                 if content.strip().startswith(("MODERATOR CONTEXT", "MODERATOR EVALUATION", "Error:")): log_line = f"{content.strip()}\n"
                 else: log_line = f"SYSTEM: {content}\n"
            else: log_line = f"{role}: {content}\n"
            st.session_state.log_file_handle.write(log_line)
            st.session_state.log_file_handle.write("----------------------------------------\n")
            st.session_state.log_file_handle.flush()
        except Exception as e:
            logger.error(f"Error writing to log file: {e}", exc_info=True)
            if st.session_state.current_status != "Error writing to log file.": st.session_state.current_status = "Error writing to log file."; st.toast("Error writing to log.", icon="⚠️")

def close_log():
    """Closes the log file if open."""
    if 'log_file_handle' in st.session_state and st.session_state.log_file_handle:
        if not st.session_state.log_file_handle.closed:
             log_filename = st.session_state.get('current_log_filename', 'Unknown Log File')
             try:
                 st.session_state.log_file_handle.write("\n--- Log file closed ---\n"); st.session_state.log_file_handle.close()
                 logger.info(f"Closed log file: {log_filename}")
             except Exception as e: logger.error(f"Error closing log file {log_filename}: {e}")
        st.session_state.log_file_handle = None; st.session_state.current_log_filename = None
# --- End Log Handling ---


# --- Initialize Session State ---
default_values = {
    'messages': [],
    'director_instance': None,
    'current_status': "Ready.",
    'log_file_handle': None,
    'current_log_filename': None,
    'show_monologue_cb': False,
    'show_moderator_cb': True,
    'bypass_moderator_cb': False,
    'starting_philosopher': 'Socrates',
    'num_rounds': DEFAULT_NUM_ROUNDS,
    # Initialize conversation_mode based on gui.py default
    'conversation_mode': DEFAULT_CONVERSATION_MODE
}
for key, default_value in default_values.items():
    if key not in st.session_state:
        st.session_state[key] = default_value

# Initialize Director instance once (it no longer loads chains on init)
if st.session_state.director_instance is None:
    try:
        st.session_state.director_instance = Director()
        logger.info("Director instance created successfully.")
    except Exception as e:
        # Errors during Director init itself (if any added later)
        st.error(f"Error initializing Director: {e}")
        logger.exception("Director initialization failed.")
        st.stop()


# --- Render UI ---
# Display sidebar first to ensure session state keys are set/updated
try:
    model_info = gui.get_model_info_from_config()
    gui.display_sidebar(model_info) # Contains mode selector now
except Exception as e:
    st.error(f"Error rendering sidebar: {e}")
    logger.exception("Error during sidebar rendering.")
# Display rest of UI
try:
    gui.display_header()
    gui.display_conversation(st.session_state.messages)
except Exception as e:
    st.error(f"Error rendering main UI components: {e}")
    logger.exception("Error during main UI rendering.")


# --- Display Internal Monologue (Conditionally) ---
# (Code identical to previous version - kept for brevity)
if st.session_state.get('show_monologue_cb', False):
    with st.expander("Internal Monologue / Debug"):
        monologue_found = False
        if isinstance(st.session_state.messages, list):
             for message in st.session_state.messages:
                 if isinstance(message, dict):
                      monologue = message.get('monologue')
                      if monologue: monologue_found = True; role = message.get('role', 'System'); st.markdown(f"**[{role}] Thought:**"); st.text(monologue); st.divider()
        if not monologue_found: st.caption("No monologue entries found.")

# Display Status
gui.display_status(st.session_state.current_status)


# --- Handle User Input ---
prompt: Optional[str] = st.chat_input("Enter your initial question...")

if prompt:
    logger.info(f"User input received: '{prompt[:50]}...'")
    st.session_state.current_status = "Processing..."

    st.session_state.messages = []
    close_log()

    # Get config from session state (including the selected mode)
    num_rounds_selected = st.session_state.get('num_rounds', DEFAULT_NUM_ROUNDS)
    starting_philosopher_selected = st.session_state.get('starting_philosopher', 'Socrates')
    # --> Get the selected conversation mode from the radio button state <--
    selected_mode = st.session_state.get('conversation_mode', DEFAULT_CONVERSATION_MODE) # Read from state key set by st.radio
    logger.info(f"Starting new conversation with mode: {selected_mode}")


    if not initialize_log(num_rounds_selected): # Initialize log (now logs the mode too)
        st.session_state.current_status = "Log initialization failed. Cannot proceed."
        st.rerun()

    user_message: Dict[str, Any] = {"role": "user", "content": prompt, "monologue": None}
    st.session_state.messages.append(user_message)
    write_log(user_message)

    # Set flag to run conversation after rerun
    st.session_state.run_conversation_flag = True
    # Store the mode selected for this run, so it's available after the rerun
    st.session_state.current_run_mode = selected_mode
    st.rerun()


# --- Run Conversation if Flag is Set ---
if st.session_state.get('run_conversation_flag', False):
    st.session_state.run_conversation_flag = False

    initial_prompt = st.session_state.messages[0]['content']
    num_rounds_selected = st.session_state.get('num_rounds', DEFAULT_NUM_ROUNDS)
    starting_philosopher_selected = st.session_state.get('starting_philosopher', 'Socrates')
    bypass_moderator_mode = st.session_state.get('bypass_moderator_cb', False)
    run_moderated_flag = not bypass_moderator_mode
    # --> Retrieve the mode selected for this specific run <--
    current_mode = st.session_state.get('current_run_mode', DEFAULT_CONVERSATION_MODE)

    director = st.session_state.director_instance

    if director:
        try:
            with st.spinner(f"Philosophers conferring ({current_mode} mode)..."):
                 logger.info(f"Calling Director: Mode='{current_mode}', Rounds={num_rounds_selected}, Starter='{starting_philosopher_selected}', Moderated={run_moderated_flag}")

                 # --> Pass the selected mode to the director's run method <--
                 generated_messages, final_status, success = director.run_conversation_streamlit(
                     initial_input=initial_prompt,
                     num_rounds=num_rounds_selected,
                     starting_philosopher=starting_philosopher_selected,
                     run_moderated=run_moderated_flag,
                     mode=current_mode # Pass the mode here
                 )
                 logger.info(f"Director finished '{current_mode}' mode run. Success: {success}. Status: {final_status}")

            st.session_state.current_status = final_status
            st.session_state.messages.extend(generated_messages)
            for msg in generated_messages: write_log(msg)

            if success: st.toast(f"Conversation completed ({current_mode} mode).", icon="✅")
            else: st.toast(f"Conversation ended: {final_status}", icon="⚠️")

        except Exception as e:
            error_msg = f"An unexpected error occurred during conversation: {e}"
            st.error(error_msg); logger.exception(error_msg)
            st.session_state.current_status = "Critical error during conversation."
        finally:
            close_log()
            # Clean up the run-specific mode state
            if 'current_run_mode' in st.session_state:
                del st.session_state.current_run_mode
            st.rerun()
    else:
        st.error("Director instance not available."); logger.error("Director instance is None, cannot run conversation.")
        st.session_state.current_status = "Error: Director not loaded."
        close_log()


# --- Clear History Button ---
# (Code identical to previous version - kept for brevity)
st.divider()
if st.button("Clear Conversation History"):
    logger.info("Clear Conversation History button clicked.")
    st.session_state.messages = []
    st.session_state.current_status = "Ready."
    close_log()
    if 'run_conversation_flag' in st.session_state: del st.session_state.run_conversation_flag
    if 'current_run_mode' in st.session_state: del st.session_state.current_run_mode
    logger.info("Conversation history cleared.")
    st.rerun()