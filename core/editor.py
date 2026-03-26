# core/editor.py — Per-message editor: rewrite a philosopher's response shorter or longer.

import logging
from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from core.config import load_llm_config_for_persona
from core.registry import get_philosopher, get_philosopher_ids
from core.utils import extract_and_clean

logger = logging.getLogger(__name__)

VALID_DIRECTIONS = {"shorter", "longer"}
STEP_FACTOR = 0.25  # Each click changes target by 25%
MIN_WORDS = 15      # Floor for shortest rewrite


def _resolve_philosopher_id(display_name: str) -> str:
    """Resolve a philosopher display name to their registry ID."""
    for pid in get_philosopher_ids():
        pcfg = get_philosopher(pid)
        if pcfg and pcfg.display_name.lower() == display_name.lower():
            return pid
    return display_name.lower().replace(" ", "")


def get_editor_chain() -> Optional[Any]:
    """Create and return the editor LangChain chain."""
    llm, system_prompt = load_llm_config_for_persona("editor", mode="main")
    if not llm or not system_prompt:
        logger.error("Failed to load editor chain.")
        return None
    try:
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", "{editor_input}"),
        ])
        chain = prompt | llm | StrOutputParser()
        return chain
    except Exception as e:
        logger.error(f"Error creating editor chain: {e}", exc_info=True)
        return None


def build_voice_description(philosopher_id: str) -> str:
    """Build a voice description string from the philosopher's registry entry."""
    pcfg = get_philosopher(philosopher_id)
    if not pcfg or not pcfg.voice_profile:
        return "Speak in the philosopher's natural voice."
    vp = pcfg.voice_profile
    parts = []
    if vp.get("style_keywords"):
        parts.append(f"Style: {', '.join(vp['style_keywords'])}.")
    if vp.get("personality_summary"):
        parts.append(f"Personality: {vp['personality_summary']}")
    return " ".join(parts) if parts else "Speak in the philosopher's natural voice."


def compute_target_words(original_content: str, current_target: int, direction: str) -> int:
    """Compute the new target word count after a step in the given direction.

    Args:
        original_content: The original (unedited) message text.
        current_target: The current target word count (0 means use original length).
        direction: "shorter" or "longer".

    Returns:
        New target word count.
    """
    original_words = len(original_content.split())
    base = current_target if current_target > 0 else original_words

    if direction == "shorter":
        new_target = int(base * (1 - STEP_FACTOR))
        return max(MIN_WORDS, new_target)
    else:
        new_target = int(base * (1 + STEP_FACTOR))
        return new_target


def format_editor_input(
    messages: List[Dict[str, Any]],
    message_index: int,
    target_words: int,
    philosopher_name: str,
    voice_description: str,
    original_content: str,
) -> str:
    """Format the input for the editor chain.

    Args:
        messages: Full conversation messages list.
        message_index: Index of the message to rewrite.
        target_words: Target word count for the rewrite.
        philosopher_name: Display name of the philosopher.
        voice_description: Voice/style description string.
        original_content: The original (unedited) message text to rewrite from.

    Returns:
        Formatted input string for the editor chain.

    Raises:
        ValueError: If message_index is out of range.
    """
    if message_index < 0 or message_index >= len(messages):
        raise ValueError(f"message_index {message_index} out of range (0-{len(messages) - 1})")

    context_lines = []
    for i, msg in enumerate(messages):
        if i >= message_index:
            break
        role = msg.get("role", "system").upper()
        content = msg.get("content", "")
        if role == "USER":
            context_lines.append(f"USER: {content}")
        elif role != "SYSTEM":
            context_lines.append(f"{role}: {content}")
    context = "\n\n".join(context_lines) if context_lines else "(This is the first response.)"

    original_words = len(original_content.split())
    return (
        f"PHILOSOPHER: {philosopher_name}\n"
        f"VOICE: {voice_description}\n"
        f"TARGET: Rewrite to approximately {target_words} words "
        f"(original was {original_words} words)\n\n"
        f"--- CONVERSATION CONTEXT ---\n{context}\n\n"
        f"--- ORIGINAL MESSAGE TO REWRITE ---\n{original_content}"
    )


def rewrite_message(
    messages: List[Dict[str, Any]],
    message_index: int,
    target_words: int,
    original_content: str,
) -> Optional[str]:
    """Rewrite a single message to hit a target word count.

    Args:
        messages: Full conversation messages list.
        message_index: Index of the message to rewrite.
        target_words: Target word count for the rewrite.
        original_content: The original (unedited) message text.

    Returns:
        The rewritten message text, or None on failure.
    """
    target_msg = messages[message_index]
    philosopher_name = target_msg.get("role", "")

    if philosopher_name.lower() in ("user", "system"):
        logger.warning(
            f"Editor refused to rewrite non-philosopher message (role={philosopher_name})"
        )
        return None

    philosopher_id = _resolve_philosopher_id(philosopher_name)
    voice_desc = build_voice_description(philosopher_id)

    editor_input = format_editor_input(
        messages=messages,
        message_index=message_index,
        target_words=target_words,
        philosopher_name=philosopher_name,
        voice_description=voice_desc,
        original_content=original_content,
    )

    chain = get_editor_chain()
    if chain is None:
        return None

    try:
        logger.info(
            f"Editor rewriting message {message_index} to ~{target_words} words for {philosopher_name}"
        )
        raw_result = chain.invoke({"editor_input": editor_input})
        cleaned, _ = extract_and_clean(raw_result)
        return cleaned if cleaned else None
    except Exception as e:
        logger.error(f"Editor rewrite failed: {e}", exc_info=True)
        return None
