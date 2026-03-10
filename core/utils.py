# core/utils.py — Shared utilities (think-block extraction, text cleaning, direction tags).

import re
from typing import Optional, Tuple, Dict

THINK_BLOCK_REGEX = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)

# Direction tag: [NEXT: <name> | INTENT: <intent>]
DIRECTION_TAG_REGEX = re.compile(
    r"\[NEXT:\s*(?P<next>[^|]+?)\s*\|\s*INTENT:\s*(?P<intent>\w+)\s*\]",
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
