# app.py — Streamlined main application entry point.
# UI: "Warm Study" design — clean main view with popover settings.

import io
import datetime
import logging
import os
from typing import Dict, Any, Optional

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# Bridge Streamlit Cloud secrets into os.environ so core modules
# (which use os.getenv) work without a .env file.
try:
    for key in ("NEBIUS_API_KEY", "NEBIUS_API_BASE"):
        if key in st.secrets and key not in os.environ:
            os.environ[key] = st.secrets[key]
except Exception:
    pass  # No secrets configured (local dev with .env)

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
    import gui
    from translator import translate_conversation
    from core.validation import sanitize_input, validate_user_input
    from core.graph import run_agentic_conversation, list_saved_conversations
except ImportError as e:
    st.error(f"Failed to import modules: {e}")
    logger.exception("Module import failed.")
    st.stop()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_NUM_ROUNDS = 3
DEFAULT_CONVERSATION_MODE = "Philosophy"
DEFAULT_CONVERSATION_STYLE = "Self-Directed"

# ---------------------------------------------------------------------------
# Session state initialisation (one flat dict, no file handles)
# ---------------------------------------------------------------------------
_DEFAULTS: Dict[str, Any] = {
    "messages": [],
    "current_status": "Ready.",
    "log_content": None,
    "current_log_filename": None,
    "show_monologue_cb": False,
    "philosopher_1": "Socrates",
    "philosopher_2": "Confucius",
    "num_rounds": DEFAULT_NUM_ROUNDS,
    "conversation_mode": DEFAULT_CONVERSATION_MODE,
    "conversation_style": DEFAULT_CONVERSATION_STYLE,
    "max_tokens": 400,
    "run_conversation_flag": False,
    "conversation_completed": False,
    "prompt_overrides": {},
    "current_thread_id": None,
    "translated_messages": None,
}
for key, default in _DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default


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
        f"Style: Self-Directed (Agentic)",
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
    st.session_state.current_thread_id = None
    st.session_state.translated_messages = None
    st.session_state.pop("run_conversation_flag", None)
    st.session_state.pop("current_run_mode", None)
    _close_log()
    logger.info("Conversation state reset.")


# ---------------------------------------------------------------------------
# Conversation runners
# ---------------------------------------------------------------------------

def _run_initial_conversation(prompt: str) -> None:
    """Start a new agentic conversation from an initial user prompt."""
    num_rounds = st.session_state.get("num_rounds", DEFAULT_NUM_ROUNDS)
    mode = st.session_state.get("current_run_mode", DEFAULT_CONVERSATION_MODE)
    starter = st.session_state.get("philosopher_1", "Socrates")
    philosopher_2 = st.session_state.get("philosopher_2", "Confucius")

    try:
        st.session_state.current_status = f"Philosophers conferring ({mode} mode)..."

        # Show warm-themed thinking indicator
        thinking_placeholder = st.empty()
        thinking_placeholder.markdown(
            gui.render_thinking_indicator(f"Philosophers conferring ({mode} mode)..."),
            unsafe_allow_html=True,
        )

        max_tokens = st.session_state.get("max_tokens", 0)
        gen_msgs, final_status, success, thread_id = run_agentic_conversation(
            topic=prompt,
            philosopher_1=starter,
            philosopher_2=philosopher_2,
            num_rounds=num_rounds,
            mode=mode,
            max_tokens=max_tokens,
        )
        logger.info(f"Agentic conversation finished. success={success}, status={final_status}")
        thinking_placeholder.empty()

        st.session_state.current_status = final_status
        st.session_state.current_thread_id = thread_id
        st.session_state.messages.extend(gen_msgs)
        for m in gen_msgs:
            _write_log(m)

        st.session_state.conversation_completed = success
        if success:
            _maybe_translate(mode)
        _close_log()
    except Exception as e:
        logger.exception("Conversation error.")
        st.error(f"Conversation error: {e}")
        st.session_state.current_status = "Critical error during conversation."
        _close_log()
    finally:
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
        thinking_placeholder = st.empty()
        thinking_placeholder.markdown(
            gui.render_thinking_indicator("Translating conversation..."),
            unsafe_allow_html=True,
        )
        original = st.session_state.messages[:]
        translated = translate_conversation(original)
        thinking_placeholder.empty()

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
# UI Rendering — Warm Study Layout
# ---------------------------------------------------------------------------

# Inject CSS (includes sidebar hide, fonts, warm theme)
gui.inject_chat_css()

# Header bar
gui.display_header()

# Top action bar: Settings popover + action buttons
try:
    model_info = gui.get_model_info_from_config()
except Exception as e:
    model_info = {}
    logger.exception("Model info load failed.")

# Layout: Settings + action buttons
col_settings, col_reset, col_download, col_logout = st.columns([3, 2, 2, 1.5])

with col_settings:
    gui.display_settings_popover(model_info)

with col_reset:
    if st.button("Clear & Reset"):
        _reset_conversation()
        st.rerun()

with col_download:
    if (
        st.session_state.get("conversation_completed")
        and isinstance(st.session_state.get("log_content"), list)
        and st.session_state["log_content"]
    ):
        log_text = "\n".join(st.session_state["log_content"])
        st.download_button(
            label="Download Log",
            data=log_text.encode("utf-8"),
            file_name=st.session_state.get("current_log_filename", "conversation_log.txt"),
            mime="text/plain",
        )

with col_logout:
    if st.button("Logout"):
        auth.logout()
        st.rerun()

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
    awaiting_guidance=False,
    next_speaker_for_guidance="",
    num_rounds=st.session_state.get("num_rounds", DEFAULT_NUM_ROUNDS),
    mode=st.session_state.get("conversation_mode", DEFAULT_CONVERSATION_MODE),
)

# Internal monologue expander
gui.display_monologue(st.session_state.messages)

# Status line (minimal)
ts = datetime.datetime.now().strftime("%H:%M:%S")
status_text = st.session_state.get("current_status", "Ready.")
st.caption(f"[{ts}] {status_text}")

# ---------------------------------------------------------------------------
# Chat input handling
# ---------------------------------------------------------------------------

input_prompt = "Enter your question to start a philosophical dialogue..."

prompt: Optional[str] = st.chat_input(input_prompt, key="main_chat_input")

if prompt:
    # -- New conversation path --
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

if st.session_state.get("run_conversation_flag"):
    st.session_state.run_conversation_flag = False
    if st.session_state.messages:
        _run_initial_conversation(st.session_state.messages[0]["content"])
    else:
        st.error("No prompt found.")
        st.session_state.current_status = "Error: prompt missing."
