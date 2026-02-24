# tests/test_translator.py — Unit tests for translator.py

import pytest
from unittest.mock import patch, MagicMock

from translator import format_conversation_for_translation, translate_conversation


class TestFormatConversationForTranslation:
    def test_excludes_system_messages(self):
        messages = [
            {"role": "user", "content": "What is justice?"},
            {"role": "Socrates", "content": "Justice is..."},
            {"role": "system", "content": "MODERATOR CONTEXT..."},
            {"role": "Confucius", "content": "Virtue is..."},
        ]
        result = format_conversation_for_translation(messages)
        assert "MODERATOR" not in result
        assert "Socrates" not in result  # role is uppercased
        assert "SOCRATES" in result
        assert "CONFUCIUS" in result
        assert "INITIAL PROMPT" in result

    def test_includes_all_dialogue_roles(self):
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "Socrates", "content": "Greetings"},
            {"role": "Confucius", "content": "Welcome"},
        ]
        result = format_conversation_for_translation(messages)
        assert "INITIAL PROMPT: Hello" in result
        assert "SOCRATES: Greetings" in result
        assert "CONFUCIUS: Welcome" in result

    def test_empty_messages_returns_empty(self):
        result = format_conversation_for_translation([])
        assert result == ""

    def test_only_system_messages_returns_empty(self):
        messages = [
            {"role": "system", "content": "Some context"},
            {"role": "system", "content": "More context"},
        ]
        result = format_conversation_for_translation(messages)
        assert result == ""


class TestTranslateConversation:
    @patch("translator.get_translator_chain")
    def test_successful_translation(self, mock_get_chain):
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = "Translated dialogue here"
        mock_get_chain.return_value = mock_chain

        messages = [
            {"role": "user", "content": "What is virtue?"},
            {"role": "Socrates", "content": "Virtue is knowledge."},
        ]
        result = translate_conversation(messages)
        assert result == "Translated dialogue here"
        mock_chain.invoke.assert_called_once()

    @patch("translator.get_translator_chain")
    def test_chain_load_failure(self, mock_get_chain):
        mock_get_chain.return_value = None
        result = translate_conversation([{"role": "user", "content": "Hi"}])
        assert "Error" in result

    @patch("translator.get_translator_chain")
    def test_empty_dialogue_not_translated(self, mock_get_chain):
        mock_chain = MagicMock()
        mock_get_chain.return_value = mock_chain
        # Only system messages — nothing to translate
        messages = [{"role": "system", "content": "Context only"}]
        result = translate_conversation(messages)
        assert "no dialogue" in result.lower()
        mock_chain.invoke.assert_not_called()
