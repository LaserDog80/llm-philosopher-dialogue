# core/utils.py — Shared utilities (think-block extraction, text cleaning, direction tags, LLM invocation).

import logging
import re
import time
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

THINK_BLOCK_REGEX = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)

# Direction tag: [NEXT: <name> | INTENT: <intent>] or [NEXT: <name> | <intent>]
DIRECTION_TAG_REGEX = re.compile(
    r"\[NEXT:\s*(?P<next>[^|]+?)\s*\|\s*(?:INTENT:\s*)?(?P<intent>\w+)\s*\]",
    re.IGNORECASE,
)


def extract_think_block(text: Optional[str]) -> Optional[str]:
    """Extract content from the first <think> block found."""
    if not text:
        return None
    match = THINK_BLOCK_REGEX.search(text)
    return match.group(1).strip() if match else None


def clean_response(text: Optional[str]) -> str:
    """Remove all <think> blocks and return cleaned text."""
    if not text:
        return ""
    return THINK_BLOCK_REGEX.sub('', text).strip()


def extract_and_clean(raw_response: Optional[str]) -> Tuple[str, Optional[str]]:
    """Extract think block and return (cleaned_response, monologue)."""
    if not raw_response:
        return "", None
    monologue = extract_think_block(raw_response)
    cleaned = clean_response(raw_response)
    if not cleaned and raw_response:
        return "", monologue
    return cleaned, monologue


def robust_invoke(
    chain: Any, input_dict: Dict, actor_name: str, round_num: int
) -> Tuple[Optional[str], Optional[str]]:
    """Invoke a chain with retry logic. Returns (clean_response, monologue).

    Shared between the LangGraph engine (core/graph.py) and the legacy
    Director class (direction.py).
    """
    if chain is None:
        logger.error(f"Round {round_num}: Cannot invoke {actor_name}, chain is None.")
        return None, None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                f"Round {round_num}: Requesting {actor_name} (Attempt {attempt}/{MAX_RETRIES})"
            )
            start_time = time.time()
            raw = chain.invoke(input_dict)
            raw_str = str(raw) if raw is not None else None
            elapsed = time.time() - start_time
            logger.info(f"Round {round_num}: {actor_name} responded in {elapsed:.2f}s.")
            if raw_str is not None and raw_str.strip():
                return extract_and_clean(raw_str)
            elif raw_str == "":
                return "", None
            else:
                raise ValueError(f"Empty response from {actor_name}")
        except Exception as e:
            logger.error(
                f"Round {round_num}: {actor_name} failed (Attempt {attempt}): {e}",
                exc_info=True,
            )
            if attempt == MAX_RETRIES:
                return None, None
            time.sleep(RETRY_DELAY)
    return None, None


def parse_direction_tag(text: str) -> Tuple[str, Dict[str, str]]:
    """Parse and strip a direction tag from a philosopher's response.

    Returns (cleaned_text, {"next": "<name>", "intent": "<intent>"}).
    If no tag is found, returns (original_text, {}).
    """
    match = DIRECTION_TAG_REGEX.search(text)
    if not match:
        return text.strip(), {}

    tag_info = {
        "next": match.group("next").strip(),
        "intent": match.group("intent").strip().lower(),
    }
    cleaned = text[:match.start()] + text[match.end():]
    return cleaned.strip(), tag_info
