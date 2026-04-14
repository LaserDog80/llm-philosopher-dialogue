# core/persona.py — Single chain factory replacing socrates.py, confucius.py, moderator.py.

import logging
from typing import Optional, Any, Dict, List

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda, RunnablePassthrough

from core.config import load_llm_config_for_persona

logger = logging.getLogger(__name__)

STORY_MODE_MAX_TOKENS = 1200


def _is_herodotus_story(persona_id: str, mode: str) -> bool:
    return persona_id.lower() == "herodotus" and mode.lower() == "story"


def _normalize_chat_history(raw_history: Any) -> List[Dict[str, str]]:
    """Normalize LangChain messages OR dicts into [{"role": ..., "content": ...}, ...]."""
    if not raw_history:
        return []
    out: List[Dict[str, str]] = []
    for m in raw_history:
        if hasattr(m, "content"):
            role_type = getattr(m, "type", None) or "?"
            out.append({"role": role_type, "content": m.content or ""})
        elif isinstance(m, dict):
            out.append({
                "role": m.get("role", "?"),
                "content": m.get("content", "") or "",
            })
    return out


def _make_story_passages_runnable() -> RunnableLambda:
    """Factory returning a Runnable that computes {story_passages} from the chain input."""
    # Lazy import so librarian code only loads when story mode is used.
    from core.librarian import select_stories, format_passages

    def _compute(input_dict: Dict[str, Any]) -> str:
        try:
            history = _normalize_chat_history(input_dict.get("chat_history"))
            current_input = input_dict.get("input") or ""
            if current_input:
                history.append({"role": "next_prompt", "content": current_input})
            ids = select_stories(history, k=3)
            return format_passages(ids)
        except Exception as e:
            logger.warning(f"Librarian pass failed; proceeding with no passages: {e}", exc_info=True)
            return "(no story pulled this turn — speak normally.)"

    return RunnableLambda(_compute)


def create_chain(
    persona_id: str,
    mode: str = "philosophy",
    prompt_overrides: Optional[Dict[str, str]] = None,
    max_tokens_override: Optional[int] = None,
    personality_notes: Optional[str] = None,
) -> Optional[Any]:
    """
    Create a LangChain chain for any persona/mode combination.

    For Herodotus in ``story`` mode, the returned chain wraps the base
    prompt with a librarian pass that injects curated passages into the
    ``{story_passages}`` placeholder each turn.
    """
    logger.info(f"Creating chain for '{persona_id}' mode '{mode}'")

    is_story_mode = _is_herodotus_story(persona_id, mode)
    if is_story_mode:
        # Ensure a floor of ~1200 tokens so a full retelling isn't clipped.
        requested = max_tokens_override or 0
        max_tokens_override = max(requested, STORY_MODE_MAX_TOKENS)

    llm, system_prompt = load_llm_config_for_persona(
        persona_id, mode=mode, prompt_overrides=prompt_overrides,
        max_tokens_override=max_tokens_override,
        personality_notes=personality_notes,
        suppress_sentence_range=is_story_mode,
    )

    if not llm or not system_prompt:
        logger.error(f"Failed to load LLM/prompt for '{persona_id}' mode '{mode}'")
        return None

    try:
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("user", "{input}"),
        ])

        if is_story_mode:
            chain = (
                RunnablePassthrough.assign(story_passages=_make_story_passages_runnable())
                | prompt_template
                | llm
                | StrOutputParser()
            )
            logger.info(f"Story-mode chain created for '{persona_id}' (librarian wired, max_tokens={max_tokens_override}).")
        else:
            chain = prompt_template | llm | StrOutputParser()
            logger.info(f"Chain created for '{persona_id}' mode '{mode}'")
        return chain
    except Exception as e:
        logger.error(f"Error creating chain for '{persona_id}' mode '{mode}': {e}", exc_info=True)
        return None
