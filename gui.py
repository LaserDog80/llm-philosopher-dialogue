# gui.py — "Warm Study" modern chat interface with custom HTML/CSS rendering.
# Design: warm neutrals, soft neumorphic depth, Manrope + Inter fonts.

import html
import json
import logging
import streamlit as st
from typing import List, Dict, Any, Optional

from core.registry import get_speaker_styles, get_display_names, get_philosopher_ids, get_philosopher
from core.config import load_llm_params

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Speaker visual configuration — loaded from philosophers.json registry
# ---------------------------------------------------------------------------
SPEAKER_STYLES = get_speaker_styles()

# Reverse lookup: lowercased display name -> style key (philosopher ID).
# Handles cases like "Sima Qian" -> "simaqian" where display_name.lower() != id.
_DISPLAY_NAME_TO_KEY = {
    style["display_name"].lower(): key for key, style in SPEAKER_STYLES.items()
}

# ---------------------------------------------------------------------------
# CSS Stylesheet — "Warm Study" theme
# ---------------------------------------------------------------------------
CHAT_CSS = """<style>
/* ===== Warm Study — Minimal Overrides ===== */

/* Hide Streamlit sidebar and page navigation */
section[data-testid="stSidebar"],
button[data-testid="stSidebarCollapsedControl"],
div[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"] {
    display: none !important;
}

/* ===== Top Header Bar ===== */
.ws-header-bar {
    display: flex;
    align-items: center;
    padding: 8px 0 20px;
    border-bottom: 1px solid #EDE8E0;
    margin-bottom: 16px;
}
.ws-header-left {
    display: flex;
    align-items: center;
    gap: 12px;
}
.ws-header-icon {
    width: 40px;
    height: 40px;
    border-radius: 12px;
    background: linear-gradient(135deg, #8B9D83 0%, #C9956B 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    box-shadow: 0 4px 12px rgba(45,38,32,0.1);
}
.ws-title {
    font-size: 22px;
    font-weight: 700;
    color: #2D2620;
    margin: 0;
    letter-spacing: -0.5px;
}
.ws-subtitle {
    font-size: 13px;
    color: #A39B8F;
    margin: 0;
    font-weight: 400;
}

/* ===== Container ===== */
.phd-container {
    max-width: 740px;
    margin: 0 auto;
    padding: 0;
}

/* ===== Topic Card ===== */
.phd-topic-card {
    background: #FEFDFB;
    border: 1px solid #E0D9CF;
    border-radius: 16px;
    padding: 22px 26px;
    margin-bottom: 28px;
    box-shadow: 0 4px 16px rgba(45,38,32,0.05),
                inset 0 1px 0 rgba(255,255,255,0.8);
}
.phd-topic-label {
    font-family: 'Manrope', sans-serif;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 2px;
    color: #A39B8F;
    margin-bottom: 10px;
    font-weight: 600;
}
.phd-topic-content {
    font-family: 'Inter', sans-serif;
    font-size: 17px;
    line-height: 1.6;
    color: #2D2620;
    font-weight: 400;
}

/* ===== Round Separator ===== */
.phd-round-sep {
    display: flex;
    align-items: center;
    margin: 28px 0 18px;
    gap: 16px;
}
.phd-round-sep::before,
.phd-round-sep::after {
    content: '';
    flex: 1;
    height: 1px;
    background: linear-gradient(to right, transparent, #D4CFC6, transparent);
}
.phd-round-text {
    font-family: 'Manrope', sans-serif;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 2.5px;
    color: #B5ADA3;
    white-space: nowrap;
    font-weight: 600;
}

/* ===== Message Turn ===== */
.phd-turn {
    display: flex;
    align-items: flex-start;
    gap: 14px;
    padding: 8px 0;
    margin: 8px 0;
}

/* ===== Avatar ===== */
.phd-avatar {
    width: 40px;
    height: 40px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    font-family: 'Manrope', sans-serif;
    font-weight: 700;
    font-size: 15px;
    color: white;
    box-shadow: 0 3px 10px rgba(45,38,32,0.12);
}

/* ===== Message Body ===== */
.phd-msg-body {
    flex: 1;
    min-width: 0;
}
.phd-msg-header {
    display: flex;
    align-items: baseline;
    gap: 10px;
    margin-bottom: 6px;
}
.phd-speaker {
    font-family: 'Manrope', sans-serif;
    font-weight: 600;
    font-size: 14px;
    letter-spacing: -0.2px;
}
.phd-meta {
    font-family: 'Inter', sans-serif;
    font-size: 11px;
    color: #B5ADA3;
    font-weight: 400;
}

/* ===== Message Card — neumorphic ===== */
.phd-card {
    padding: 16px 20px;
    border-radius: 14px;
    border-left: 3px solid transparent;
    box-shadow: 0 4px 16px rgba(45,38,32,0.05),
                inset 0 1px 0 rgba(255,255,255,0.6);
    transition: box-shadow 0.2s ease;
}
.phd-card:hover {
    box-shadow: 0 6px 20px rgba(45,38,32,0.08),
                inset 0 1px 0 rgba(255,255,255,0.6);
}
.phd-content {
    font-family: 'Inter', sans-serif;
    font-size: 15px;
    line-height: 1.8;
    color: #2D2620;
    word-wrap: break-word;
    overflow-wrap: break-word;
}
.phd-content p {
    margin: 0 0 10px;
}
.phd-content p:last-child {
    margin-bottom: 0;
}

/* ===== Moderator Context (collapsible) ===== */
.phd-mod-ctx {
    margin: 6px 0 6px 54px;
    border-radius: 10px;
}
.phd-mod-toggle {
    font-family: 'Inter', sans-serif;
    font-size: 12px;
    color: #A39B8F;
    cursor: pointer;
    padding: 6px 12px;
    border-radius: 8px;
    list-style: none;
    display: flex;
    align-items: center;
    gap: 6px;
    user-select: none;
    transition: all 0.2s ease;
}
.phd-mod-toggle::-webkit-details-marker { display: none; }
.phd-mod-toggle:hover {
    background: rgba(45,38,32,0.04);
    color: #6B6460;
}
.phd-mod-body {
    padding: 10px 14px 12px;
    font-family: 'Inter', sans-serif;
    font-size: 13px;
    line-height: 1.6;
    color: #6B6460;
    background: #F5F1EB;
    border-radius: 0 0 8px 8px;
}
.phd-mod-body strong {
    color: #4A4540;
}

/* ===== User Guidance ===== */
.phd-guidance {
    margin: 6px 0 10px 54px;
    padding: 10px 16px;
    border-radius: 10px;
    border-left: 3px solid #8B9D83;
    background: #F0F4ED;
    font-family: 'Inter', sans-serif;
    font-size: 13px;
    color: #5A6E52;
    line-height: 1.6;
    box-shadow: 0 2px 8px rgba(45,38,32,0.04);
}
.phd-guidance-label {
    font-family: 'Manrope', sans-serif;
    font-weight: 600;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: #7C9A8E;
    margin-bottom: 4px;
}

/* ===== Error Message ===== */
.phd-error {
    margin: 6px 0 10px 54px;
    padding: 10px 16px;
    border-radius: 10px;
    border-left: 3px solid #C9736B;
    background: #FDF3F1;
    font-family: 'Inter', sans-serif;
    font-size: 13px;
    color: #A0453B;
}

/* ===== Empty State ===== */
.phd-empty {
    text-align: center;
    padding: 72px 24px;
}
.phd-empty-icon {
    font-size: 48px;
    margin-bottom: 16px;
    opacity: 0.35;
}
.phd-empty-text {
    font-family: 'Manrope', sans-serif;
    font-size: 20px;
    color: #6B6460;
    margin-bottom: 10px;
    font-weight: 600;
}
.phd-empty-hint {
    font-family: 'Inter', sans-serif;
    font-size: 14px;
    color: #B5ADA3;
    font-weight: 400;
}

/* ===== Completion Banner ===== */
.phd-complete {
    text-align: center;
    padding: 18px 24px;
    margin: 24px 0 8px;
    border-radius: 14px;
    background: #FEFDFB;
    border: 1px solid #E0D9CF;
    box-shadow: 0 4px 16px rgba(45,38,32,0.05);
}
.phd-complete-text {
    font-family: 'Manrope', sans-serif;
    font-size: 14px;
    color: #6B6460;
    font-weight: 500;
}

/* ===== Progress Bar ===== */
.ws-progress-container {
    margin: 16px 0 8px 54px;
    padding: 14px 18px;
    border-radius: 12px;
    background: #FEFDFB;
    border: 1px solid #E0D9CF;
    box-shadow: 0 2px 10px rgba(45,38,32,0.04);
}
.ws-progress-status {
    font-family: 'Inter', sans-serif;
    font-size: 13px;
    color: #6B6460;
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.ws-progress-track {
    width: 100%;
    height: 4px;
    background: #EDE8E0;
    border-radius: 4px;
    overflow: hidden;
    margin-bottom: 6px;
}
.ws-progress-fill {
    height: 100%;
    border-radius: 4px;
    background: linear-gradient(90deg, #8B9D83 0%, #C9956B 100%);
    transition: width 0.5s ease;
}
.ws-progress-label {
    font-family: 'Inter', sans-serif;
    font-size: 11px;
    color: #B5ADA3;
    text-align: right;
}

/* ===== Waiting / Thinking Indicator ===== */
.phd-waiting {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 14px 18px;
    margin: 14px 0 6px 54px;
    border-radius: 12px;
    border-left: 3px solid #8B9D83;
    background: #F5F1EB;
    box-shadow: 0 2px 10px rgba(45,38,32,0.04);
}
.phd-waiting-label {
    font-family: 'Inter', sans-serif;
    font-size: 13px;
    font-style: italic;
    color: #7C9A8E;
    font-weight: 500;
}

/* Wave dots animation */
.phd-dots {
    display: inline-flex;
    gap: 4px;
    align-items: center;
}
.phd-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #8B9D83;
    animation: ws-wave 1.4s infinite ease-in-out both;
}
.phd-dot:nth-child(1) { animation-delay: -0.32s; }
.phd-dot:nth-child(2) { animation-delay: -0.16s; }
.phd-dot:nth-child(3) { animation-delay: 0s; }
@keyframes ws-wave {
    0%, 80%, 100% {
        transform: translateY(0) scale(0.8);
        opacity: 0.4;
    }
    40% {
        transform: translateY(-4px) scale(1);
        opacity: 1;
    }
}

/* ===== Thinking Indicator (used during LLM processing) ===== */
.ws-thinking {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 14px 18px;
    margin: 14px 0 6px 0;
    border-radius: 12px;
    background: #F5F1EB;
    border: 1px solid #E0D9CF;
    box-shadow: 0 2px 10px rgba(45,38,32,0.04);
}
.ws-thinking-label {
    font-family: 'Inter', sans-serif;
    font-size: 14px;
    color: #6B6460;
    font-weight: 500;
}
.ws-thinking-dots {
    display: inline-flex;
    gap: 4px;
    align-items: center;
}
.ws-thinking-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: linear-gradient(135deg, #8B9D83, #C9956B);
    animation: ws-wave 1.4s infinite ease-in-out both;
}
.ws-thinking-dot:nth-child(1) { animation-delay: -0.32s; }
.ws-thinking-dot:nth-child(2) { animation-delay: -0.16s; }
.ws-thinking-dot:nth-child(3) { animation-delay: 0s; }

/* ===== Settings Panel Styling ===== */
.ws-settings-section {
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: #A39B8F;
    margin: 16px 0 8px;
    padding-bottom: 4px;
    border-bottom: 1px solid #EDE8E0;
}

/* ===== Responsive ===== */
@media (max-width: 768px) {
    .phd-turn { gap: 10px; }
    .phd-avatar { width: 34px; height: 34px; font-size: 13px; border-radius: 10px; }
    .phd-content { font-size: 14px; line-height: 1.7; }
    .phd-topic-card { padding: 18px 20px; }
    .phd-mod-ctx, .phd-guidance, .phd-error, .phd-waiting,
    .ws-progress-container { margin-left: 44px; }
    .ws-title { font-size: 20px; }
}
@media (max-width: 480px) {
    .phd-avatar { width: 28px; height: 28px; font-size: 11px; border-radius: 8px; }
    .phd-content { font-size: 13px; }
    .phd-card { padding: 12px 14px; }
    .phd-mod-ctx, .phd-guidance, .phd-error, .phd-waiting,
    .ws-progress-container { margin-left: 38px; }
    .ws-title { font-size: 18px; }
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
    # Try direct ID match first, then display-name reverse lookup
    if key in SPEAKER_STYLES:
        return SPEAKER_STYLES[key]
    resolved = _DISPLAY_NAME_TO_KEY.get(key)
    if resolved:
        return SPEAKER_STYLES[resolved]
    return SPEAKER_STYLES["system"]


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


def _render_message(role: str, content: str, round_num: int = 0, intent: str = "") -> str:
    """Render a philosopher or user message as a chat turn."""
    style = _get_style(role)
    meta_parts = []
    if round_num > 0:
        meta_parts.append(f"Round {round_num}")
    if intent:
        meta_parts.append(intent)
    meta = " &middot; ".join(meta_parts)
    border_color = style.get("border", style["color"])
    return (
        f'<div class="phd-turn">'
        f'  <div class="phd-avatar" style="background:{style["color"]};">{style["initials"]}</div>'
        f'  <div class="phd-msg-body">'
        f'    <div class="phd-msg-header">'
        f'      <span class="phd-speaker" style="color:{style["text_color"]};">{style["display_name"]}</span>'
        f'      <span class="phd-meta">{meta}</span>'
        f'    </div>'
        f'    <div class="phd-card" style="border-left-color:{border_color}; background:{style["bg"]};">'
        f'      <div class="phd-content">{_esc(content)}</div>'
        f'    </div>'
        f'  </div>'
        f'</div>'
    )


def _render_moderator_context(content: str) -> str:
    """Render moderator context as a collapsible details element."""
    lines = content.strip().splitlines()
    summary = ""
    guidance = ""
    target = ""

    for line in lines:
        stripped = line.strip()
        upper = stripped.upper()
        if upper.startswith("MODERATOR CONTEXT"):
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
    p1 = st.session_state.get("philosopher_1", "Socrates")
    p2 = st.session_state.get("philosopher_2", "Confucius")
    return (
        '<div class="phd-empty">'
        '  <div class="phd-empty-icon">&#x1F3DB;</div>'
        '  <div class="phd-empty-text">Begin a philosophical dialogue</div>'
        f'  <div class="phd-empty-hint">Enter a question below to start the conversation between {_esc(p1)} and {_esc(p2)}</div>'
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
    """Render the waiting-for-guidance indicator with wave dots."""
    return (
        '<div class="phd-waiting">'
        '  <span class="phd-dots">'
        '    <span class="phd-dot"></span>'
        '    <span class="phd-dot"></span>'
        '    <span class="phd-dot"></span>'
        '  </span>'
        f'  <span class="phd-waiting-label">Awaiting your guidance for {_esc(next_speaker)}</span>'
        '</div>'
    )


def _render_progress_bar(current_round: int, total_rounds: int, speaker: str = "") -> str:
    """Render a round-aware progress bar with speaker status."""
    pct = min(100, int((current_round / max(total_rounds, 1)) * 100))
    speaker_text = f"{_esc(speaker)} is reflecting..." if speaker else "Processing..."
    return (
        '<div class="ws-progress-container">'
        f'  <div class="ws-progress-status">'
        f'    <span class="phd-dots">'
        f'      <span class="phd-dot"></span>'
        f'      <span class="phd-dot"></span>'
        f'      <span class="phd-dot"></span>'
        f'    </span>'
        f'    {speaker_text}'
        f'  </div>'
        f'  <div class="ws-progress-track">'
        f'    <div class="ws-progress-fill" style="width:{pct}%;"></div>'
        f'  </div>'
        f'  <div class="ws-progress-label">Round {current_round} of {total_rounds}</div>'
        '</div>'
    )


def render_thinking_indicator(text: str = "Philosophers are conferring...") -> str:
    """Render an inline thinking/loading indicator."""
    return (
        '<div class="ws-thinking">'
        '  <span class="ws-thinking-dots">'
        '    <span class="ws-thinking-dot"></span>'
        '    <span class="ws-thinking-dot"></span>'
        '    <span class="ws-thinking-dot"></span>'
        '  </span>'
        f'  <span class="ws-thinking-label">{_esc(text)}</span>'
        '</div>'
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def inject_chat_css():
    """Inject the chat stylesheet into the page. Call once at page top."""
    st.markdown(CHAT_CSS, unsafe_allow_html=True)


def display_header():
    """Render the Warm Study application header."""
    p1 = st.session_state.get("philosopher_1", "Socrates")
    p2 = st.session_state.get("philosopher_2", "Confucius")
    subtitle = f"A self-directed dialogue between {html.escape(p1)} and {html.escape(p2)}"
    st.markdown(
        '<div class="ws-header-bar">'
        '  <div class="ws-header-left">'
        '    <div class="ws-header-icon">&#x1F3DB;</div>'
        '    <div>'
        '      <h1 class="ws-title">Philosopher Dialogue</h1>'
        f'      <p class="ws-subtitle">{subtitle}</p>'
        '    </div>'
        '  </div>'
        '</div>',
        unsafe_allow_html=True,
    )


def get_model_info_from_config(config_path: str = "llm_config.json") -> Dict[str, str]:
    """Load model names from config for display.

    Uses the philosopher registry so the list adapts automatically when
    a new philosopher is added to ``philosophers.json``.
    """
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        from core.registry import load_registry
        reg = load_registry()
        info: Dict[str, str] = {}
        for pid, pcfg in reg.items():
            if pid == "moderator":
                continue  # Moderator LLM is no longer used; routing is rule-based
            info[pcfg.display_name] = config.get(pid, {}).get("model_name", "Unknown")
        return info
    except Exception as e:
        logger.warning(f"Could not load model info: {e}")
        return {}


def display_settings_popover(model_info: Dict[str, str]):
    """Render the settings as a popover triggered by a gear button."""

    with st.popover("Settings", use_container_width=False):
        # --- Conversation Section ---
        st.markdown('<div class="ws-settings-section">Conversation</div>', unsafe_allow_html=True)

        st.radio(
            "Mode:",
            options=["Philosophy", "Bio"],
            format_func=lambda x: "Philosophical" if x == "Philosophy" else "Biographical",
            key="conversation_mode",
            index=0,
            horizontal=True,
            help="Select the conversation topic focus.",
        )

        _philosopher_names = get_display_names()
        st.selectbox(
            "Philosopher 1 (speaks first):",
            _philosopher_names,
            key="philosopher_1",
        )
        st.selectbox(
            "Philosopher 2:",
            _philosopher_names,
            key="philosopher_2",
        )

        st.number_input(
            "Number of Rounds:",
            min_value=1,
            max_value=10,
            step=1,
            key="num_rounds",
            help="One round = one response from each philosopher.",
        )

        _p1_name = st.session_state.get("philosopher_1", "Philosopher 1")
        _p2_name = st.session_state.get("philosopher_2", "Philosopher 2")

        # Helper to get per-philosopher default max_tokens from voice profile
        def _get_default_tokens(name: str) -> int:
            pid = name.lower().replace(" ", "")
            pcfg = get_philosopher(pid)
            if pcfg and pcfg.voice_profile:
                return pcfg.voice_profile.get("default_max_tokens", 400)
            return 400

        from core.config import _tokens_to_sentence_range

        # Check for pending resets before rendering sliders (Streamlit
        # does not allow session state changes after widget instantiation).
        for slider_key, phil_name in [
            ("max_tokens_p1", _p1_name),
            ("max_tokens_p2", _p2_name),
        ]:
            reset_flag = f"_pending_reset_{slider_key}"
            if st.session_state.pop(reset_flag, False):
                st.session_state[slider_key] = _get_default_tokens(phil_name)

        with st.expander("Verbosity (experimental)", expanded=False):
            st.caption("Hint only — use Shorter/Longer buttons after a conversation for reliable control.")
            for label, slider_key, phil_name in [
                (f"Verbosity — {_p1_name}", "max_tokens_p1", _p1_name),
                (f"Verbosity — {_p2_name}", "max_tokens_p2", _p2_name),
            ]:
                default_tokens = _get_default_tokens(phil_name)
                col_slider, col_reset = st.columns([5, 1])
                with col_slider:
                    current_val = st.session_state.get(slider_key, default_tokens)
                    sentence_hint = _tokens_to_sentence_range(current_val)
                    st.slider(
                        f"{label} ({sentence_hint} sentences):",
                        min_value=100,
                        max_value=800,
                        step=50,
                        key=slider_key,
                        disabled=True,
                    )
                with col_reset:
                    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                    if st.button("↺", key=f"reset_{slider_key}",
                                 help=f"Reset to {phil_name}'s default ({default_tokens})",
                                 disabled=True):
                        st.session_state[f"_pending_reset_{slider_key}"] = True
                        st.rerun()

        # --- Character Notes Section ---
        st.markdown('<div class="ws-settings-section">Character Notes</div>', unsafe_allow_html=True)
        st.caption("Add optional style instructions for each philosopher. "
                   "These take effect the next time you start a conversation.")

        st.text_area(
            f"Notes for {_p1_name}:",
            key="personality_notes_p1",
            height=80,
            placeholder="e.g. 'Be more gossipy, use more parenthetical asides'",
            help="These notes are added to the philosopher's system prompt to adjust their speaking style.",
        )
        st.text_area(
            f"Notes for {_p2_name}:",
            key="personality_notes_p2",
            height=80,
            placeholder="e.g. 'Be more restrained, let emotion show through brevity'",
            help="These notes are added to the philosopher's system prompt to adjust their speaking style.",
        )

        # --- Display Section ---
        st.markdown('<div class="ws-settings-section">Display</div>', unsafe_allow_html=True)

        st.radio(
            "Output Style:",
            ("Original Text", "Translated Text"),
            key="output_style",
            horizontal=True,
            index=0,
            help="View original dialogue or a casual translation.",
        )

        st.checkbox(
            "Show Internal Monologue",
            key="show_monologue_cb",
            value=st.session_state.get("show_monologue_cb", False),
        )

        # --- Model Info ---
        st.markdown('<div class="ws-settings-section">Models</div>', unsafe_allow_html=True)
        for name, model in model_info.items():
            st.caption(f"**{name}:** {model}")

        # --- Per-Philosopher Config Viewer ---
        _p1_key = _p1_name.lower().replace(" ", "")
        _p2_key = _p2_name.lower().replace(" ", "")
        for label, pkey, notes_key, tokens_key in [
            (_p1_name, _p1_key, "personality_notes_p1", "max_tokens_p1"),
            (_p2_name, _p2_key, "personality_notes_p2", "max_tokens_p2"),
        ]:
            with st.expander(f"Config: {label}"):
                params = load_llm_params(pkey)
                current_tokens = st.session_state.get(tokens_key, 400)
                effective_sentences = _tokens_to_sentence_range(current_tokens)
                if params:
                    st.caption(
                        f"**Temperature:** {params.get('temperature', '—')}  \n"
                        f"**Max Tokens:** {current_tokens} (→ {effective_sentences} sentences)  \n"
                        f"**Top P:** {params.get('top_p', '—')}  \n"
                        f"**Presence Penalty:** {params.get('presence_penalty', 0.0)}  \n"
                        f"**Frequency Penalty:** {params.get('frequency_penalty', 0.0)}"
                    )
                pcfg_viewer = get_philosopher(pkey)
                if pcfg_viewer and pcfg_viewer.voice_profile:
                    vp = pcfg_viewer.voice_profile
                    parts = []
                    if vp.get("style_keywords"):
                        parts.append(f"**Style:** {', '.join(vp['style_keywords'])}")
                    if parts:
                        st.caption("  \n".join(parts))
                    if vp.get("personality_summary"):
                        st.caption(f"**Personality:** {vp['personality_summary']}")
                notes = st.session_state.get(notes_key, "")
                if notes and notes.strip():
                    st.caption(f"**Active Notes:** {notes.strip()}")


def display_conversation(
    messages: List[Dict[str, Any]],
    show_moderator_ctx: Optional[bool] = None,
    conversation_completed: bool = False,
    awaiting_guidance: bool = False,
    next_speaker_for_guidance: str = "",
    num_rounds: int = 0,
    mode: str = "",
    is_translated_view: bool = False,
):
    """Render the full conversation using custom HTML."""
    if show_moderator_ctx is None:
        show_moderator_ctx = st.session_state.get("show_moderator_cb", False)

    if not messages:
        st.markdown(_render_empty_state(), unsafe_allow_html=True)
        return

    html_parts = ['<div class="phd-container">']
    philosopher_turn_count = 0
    current_round = 0

    for msg_idx, msg in enumerate(messages):
        role = msg.get("role", "system")
        content = msg.get("content", "")
        role_lower = role.lower().strip()

        # --- User message -> topic card ---
        if role_lower == "user":
            html_parts.append(_render_topic_card(content))
            continue

        # --- Philosopher messages ---
        _philosopher_ids = set(get_philosopher_ids())
        _is_philosopher = role_lower in _philosopher_ids or _DISPLAY_NAME_TO_KEY.get(role_lower) in _philosopher_ids
        if _is_philosopher:
            philosopher_turn_count += 1
            round_num = (philosopher_turn_count - 1) // 2 + 1

            if round_num != current_round:
                current_round = round_num
                html_parts.append(_render_round_separator(round_num))

            intent = msg.get("intent", "")
            html_parts.append(_render_message(role, content, round_num, intent=intent))

            # Flush HTML buffer before rendering Streamlit buttons.
            # Close the container div so each fragment is self-contained.
            if html_parts:
                html_parts.append('</div>')
                st.markdown("".join(html_parts), unsafe_allow_html=True)
                html_parts = ['<div class="phd-container">']

            # Editor buttons (only after conversation is complete, not on translated view)
            if conversation_completed and not is_translated_view:
                _edit_left, _edit_spacer = st.columns([3, 9])
                with _edit_left:
                    _eb1, _eb2 = st.columns(2)
                    with _eb1:
                        if st.button("Shorter", key=f"edit_shorter_{msg_idx}"):
                            st.session_state["_editor_request"] = {
                                "index": msg_idx, "direction": "shorter"
                            }
                            st.rerun()
                    with _eb2:
                        if st.button("Longer", key=f"edit_longer_{msg_idx}"):
                            st.session_state["_editor_request"] = {
                                "index": msg_idx, "direction": "longer"
                            }
                            st.rerun()

            continue

        # --- System messages ---
        if role_lower == "system":
            content_str = str(content).strip() if content else ""
            content_upper = content_str.upper()

            if content_upper.startswith("MODERATOR CONTEXT"):
                if show_moderator_ctx:
                    html_parts.append(_render_moderator_context(content_str))
                continue

            if content_upper.startswith("USER GUIDANCE FOR") or content_upper.startswith("SYSTEM: USER OPTED"):
                if show_moderator_ctx:
                    html_parts.append(_render_user_guidance(content_str))
                continue

            if content_upper.startswith("ERROR:"):
                html_parts.append(_render_error(content_str))
                continue

            if content_str:
                html_parts.append(
                    f'<div style="padding:14px 18px; margin:10px 0; '
                    f'border-radius:14px; background:#FEFDFB; border:1px solid #E0D9CF; '
                    f'font-family:Inter,sans-serif; font-size:15px; '
                    f'line-height:1.8; color:#2D2620; '
                    f'box-shadow:0 2px 8px rgba(45,38,32,0.04);">'
                    f'{_esc(content_str)}</div>'
                )
            continue

        # --- Fallback ---
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
