# gui.py — Modern chat interface with custom HTML/CSS rendering.

import html
import json
import logging
import streamlit as st
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Speaker visual configuration
# ---------------------------------------------------------------------------
SPEAKER_STYLES = {
    "socrates": {
        "color": "#5B8DEF",
        "bg": "#f0f5ff",
        "text_color": "#2D5FC4",
        "initials": "S",
        "display_name": "Socrates",
    },
    "confucius": {
        "color": "#D4A03C",
        "bg": "#fdf6e3",
        "text_color": "#8B6914",
        "initials": "C",
        "display_name": "Confucius",
    },
    "moderator": {
        "color": "#8B8B8B",
        "bg": "#f5f5f5",
        "text_color": "#555555",
        "initials": "M",
        "display_name": "Moderator",
    },
    "user": {
        "color": "#2ECC71",
        "bg": "#e8faf0",
        "text_color": "#1B8A4A",
        "initials": "U",
        "display_name": "You",
    },
    "system": {
        "color": "#8B8B8B",
        "bg": "#f5f5f5",
        "text_color": "#555555",
        "initials": "S",
        "display_name": "System",
    },
}

# ---------------------------------------------------------------------------
# CSS Stylesheet — injected once at the top of each page render
# ---------------------------------------------------------------------------
CHAT_CSS = """
<style>
/* ===== Philosopher Dialogue Chat Styles ===== */

/* Container */
.phd-container {
    max-width: 740px;
    margin: 0 auto;
    padding: 0;
}

/* App header */
.phd-header {
    text-align: center;
    padding: 8px 0 20px;
}
.phd-title {
    font-family: Georgia, Cambria, 'Times New Roman', serif;
    font-size: 28px;
    font-weight: 700;
    color: #1a1a1a;
    margin: 0 0 4px;
    letter-spacing: -0.5px;
}
.phd-subtitle {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 14px;
    color: #999;
    margin: 0;
}

/* Topic Card — user's initial question */
.phd-topic-card {
    background: linear-gradient(135deg, #f8f9ff 0%, #fff8f0 100%);
    border: 1px solid #e4e4e7;
    border-radius: 14px;
    padding: 20px 24px;
    margin-bottom: 24px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.phd-topic-label {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: #999;
    margin-bottom: 8px;
    font-weight: 600;
}
.phd-topic-content {
    font-family: Georgia, Cambria, 'Times New Roman', serif;
    font-size: 17px;
    line-height: 1.6;
    color: #1a1a1a;
}

/* Round Separator */
.phd-round-sep {
    display: flex;
    align-items: center;
    margin: 24px 0 16px;
    gap: 16px;
}
.phd-round-sep::before,
.phd-round-sep::after {
    content: '';
    flex: 1;
    height: 1px;
    background: #e0e0e0;
}
.phd-round-text {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 2px;
    color: #b0b0b0;
    white-space: nowrap;
    font-weight: 500;
}

/* Message Turn */
.phd-turn {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 6px 0;
    margin: 6px 0;
}

/* Avatar */
.phd-avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-weight: 700;
    font-size: 14px;
    color: white;
    box-shadow: 0 1px 4px rgba(0,0,0,0.1);
}

/* Message Body */
.phd-msg-body {
    flex: 1;
    min-width: 0;
}
.phd-msg-header {
    display: flex;
    align-items: baseline;
    gap: 8px;
    margin-bottom: 3px;
}
.phd-speaker {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-weight: 600;
    font-size: 14px;
}
.phd-meta {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 11px;
    color: #b0b0b0;
}

/* Message Card */
.phd-card {
    padding: 12px 16px;
    border-radius: 10px;
    border-left: 3px solid transparent;
}
.phd-content {
    font-family: Georgia, Cambria, 'Times New Roman', serif;
    font-size: 16px;
    line-height: 1.75;
    color: #1a1a1a;
    word-wrap: break-word;
    overflow-wrap: break-word;
}
.phd-content p {
    margin: 0 0 8px;
}
.phd-content p:last-child {
    margin-bottom: 0;
}

/* Moderator Context (collapsible) */
.phd-mod-ctx {
    margin: 4px 0 4px 48px;
    border-radius: 6px;
}
.phd-mod-toggle {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 12px;
    color: #aaa;
    cursor: pointer;
    padding: 5px 10px;
    border-radius: 6px;
    list-style: none;
    display: flex;
    align-items: center;
    gap: 6px;
    user-select: none;
}
.phd-mod-toggle::-webkit-details-marker { display: none; }
.phd-mod-toggle:hover {
    background: rgba(0,0,0,0.03);
    color: #777;
}
.phd-mod-body {
    padding: 8px 12px 10px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 13px;
    line-height: 1.5;
    color: #666;
    background: #f7f7f7;
    border-radius: 0 0 6px 6px;
}
.phd-mod-body strong {
    color: #555;
}

/* User Guidance */
.phd-guidance {
    margin: 4px 0 8px 48px;
    padding: 8px 14px;
    border-radius: 8px;
    border-left: 3px solid #2ECC71;
    background: #eafaf1;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 13px;
    color: #1B8A4A;
    line-height: 1.5;
}
.phd-guidance-label {
    font-weight: 600;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #27ae60;
    margin-bottom: 2px;
}

/* Error message */
.phd-error {
    margin: 4px 0 8px 48px;
    padding: 8px 14px;
    border-radius: 8px;
    border-left: 3px solid #e74c3c;
    background: #fdf0ef;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 13px;
    color: #c0392b;
}

/* Empty State */
.phd-empty {
    text-align: center;
    padding: 60px 20px;
}
.phd-empty-icon {
    font-size: 48px;
    margin-bottom: 16px;
    opacity: 0.4;
}
.phd-empty-text {
    font-family: Georgia, Cambria, serif;
    font-size: 18px;
    color: #888;
    margin-bottom: 8px;
}
.phd-empty-hint {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 14px;
    color: #bbb;
}

/* Completion Banner */
.phd-complete {
    text-align: center;
    padding: 14px 20px;
    margin: 20px 0 8px;
    border-radius: 10px;
    background: linear-gradient(135deg, #f0f5ff 0%, #fdf6e3 100%);
    border: 1px solid #e4e4e7;
}
.phd-complete-text {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 13px;
    color: #777;
}

/* Waiting indicator */
.phd-waiting {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 16px;
    margin: 12px 0 4px 48px;
    border-radius: 10px;
    border-left: 3px solid #2ECC71;
    background: #eafaf1;
}
.phd-waiting-label {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 13px;
    font-style: italic;
    color: #27ae60;
}
.phd-dots {
    display: inline-flex;
    gap: 3px;
}
.phd-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: #27ae60;
    animation: phd-pulse 1.4s infinite ease-in-out both;
}
.phd-dot:nth-child(1) { animation-delay: -0.32s; }
.phd-dot:nth-child(2) { animation-delay: -0.16s; }
.phd-dot:nth-child(3) { animation-delay: 0s; }
@keyframes phd-pulse {
    0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
    40% { transform: scale(1); opacity: 1; }
}

/* Responsive */
@media (max-width: 768px) {
    .phd-turn { gap: 8px; }
    .phd-avatar { width: 30px; height: 30px; font-size: 12px; }
    .phd-content { font-size: 15px; line-height: 1.6; }
    .phd-topic-card { padding: 16px; }
    .phd-mod-ctx, .phd-guidance, .phd-error, .phd-waiting { margin-left: 38px; }
}
@media (max-width: 480px) {
    .phd-avatar { width: 26px; height: 26px; font-size: 11px; }
    .phd-content { font-size: 14px; }
    .phd-card { padding: 10px 12px; }
    .phd-mod-ctx, .phd-guidance, .phd-error, .phd-waiting { margin-left: 34px; }
}

/* Override Streamlit defaults for cleaner look */
div[data-testid="stChatInput"] textarea::placeholder {
    font-style: italic;
}
</style>
"""


# ---------------------------------------------------------------------------
# HTML rendering helpers
# ---------------------------------------------------------------------------

def _esc(text: str) -> str:
    """HTML-escape text, preserving newlines as <br>."""
    escaped = html.escape(str(text))
    return escaped.replace("\n", "<br>")


def _get_style(role: str) -> dict:
    """Get the visual style dict for a given role."""
    key = role.lower().strip()
    return SPEAKER_STYLES.get(key, SPEAKER_STYLES["system"])


def _render_topic_card(content: str) -> str:
    """Render the user's initial question as a topic card."""
    return (
        '<div class="phd-topic-card">'
        '<div class="phd-topic-label">Topic for Discussion</div>'
        f'<div class="phd-topic-content">{_esc(content)}</div>'
        '</div>'
    )


def _render_round_separator(round_num: int) -> str:
    """Render a round divider line."""
    return (
        '<div class="phd-round-sep">'
        f'<span class="phd-round-text">Round {round_num}</span>'
        '</div>'
    )


def _render_message(role: str, content: str, round_num: int = 0) -> str:
    """Render a philosopher or user message as a chat turn."""
    style = _get_style(role)
    meta = f"Round {round_num}" if round_num > 0 else ""
    return (
        f'<div class="phd-turn">'
        f'  <div class="phd-avatar" style="background:{style["color"]};">{style["initials"]}</div>'
        f'  <div class="phd-msg-body">'
        f'    <div class="phd-msg-header">'
        f'      <span class="phd-speaker" style="color:{style["text_color"]};">{style["display_name"]}</span>'
        f'      <span class="phd-meta">{meta}</span>'
        f'    </div>'
        f'    <div class="phd-card" style="border-left-color:{style["color"]}; background:{style["bg"]};">'
        f'      <div class="phd-content">{_esc(content)}</div>'
        f'    </div>'
        f'  </div>'
        f'</div>'
    )


def _render_moderator_context(content: str) -> str:
    """Render moderator context as a collapsible details element."""
    # Parse SUMMARY and GUIDANCE from the content
    lines = content.strip().splitlines()
    summary = ""
    guidance = ""
    target = ""

    for line in lines:
        stripped = line.strip()
        upper = stripped.upper()
        if upper.startswith("MODERATOR CONTEXT"):
            # Extract target from "MODERATOR CONTEXT (for Confucius):"
            if "(" in stripped and ")" in stripped:
                target = stripped[stripped.index("(") + 1:stripped.index(")")]
        elif upper.startswith("SUMMARY:"):
            summary = stripped.split(":", 1)[1].strip() if ":" in stripped else ""
        elif upper.startswith("AI GUIDANCE:") or upper.startswith("GUIDANCE:"):
            guidance = stripped.split(":", 1)[1].strip() if ":" in stripped else ""

    target_text = f" for {_esc(target)}" if target else ""
    body_parts = []
    if summary:
        body_parts.append(f'<strong>Summary:</strong> {_esc(summary)}')
    if guidance:
        body_parts.append(f'<strong>Guidance:</strong> {_esc(guidance)}')
    if not body_parts:
        body_parts.append(_esc(content))

    body_html = "<br>".join(body_parts)

    return (
        f'<details class="phd-mod-ctx">'
        f'  <summary class="phd-mod-toggle">&#9881; Moderator Context{_esc(target_text)}</summary>'
        f'  <div class="phd-mod-body">{body_html}</div>'
        f'</details>'
    )


def _render_user_guidance(content: str) -> str:
    """Render user guidance message."""
    # Strip the "USER GUIDANCE FOR <name>:" prefix if present
    display = content
    if ":" in content and content.strip().upper().startswith("USER GUIDANCE"):
        display = content.split(":", 1)[1].strip()
    elif content.strip().upper().startswith("SYSTEM:"):
        display = content.split(":", 1)[1].strip()

    return (
        f'<div class="phd-guidance">'
        f'  <div class="phd-guidance-label">Your Guidance</div>'
        f'  {_esc(display)}'
        f'</div>'
    )


def _render_error(content: str) -> str:
    """Render an error message."""
    return f'<div class="phd-error">{_esc(content)}</div>'


def _render_empty_state() -> str:
    """Render the empty conversation state."""
    return (
        '<div class="phd-empty">'
        '  <div class="phd-empty-icon">&#x1F4AC;</div>'
        '  <div class="phd-empty-text">Begin a philosophical dialogue</div>'
        '  <div class="phd-empty-hint">Enter a question below to start the conversation between Socrates and Confucius</div>'
        '</div>'
    )


def _render_completion_banner(mode: str, num_rounds: int) -> str:
    """Render the conversation completion banner."""
    return (
        '<div class="phd-complete">'
        f'  <div class="phd-complete-text">Dialogue complete &mdash; {num_rounds} round{"s" if num_rounds != 1 else ""} in {_esc(mode)} mode</div>'
        '</div>'
    )


def _render_waiting_indicator(next_speaker: str) -> str:
    """Render the waiting-for-guidance indicator."""
    return (
        '<div class="phd-waiting">'
        f'  <span class="phd-waiting-label">Awaiting your guidance for {_esc(next_speaker)}</span>'
        '  <span class="phd-dots">'
        '    <span class="phd-dot"></span>'
        '    <span class="phd-dot"></span>'
        '    <span class="phd-dot"></span>'
        '  </span>'
        '</div>'
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def inject_chat_css():
    """Inject the chat stylesheet into the page. Call once at page top."""
    st.markdown(CHAT_CSS, unsafe_allow_html=True)


def display_header():
    """Render the application header."""
    st.markdown(
        '<div class="phd-header">'
        '  <h1 class="phd-title">Philosopher Dialogue</h1>'
        '  <p class="phd-subtitle">A moderated conversation between Socrates and Confucius</p>'
        '</div>',
        unsafe_allow_html=True,
    )


def get_model_info_from_config(config_path: str = "llm_config.json") -> Dict[str, str]:
    """Load model names from config for sidebar display."""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        return {
            "Socrates": config.get("socrates", {}).get("model_name", "Unknown"),
            "Confucius": config.get("confucius", {}).get("model_name", "Unknown"),
            "Moderator": config.get("moderator", {}).get("model_name", "Unknown"),
        }
    except Exception as e:
        logger.warning(f"Could not load model info: {e}")
        return {"Socrates": "Unknown", "Confucius": "Unknown", "Moderator": "Unknown"}


def display_sidebar(model_info: Dict[str, str]):
    """Render the sidebar configuration panel."""
    with st.sidebar:
        st.header("Configuration")

        # --- Conversation Setup ---
        st.radio(
            "Conversation Mode:",
            options=["Philosophy", "Bio"],
            format_func=lambda x: "Philosophical" if x == "Philosophy" else "Biographical",
            key="conversation_mode",
            index=0,
            horizontal=True,
            help="Select the conversation topic focus.",
        )

        st.radio(
            "Starting Philosopher:",
            ("Socrates", "Confucius"),
            key="starting_philosopher",
            horizontal=True,
            index=0,
        )

        st.number_input(
            "Number of Rounds:",
            min_value=1,
            max_value=10,
            step=1,
            key="num_rounds",
            help="One round = one response from each philosopher.",
        )

        st.divider()

        # --- Moderation ---
        st.radio(
            "Moderator Control:",
            options=["AI Moderator", "User as Moderator (Guidance)"],
            key="moderator_control_mode",
            index=0,
            horizontal=True,
            help="Choose who provides guidance: AI or You. AI always provides summary.",
        )

        st.checkbox(
            "Bypass Moderator",
            key="bypass_moderator_cb",
            value=st.session_state.get("bypass_moderator_cb", False),
            help="Philosophers respond directly without moderator.",
        )

        st.divider()

        # --- Display ---
        st.radio(
            "Output Style:",
            ("Original Text", "Translated Text"),
            key="output_style",
            horizontal=True,
            index=0,
            help="View original dialogue or a casual translation (applied after completion).",
        )

        st.checkbox(
            "Show Moderator Context",
            key="show_moderator_cb",
            value=st.session_state.get("show_moderator_cb", False),
            help="Show/hide the moderator's summary and guidance blocks.",
        )

        st.checkbox(
            "Show Internal Monologue",
            key="show_monologue_cb",
            value=st.session_state.get("show_monologue_cb", False),
            help="Show/hide the LLM's <think> blocks.",
        )

        st.divider()

        # --- Model Info (compact) ---
        with st.expander("Model Info", expanded=False):
            st.markdown(f"**Socrates:** `{model_info.get('Socrates', 'Unknown')}`")
            st.markdown(f"**Confucius:** `{model_info.get('Confucius', 'Unknown')}`")
            st.markdown(f"**Moderator:** `{model_info.get('Moderator', 'Unknown')}`")


def display_conversation(
    messages: List[Dict[str, Any]],
    show_moderator_ctx: Optional[bool] = None,
    conversation_completed: bool = False,
    awaiting_guidance: bool = False,
    next_speaker_for_guidance: str = "",
    num_rounds: int = 0,
    mode: str = "",
):
    """
    Render the full conversation using custom HTML.

    This replaces the old st.chat_message approach with a modern
    turn-by-turn chat interface featuring:
    - Color-coded speakers with avatar circles
    - Left-border accent on message cards
    - Round separators
    - Collapsible moderator context
    - Serif typography for dialogue
    """
    if show_moderator_ctx is None:
        show_moderator_ctx = st.session_state.get("show_moderator_cb", False)

    if not messages:
        st.markdown(_render_empty_state(), unsafe_allow_html=True)
        return

    html_parts = ['<div class="phd-container">']
    philosopher_turn_count = 0
    current_round = 0

    for msg in messages:
        role = msg.get("role", "system")
        content = msg.get("content", "")
        role_lower = role.lower().strip()

        # --- User message → topic card ---
        if role_lower == "user":
            html_parts.append(_render_topic_card(content))
            continue

        # --- Philosopher messages ---
        if role_lower in ("socrates", "confucius"):
            philosopher_turn_count += 1
            round_num = (philosopher_turn_count - 1) // 2 + 1

            # Insert round separator at the start of each new round
            if round_num != current_round:
                current_round = round_num
                html_parts.append(_render_round_separator(round_num))

            html_parts.append(_render_message(role, content, round_num))
            continue

        # --- System messages (moderator context, guidance, errors, translation) ---
        if role_lower == "system":
            content_str = str(content).strip() if content else ""
            content_upper = content_str.upper()

            # Moderator context
            if content_upper.startswith("MODERATOR CONTEXT"):
                if show_moderator_ctx:
                    html_parts.append(_render_moderator_context(content_str))
                continue

            # User guidance
            if content_upper.startswith("USER GUIDANCE FOR") or content_upper.startswith("SYSTEM: USER OPTED"):
                if show_moderator_ctx:
                    html_parts.append(_render_user_guidance(content_str))
                continue

            # Error messages
            if content_upper.startswith("ERROR:"):
                html_parts.append(_render_error(content_str))
                continue

            # Translated conversation or other system messages
            if content_str:
                # For translated text or general system messages,
                # render as a simple card
                html_parts.append(
                    f'<div style="padding:12px 16px; margin:8px 0; '
                    f'border-radius:10px; background:#fafafa; '
                    f'font-family:Georgia,Cambria,serif; font-size:16px; '
                    f'line-height:1.75; color:#1a1a1a;">'
                    f'{_esc(content_str)}</div>'
                )
            continue

        # --- Fallback: unknown role (treat as philosopher-like) ---
        html_parts.append(_render_message(role, content))

    # --- Waiting indicator ---
    if awaiting_guidance and next_speaker_for_guidance:
        html_parts.append(_render_waiting_indicator(next_speaker_for_guidance))

    # --- Completion banner ---
    if conversation_completed and not awaiting_guidance:
        html_parts.append(
            _render_completion_banner(mode or "Philosophy", num_rounds or current_round)
        )

    html_parts.append('</div>')

    st.markdown("\n".join(html_parts), unsafe_allow_html=True)


def display_monologue(messages: List[Dict[str, Any]]):
    """Render internal monologue/thinking in an expander if enabled."""
    if not st.session_state.get("show_monologue_cb", False):
        return

    monologue_entries = []
    for msg in messages:
        if isinstance(msg, dict):
            monologue = msg.get("monologue")
            role = msg.get("role", "Unknown")
            if monologue:
                monologue_entries.append((role, monologue))

    if not monologue_entries:
        return

    with st.expander("Internal Monologue / Thinking", expanded=False):
        for role, text in monologue_entries:
            style = _get_style(role)
            st.markdown(
                f'**<span style="color:{style["text_color"]};">[{style["display_name"]}] Thinking:</span>**',
                unsafe_allow_html=True,
            )
            st.text(str(text))
            st.divider()
