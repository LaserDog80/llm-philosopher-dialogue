"""Tests for core/utils.py — think-block extraction, text cleaning, direction tags."""

from core.utils import extract_think_block, clean_response, extract_and_clean, parse_direction_tag


class TestExtractThinkBlock:
    def test_basic_extraction(self):
        text = "Hello <think>inner thought</think> world"
        assert extract_think_block(text) == "inner thought"

    def test_none_input(self):
        assert extract_think_block(None) is None

    def test_empty_input(self):
        assert extract_think_block("") is None

    def test_no_think_block(self):
        assert extract_think_block("Just normal text") is None

    def test_multiline_block(self):
        text = "<think>\nline one\nline two\n</think> response"
        result = extract_think_block(text)
        assert "line one" in result
        assert "line two" in result


class TestCleanResponse:
    def test_removes_think_block(self):
        text = "Hello <think>secret</think> world"
        assert clean_response(text) == "Hello  world"

    def test_none_input(self):
        assert clean_response(None) == ""

    def test_empty_input(self):
        assert clean_response("") == ""

    def test_no_block_returns_original(self):
        assert clean_response("Just text") == "Just text"


class TestExtractAndClean:
    def test_full_extraction(self):
        text = "<think>my thought</think>The response."
        cleaned, monologue = extract_and_clean(text)
        assert cleaned == "The response."
        assert monologue == "my thought"

    def test_no_think_block(self):
        cleaned, monologue = extract_and_clean("Plain text here")
        assert cleaned == "Plain text here"
        assert monologue is None

    def test_none_input(self):
        cleaned, monologue = extract_and_clean(None)
        assert cleaned == ""
        assert monologue is None

    def test_only_think_block(self):
        text = "<think>just thinking</think>"
        cleaned, monologue = extract_and_clean(text)
        assert cleaned == ""
        assert monologue == "just thinking"


class TestParseDirectionTag:
    def test_basic_tag(self):
        text = "I believed virtue was knowledge.\n[NEXT: Confucius | INTENT: address]"
        cleaned, info = parse_direction_tag(text)
        assert cleaned == "I believed virtue was knowledge."
        assert info["next"] == "Confucius"
        assert info["intent"] == "address"

    def test_challenge_intent(self):
        text = "That is not how I saw it.\n[NEXT: Socrates | INTENT: challenge]"
        cleaned, info = parse_direction_tag(text)
        assert "not how I saw it" in cleaned
        assert info["intent"] == "challenge"

    def test_no_tag(self):
        text = "Just a response without any tag."
        cleaned, info = parse_direction_tag(text)
        assert cleaned == text
        assert info == {}

    def test_tag_stripped_from_middle(self):
        text = "Some text [NEXT: Aristotle | INTENT: yield] and more."
        cleaned, info = parse_direction_tag(text)
        assert "[NEXT:" not in cleaned
        assert info["next"] == "Aristotle"
        assert info["intent"] == "yield"

    def test_case_insensitive(self):
        text = "Response.\n[next: Confucius | intent: Reflect]"
        cleaned, info = parse_direction_tag(text)
        assert info["next"] == "Confucius"
        assert info["intent"] == "reflect"

    def test_extra_whitespace(self):
        text = "Response.\n[NEXT:   Sima Qian   |  INTENT:   address  ]"
        cleaned, info = parse_direction_tag(text)
        assert info["next"] == "Sima Qian"
        assert info["intent"] == "address"
