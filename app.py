# Filename: app.py

import streamlit as st
import os
import logging
from dotenv import load_dotenv # Keep load_dotenv here, call early
import datetime
import json
from typing import List, Dict, Any, Optional

# --- Load Environment Variables ---
# Call early, before other imports that might rely on env vars (like auth)
load_dotenv()

# --- Import Authentication Module ---
try:
    import auth # Import the new authentication module
except ImportError:
    st.error("Fatal Error: Authentication module (`auth.py`) not found.")
    st.stop()

# Configure root logger
# Include microseconds for potentially rapid status updates
logging.basicConfig(level=logging.INFO, format='%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

# --- Main App Execution ---

# Initialize authentication status if it doesn't exist in session state
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# Run the password check using the auth module.
if not auth.check_password():
    st.stop()

# --- !!! --- APPLICATION CODE BELOW RUNS ONLY IF AUTHENTICATED --- !!! ---

# --- Local Imports (needed only after authentication) ---
try:
    from direction import Director
    import gui
except ImportError as e:
    st.error(f"Critical Error: Failed to import local modules post-authentication. Details: {e}")
    logging.exception("Failed to import local modules post-authentication.")
    st.stop()
except Exception as e:
    st.error(f"Critical Error during initial imports post-authentication: {e}")
    logging.exception("Failed during initial imports post-authentication.")
    st.stop()

# --- Configuration (specific to the authenticated app) ---
LOG_DIR = "logs"
DEFAULT_NUM_ROUNDS = 3
DEFAULT_CONVERSATION_MODE = 'Philosophy'

# --- Log File Handling ---
# (Log handling functions remain unchanged)
def initialize_log(num_rounds_for_log: int) -> bool:
    log_base_filename = f"streamlit_conversation_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    st.session_state.current_log_filename = log_base_filename
    st.session_state.log_content = []
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    selected_mode = st.session_state.get('conversation_mode', DEFAULT_CONVERSATION_MODE)
    st.session_state.log_content.append(f"Streamlit Conversation Log - {timestamp}")
    st.session_state.log_content.append(f"Requested Rounds: {num_rounds_for_log}")
    st.session_state.log_content.append(f"Conversation Mode: {selected_mode}")
    st.session_state.log_content.append("========================================")
    st.session_state.log_content.append("")
    logger.info(f"Initialized in-memory log for download: {log_base_filename} (Mode: '{selected_mode}')")
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        local_log_path = os.path.join(LOG_DIR, log_base_filename)
        # Use 'a' append mode maybe safer if init called multiple times? Though reset logic should handle it.
        # Sticking with 'w' based on reset logic.
        st.session_state.local_log_file_handle = open(local_log_path, 'w', encoding='utf-8')
        for line in st.session_state.log_content:
            st.session_state.local_log_file_handle.write(line + "\n")
        st.session_state.local_log_file_handle.flush()
        logger.info(f"Also writing log to local file: {local_log_path}")
    except Exception as e:
        logger.warning(f"Could not open local log file {log_base_filename}: {e}")
        st.session_state.local_log_file_handle = None
    return True

def write_log(message_dict: Dict[str, Any]):
    if 'log_content' not in st.session_state or st.session_state.log_content is None:
        return
    try:
        role = message_dict.get('role', 'system').upper()
        content = message_dict.get('content', '')
        log_line = ""
        # Handle specific system messages distinctly
        if role == 'SYSTEM':
             # Ensure content is a string before checking startswith
             content_str = str(content).strip() if content is not None else ""
             if content_str.startswith(("MODERATOR CONTEXT", "MODERATOR EVALUATION", "Error:")):
                 log_line = f"{content_str}" # Log moderator context/errors directly
             else:
                 # General system messages (like status updates if they were messages)
                 log_line = f"SYSTEM: {content_str}"
        elif role == 'USER':
            log_line = f"USER: {str(content)}"
        else: # Philosopher roles (Socrates, Confucius)
            log_line = f"{role}: {str(content)}"

        separator = "----------------------------------------"
        st.session_state.log_content.append(log_line)
        st.session_state.log_content.append(separator)
        if st.session_state.get('local_log_file_handle') and not st.session_state.local_log_file_handle.closed:
            try:
                st.session_state.local_log_file_handle.write(log_line + "\n")
                st.session_state.local_log_file_handle.write(separator + "\n")
                st.session_state.local_log_file_handle.flush()
            except Exception as e: logger.error(f"Error writing to local log file: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Error preparing log entry: {e}", exc_info=True)
        if 'current_status' in st.session_state and st.session_state.current_status != "Error writing to log.":
             st.session_state.current_status = "Error writing to log."; st.toast("Error writing to log.", icon="⚠️")

def close_log():
    if 'log_content' in st.session_state and st.session_state.log_content:
        # Ensure log_content is a list and check last element safely
        if isinstance(st.session_state.log_content, list) and st.session_state.log_content:
             # Check if the last log entry IS the end marker to avoid duplicates
             if not st.session_state.log_content[-1].strip().endswith("--- Log End ---"):
                  st.session_state.log_content.append("\n--- Log End ---")
        elif isinstance(st.session_state.log_content, list) and not st.session_state.log_content:
             # If list is empty, still add the end marker maybe? Or just leave empty. Leaving empty.
             pass

    if 'local_log_file_handle' in st.session_state and st.session_state.local_log_file_handle:
        if not st.session_state.local_log_file_handle.closed:
             log_filename = st.session_state.get('current_log_filename', 'Unknown Local Log File')
             try:
                 st.session_state.local_log_file_handle.write("\n--- Log file closed ---\n")
                 st.session_state.local_log_file_handle.close()
                 logger.info(f"Closed local log file: {log_filename}")
             except Exception as e: logger.error(f"Error closing local log file {log_filename}: {e}")
        st.session_state.local_log_file_handle = None


# --- Initialize Session State ---
default_app_values = {
    'messages': [], 'director_instance': None, 'current_status': "Ready.",
    'log_content': None, 'current_log_filename': None, 'local_log_file_handle': None,
    'show_monologue_cb': False, 'show_moderator_cb': True, 'bypass_moderator_cb': False,
    'starting_philosopher': 'Socrates', 'num_rounds': DEFAULT_NUM_ROUNDS,
    'conversation_mode': DEFAULT_CONVERSATION_MODE, 'run_conversation_flag': False,
    'conversation_completed': False,
    'prompt_overrides': {}
}
for key, default_value in default_app_values.items():
    if key not in st.session_state: st.session_state[key] = default_value

# Initialize Director instance once after authentication
if st.session_state.director_instance is None:
    try:
        st.session_state.director_instance = Director()
        logger.info("Director instance created successfully post-authentication.")
    except Exception as e:
        st.error(f"Error initializing Director post-authentication: {e}")
        logger.exception("Director initialization failed post-authentication.")
        st.stop()

# --- Render Authenticated UI ---
try:
    model_info = gui.get_model_info_from_config()
    gui.display_sidebar(model_info)
except Exception as e: st.error(f"Error rendering sidebar: {e}"); logger.exception("Error during sidebar rendering.")
try:
    gui.display_header()
    gui.display_conversation(st.session_state.messages)
except Exception as e: st.error(f"Error rendering main UI components: {e}"); logger.exception("Error during main UI rendering.")

# --- Display Internal Monologue (Conditionally) ---
if st.session_state.get('show_monologue_cb', False):
    with st.expander("Internal Monologue / Debug"):
        monologue_found = False
        # Check if messages is iterable and not None
        messages_to_check = st.session_state.get('messages')
        if isinstance(messages_to_check, list):
             for message in messages_to_check:
                 monologue = None
                 role = 'Unknown'
                 if isinstance(message, dict):
                      monologue = message.get('monologue')
                      role = message.get('role', 'System')
                 # Add checks for other potential message formats if necessary

                 if monologue:
                      monologue_found = True
                      st.markdown(f"**[{role}] Thought:**")
                      # Display monologue safely, converting to string
                      st.text(str(monologue)); st.divider()
        if not monologue_found: st.caption("No monologue entries found.")

# --- Display Status (New Method) ---
# Remove the old call: gui.display_status(st.session_state.get('current_status', 'Status unavailable.'))
# Add placeholder for the new status line (place it logically, e.g., before controls)
status_placeholder = st.empty()
# Update the placeholder with current status and timestamp
with status_placeholder.container():
    current_status_text = st.session_state.get('current_status', 'Status unavailable.')
    timestamp_str = datetime.datetime.now().strftime('%H:%M:%S')
    st.caption(f"[{timestamp_str}] {current_status_text}")
# --- End New Status Display ---


# --- Handle User Input (Authenticated) ---
prompt: Optional[str] = st.chat_input("Enter your initial question...")
if prompt:
    logger.info(f"User input received: '{prompt[:50]}...'")
    st.session_state.current_status = "Processing..." # Update status
    # --- Reset Logic ---
    st.session_state.messages = []
    st.session_state.conversation_completed = False
    st.session_state.log_content = None
    st.session_state.current_log_filename = None
    close_log()
    # --- End Reset Logic ---
    num_rounds_selected = st.session_state.get('num_rounds', DEFAULT_NUM_ROUNDS)
    starting_philosopher_selected = st.session_state.get('starting_philosopher', 'Socrates')
    selected_mode = st.session_state.get('conversation_mode', DEFAULT_CONVERSATION_MODE)
    logger.info(f"Starting new conversation with mode: {selected_mode}")
    if not initialize_log(num_rounds_selected):
        st.session_state.current_status = "Log initialization failed. Cannot proceed." # Update status
        st.rerun() # Rerun to show status update
    else:
        user_message: Dict[str, Any] = {"role": "user", "content": prompt, "monologue": None}
        st.session_state.messages.append(user_message)
        write_log(user_message)
        st.session_state.run_conversation_flag = True
        st.session_state.current_run_mode = selected_mode
        st.rerun() # Rerun to show "Processing..." status and trigger conversation


# --- Run Conversation if Flag is Set (Authenticated) ---
if st.session_state.get('run_conversation_flag', False):
    st.session_state.run_conversation_flag = False # Consume the flag
    if not st.session_state.messages:
         logger.error("Run conversation flag set, but message list is empty.")
         st.error("Cannot start conversation, initial prompt missing.")
         st.session_state.current_status = "Error: Initial prompt missing." # Update status
    else:
        initial_prompt = st.session_state.messages[0]['content']
        num_rounds_selected = st.session_state.get('num_rounds', DEFAULT_NUM_ROUNDS)
        starting_philosopher_selected = st.session_state.get('starting_philosopher', 'Socrates')
        bypass_moderator_mode = st.session_state.get('bypass_moderator_cb', False)
        run_moderated_flag = not bypass_moderator_mode
        current_mode = st.session_state.get('current_run_mode', DEFAULT_CONVERSATION_MODE)
        director = st.session_state.director_instance

        if director:
            try:
                # Update status before starting the potentially long operation
                st.session_state.current_status = f"Philosophers conferring ({current_mode} mode)..."
                # Use a spinner for visual feedback during the blocking call
                with st.spinner(f"Philosophers conferring ({current_mode} mode)..."):
                     logger.info(f"Calling Director: Mode='{current_mode}', Rounds={num_rounds_selected}, Starter='{starting_philosopher_selected}', Moderated={run_moderated_flag}")
                     generated_messages, final_status, success = director.run_conversation_streamlit(
                         initial_input=initial_prompt, num_rounds=num_rounds_selected,
                         starting_philosopher=starting_philosopher_selected, run_moderated=run_moderated_flag, mode=current_mode
                     )
                     logger.info(f"Director finished '{current_mode}' mode run. Success: {success}. Status: {final_status}")
                # Update status with the final result from the director
                st.session_state.current_status = final_status
                st.session_state.messages.extend(generated_messages) # Append new messages
                for msg in generated_messages: write_log(msg) # Log new messages
                if success: st.toast(f"Conversation completed ({current_mode} mode).", icon="✅"); st.session_state.conversation_completed = True
                else: st.toast(f"Conversation ended: {final_status}", icon="⚠️"); st.session_state.conversation_completed = True # Allow download even if ended with error
            except Exception as e:
                error_msg = f"An unexpected error occurred during conversation: {e}"
                st.error(error_msg); logger.exception(error_msg)
                st.session_state.current_status = "Critical error during conversation." # Update status
                st.session_state.conversation_completed = False # Don't allow download on critical failure
            finally:
                close_log() # Close logs after attempt
                if 'current_run_mode' in st.session_state: del st.session_state.current_run_mode # Clean up run-specific state
                st.rerun() # Rerun to display results/status/download button
        else:
            st.error("Director instance not available."); logger.error("Director instance is None, cannot run conversation.")
            st.session_state.current_status = "Error: Director not loaded." # Update status
            close_log()
            st.rerun() # Rerun to show status update


# --- Controls Below Conversation (Authenticated) ---
st.divider()
col1, col2 = st.columns([1, 1])
with col1:
    if st.button("Clear & Reset Conversation"):
        logger.info("Clear Conversation History button clicked.")
        st.session_state.messages = []
        st.session_state.current_status = "Ready." # Reset status
        st.session_state.log_content = None
        st.session_state.current_log_filename = None
        st.session_state.conversation_completed = False
        close_log()
        if 'run_conversation_flag' in st.session_state: del st.session_state.run_conversation_flag
        if 'current_run_mode' in st.session_state: del st.session_state.current_run_mode
        logger.info("Conversation history and log state cleared.")
        st.rerun() # Rerun to show "Ready" status and clear chat
with col2:
    # Download button logic remains unchanged
    if st.session_state.get('conversation_completed', False) and st.session_state.get('log_content'):
        log_filename_to_use = st.session_state.get('current_log_filename', 'conversation_log.txt')
        log_data = st.session_state.log_content
        if isinstance(log_data, list):
            log_data_string = "\n".join(log_data)
            try:
                st.download_button(
                    label="Download Conversation Log", data=log_data_string.encode('utf-8'),
                    file_name=log_filename_to_use, mime='text/plain'
                )
            except Exception as e:
                logger.error(f"Error creating download button: {e}")
                st.caption("Error creating download link.")
        else:
            logger.warning("Log content is not a list, cannot create download.")
            st.caption("Log data unavailable for download.")
    elif st.session_state.get('conversation_completed', False):
         st.caption("Log content not available for download.")


# --- Optional: Logout Button ---
st.sidebar.divider()
if st.sidebar.button("Logout"):
    auth.logout()
    st.rerun()