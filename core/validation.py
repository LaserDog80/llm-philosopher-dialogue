# core/validation.py — Input validation and sanitization.

import re
from typing import Tuple

MAX_INPUT_LENGTH = 2000
MIN_INPUT_LENGTH = 3


def sanitize_input(text: str) -> str:
    """Strip leading/trailing whitespace and collapse internal runs of whitespace."""
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text


def validate_user_input(text: str) -> Tuple[bool, str]:
    """Validate user input text.

    Returns (is_valid, error_message).  When valid, error_message is empty.
    """
    if not text:
        return False, "Please enter a question or topic to start the dialogue."

    if len(text) < MIN_INPUT_LENGTH:
        return False, f"Input is too short (minimum {MIN_INPUT_LENGTH} characters)."

    if len(text) > MAX_INPUT_LENGTH:
        return False, f"Input is too long (maximum {MAX_INPUT_LENGTH} characters)."

    return True, ""
