# Filename: gui.py

import streamlit as st
import json

def display_header():
    """Displays the main title of the application."""
    st.title("Philosopher Dialogue (Streamlit Edition)")

def get_model_info_from_config(config_path="llm_config.json"):
    """Loads model names from config file for display."""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
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

        # --- Checkbox for Monologue ---
        st.checkbox(
            "Show Internal Monologue",
            key='show_monologue_cb',
            value=st.session_state.get('show_monologue_cb', False)
        )
        # -----------------------------


def display_conversation(messages):
    """Displays the chat messages (main content only)."""
    # (Identical to previous version)
    for message in messages:
        role = message.get("role", "system")
        display_role = "user" if role.lower() == "user" else "assistant"
        with st.chat_message(display_role, avatar=("👤" if display_role=="user" else "🤖")):
             prefix = f"**{role}:**\n" if display_role == "assistant" and role.lower() != 'system' else ""
             st.markdown(f"{prefix}{message.get('content', '')}")


def display_status(status_text):
    """Displays the current application status."""
    # (Identical to previous version)
    st.caption(f"Status: {status_text}")