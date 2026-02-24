# tests/test_validation.py — Tests for core/validation.py

import pytest
from core.validation import validate_user_input, sanitize_input, MAX_INPUT_LENGTH, MIN_INPUT_LENGTH


class TestValidateUserInput:
    def test_empty_rejected(self):
        valid, msg = validate_user_input("")
        assert valid is False
        assert "enter" in msg.lower()

    def test_whitespace_only_rejected(self):
        """After sanitize_input, whitespace-only becomes empty."""
        sanitized = sanitize_input("   \t\n  ")
        valid, msg = validate_user_input(sanitized)
        assert valid is False

    def test_too_short(self):
        valid, msg = validate_user_input("Hi")
        assert valid is False
        assert "short" in msg.lower()

    def test_too_long(self):
        valid, msg = validate_user_input("x" * (MAX_INPUT_LENGTH + 1))
        assert valid is False
        assert "long" in msg.lower()

    def test_valid_input(self):
        valid, msg = validate_user_input("What is justice?")
        assert valid is True
        assert msg == ""

    def test_exact_min_length(self):
        valid, _ = validate_user_input("x" * MIN_INPUT_LENGTH)
        assert valid is True

    def test_exact_max_length(self):
        valid, _ = validate_user_input("x" * MAX_INPUT_LENGTH)
        assert valid is True


class TestSanitizeInput:
    def test_strips_whitespace(self):
        assert sanitize_input("  hello  ") == "hello"

    def test_collapses_internal_whitespace(self):
        assert sanitize_input("hello   world   foo") == "hello world foo"

    def test_collapses_newlines_and_tabs(self):
        assert sanitize_input("hello\n\n\tworld") == "hello world"

    def test_empty_input(self):
        assert sanitize_input("") == ""

    def test_already_clean(self):
        assert sanitize_input("clean input") == "clean input"
