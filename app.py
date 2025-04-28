# Filename: app.py

import streamlit as st
import os
import datetime
import json
import logging

# --- Local Imports ---
try:
    from direction import Director
    import gui
except ImportError as e:
    logging.error(f"Failed to import local modules (direction.py or gui.py): {e}")
    st.error(f"Critical Error: Failed to import local modules. Details: {e}")
    st.stop()

# --- Configuration ---
LOG_DIR = "logs"
# Log filename is now dynamic based on timestamp
# Default rounds - will be overwritten by UI selection if available
DEFAULT_NUM_ROUNDS = 3

logging.basicConfig(level=logging.INFO, format='%(asctime)s - APP - %(levelname)s - %(message)s')

# --- Log File Handling (functions remain the same) ---
def initialize_log(num_rounds_for_log):
    """Creates log dir and opens file, stores handle in session state."""
    log_filename = os.path.join(LOG_DIR, f"streamlit_conversation_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        handle = open(log_filename, 'w', encoding='utf-8')
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        handle.write(f"Streamlit Conversation Log - {timestamp}\n")
        handle.write(f"Requested Rounds: {num_rounds_for_log}\n") # Log selected rounds
        handle.write("========================================\n\n")
        st.session_state.log_file_handle = handle
        st.session_state.current_log_filename = log_filename # Store filename if needed
        logging.info(f"Initialized log file: {log_filename}")
        return True
    except IOError as e:
        st.error(f"Failed to initialize log file: {e}")
        logging.error(f"Failed to initialize log file {log_filename}: {e}")
        st.session_state.log_file_handle = None
        return False

def write_log(message_dict):
    """Writes main content to the log file."""
    if 'log_file_handle' in st.session_state and st.session_state.log_file_handle:
        try:
            role = message_dict.get('role', 'system').upper()
            content = message_dict.get('content', '')
            st.session_state.log_file_handle.write(f"{role}: {content}\n")
            st.session_state.log_file_handle.write("----------------------------------------\n")
            st.session_state.log_file_handle.flush()
        except Exception as e:
            logging.error(f"Error writing to log file: {e}")
            st.session_state.current_status = "Error writing to log file."

def close_log():
    """Closes the log file if open."""
    if 'log_file_handle' in st.session_state and st.session_state.log_file_handle:
        log_filename = st.session_state.get('current_log_filename', 'Unknown Log File')
        try:
            st.session_state.log_file_handle.write("\n--- Log file closed ---\n")
            st.session_state.log_file_handle.close()
            logging.info(f"Closed log file: {log_filename}")
        except Exception as e:
             logging.error(f"Error closing log file {log_filename}: {e}")
        st.session_state.log_file_handle = None
        st.session_state.current_log_filename = None

# --- Streamlit App ---

# Initialize session state variables
if 'messages' not in st.session_state: st.session_state.messages = []
if 'director_instance' not in st.session_state:
    try: st.session_state.director_instance = Director()
    except ImportError as e: st.error(f"Failed Director init: {e}"); st.stop()
if 'current_status' not in st.session_state: st.session_state.current_status = "Ready."
if 'log_file_handle' not in st.session_state: st.session_state.log_file_handle = None
if 'show_monologue_cb' not in st.session_state: st.session_state.show_monologue_cb = False
# Initialize state for new controls (use defaults from gui.py if not set)
if 'starting_philosopher' not in st.session_state: st.session_state.starting_philosopher = 'Socrates'
if 'num_rounds' not in st.session_state: st.session_state.num_rounds = DEFAULT_NUM_ROUNDS


# --- Render UI ---
model_info = gui.get_model_info_from_config()
# Sidebar now renders the new controls
gui.display_sidebar(model_info)
gui.display_header()
gui.display_conversation(st.session_state.messages) # Display chat history

# --- Display Internal Monologue (Conditionally) ---
if st.session_state.get('show_monologue_cb', False):
    with st.expander("Internal Monologue / Debug"):
        # (Logic identical to previous version)
        monologue_found = False
        for message in st.session_state.messages:
            monologue = message.get('monologue')
            if monologue:
                monologue_found = True; role = message.get('role', 'System')
                st.markdown(f"**[{role}] Thought:**"); st.text(monologue); st.divider()
        if not monologue_found: st.caption("No monologue entries found.")

# Display Status
gui.display_status(st.session_state.current_status)

# --- Handle User Input ---
prompt = st.chat_input("Enter your initial question...")

if prompt:
    logging.info(f"User input received: {prompt}")
    st.session_state.current_status = "Processing..."

    # Get config from session state (set by widgets in gui.py)
    num_rounds_selected = st.session_state.get('num_rounds', DEFAULT_NUM_ROUNDS)
    starting_philosopher_selected = st.session_state.get('starting_philosopher', 'Socrates')

    # Initialize log file (pass selected rounds for logging)
    if st.session_state.log_file_handle is None:
        if not initialize_log(num_rounds_selected):
            st.session_state.current_status = "Log initialization failed. Cannot proceed."
            st.rerun()

    # Store user message
    user_message = {"role": "user", "content": prompt, "monologue": None}
    st.session_state.messages.append(user_message)
    write_log(user_message)

    # --- Call the Director ---
    director = st.session_state.director_instance
    if director:
        try:
            with st.spinner("Philosophers and Moderator are conferring..."):
                 logging.info(f"Calling Director with {num_rounds_selected} rounds, starting with {starting_philosopher_selected}.")
                 # Pass selected options to the director
                 generated_messages, final_status, success = director.run_conversation_streamlit(
                     initial_input=prompt,
                     num_rounds=num_rounds_selected,
                     starting_philosopher=starting_philosopher_selected # Pass the selected starter
                 )
                 logging.info(f"Director finished. Success: {success}. Status: {final_status}")

            # Process results
            st.session_state.current_status = final_status
            st.session_state.messages.extend(generated_messages)

            # Log generated messages
            for msg in generated_messages: write_log(msg)

            if success: st.toast(f"Conversation completed.", icon="✅")
            else: st.toast(f"Conversation ended: {final_status}", icon="⚠️")
            close_log()
            st.rerun() # Update display

        except Exception as e:
            error_msg = f"An unexpected error occurred: {e}"
            st.error(error_msg); logging.exception(error_msg)
            st.session_state.current_status = "Critical error."
            close_log()
    else:
        st.error("Director instance not available."); logging.error("Director instance None.")
        st.session_state.current_status = "Error: Director not loaded."


# --- Clear History Button ---
st.divider()
if st.button("Clear Conversation History"):
    st.session_state.messages = []
    st.session_state.current_status = "Ready."
    # Keep UI selections or reset them? Let's keep them for now.
    # st.session_state.num_rounds = DEFAULT_NUM_ROUNDS
    # st.session_state.starting_philosopher = 'Socrates'
    # st.session_state.show_monologue_cb = False
    close_log()
    logging.info("Conversation history cleared.")
    st.rerun()