"""Tests for core/utils.py — think-block extraction and text cleaning."""

from core.utils import extract_think_block, clean_response, extract_and_clean


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
