# tests/test_streaming.py — Tests for streaming functionality in direction.py.

import pytest
from unittest.mock import patch, MagicMock

from direction import Director


class TestRobustStream:
    def setup_method(self):
        self.director = Director()

    def test_stream_accumulates_tokens(self):
        """Streaming should accumulate all chunks into a full response."""
        mock_chain = MagicMock()
        mock_chain.stream.return_value = iter(["Hello ", "world ", "!"])

        result, monologue = self.director._robust_stream(
            mock_chain, {"input": "test"}, "Socrates", 1
        )
        assert result == "Hello world !"
        assert monologue is None

    def test_stream_callback_called_per_chunk(self):
        """on_token callback is called for each streamed chunk."""
        mock_chain = MagicMock()
        mock_chain.stream.return_value = iter(["A", "B", "C"])
        callback = MagicMock()

        self.director._robust_stream(
            mock_chain, {"input": "test"}, "Socrates", 1,
            on_token_callback=callback
        )
        assert callback.call_count == 3
        callback.assert_any_call("A")
        callback.assert_any_call("B")
        callback.assert_any_call("C")

    def test_stream_with_think_block(self):
        """Streaming should extract think blocks from accumulated response."""
        mock_chain = MagicMock()
        mock_chain.stream.return_value = iter(["<think>", "internal", "</think>", "Visible"])

        result, monologue = self.director._robust_stream(
            mock_chain, {"input": "test"}, "Socrates", 1
        )
        assert result == "Visible"
        assert monologue == "internal"

    @patch.object(Director, "_robust_invoke")
    def test_stream_fallback_on_error(self, mock_invoke):
        """If streaming fails, fall back to _robust_invoke."""
        mock_chain = MagicMock()
        mock_chain.stream.side_effect = Exception("stream not supported")
        mock_invoke.return_value = ("fallback response", None)

        result, monologue = self.director._robust_stream(
            mock_chain, {"input": "test"}, "Socrates", 1
        )
        assert result == "fallback response"
        mock_invoke.assert_called_once()

    def test_stream_none_chain(self):
        """None chain should return (None, None)."""
        result, monologue = self.director._robust_stream(
            None, {"input": "test"}, "Socrates", 1
        )
        assert result is None
        assert monologue is None

    def test_stream_empty_response(self):
        """Empty stream should fall back to invoke."""
        mock_chain = MagicMock()
        mock_chain.stream.return_value = iter([])
        mock_chain.invoke.return_value = "fallback"

        result, monologue = self.director._robust_stream(
            mock_chain, {"input": "test"}, "Socrates", 1
        )
        # Empty stream triggers fallback
        assert result is not None
