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
        return {
            'Socrates': config.get('socrates', {}).get('model_name', 'Unknown'),
            'Confucius': config.get('confucius', {}).get('model_name', 'Unknown'),
            'Moderator': config.get('moderator', {}).get('model_name', 'Unknown'),
            'Translator': config.get('translator', {}).get('model_name', 'Unknown'), # Added this line
        }
    except FileNotFoundError:
        warning_msg = f"Config file not found at {config_path}. Cannot display model info."
        st.warning(warning_msg)
        logging.warning(warning_msg)
        return {'Socrates': 'Unknown', 'Confucius': 'Unknown', 'Moderator': 'Unknown', 'Translator': 'Unknown'}
    except json.JSONDecodeError as e:
        error_msg = f"Error decoding JSON from {config_path}: {e}"
        st.error(error_msg)
        logging.error(error_msg)
        return {'Socrates': 'Unknown', 'Confucius': 'Unknown', 'Moderator': 'Unknown', 'Translator': 'Unknown'}
    except Exception as e:
        error_msg = f"Error loading model info from config {config_path}: {e}"
        st.error(error_msg)
        logging.error(error_msg, exc_info=True) # Log full traceback
        return {'Socrates': 'Unknown', 'Confucius': 'Unknown', 'Moderator': 'Unknown', 'Translator': 'Unknown'}


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
        st.divider()

        # --- Moderator Control Mode ---
        st.radio(
            "Moderator Control:",
            options=['AI Moderator', 'User as Moderator (Guidance)'],
            format_func=lambda x: x, # Display names are fine
            key='moderator_control_mode',
            index=0, # Default to AI Moderator
            horizontal=True,
            help="Choose who provides guidance: AI or User. AI always provides summary."
        )
        # --- End Moderator Control Mode ---

        st.caption("Model Instances:")
        st.markdown(f"**Socrates:** `{model_info.get('Socrates', 'Unknown')}`")
        st.markdown(f"**Confucius:** `{model_info.get('Confucius', 'Unknown')}`")
        st.markdown(f"**Moderator:** `{model_info.get('Moderator', 'Unknown')}`")
        st.markdown(f"**Translator:** `{model_info.get('Translator', 'Unknown')}`") # Added this line

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

        st.radio(
            "Output Style:",
            ('Original Text', 'Translated Text'),
            key='output_style',
            horizontal=True,
            index=0, # Default to Original
            help="Choose to view the original dialogue or a more casual translation (applied after conversation finishes)."
        )
        
        st.caption("Display Options:")

        st.checkbox(
            "Bypass Moderator (Direct Dialogue)",
            key='bypass_moderator_cb',
            value=st.session_state.get('bypass_moderator_cb', False),
            help="If checked, philosophers respond directly without moderator summaries/guidance. Overrides 'Moderator Control' selection."
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
    show_moderator_ctx = st.session_state.get('show_moderator_cb', True)
    moderator_control_mode = st.session_state.get('moderator_control_mode', 'AI Moderator')
    awaiting_user_guidance = st.session_state.get('awaiting_user_guidance', False)

    if not messages:
        st.info("Start the conversation by entering a question below.")
        return

    for message in messages:
        role = message.get("role", "system")
        content = message.get('content', '')

        is_moderator_system_message = (role.lower() == 'system' and
                                      isinstance(content, str) and
                                      (content.strip().startswith("MODERATOR CONTEXT") or
                                       content.strip().startswith("USER GUIDANCE FOR")))


        if is_moderator_system_message and not show_moderator_ctx:
            # If user has "Show Moderator Context" unchecked, hide all moderator-related system messages
            continue
        
        if (is_moderator_system_message and
            content.strip().startswith("MODERATOR CONTEXT") and
            moderator_control_mode == 'User as Moderator (Guidance)' and
            not awaiting_user_guidance and
            "AI Guidance:" in content):
            pass


        display_role = "user" if role.lower() == "user" else "assistant"
        avatar = "👤" if display_role=="user" else "🤖"
        if role.lower() == "system" and "guidance" in content.lower():
             avatar = "🧑‍🏫"
        elif role.lower() not in ["user", "system"]:
             avatar = "🧑‍🎨"


        with st.chat_message(display_role, avatar=avatar):
             prefix = ""
             if display_role == "assistant" and role.lower() not in ['system', 'user']:
                 prefix = f"**{role}:**\n"
             elif role.lower() == 'system' and (content.strip().startswith("MODERATOR CONTEXT") or content.strip().startswith("USER GUIDANCE FOR")):
                 pass
             
             display_content = str(content) if content is not None else ""
             st.markdown(f"{prefix}{display_content}")
