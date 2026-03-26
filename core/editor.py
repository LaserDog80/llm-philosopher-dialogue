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


def format_editor_input(
    messages: List[Dict[str, Any]],
    message_index: int,
    direction: str,
    philosopher_name: str,
    voice_description: str,
) -> str:
    """Format the input for the editor chain."""
    if message_index < 0 or message_index >= len(messages):
        raise ValueError(f"message_index {message_index} out of range (0-{len(messages) - 1})")
    if direction not in VALID_DIRECTIONS:
        raise ValueError(f"direction must be one of {VALID_DIRECTIONS}, got '{direction}'")

    target_msg = messages[message_index]
    target_content = target_msg.get("content", "")

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

    return (
        f"PHILOSOPHER: {philosopher_name}\n"
        f"VOICE: {voice_description}\n"
        f"DIRECTION: Make this {direction}\n\n"
        f"--- CONVERSATION CONTEXT ---\n{context}\n\n"
        f"--- MESSAGE TO REWRITE ---\n{target_content}"
    )


def rewrite_message(
    messages: List[Dict[str, Any]],
    message_index: int,
    direction: str,
) -> Optional[str]:
    """Rewrite a single message shorter or longer."""
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
        direction=direction,
        philosopher_name=philosopher_name,
        voice_description=voice_desc,
    )

    chain = get_editor_chain()
    if chain is None:
        return None

    try:
        logger.info(
            f"Editor rewriting message {message_index} ({direction}) for {philosopher_name}"
        )
        raw_result = chain.invoke({"editor_input": editor_input})
        cleaned, _ = extract_and_clean(raw_result)
        return cleaned if cleaned else None
    except Exception as e:
        logger.error(f"Editor rewrite failed: {e}", exc_info=True)
        return None
