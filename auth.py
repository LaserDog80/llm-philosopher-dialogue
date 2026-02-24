# Filename: auth.py

import streamlit as st
import os
import logging
# Note: load_dotenv() is called in app.py before this is likely imported,
# so environment variables should be available.

# Configure logger for this module
logger = logging.getLogger(__name__)

# --- Password Configuration (Internal to this module) ---

# Initialize password variable
_correct_password_value = None
_password_source = None

# 1. Try Streamlit secrets
try:
    if hasattr(st, 'secrets') and "app_password" in st.secrets:
        _correct_password_value = st.secrets["app_password"]
        _password_source = "Streamlit secrets"
except Exception as e:
    logging.warning(f"Could not access Streamlit secrets: {e}")


# 2. Try environment variables if not found in secrets
if _correct_password_value is None:
    _correct_password_value = os.environ.get("APP_PASSWORD")
    if _correct_password_value:
        _password_source = "Environment variable (.env or system)"

# 3. Log result or handle missing password
if _correct_password_value:
    logger.info(f"Authentication password loaded successfully from: {_password_source}")
else:
    logger.error("CRITICAL: No password configured via Streamlit secrets or APP_PASSWORD environment variable.")
    # We won't display st.error here, as check_password will handle UI interaction
    # Setting password to None will cause check_password to fail safely below if called.

# Store the loaded password in a module-level variable (internal use)
CORRECT_PASSWORD = _correct_password_value


# --- Authentication Functions ---

def check_password():
    """
    Checks if user is authenticated. If not, displays password prompt.
    Returns True if authenticated, False otherwise.
    Handles the case where CORRECT_PASSWORD failed to load.
    """
    # If already authenticated, return True
    if st.session_state.get("authenticated", False):
        return True

    # Check if password was loaded correctly
    if CORRECT_PASSWORD is None:
         st.error("Application Security Error: Password configuration is missing. Cannot proceed.")
         return False # Stop execution flow

    # Show password input form
    st.title("🔒 Philosopher Dialogue Access")
    st.write("Please enter the password to continue.")
    password_input = st.text_input("Password:", type="password", key="password_input")
    login_button = st.button("Login", key="login_button")

    if login_button:
        if password_input == CORRECT_PASSWORD:
            st.session_state.authenticated = True
            st.rerun() # Rerun to reflect authenticated state
        elif password_input:
            st.error("😕 Incorrect password. Please try again.")
            st.session_state.authenticated = False
        else:
            st.warning("Please enter the password.")
            st.session_state.authenticated = False

    # Return current (potentially updated) authentication status
    # It will be False until the rerun happens after successful login
    return st.session_state.get("authenticated", False)

def is_authenticated():
    """Simple check if the user is marked as authenticated in session state."""
    return st.session_state.get("authenticated", False)

def logout():
    """Clears authentication status and known session state variables."""
    st.session_state.authenticated = False

    # Clear known application state variables
    keys_to_clear = [
        'messages', 'director_instance', 'current_status', 'log_content',
        'current_log_filename', 'local_log_file_handle', 'show_monologue_cb',
        'show_moderator_cb', 'bypass_moderator_cb', 'starting_philosopher',
        'num_rounds', 'conversation_mode', 'run_conversation_flag',
        'conversation_completed', 'prompt_overrides', 'current_run_mode',
        # Add keys from other pages if necessary
        'debug_chat_persona', 'debug_messages', 'debug_llm',
        'debug_system_prompt', 'current_debug_config_key',
        'settings_persona_select', 'settings_mode_select',
        # New keys for moderator control
        'moderator_control_mode', 'awaiting_user_guidance',
        'ai_summary_for_guidance_input', 'next_speaker_for_guidance',
        'director_resume_state'
    ]
    # Also clear potentially dynamic keys like the prompt editor
    # Safer approach: iterate and remove known keys vs clearing all
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]

    # Optionally clear dynamic text area keys if pattern is known (e.g., starts with 'prompt_editor_')
    dynamic_keys = [k for k in st.session_state if k.startswith('prompt_editor_') or k.startswith('sp_') or k.startswith('debug_transcript_text')]
    for key in dynamic_keys:
         if key in st.session_state:
             del st.session_state[key]

    # Clear password input field just in case
    if 'password_input' in st.session_state:
        del st.session_state['password_input']


    logger.info("User logged out, session state cleared.")
    # Rerun should be called in the page script after calling logout()