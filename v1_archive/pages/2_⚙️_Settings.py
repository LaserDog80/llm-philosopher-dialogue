# pages/2_⚙️_Settings.py

import streamlit as st
import os
import logging

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
    # Import ONLY the function needed to load default text
    from llm_loader import load_default_prompt_text
except ImportError:
    st.error("Could not import `load_default_prompt_text` from `llm_loader`. Make sure it's accessible.")
    st.stop()

# Configure logger for this page
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - SettingsPage - %(levelname)s - %(message)s')

# --- Page Configuration ---
# st.set_page_config(page_title="Settings", layout="wide") # Called once in app.py
st.title("⚙️ AI Persona Prompt Settings")
st.caption("View and override the default system prompts for each AI persona and conversation mode.")

# --- Constants ---
PERSONAS = ["Socrates", "Confucius", "Moderator"]
MODES = ["Philosophy", "Bio"] # Modes available for override
DEFAULT_FALLBACK_PROMPT_TEXT = "Default prompt file not found or could not be read."


# --- Initialize Override State and Editor Content State ---
st.session_state.setdefault('prompt_overrides', {})
# New state to manage what the editor should display
st.session_state.setdefault('editor_content_state', {})
# State to track the last processed selection to manage editor updates
st.session_state.setdefault('last_processed_key_settings', None)


# --- UI Selectors ---
col1, col2 = st.columns(2)
with col1:
    selected_persona = st.selectbox(
        "Select Persona:",
        PERSONAS,
        key="settings_persona_select"
    )
with col2:
    mode_map = {mode: mode.lower() for mode in MODES}
    selected_mode_display = st.selectbox(
        "Select Mode:",
        MODES, # Show user-friendly names
        key="settings_mode_select"
    )
    selected_mode_key = mode_map[selected_mode_display] # Get the lowercase key

persona_key = selected_persona.lower()
# Key representing the current persona/mode selection
current_selection_key = f"{persona_key}_{selected_mode_key}"
# Key for the text area widget itself
text_area_key = f"prompt_editor_{current_selection_key}"

# --- Logic to Update Editor Content State when Selection Changes ---
# This runs *before* the text_area is rendered
if st.session_state.last_processed_key_settings != current_selection_key:
    logger.debug(f"Selection changed to {current_selection_key}. Updating editor content state.")
    prompt_source = ""
    # Check if an override exists for this combination
    if current_selection_key in st.session_state.prompt_overrides:
        prompt_for_editor = st.session_state.prompt_overrides[current_selection_key]
        prompt_source = "User Override"
    else:
        # No override, load the default from file
        default_prompt = load_default_prompt_text(persona_key, selected_mode_key)
        if default_prompt is not None:
            prompt_for_editor = default_prompt
            prompt_source = "Default (from file)"
        else:
            prompt_for_editor = DEFAULT_FALLBACK_PROMPT_TEXT
            prompt_source = "Default (Not Found!)"

    # Set the intermediate state that the text_area will read from
    st.session_state.editor_content_state[current_selection_key] = prompt_for_editor
    st.session_state.last_processed_key_settings = current_selection_key
    # # <<< REMOVED THIS LINE >>>
    # # st.session_state[text_area_key] = prompt_for_editor # Also sync the actual widget state key initially
    logger.info(f"Displaying prompt for {current_selection_key}. Source: {prompt_source}")
    # Display the source info message (could be moved below the editor if preferred)
    st.info(f"Displaying prompt for **{selected_persona}** ({selected_mode_display} Mode). Source: **{prompt_source}**")


# --- Prompt Editor ---
# Ensure the editor content state for the current key exists (redundant due to above but safe)
st.session_state.editor_content_state.setdefault(current_selection_key, "")

# Text Area now reads its initial value from the intermediate state.
# User edits directly modify st.session_state[text_area_key] via Streamlit's handling.
edited_prompt_value = st.text_area(
    "System Prompt:",
    # Read the value from our managed intermediate state
    value=st.session_state.editor_content_state[current_selection_key],
    height=300,
    key=text_area_key, # Widget state associated with this key
    help="Edit the prompt below. Click 'Save Override' to apply your changes for future sessions."
)

# --- Action Buttons ---
col_btn1, col_btn2, col_btn3 = st.columns(3)

with col_btn1:
    # Save button reads the value directly from the text_area's state key
    if st.button("💾 Save Override", key=f"save_{current_selection_key}"):
        # Read the current value directly from the text area state key
        current_editor_text = st.session_state.get(text_area_key, "")
        st.session_state.prompt_overrides[current_selection_key] = current_editor_text
        # Update the intermediate state to match what was saved
        st.session_state.editor_content_state[current_selection_key] = current_editor_text
        logger.info(f"Saved override for {current_selection_key}")
        st.toast(f"✅ Override saved for {selected_persona} ({selected_mode_display})!", icon="💾")
        # Rerun needed to update the "Source:" info message
        st.rerun()

with col_btn2:
    # Load default button updates the intermediate state, then reruns
    if st.button("🔄 Load Default", key=f"load_{current_selection_key}"):
        default_prompt = load_default_prompt_text(persona_key, selected_mode_key)
        loaded_text = default_prompt if default_prompt is not None else DEFAULT_FALLBACK_PROMPT_TEXT
        # Update the intermediate state variable ONLY
        st.session_state.editor_content_state[current_selection_key] = loaded_text
        logger.info(f"Set editor content state to default for {current_selection_key}")
        if default_prompt is not None:
            st.toast("🔄 Default prompt loaded into editor.", icon="🔄")
        else:
             st.error(f"Could not load default prompt for {selected_persona} ({selected_mode_display}). File might be missing.")
        # Rerun will cause the text_area to read the updated intermediate state
        st.rerun()

with col_btn3:
    # Clear override button removes override, updates intermediate state, then reruns
    if current_selection_key in st.session_state.prompt_overrides:
        if st.button("❌ Clear Override", key=f"clear_{current_selection_key}"):
            # 1. Delete the actual override
            del st.session_state.prompt_overrides[current_selection_key]
            logger.info(f"Cleared override for {current_selection_key}")

            # 2. Load the default prompt to update the editor display on next run
            default_prompt_after_clear = load_default_prompt_text(persona_key, selected_mode_key)
            loaded_text = default_prompt_after_clear if default_prompt_after_clear is not None else DEFAULT_FALLBACK_PROMPT_TEXT
            # Update the intermediate state variable ONLY
            st.session_state.editor_content_state[current_selection_key] = loaded_text

            # 3. Show toast and rerun
            st.toast(f"🗑️ Override cleared for {selected_persona} ({selected_mode_display}). Using default.", icon="🗑️")
            st.rerun()
    else:
        # Display disabled button if no override exists
        st.button("❌ Clear Override", key=f"clear_{current_selection_key}", disabled=True, help="No override saved for this combination.")

st.divider()
st.caption("Changes saved here will persist for your current session and affect both the main dialogue and the Direct AI Chat.")
st.caption("Default prompts are loaded directly from the `.txt` files in the `prompts` directory.")

# Display current overrides (optional debug view)
with st.expander("View All Current Overrides"):
    st.write(st.session_state.get('prompt_overrides', {}))