# Filename: gui.py

import streamlit as st
import json

def display_header():
    """Displays the main title of the application."""
    st.title("Philosopher Dialogue")

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
        }
    except FileNotFoundError:
        st.warning(f"Config file not found at {config_path}. Cannot display model info.")
        return {'Socrates': 'Unknown', 'Confucius': 'Unknown', 'Moderator': 'Unknown'}
    except Exception as e:
        st.error(f"Error loading model info from config: {e}")
        return {'Socrates': 'Unknown', 'Confucius': 'Unknown', 'Moderator': 'Unknown'}


def display_sidebar(model_info):
    """Displays information and controls in the sidebar."""
    with st.sidebar:
        st.header("Configuration")
        st.caption("Model Instances:")
        st.markdown(f"**Socrates:** `{model_info.get('Socrates', 'Unknown')}`")
        st.markdown(f"**Confucius:** `{model_info.get('Confucius', 'Unknown')}`")
        st.markdown(f"**Moderator:** `{model_info.get('Moderator', 'Unknown')}`")

        st.divider()

        # --- Add Controls for Rounds and Starting Philosopher ---
        st.radio(
            "Starting Philosopher:",
            ('Socrates', 'Confucius'),
            key='starting_philosopher', # Key to access value in session state
            horizontal=True,
            index=0 # Default to Socrates
        )

        st.number_input(
            "Number of Rounds:",
            min_value=1,
            max_value=10, # Set a reasonable max
            value=st.session_state.get('num_rounds', 3), # Default value, get from state if already set
            step=1,
            key='num_rounds', # Key to access value in session state
            help="One round includes one response from each philosopher (S->M->C or C->M->S)."
        )
        # -------------------------------------------------------

        st.divider()

        # --- Add the new checkbox for Moderator Context ---
        st.checkbox(
            "Show Moderator Context",
            key='show_moderator_cb', # Unique key for this checkbox
            value=st.session_state.get('show_moderator_cb', True) # Default to True (checked)
        )
        # ----------------------------------------------------

        # --- Checkbox for Monologue ---
        st.checkbox(
            "Show Internal Monologue",
            key='show_monologue_cb',
            value=st.session_state.get('show_monologue_cb', False) # Default to False (unchecked)
        )
        # -----------------------------


def display_conversation(messages):
    """Displays the chat messages, conditionally hiding moderator context."""
    # Get the current state of the checkbox
    show_moderator = st.session_state.get('show_moderator_cb', True)

    for message in messages:
        role = message.get("role", "system")
        content = message.get('content', '')

        # --- Logic to conditionally skip moderator messages ---
        # Check if role is system AND content starts with "MODERATOR CONTEXT"
        is_moderator_context = role.lower() == 'system' and content.strip().startswith("MODERATOR CONTEXT")

        if is_moderator_context and not show_moderator:
            continue # Skip the rest of the loop for this message (don't display it)
        # ----------------------------------------------------

        # Determine display role (user or assistant)
        display_role = "user" if role.lower() == "user" else "assistant"

        # Display the chat bubble
        with st.chat_message(display_role, avatar=("👤" if display_role=="user" else "🤖")):
             # Add speaker prefix only for actual philosopher responses (not user or system)
             prefix = f"**{role}:**\n" if display_role == "assistant" and role.lower() not in ['system', 'user'] else ""
             # Display the content
             st.markdown(f"{prefix}{content}")


def display_status(status_text):
    """Displays the current application status."""
    # (Identical to previous version)
    st.caption(f"Status: {status_text}")