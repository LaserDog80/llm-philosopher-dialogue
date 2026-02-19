# core/utils.py — Shared utilities (think-block extraction, text cleaning).

import re
from typing import Optional, Tuple

THINK_BLOCK_REGEX = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)


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
