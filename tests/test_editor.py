# tests/test_editor.py — Unit tests for the editor module.

import pytest
from unittest.mock import patch, MagicMock


class TestFormatEditorInput:
    """Tests for format_editor_input()."""

    def test_formats_shorter_request(self):
        from core.editor import format_editor_input

        messages = [
            {"role": "user", "content": "What is love?"},
            {"role": "Herodotus", "content": "A long response about love.", "intent": "address"},
            {"role": "Sima Qian", "content": "A reply about love.", "intent": "challenge"},
        ]
        result = format_editor_input(
            messages=messages,
            message_index=1,
            direction="shorter",
            philosopher_name="Herodotus",
            voice_description="Discursive, anecdotal, wondering, chatty",
        )
        assert "shorter" in result.lower()
        assert "Herodotus" in result
        assert "A long response about love." in result
        assert "What is love?" in result
        assert "Discursive" in result

    def test_formats_longer_request(self):
        from core.editor import format_editor_input

        messages = [
            {"role": "user", "content": "What is virtue?"},
            {"role": "Socrates", "content": "Short reply.", "intent": "address"},
        ]
        result = format_editor_input(
            messages=messages,
            message_index=1,
            direction="longer",
            philosopher_name="Socrates",
            voice_description="Probing, ironic, questioning",
        )
        assert "longer" in result.lower()
        assert "Socrates" in result
        assert "Short reply." in result

    def test_invalid_index_raises(self):
        from core.editor import format_editor_input

        with pytest.raises(ValueError):
            format_editor_input(
                messages=[{"role": "user", "content": "hi"}],
                message_index=5,
                direction="shorter",
                philosopher_name="Socrates",
                voice_description="probing",
            )

    def test_invalid_direction_raises(self):
        from core.editor import format_editor_input

        with pytest.raises(ValueError):
            format_editor_input(
                messages=[
                    {"role": "user", "content": "hi"},
                    {"role": "Socrates", "content": "reply", "intent": "address"},
                ],
                message_index=1,
                direction="sideways",
                philosopher_name="Socrates",
                voice_description="probing",
            )


class TestGetEditorChain:
    """Tests for get_editor_chain()."""

    @patch("core.editor.load_llm_config_for_persona")
    def test_returns_chain_when_config_loads(self, mock_load):
        mock_llm = MagicMock()
        mock_load.return_value = (mock_llm, "You are an editor.")
        from core.editor import get_editor_chain

        chain = get_editor_chain()
        assert chain is not None
        mock_load.assert_called_once_with("editor", mode="main")

    @patch("core.editor.load_llm_config_for_persona")
    def test_returns_none_when_config_fails(self, mock_load):
        mock_load.return_value = (None, None)
        from core.editor import get_editor_chain

        chain = get_editor_chain()
        assert chain is None


class TestBuildVoiceDescription:
    """Tests for build_voice_description()."""

    @patch("core.editor.get_philosopher")
    def test_builds_description_from_voice_profile(self, mock_get):
        mock_cfg = MagicMock()
        mock_cfg.voice_profile = {
            "style_keywords": ["probing", "ironic"],
            "personality_summary": "Charismatic and provocative.",
        }
        mock_get.return_value = mock_cfg
        from core.editor import build_voice_description

        desc = build_voice_description("socrates")
        assert "probing" in desc
        assert "Charismatic" in desc

    @patch("core.editor.get_philosopher")
    def test_returns_fallback_when_no_profile(self, mock_get):
        mock_get.return_value = None
        from core.editor import build_voice_description

        desc = build_voice_description("unknown")
        assert len(desc) > 0


class TestRewriteMessage:
    """Tests for rewrite_message()."""

    def test_rejects_user_message(self):
        from core.editor import rewrite_message

        messages = [
            {"role": "user", "content": "What is love?"},
            {"role": "Socrates", "content": "A reply.", "intent": "address"},
        ]
        result = rewrite_message(messages, 0, "shorter")
        assert result is None

    @patch("core.editor.get_editor_chain")
    @patch("core.editor._resolve_philosopher_id")
    @patch("core.editor.build_voice_description")
    def test_calls_chain_and_returns_cleaned(self, mock_voice, mock_resolve, mock_chain):
        mock_resolve.return_value = "socrates"
        mock_voice.return_value = "probing, ironic"
        mock_chain_instance = MagicMock()
        mock_chain_instance.invoke.return_value = "A shorter reply."
        mock_chain.return_value = mock_chain_instance
        from core.editor import rewrite_message

        messages = [
            {"role": "user", "content": "What is love?"},
            {"role": "Socrates", "content": "A long reply about love.", "intent": "address"},
        ]
        result = rewrite_message(messages, 1, "shorter")
        assert result == "A shorter reply."
        mock_chain_instance.invoke.assert_called_once()
