"""Tests for core/persona.py — chain factory."""

from unittest.mock import patch, MagicMock

from core.persona import create_chain


class TestCreateChain:
    @patch("core.persona.load_llm_config_for_persona")
    def test_returns_runnable(self, mock_load):
        mock_llm = MagicMock()
        mock_load.return_value = (mock_llm, "You are Socrates.")
        chain = create_chain("socrates", mode="philosophy")
        assert chain is not None

    @patch("core.persona.load_llm_config_for_persona")
    def test_prompt_has_history_placeholder(self, mock_load):
        mock_llm = MagicMock()
        mock_load.return_value = (mock_llm, "You are Socrates.")
        chain = create_chain("socrates", mode="philosophy")
        # The chain's first element is the prompt template
        prompt = chain.first
        # Check that chat_history variable is in the prompt
        input_vars = prompt.input_variables
        # chat_history is optional, so it might be in partial_variables or
        # accessible via the messages placeholder
        messages = prompt.messages
        placeholder_found = any(
            hasattr(m, "variable_name") and m.variable_name == "chat_history"
            for m in messages
        )
        assert placeholder_found, "MessagesPlaceholder for chat_history not found"

    @patch("core.persona.load_llm_config_for_persona")
    def test_invalid_persona_returns_none(self, mock_load):
        mock_load.return_value = (None, None)
        chain = create_chain("nonexistent", mode="philosophy")
        assert chain is None

    @patch("core.persona.load_llm_config_for_persona")
    def test_with_prompt_override(self, mock_load):
        mock_llm = MagicMock()
        mock_load.return_value = (mock_llm, "Custom prompt.")
        overrides = {"socrates_philosophy": "Custom prompt."}
        chain = create_chain("socrates", mode="philosophy", prompt_overrides=overrides)
        assert chain is not None
        mock_load.assert_called_once_with("socrates", mode="philosophy", prompt_overrides=overrides)
