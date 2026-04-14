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
    "philosopher_1": "Herodotus",
    "philosopher_2": "Sima Qian",
    "num_rounds": DEFAULT_NUM_ROUNDS,
    "conversation_mode": DEFAULT_CONVERSATION_MODE,
    "conversation_style": DEFAULT_CONVERSATION_STYLE,
    "max_tokens_p1": 600,   # Herodotus default from voice_profile
    "max_tokens_p2": 350,   # Sima Qian default from voice_profile
    "personality_notes_p1": "",
    "personality_notes_p2": "",
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

def _run_story_turn(prompt: str) -> None:
    """Single-speaker, single-turn STORY mode (Herodotus-only).

    Bypasses the agentic graph — STORY mode is one prompt, one story, end.
    """
    from core.persona import create_chain
    from core.utils import extract_and_clean, parse_direction_tag

    starter = "Herodotus"
    pid = "herodotus"
    personality_notes = st.session_state.get("personality_notes_story", "")

    try:
        st.session_state.current_status = "Herodotus is choosing a story..."
        thinking_placeholder = st.empty()
        thinking_placeholder.markdown(
            gui.render_thinking_indicator("Herodotus is choosing a story..."),
            unsafe_allow_html=True,
        )

        chain = create_chain(
            pid, mode="story",
            personality_notes=(personality_notes.strip() or None),
        )
        if chain is None:
            raise RuntimeError("Failed to load Herodotus story chain.")

        raw = chain.invoke({"input": prompt, "chat_history": []})
        cleaned_raw, monologue = extract_and_clean(raw)
        cleaned, _direction = parse_direction_tag(cleaned_raw)

        thinking_placeholder.empty()

        story_msg: Dict[str, Any] = {"role": starter, "content": cleaned, "monologue": monologue}
        st.session_state.messages.append(story_msg)
        _write_log(story_msg)

        st.session_state.current_status = "Story complete."
        st.session_state.conversation_completed = True
        _close_log()
    except Exception as e:
        logger.exception("Story mode error.")
        st.error(f"Story mode error: {e}")
        st.session_state.current_status = "Critical error in Story mode."
        _close_log()
    finally:
        st.session_state.pop("current_run_mode", None)
        st.rerun()


def _run_initial_conversation(prompt: str) -> None:
    """Start a new agentic conversation from an initial user prompt."""
    mode = st.session_state.get("current_run_mode", DEFAULT_CONVERSATION_MODE)
    if mode == "Story":
        _run_story_turn(prompt)
        return

    num_rounds = st.session_state.get("num_rounds", DEFAULT_NUM_ROUNDS)
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

        max_tokens_p1 = st.session_state.get("max_tokens_p1", 0)
        max_tokens_p2 = st.session_state.get("max_tokens_p2", 0)
        personality_notes_p1 = st.session_state.get("personality_notes_p1", "")
        personality_notes_p2 = st.session_state.get("personality_notes_p2", "")
        gen_msgs, final_status, success, thread_id = run_agentic_conversation(
            topic=prompt,
            philosopher_1=starter,
            philosopher_2=philosopher_2,
            num_rounds=num_rounds,
            mode=mode,
            max_tokens_p1=max_tokens_p1,
            max_tokens_p2=max_tokens_p2,
            personality_notes_p1=personality_notes_p1,
            personality_notes_p2=personality_notes_p2,
        )
        logger.info(f"Agentic conversation finished. success={success}, status={final_status}")
        thinking_placeholder.empty()

        st.session_state.current_status = final_status
        st.session_state.current_thread_id = thread_id
        st.session_state.messages.extend(gen_msgs)
        for m in gen_msgs:
            _write_log(m)

        st.session_state.conversation_completed = success
        _close_log()
    except Exception as e:
        logger.exception("Conversation error.")
        st.error(f"Conversation error: {e}")
        st.session_state.current_status = "Critical error during conversation."
        _close_log()
    finally:
        st.session_state.pop("current_run_mode", None)
        st.rerun()


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

_conversation_completed = st.session_state.get("conversation_completed", False)

# Layout: Settings + action buttons. "Translate All" only appears after a
# conversation completes.
if _conversation_completed:
    col_settings, col_reset, col_translate_all, col_download, col_logout = st.columns(
        [3, 2, 2, 2, 1.5]
    )
else:
    col_settings, col_reset, col_download, col_logout = st.columns([3, 2, 2, 1.5])
    col_translate_all = None

with col_settings:
    gui.display_settings_popover(model_info)

with col_reset:
    if st.button("Clear & Reset"):
        _reset_conversation()
        st.rerun()

if col_translate_all is not None:
    with col_translate_all:
        if st.button("Translate All", help="Rewrite every philosopher message in casual English."):
            st.session_state["_translate_all_request"] = True
            st.rerun()

with col_download:
    if (
        _conversation_completed
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

_display_messages = st.session_state.messages

# ---------------------------------------------------------------------------
# Handle editor rewrite requests
# ---------------------------------------------------------------------------
# Handle editor reset requests (restore original text)
_editor_reset_idx = st.session_state.pop("_editor_reset", None)
if _editor_reset_idx is not None and st.session_state.get("conversation_completed"):
    messages = st.session_state.messages
    if 0 <= _editor_reset_idx < len(messages):
        msg = messages[_editor_reset_idx]
        if "_original_content" in msg:
            msg["content"] = msg.pop("_original_content")
            msg.pop("_target_words", None)
            # Reset the slider to 100%
            slider_key = f"_editor_pct_{_editor_reset_idx}"
            if slider_key in st.session_state:
                del st.session_state[slider_key]
            logger.info(f"Editor reset message {_editor_reset_idx} to original")
            st.session_state["_scroll_to_msg"] = _editor_reset_idx

# Handle editor rewrite requests (percentage-based)
_editor_req = st.session_state.pop("_editor_request", None)
if _editor_req and st.session_state.get("conversation_completed"):
    msg_idx = _editor_req["index"]
    pct = _editor_req["pct"]
    messages = st.session_state.messages

    if 0 <= msg_idx < len(messages):
        msg = messages[msg_idx]

        # Store original on first edit — this is the permanent source of truth
        if "_original_content" not in msg:
            msg["_original_content"] = msg["content"]
        original = msg["_original_content"]

        # Compute target word count from percentage of original
        original_words = len(original.split())
        target_words = max(15, int(original_words * pct / 100))

        thinking_placeholder = st.empty()
        thinking_placeholder.markdown(
            gui.render_thinking_indicator(
                f"Editor rewriting to ~{target_words} words ({pct}%)..."
            ),
            unsafe_allow_html=True,
        )
        try:
            from core.editor import rewrite_message
            rewritten = rewrite_message(messages, msg_idx, target_words, original)
            if rewritten:
                msg["content"] = rewritten
                msg["_target_words"] = target_words
                logger.info(f"Editor rewrote message {msg_idx} to ~{target_words} words ({pct}%)")
                st.session_state["_scroll_to_msg"] = msg_idx
            else:
                st.warning("Editor could not rewrite the message.")
        except Exception as e:
            logger.error(f"Editor error: {e}", exc_info=True)
            st.error(f"Editor error: {e}")
        finally:
            thinking_placeholder.empty()

    # Re-derive display messages after edit
    _display_messages = st.session_state.messages


# ---------------------------------------------------------------------------
# Per-message translate toggle — rewrite a single message in casual English.
# ---------------------------------------------------------------------------
def _apply_translate_toggle(msg: Dict[str, Any]) -> None:
    """Flip a message between its original content and its casual translation.

    Caches the translation in ``_translated_content`` so the second click is
    instant. ``_pre_translate_content`` remembers the text we swapped out.
    """
    from translator import translate_single_message

    if msg.get("_is_translated"):
        pre = msg.get("_pre_translate_content")
        if pre is not None:
            msg["content"] = pre
        msg["_is_translated"] = False
        return

    if "_translated_content" not in msg:
        speaker = msg.get("role", "speaker")
        msg["_pre_translate_content"] = msg["content"]
        with st.spinner(f"Translating {speaker} to casual English..."):
            translated = translate_single_message(speaker, msg["_pre_translate_content"])
        if not translated:
            st.warning(f"Translation failed for {speaker}.")
            return
        msg["_translated_content"] = translated
    else:
        msg.setdefault("_pre_translate_content", msg["content"])

    msg["content"] = msg["_translated_content"]
    msg["_is_translated"] = True


_translate_req = st.session_state.pop("_translate_request", None)
if _translate_req and st.session_state.get("conversation_completed"):
    _idx = _translate_req.get("index")
    messages = st.session_state.messages
    if _idx is not None and 0 <= _idx < len(messages):
        _msg = messages[_idx]
        if _msg.get("role", "").lower() not in ("user", "system"):
            _apply_translate_toggle(_msg)
            st.session_state["_scroll_to_msg"] = _idx
    _display_messages = st.session_state.messages


if st.session_state.pop("_translate_all_request", False) and st.session_state.get("conversation_completed"):
    messages = st.session_state.messages
    with st.spinner("Translating all philosopher messages to casual English..."):
        for _msg in messages:
            if _msg.get("role", "").lower() in ("user", "system"):
                continue
            if _msg.get("_is_translated"):
                continue  # already translated
            _apply_translate_toggle(_msg)
    _display_messages = st.session_state.messages


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

    mode = st.session_state.get("conversation_mode", DEFAULT_CONVERSATION_MODE)
    num_rounds = 1 if mode == "Story" else st.session_state.get("num_rounds", DEFAULT_NUM_ROUNDS)

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
