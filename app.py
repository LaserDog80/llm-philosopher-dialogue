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
DEFAULT_MODERATOR_CONTROL_MODE = 'AI Moderator' # 'AI Moderator' or 'User as Moderator (Guidance)'

# --- Log File Handling ---
def initialize_log(num_rounds_for_log: int) -> bool:
    log_base_filename = f"streamlit_conversation_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    st.session_state.current_log_filename = log_base_filename
    st.session_state.log_content = []
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    selected_mode = st.session_state.get('conversation_mode', DEFAULT_CONVERSATION_MODE)
    moderator_control = st.session_state.get('moderator_control_mode', DEFAULT_MODERATOR_CONTROL_MODE)
    bypass_moderator = st.session_state.get('bypass_moderator_cb', False)

    st.session_state.log_content.append(f"Streamlit Conversation Log - {timestamp}")
    st.session_state.log_content.append(f"Requested Rounds: {num_rounds_for_log}")
    st.session_state.log_content.append(f"Conversation Mode: {selected_mode}")
    if bypass_moderator:
        st.session_state.log_content.append(f"Moderation: Bypassed")
    else:
        st.session_state.log_content.append(f"Moderator Control: {moderator_control}")
    st.session_state.log_content.append("========================================")
    st.session_state.log_content.append("")
    logger.info(f"Initialized in-memory log for download: {log_base_filename} (Mode: '{selected_mode}', ModCtrl: '{moderator_control}', Bypass: {bypass_moderator})")
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        local_log_path = os.path.join(LOG_DIR, log_base_filename)
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
        # Attempt to re-initialize if log_content is None but should exist
        if st.session_state.get('conversation_started_for_log', False): # Add a flag to know if log should exist
             logger.warning("write_log called but log_content is None. Re-initializing log.")
             # This might be too aggressive, consider if this scenario is valid
             # initialize_log(st.session_state.get('num_rounds', DEFAULT_NUM_ROUNDS))
        else:
             logger.debug("write_log called but log not initialized or already closed. Skipping.")
             return

    try:
        role = message_dict.get('role', 'system').upper()
        content = message_dict.get('content', '')
        log_line = ""
        
        if role == 'SYSTEM':
             content_str = str(content).strip() if content is not None else ""
             if content_str.startswith(("MODERATOR CONTEXT", "MODERATOR EVALUATION", "Error:", "USER GUIDANCE FOR")):
                 log_line = f"{content_str}"
             else:
                 log_line = f"SYSTEM: {content_str}"
        elif role == 'USER': # This is the initial user prompt
            log_line = f"USER PROMPT: {str(content)}"
        else: # Philosopher roles
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
        if isinstance(st.session_state.log_content, list) and st.session_state.log_content:
             if not st.session_state.log_content[-1].strip().endswith("--- Log End ---"):
                  st.session_state.log_content.append("\n--- Log End ---")
        elif isinstance(st.session_state.log_content, list) and not st.session_state.log_content:
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
    st.session_state.conversation_started_for_log = False


# --- Initialize Session State ---
default_app_values = {
    'messages': [], 'director_instance': None, 'current_status': "Ready.",
    'log_content': None, 'current_log_filename': None, 'local_log_file_handle': None,
    'show_monologue_cb': False, 'show_moderator_cb': False, 'bypass_moderator_cb': False,
    'starting_philosopher': 'Socrates', 'num_rounds': DEFAULT_NUM_ROUNDS,
    'conversation_mode': DEFAULT_CONVERSATION_MODE, 'run_conversation_flag': False,
    'conversation_completed': False, 'conversation_started_for_log': False,
    'prompt_overrides': {},
    # New state for moderator control
    'moderator_control_mode': DEFAULT_MODERATOR_CONTROL_MODE,
    'awaiting_user_guidance': False,
    'ai_summary_for_guidance_input': None,
    'next_speaker_for_guidance': None,
    'director_resume_state': None
}
for key, default_value in default_app_values.items():
    if key not in st.session_state: st.session_state[key] = default_value

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

if st.session_state.get('show_monologue_cb', False):
    with st.expander("Internal Monologue / Debug"):
        monologue_found = False
        messages_to_check = st.session_state.get('messages')
        if isinstance(messages_to_check, list):
             for message in messages_to_check:
                 monologue = None; role = 'Unknown'
                 if isinstance(message, dict):
                      monologue = message.get('monologue'); role = message.get('role', 'System')
                 if monologue:
                      monologue_found = True; st.markdown(f"**[{role}] Thought:**"); st.text(str(monologue)); st.divider()
        if not monologue_found: st.caption("No monologue entries found.")

status_placeholder = st.empty()
with status_placeholder.container():
    current_status_text = st.session_state.get('current_status', 'Status unavailable.')
    timestamp_str = datetime.datetime.now().strftime('%H:%M:%S')
    st.caption(f"[{timestamp_str}] {current_status_text}")


# --- Determine Chat Input Prompt ---
chat_input_prompt_text = "Enter your initial question..."
if st.session_state.get('awaiting_user_guidance', False):
    next_speaker = st.session_state.get('next_speaker_for_guidance', 'the next philosopher')
    summary_for_user = st.session_state.get('ai_summary_for_guidance_input', '')
    if summary_for_user:
        # st.info(f"**Moderator Summary (for your guidance):**\n{summary_for_user}") # Display summary above input box
        # This is better handled by ensuring the summary is the last message in display_conversation
        pass
    chat_input_prompt_text = f"Enter your GUIDANCE for {next_speaker} (or type 'auto' for AI guidance this turn):"

# --- Handle User Input (Initial Prompt or User Guidance) ---
prompt: Optional[str] = st.chat_input(chat_input_prompt_text, key="main_chat_input")

if prompt:
    if st.session_state.get('awaiting_user_guidance', False):
        # --- This is User-Provided Guidance ---
        logger.info(f"User guidance received for {st.session_state.get('next_speaker_for_guidance', 'N/A')}: '{prompt[:50]}...'")
        st.session_state.current_status = "Processing your guidance..."
        
        user_guidance_message_content = f"USER GUIDANCE FOR {st.session_state.next_speaker_for_guidance}:\n{prompt}"
        if prompt.strip().lower() == "auto":
            user_guidance_message_content = f"SYSTEM: User opted for AI guidance for {st.session_state.next_speaker_for_guidance} this turn."
            # The Director will use the AI's original guidance stored in resume_state
        
        user_guidance_message: Dict[str, Any] = {"role": "system", "content": user_guidance_message_content, "monologue": None}
        st.session_state.messages.append(user_guidance_message) # Add user guidance to chat
        write_log(user_guidance_message)

        st.session_state.awaiting_user_guidance = False # Consume this state for now
        
        # Call Director to resume
        director = st.session_state.director_instance
        if director and st.session_state.director_resume_state:
            try:
                current_mode_resuming = st.session_state.director_resume_state.get('mode', DEFAULT_CONVERSATION_MODE)
                with st.spinner(f"Philosophers conferring ({current_mode_resuming} mode) with your guidance..."):
                    logger.info(f"Calling Director to resume with user guidance. Mode='{current_mode_resuming}'")
                    
                    # Pass the actual prompt, Director will know if it's 'auto'
                    gen_msgs, final_stat, success, resume_state, guidance_data = director.resume_conversation_streamlit(
                        st.session_state.director_resume_state,
                        user_provided_guidance=prompt # Pass 'auto' if user typed it
                    )
                    logger.info(f"Director resumed. Success: {success}. Status: {final_stat}")

                st.session_state.current_status = final_stat
                st.session_state.messages.extend(gen_msgs) # Add new messages from resumed turn
                for msg in gen_msgs: write_log(msg)

                if final_stat == "WAITING_FOR_USER_GUIDANCE":
                    st.session_state.awaiting_user_guidance = True
                    st.session_state.ai_summary_for_guidance_input = guidance_data['ai_summary']
                    st.session_state.next_speaker_for_guidance = guidance_data['next_speaker_name']
                    st.session_state.director_resume_state = resume_state
                    st.session_state.current_status = f"Waiting for your guidance for {st.session_state.next_speaker_for_guidance}..."
                elif success:
                    st.toast(f"Conversation continued ({current_mode_resuming} mode).", icon="✅")
                    st.session_state.conversation_completed = True # Or partial completion
                    st.session_state.director_resume_state = None
                    close_log()
                else: # Error or non-success completion
                    st.toast(f"Conversation ended: {final_stat}", icon="⚠️")
                    st.session_state.conversation_completed = True
                    st.session_state.director_resume_state = None
                    close_log()

            except Exception as e:
                error_msg = f"An unexpected error occurred during conversation resume: {e}"
                st.error(error_msg); logger.exception(error_msg)
                st.session_state.current_status = "Critical error during conversation resume."
                st.session_state.conversation_completed = False
                st.session_state.director_resume_state = None
                close_log()
            finally:
                if final_stat != "WAITING_FOR_USER_GUIDANCE": # Only clear if not waiting for more input
                    if 'current_run_mode' in st.session_state: del st.session_state.current_run_mode
                st.rerun()
        else:
            st.error("Error: Director or resume state not available. Cannot resume.")
            logger.error("Director or resume state missing, cannot resume user-guided conversation.")
            st.session_state.current_status = "Error: Cannot resume conversation."
            st.session_state.director_resume_state = None
            close_log()
            st.rerun()

    else:
        # --- This is an Initial User Prompt ---
        logger.info(f"User input received: '{prompt[:50]}...'")
        st.session_state.current_status = "Processing..."
        # --- Reset Logic for new conversation ---
        st.session_state.messages = []
        st.session_state.conversation_completed = False
        st.session_state.log_content = None
        st.session_state.current_log_filename = None
        st.session_state.awaiting_user_guidance = False # Crucial reset
        st.session_state.ai_summary_for_guidance_input = None
        st.session_state.next_speaker_for_guidance = None
        st.session_state.director_resume_state = None
        close_log() 
        # --- End Reset Logic ---

        num_rounds_selected = st.session_state.get('num_rounds', DEFAULT_NUM_ROUNDS)
        selected_mode = st.session_state.get('conversation_mode', DEFAULT_CONVERSATION_MODE)
        
        st.session_state.conversation_started_for_log = True # Mark that log should be active
        if not initialize_log(num_rounds_selected):
            st.session_state.current_status = "Log initialization failed. Cannot proceed."
            st.rerun()
        else:
            user_message: Dict[str, Any] = {"role": "user", "content": prompt, "monologue": None}
            st.session_state.messages.append(user_message)
            write_log(user_message)
            st.session_state.run_conversation_flag = True
            st.session_state.current_run_mode = selected_mode # For the Director call
            st.rerun()


# --- Run Conversation if Flag is Set (Initial Start) ---
if st.session_state.get('run_conversation_flag', False) and not st.session_state.get('awaiting_user_guidance', False) :
    st.session_state.run_conversation_flag = False # Consume the flag
    if not st.session_state.messages:
         logger.error("Run conversation flag set, but message list is empty.")
         st.error("Cannot start conversation, initial prompt missing.")
         st.session_state.current_status = "Error: Initial prompt missing."
    else:
        initial_prompt = st.session_state.messages[0]['content']
        num_rounds_selected = st.session_state.get('num_rounds', DEFAULT_NUM_ROUNDS)
        starting_philosopher_selected = st.session_state.get('starting_philosopher', 'Socrates')
        bypass_moderator_mode = st.session_state.get('bypass_moderator_cb', False)
        run_moderated_flag = not bypass_moderator_mode
        
        # Get moderator control type
        moderator_ctrl_mode_display = st.session_state.get('moderator_control_mode', DEFAULT_MODERATOR_CONTROL_MODE)
        moderator_type_for_director = 'ai'
        if moderator_ctrl_mode_display == 'User as Moderator (Guidance)':
            moderator_type_for_director = 'user_guidance'
        
        if bypass_moderator_mode: # Bypass overrides user guidance mode for director logic
            moderator_type_for_director = 'ai' # effectively, as it won't be called.

        current_mode = st.session_state.get('current_run_mode', DEFAULT_CONVERSATION_MODE)
        director = st.session_state.director_instance

        if director:
            try:
                st.session_state.current_status = f"Philosophers conferring ({current_mode} mode)..."
                with st.spinner(f"Philosophers conferring ({current_mode} mode)..."):
                     logger.info(f"Calling Director: Mode='{current_mode}', Rounds={num_rounds_selected}, Starter='{starting_philosopher_selected}', Moderated={run_moderated_flag}, ModCtrl='{moderator_type_for_director}'")
                     
                     generated_messages, final_status, success, director_resume_state, data_for_user_guidance = director.run_conversation_streamlit(
                         initial_input=initial_prompt, num_rounds=num_rounds_selected,
                         starting_philosopher=starting_philosopher_selected, 
                         run_moderated=run_moderated_flag, 
                         mode=current_mode,
                         moderator_type=moderator_type_for_director
                     )
                     logger.info(f"Director finished initial run. Success: {success}. Status: {final_status}")
                
                st.session_state.current_status = final_status
                st.session_state.messages.extend(generated_messages)
                for msg in generated_messages: write_log(msg)

                if final_status == "WAITING_FOR_USER_GUIDANCE":
                    st.session_state.awaiting_user_guidance = True
                    st.session_state.ai_summary_for_guidance_input = data_for_user_guidance['ai_summary']
                    st.session_state.next_speaker_for_guidance = data_for_user_guidance['next_speaker_name']
                    st.session_state.director_resume_state = director_resume_state
                    st.session_state.current_status = f"Waiting for your guidance for {st.session_state.next_speaker_for_guidance}..."
                    # Do not close log yet
                elif success:
                    st.toast(f"Conversation completed ({current_mode} mode).", icon="✅"); 
                    st.session_state.conversation_completed = True
                    st.session_state.director_resume_state = None # Clear resume state
                    close_log()
                else: 
                    st.toast(f"Conversation ended: {final_status}", icon="⚠️")
                    st.session_state.conversation_completed = True 
                    st.session_state.director_resume_state = None # Clear resume state
                    close_log()

            except Exception as e:
                error_msg = f"An unexpected error occurred during conversation: {e}"
                st.error(error_msg); logger.exception(error_msg)
                st.session_state.current_status = "Critical error during conversation."
                st.session_state.conversation_completed = False
                st.session_state.director_resume_state = None
                close_log()
            finally:
                # Clean up run-specific state if not waiting for user
                if final_status != "WAITING_FOR_USER_GUIDANCE":
                    if 'current_run_mode' in st.session_state: del st.session_state.current_run_mode
                st.rerun()
        else:
            st.error("Director instance not available."); logger.error("Director instance is None, cannot run conversation.")
            st.session_state.current_status = "Error: Director not loaded."
            close_log()
            st.rerun()


# --- Controls Below Conversation (Authenticated) ---
st.divider()
col1, col2 = st.columns([1, 1])
with col1:
    if st.button("Clear & Reset Conversation"):
        logger.info("Clear Conversation History button clicked.")
        st.session_state.messages = []
        st.session_state.current_status = "Ready."
        st.session_state.log_content = None
        st.session_state.current_log_filename = None
        st.session_state.conversation_completed = False
        st.session_state.awaiting_user_guidance = False # Reset this
        st.session_state.ai_summary_for_guidance_input = None
        st.session_state.next_speaker_for_guidance = None
        st.session_state.director_resume_state = None
        close_log()
        if 'run_conversation_flag' in st.session_state: del st.session_state.run_conversation_flag
        if 'current_run_mode' in st.session_state: del st.session_state.current_run_mode
        logger.info("Conversation history and log state cleared.")
        st.rerun()
with col2:
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