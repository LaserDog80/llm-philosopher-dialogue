# core/librarian.py — Per-turn story retrieval for Herodotus STORY mode.
#
# Each Herodotus STORY-mode turn, select_stories() reads the recent conversation
# and asks a small LLM to pick 0-K story IDs from a curated library. Full
# passages are then formatted via format_passages() for injection into the
# Herodotus system prompt.

import json
import logging
import os
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from core.config import load_llm_config_for_persona

logger = logging.getLogger(__name__)

DEFAULT_LIBRARY_PATH = "data/herodotus_stories.json"
CONVERSATION_TURNS_TO_SHOW = 6  # most-recent turns passed to librarian


def _find_library_path(library_path: str = DEFAULT_LIBRARY_PATH) -> Optional[str]:
    for base in [os.getcwd(), os.path.dirname(os.path.dirname(__file__)) or "."]:
        full = os.path.join(base, library_path)
        if os.path.exists(full):
            return full
    return None


@lru_cache(maxsize=2)
def load_library(library_path: str = DEFAULT_LIBRARY_PATH) -> List[Dict[str, Any]]:
    """Load the full story library (all cards including passages)."""
    path = _find_library_path(library_path)
    if path is None:
        logger.error(f"Story library not found: {library_path}")
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading story library {path}: {e}")
        return []


@lru_cache(maxsize=2)
def build_story_index(library_path: str = DEFAULT_LIBRARY_PATH) -> str:
    """Build a compact JSON index (id + title + themes + summary) for librarian input."""
    cards = load_library(library_path)
    index = [
        {
            "id": c["id"],
            "title": c["title"],
            "themes": c["themes"],
            "summary": c["summary"],
        }
        for c in cards
    ]
    return json.dumps(index, ensure_ascii=False, indent=None)


def _get_card_by_id(story_id: str, library_path: str = DEFAULT_LIBRARY_PATH) -> Optional[Dict[str, Any]]:
    for c in load_library(library_path):
        if c["id"] == story_id:
            return c
    return None


def _get_librarian_chain():
    """Build the librarian chain lazily."""
    llm, system_prompt = load_llm_config_for_persona("librarian", mode="main")
    if not llm or not system_prompt:
        logger.error("Librarian LLM or prompt failed to load.")
        return None
    try:
        prompt = ChatPromptTemplate.from_template(system_prompt)
        return prompt | llm | StrOutputParser()
    except Exception as e:
        logger.error(f"Error building librarian chain: {e}", exc_info=True)
        return None


def _format_conversation(conversation_history: List[Dict[str, Any]], limit: int = CONVERSATION_TURNS_TO_SHOW) -> str:
    """Format recent conversation turns for librarian input."""
    if not conversation_history:
        return "(no conversation yet)"
    # Filter to actual dialogue roles, drop system/moderator rows
    dialogue = [
        t for t in conversation_history
        if t.get("role") and t["role"].lower() not in ("system", "moderator")
    ]
    recent = dialogue[-limit:]
    lines = []
    for t in recent:
        role = t.get("role", "?")
        content = (t.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n\n".join(lines) if lines else "(no conversation yet)"


def _parse_story_ids(raw: str, valid_ids: set, k: int) -> List[str]:
    """Extract a list of story IDs from the librarian's raw output.

    Tolerant: strips code fences, extracts the first JSON array it can find,
    filters to known IDs, trims to k.
    """
    if not raw:
        return []
    text = raw.strip()
    # Strip ```json fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    # Find first [...] block
    match = re.search(r"\[.*?\]", text, flags=re.DOTALL)
    if not match:
        logger.warning(f"Librarian output had no JSON array: {raw!r}")
        return []
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        logger.warning(f"Librarian JSON parse failed: {e}; raw={raw!r}")
        return []
    if not isinstance(parsed, list):
        return []
    selected = []
    for item in parsed:
        if isinstance(item, str) and item in valid_ids and item not in selected:
            selected.append(item)
        if len(selected) >= k:
            break
    dropped = [i for i in parsed if isinstance(i, str) and i not in valid_ids]
    if dropped:
        logger.info(f"Librarian returned unknown IDs (dropped): {dropped}")
    return selected


def select_stories(
    conversation_history: List[Dict[str, Any]],
    k: int = 3,
    library_path: str = DEFAULT_LIBRARY_PATH,
) -> List[str]:
    """Return 0-k story IDs the librarian judges relevant to the current conversation.

    On any failure, returns [] so the caller can proceed with no passages injected.
    """
    cards = load_library(library_path)
    if not cards:
        return []
    valid_ids = {c["id"] for c in cards}

    chain = _get_librarian_chain()
    if chain is None:
        return []

    try:
        conv = _format_conversation(conversation_history)
        index = build_story_index(library_path)
        raw = chain.invoke({
            "conversation": conv,
            "story_index": index,
            "max_stories": k,
        })
    except Exception as e:
        logger.warning(f"Librarian invocation failed: {e}", exc_info=True)
        return []

    ids = _parse_story_ids(raw, valid_ids, k)
    logger.info(f"Librarian selected {len(ids)} stories: {ids}")
    return ids


def format_passages(story_ids: List[str], library_path: str = DEFAULT_LIBRARY_PATH) -> str:
    """Format selected stories' passages for injection into the system prompt.

    Returns a string ready to drop into the `{story_passages}` placeholder. If
    the list is empty, returns an explicit "no story pulled" marker so the
    model doesn't get an empty section.
    """
    if not story_ids:
        return "(no story pulled this turn — speak normally.)"
    chunks = []
    for sid in story_ids:
        card = _get_card_by_id(sid, library_path)
        if not card:
            continue
        chunks.append(
            f"[{card['title']} — {card['source']}]\n"
            f"{card['passage'].strip()}"
        )
    if not chunks:
        return "(no story pulled this turn — speak normally.)"
    return "\n\n".join(chunks)
