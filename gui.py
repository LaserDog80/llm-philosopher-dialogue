# Filename: gui.py

import streamlit as st
import json
import logging # Added for potential error logging

# Configure logging for the GUI module
logging.basicConfig(level=logging.INFO, format='%(asctime)s - GUI - %(levelname)s - %(message)s')

def display_header():
    """Displays the main title of the application."""
    st.title("Philosopher Dialogue (Streamlit Edition)")

def get_model_info_from_config(config_path="llm_config.json"):
    """Loads model names from config file for display."""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        # Provide default 'Unknown' if a persona or model_name is missing
        # Note: Model names are still useful even if prompts are dynamic
        return {
            'Socrates': config.get('socrates', {}).get('model_name', 'Unknown'),
            'Confucius': config.get('confucius', {}).get('model_name', 'Unknown'),
            'Moderator': config.get('moderator', {}).get('model_name', 'Unknown'),
        }
    except FileNotFoundError:
        warning_msg = f"Config file not found at {config_path}. Cannot display model info."
        st.warning(warning_msg)
        logging.warning(warning_msg)
        return {'Socrates': 'Unknown', 'Confucius': 'Unknown', 'Moderator': 'Unknown'}
    except json.JSONDecodeError as e:
        error_msg = f"Error decoding JSON from {config_path}: {e}"
        st.error(error_msg)
        logging.error(error_msg)
        return {'Socrates': 'Unknown', 'Confucius': 'Unknown', 'Moderator': 'Unknown'}
    except Exception as e:
        error_msg = f"Error loading model info from config {config_path}: {e}"
        st.error(error_msg)
        logging.error(error_msg, exc_info=True) # Log full traceback
        return {'Socrates': 'Unknown', 'Confucius': 'Unknown', 'Moderator': 'Unknown'}


def display_sidebar(model_info):
    """Displays information and controls in the sidebar."""
    with st.sidebar:
        st.header("Configuration")

        # --- Mode Selection ---
        st.radio(
            "Conversation Mode:",
            # Use lowercase, underscore for keys used in filenames
            options=['Philosophy', 'Bio'],
            # Map display names to internal keys
            format_func=lambda x: "Philosophical Mode" if x == 'Philosophy' else "Biographical Mode",
            key='conversation_mode', # Unique key for session state
            index=0, # Default to Philosophical
            horizontal=True,
            help="Select the conversation topic focus."
        )
        # --- End Mode Selection ---

        st.caption("Model Instances:")
        st.markdown(f"**Socrates:** `{model_info.get('Socrates', 'Unknown')}`")
        st.markdown(f"**Confucius:** `{model_info.get('Confucius', 'Unknown')}`")
        st.markdown(f"**Moderator:** `{model_info.get('Moderator', 'Unknown')}`")

        st.divider()

        st.radio(
            "Starting Philosopher:",
            ('Socrates', 'Confucius'),
            key='starting_philosopher',
            horizontal=True,
            index=0 # Default to Socrates
        )

        st.number_input(
            "Number of Rounds:",
            min_value=1,
            max_value=10,
            step=1,
            key='num_rounds',
            help="One round includes one response from each philosopher."
        )

        st.divider()
        st.caption("Display Options:")

        st.checkbox(
            "Bypass Moderator (Direct Dialogue)",
            key='bypass_moderator_cb',
            value=st.session_state.get('bypass_moderator_cb', False),
            help="If checked, philosophers respond directly without moderator summaries/guidance."
        )

        st.checkbox(
            "Show Moderator Context",
            key='show_moderator_cb',
            value=st.session_state.get('show_moderator_cb', False), 
            help="Show/hide the Moderator's SUMMARY/GUIDANCE blocks in the chat."
        )

        st.checkbox(
            "Show Internal Monologue",
            key='show_monologue_cb',
            value=st.session_state.get('show_monologue_cb', False),
            help="Show/hide the <think> blocks extracted from LLM responses."
        )


def display_conversation(messages):
    """Displays the chat messages, conditionally hiding moderator context."""
    show_moderator = st.session_state.get('show_moderator_cb', True)

    if not messages:
        st.info("Start the conversation by entering a question below.")
        return

    for message in messages:
        role = message.get("role", "system")
        content = message.get('content', '')

        # --- Refined check for moderator system messages ---
        # Check role first, then content prefix for efficiency
        is_moderator_system_message = (role.lower() == 'system' and
                                      isinstance(content, str) and
                                      content.strip().startswith(("MODERATOR CONTEXT", "MODERATOR EVALUATION")))

        if is_moderator_system_message and not show_moderator:
            continue
        # --- End Refined Check ---

        display_role = "user" if role.lower() == "user" else "assistant"
        avatar = "👤" if display_role=="user" else "🤖"

        with st.chat_message(display_role, avatar=avatar):
             # Add bold prefix only for actual philosopher roles
             prefix = f"**{role}:**\n" if display_role == "assistant" and role.lower() not in ['system', 'user'] else ""
             # Ensure content is string before displaying
             display_content = str(content) if content is not None else ""
             st.markdown(f"{prefix}{display_content}")

# --- REMOVED display_status function ---
# def display_status(status_text):
#    """Displays the current application status, handling None."""
#    status_display = status_text if status_text is not None else "Status unavailable."
#    st.caption(f"Status: {status_display}")