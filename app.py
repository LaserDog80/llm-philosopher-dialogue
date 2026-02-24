# app.py — Streamlined main application entry point.

import io
import datetime
import logging
import os
from typing import Dict, Any, Optional

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Logging — single basicConfig call for the whole process
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Authentication gate
# ---------------------------------------------------------------------------
try:
    import auth
except ImportError:
    st.error("Fatal: `auth.py` not found.")
    st.stop()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not auth.check_password():
    st.stop()

# ---------------------------------------------------------------------------
# Authenticated imports
# ---------------------------------------------------------------------------
try:
    from direction import Director
    import gui
    from translator import translate_conversation
    from core.validation import sanitize_input, validate_user_input
except ImportError as e:
    st.error(f"Failed to import modules: {e}")
    logger.exception("Module import failed.")
    st.stop()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_NUM_ROUNDS = 3
DEFAULT_CONVERSATION_MODE = "Philosophy"
DEFAULT_MODERATOR_CONTROL = "AI Moderator"

# ---------------------------------------------------------------------------
# Session state initialisation (one flat dict, no file handles)
# ---------------------------------------------------------------------------
_DEFAULTS: Dict[str, Any] = {
    "messages": [],
    "director_instance": None,
    "current_status": "Ready.",
    "log_content": None,
    "current_log_filename": None,
    "show_monologue_cb": False,
    "show_moderator_cb": False,
    "bypass_moderator_cb": False,
    "starting_philosopher": "Socrates",
    "num_rounds": DEFAULT_NUM_ROUNDS,
    "conversation_mode": DEFAULT_CONVERSATION_MODE,
    "run_conversation_flag": False,
    "conversation_completed": False,
    "prompt_overrides": {},
    "moderator_control_mode": DEFAULT_MODERATOR_CONTROL,
    "awaiting_user_guidance": False,
    "ai_summary_for_guidance_input": None,
    "next_speaker_for_guidance": None,
    "director_resume_state": None,
    "translated_messages": None,
}
for key, default in _DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default

if st.session_state.director_instance is None:
    try:
        st.session_state.director_instance = Director()
        logger.info("Director created.")
    except Exception as e:
        st.error(f"Error initialising Director: {e}")
        logger.exception("Director init failed.")
        st.stop()


# ---------------------------------------------------------------------------
# Logging helpers (in-memory only — no open file handles in session state)
# ---------------------------------------------------------------------------

def _init_log(num_rounds: int) -> None:
    """Create a fresh in-memory log buffer."""
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    st.session_state.current_log_filename = f"conversation_log_{ts}.txt"
    header_lines = [
        f"Conversation Log — {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Rounds: {num_rounds}",
        f"Mode: {st.session_state.get('conversation_mode', DEFAULT_CONVERSATION_MODE)}",
        f"Moderator: {'Bypassed' if st.session_state.get('bypass_moderator_cb') else st.session_state.get('moderator_control_mode', DEFAULT_MODERATOR_CONTROL)}",
        "=" * 40,
        "",
    ]
    st.session_state.log_content = header_lines
    logger.info(f"Log initialised: {st.session_state.current_log_filename}")


def _write_log(msg: Dict[str, Any]) -> None:
    """Append a message dict to the in-memory log."""
    log = st.session_state.get("log_content")
    if not isinstance(log, list):
        return
    role = msg.get("role", "system").upper()
    content = str(msg.get("content", ""))
    if role == "SYSTEM":
        line = content.strip()
    elif role == "USER":
        line = f"USER PROMPT: {content}"
    else:
        line = f"{role}: {content}"
    log.append(line)
    log.append("-" * 40)


def _close_log() -> None:
    """Mark the log as finished."""
    log = st.session_state.get("log_content")
    if isinstance(log, list) and log and not log[-1].strip().endswith("--- Log End ---"):
        log.append("\n--- Log End ---")


# ---------------------------------------------------------------------------
# State reset helper
# ---------------------------------------------------------------------------

def _reset_conversation() -> None:
    """Reset all conversation-related state in one place."""
    st.session_state.messages = []
    st.session_state.current_status = "Ready."
    st.session_state.log_content = None
    st.session_state.current_log_filename = None
    st.session_state.conversation_completed = False
    st.session_state.awaiting_user_guidance = False
    st.session_state.ai_summary_for_guidance_input = None
    st.session_state.next_speaker_for_guidance = None
    st.session_state.director_resume_state = None
    st.session_state.translated_messages = None
    st.session_state.pop("run_conversation_flag", None)
    st.session_state.pop("current_run_mode", None)
    _close_log()
    logger.info("Conversation state reset.")


# ---------------------------------------------------------------------------
# Conversation runners
# ---------------------------------------------------------------------------

def _run_initial_conversation(prompt: str) -> None:
    """Start a new conversation from an initial user prompt."""
    num_rounds = st.session_state.get("num_rounds", DEFAULT_NUM_ROUNDS)
    mode = st.session_state.get("current_run_mode", DEFAULT_CONVERSATION_MODE)
    starter = st.session_state.get("starting_philosopher", "Socrates")
    bypass = st.session_state.get("bypass_moderator_cb", False)
    mod_ctrl = st.session_state.get("moderator_control_mode", DEFAULT_MODERATOR_CONTROL)

    run_moderated = not bypass
    mod_type = "ai"
    if mod_ctrl == "User as Moderator (Guidance)" and run_moderated:
        mod_type = "user_guidance"

    director: Director = st.session_state.director_instance

    final_status = "Error: conversation did not complete."
    try:
        st.session_state.current_status = f"Philosophers conferring ({mode} mode)..."
        with st.spinner(f"Philosophers conferring ({mode} mode)..."):
            gen_msgs, final_status, success, resume_state, guidance_data = (
                director.run_conversation_streamlit(
                    initial_input=prompt,
                    num_rounds=num_rounds,
                    starting_philosopher=starter,
                    run_moderated=run_moderated,
                    mode=mode,
                    moderator_type=mod_type,
                )
            )
            logger.info(f"Director finished. success={success}, status={final_status}")

        st.session_state.current_status = final_status
        st.session_state.messages.extend(gen_msgs)
        for m in gen_msgs:
            _write_log(m)

        if final_status == "WAITING_FOR_USER_GUIDANCE":
            st.session_state.awaiting_user_guidance = True
            st.session_state.ai_summary_for_guidance_input = guidance_data["ai_summary"]
            st.session_state.next_speaker_for_guidance = guidance_data["next_speaker_name"]
            st.session_state.director_resume_state = resume_state
            st.session_state.current_status = (
                f"Waiting for your guidance for {guidance_data['next_speaker_name']}..."
            )
        elif success:
            st.session_state.conversation_completed = True
            st.session_state.director_resume_state = None
            _maybe_translate(mode)
            _close_log()
        else:
            st.session_state.conversation_completed = True
            st.session_state.director_resume_state = None
            _close_log()
    except Exception as e:
        logger.exception("Conversation error.")
        st.error(f"Conversation error: {e}")
        st.session_state.current_status = "Critical error during conversation."
        st.session_state.director_resume_state = None
        _close_log()
    finally:
        if final_status != "WAITING_FOR_USER_GUIDANCE":
            st.session_state.pop("current_run_mode", None)
        st.rerun()


def _resume_conversation(user_guidance: str) -> None:
    """Resume a user-guided conversation with the provided guidance text."""
    director: Director = st.session_state.director_instance
    resume_state = st.session_state.director_resume_state
    mode = resume_state.get("mode", DEFAULT_CONVERSATION_MODE) if resume_state else DEFAULT_CONVERSATION_MODE

    final_status = "Error: resume did not complete."
    try:
        with st.spinner(f"Philosophers conferring ({mode} mode) with your guidance..."):
            gen_msgs, final_status, success, new_resume, guidance_data = (
                director.resume_conversation_streamlit(resume_state, user_provided_guidance=user_guidance)
            )
            logger.info(f"Director resumed. success={success}, status={final_status}")

        st.session_state.current_status = final_status
        st.session_state.messages.extend(gen_msgs)
        for m in gen_msgs:
            _write_log(m)

        if final_status == "WAITING_FOR_USER_GUIDANCE":
            st.session_state.awaiting_user_guidance = True
            st.session_state.ai_summary_for_guidance_input = guidance_data["ai_summary"]
            st.session_state.next_speaker_for_guidance = guidance_data["next_speaker_name"]
            st.session_state.director_resume_state = new_resume
            st.session_state.current_status = (
                f"Waiting for your guidance for {guidance_data['next_speaker_name']}..."
            )
        elif success:
            st.session_state.conversation_completed = True
            st.session_state.director_resume_state = None
            _maybe_translate(mode)
            _close_log()
        else:
            st.session_state.conversation_completed = True
            st.session_state.director_resume_state = None
            _close_log()
    except Exception as e:
        logger.exception("Resume error.")
        st.error(f"Resume error: {e}")
        st.session_state.current_status = "Critical error during resume."
        st.session_state.director_resume_state = None
        _close_log()
    finally:
        if final_status != "WAITING_FOR_USER_GUIDANCE":
            st.session_state.pop("current_run_mode", None)
        st.rerun()


def _maybe_translate(mode: str) -> None:
    """If translated output is selected, run the translator.

    Stores the result in ``translated_messages`` so that the originals in
    ``messages`` are never overwritten.  The display logic switches between
    them based on the current output style selection.
    """
    if st.session_state.get("output_style") != "Translated Text":
        return
    try:
        with st.spinner("Translating conversation..."):
            original = st.session_state.messages[:]
            translated = translate_conversation(original)
        st.session_state.translated_messages = [
            {"role": "system", "content": f"### Translated Conversation\n\n---\n\n{translated}"}
        ]
        log = st.session_state.get("log_content")
        if isinstance(log, list):
            log.append("\n\n--- TRANSLATED CONVERSATION ---")
            log.append(translated)
    except Exception as e:
        logger.error(f"Translation failed: {e}", exc_info=True)
        st.error(f"Translation failed: {e}")


# ---------------------------------------------------------------------------
# UI Rendering
# ---------------------------------------------------------------------------

# Inject CSS once
gui.inject_chat_css()

# Sidebar
try:
    model_info = gui.get_model_info_from_config()
    gui.display_sidebar(model_info)
except Exception as e:
    st.error(f"Sidebar error: {e}")
    logger.exception("Sidebar rendering failed.")

# Header
gui.display_header()

# Conversation display — show translated version when available and selected
_display_messages = st.session_state.messages
if (
    st.session_state.get("output_style") == "Translated Text"
    and st.session_state.get("translated_messages")
):
    _display_messages = st.session_state.translated_messages

gui.display_conversation(
    messages=_display_messages,
    conversation_completed=st.session_state.get("conversation_completed", False),
    awaiting_guidance=st.session_state.get("awaiting_user_guidance", False),
    next_speaker_for_guidance=st.session_state.get("next_speaker_for_guidance", ""),
    num_rounds=st.session_state.get("num_rounds", DEFAULT_NUM_ROUNDS),
    mode=st.session_state.get("conversation_mode", DEFAULT_CONVERSATION_MODE),
)

# Internal monologue expander
gui.display_monologue(st.session_state.messages)

# Status line
ts = datetime.datetime.now().strftime("%H:%M:%S")
status_text = st.session_state.get("current_status", "Ready.")
st.caption(f"[{ts}] {status_text}")

# ---------------------------------------------------------------------------
# Chat input handling
# ---------------------------------------------------------------------------

if st.session_state.get("awaiting_user_guidance"):
    next_spk = st.session_state.get("next_speaker_for_guidance", "the next philosopher")
    input_prompt = f"Enter guidance for {next_spk} (or type 'auto' for AI guidance):"
else:
    input_prompt = "Enter your question to start a philosophical dialogue..."

prompt: Optional[str] = st.chat_input(input_prompt, key="main_chat_input")

if prompt:
    if st.session_state.get("awaiting_user_guidance"):
        # ── User guidance path ──
        logger.info(f"User guidance: '{prompt[:50]}...'")
        guidance_label = st.session_state.get("next_speaker_for_guidance", "N/A")
        guidance_content = f"USER GUIDANCE FOR {guidance_label}:\n{prompt}"
        if prompt.strip().lower() == "auto":
            guidance_content = f"SYSTEM: User opted for AI guidance for {guidance_label} this turn."
        st.session_state.messages.append({"role": "system", "content": guidance_content, "monologue": None})
        _write_log({"role": "system", "content": guidance_content})
        st.session_state.awaiting_user_guidance = False

        if st.session_state.director_instance and st.session_state.director_resume_state:
            _resume_conversation(prompt)
        else:
            st.error("Cannot resume: Director or resume state unavailable.")
            _close_log()
            st.rerun()
    else:
        # ── New conversation path ──
        prompt = sanitize_input(prompt)
        is_valid, error_msg = validate_user_input(prompt)
        if not is_valid:
            st.warning(error_msg)
            st.stop()

        logger.info(f"New prompt: '{prompt[:50]}...'")
        _reset_conversation()

        num_rounds = st.session_state.get("num_rounds", DEFAULT_NUM_ROUNDS)
        mode = st.session_state.get("conversation_mode", DEFAULT_CONVERSATION_MODE)

        _init_log(num_rounds)

        user_msg: Dict[str, Any] = {"role": "user", "content": prompt, "monologue": None}
        st.session_state.messages.append(user_msg)
        _write_log(user_msg)

        st.session_state.current_run_mode = mode
        st.session_state.run_conversation_flag = True
        st.rerun()


# ---------------------------------------------------------------------------
# Run conversation if flag is set (on the rerun after storing the prompt)
# ---------------------------------------------------------------------------

if st.session_state.get("run_conversation_flag") and not st.session_state.get("awaiting_user_guidance"):
    st.session_state.run_conversation_flag = False
    if st.session_state.messages:
        _run_initial_conversation(st.session_state.messages[0]["content"])
    else:
        st.error("No prompt found.")
        st.session_state.current_status = "Error: prompt missing."


# ---------------------------------------------------------------------------
# Bottom controls
# ---------------------------------------------------------------------------

st.divider()
col1, col2 = st.columns([1, 1])

with col1:
    if st.button("Clear & Reset Conversation"):
        _reset_conversation()
        st.rerun()

with col2:
    if (
        st.session_state.get("conversation_completed")
        and isinstance(st.session_state.get("log_content"), list)
        and st.session_state["log_content"]
    ):
        log_text = "\n".join(st.session_state["log_content"])
        st.download_button(
            label="Download Conversation Log",
            data=log_text.encode("utf-8"),
            file_name=st.session_state.get("current_log_filename", "conversation_log.txt"),
            mime="text/plain",
        )
    elif st.session_state.get("conversation_completed"):
        st.caption("Log unavailable for download.")

# Logout
st.sidebar.divider()
if st.sidebar.button("Logout"):
    auth.logout()
    st.rerun()
