# tests/test_editor.py — Unit tests for the editor module.

import pytest
from unittest.mock import patch, MagicMock


class TestComputeTargetWords:
    """Tests for compute_target_words()."""

    def test_shorter_from_original(self):
        from core.editor import compute_target_words
        # 100-word original, no current target -> step down 25% = 75
        result = compute_target_words("word " * 100, 0, "shorter")
        assert result == 75

    def test_longer_from_original(self):
        from core.editor import compute_target_words
        result = compute_target_words("word " * 100, 0, "longer")
        assert result == 125

    def test_shorter_from_current_target(self):
        from core.editor import compute_target_words
        # Current target 80, step down 25% = 60
        result = compute_target_words("word " * 100, 80, "shorter")
        assert result == 60

    def test_longer_from_current_target(self):
        from core.editor import compute_target_words
        result = compute_target_words("word " * 100, 80, "longer")
        assert result == 100

    def test_shorter_respects_minimum(self):
        from core.editor import compute_target_words, MIN_WORDS
        result = compute_target_words("word " * 20, 16, "shorter")
        assert result >= MIN_WORDS

    def test_multiple_steps_down_then_up(self):
        from core.editor import compute_target_words
        original = "word " * 100
        # Step down twice, then up once
        t1 = compute_target_words(original, 0, "shorter")      # 75
        t2 = compute_target_words(original, t1, "shorter")      # 56
        t3 = compute_target_words(original, t2, "longer")       # 70
        assert t1 > t2  # each shorter step reduces
        assert t3 > t2  # longer step increases from current


class TestFormatEditorInput:
    """Tests for format_editor_input()."""

    def test_formats_with_target_words(self):
        from core.editor import format_editor_input

        messages = [
            {"role": "user", "content": "What is love?"},
            {"role": "Herodotus", "content": "A long response about love.", "intent": "address"},
        ]
        result = format_editor_input(
            messages=messages,
            message_index=1,
            target_words=50,
            philosopher_name="Herodotus",
            voice_description="Discursive, anecdotal, wondering, chatty",
            original_content="A long response about love.",
        )
        assert "50" in result
        assert "Herodotus" in result
        assert "A long response about love." in result
        assert "What is love?" in result
        assert "Discursive" in result

    def test_includes_context(self):
        from core.editor import format_editor_input

        messages = [
            {"role": "user", "content": "What is virtue?"},
            {"role": "Socrates", "content": "Short reply.", "intent": "address"},
            {"role": "Confucius", "content": "Another reply.", "intent": "address"},
        ]
        result = format_editor_input(
            messages=messages,
            message_index=2,
            target_words=80,
            philosopher_name="Confucius",
            voice_description="terse",
            original_content="Another reply.",
        )
        assert "SOCRATES: Short reply." in result
        assert "What is virtue?" in result

    def test_invalid_index_raises(self):
        from core.editor import format_editor_input

        with pytest.raises(ValueError):
            format_editor_input(
                messages=[{"role": "user", "content": "hi"}],
                message_index=5,
                target_words=50,
                philosopher_name="Socrates",
                voice_description="probing",
                original_content="hi",
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
        result = rewrite_message(messages, 0, 50, "What is love?")
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
        result = rewrite_message(messages, 1, 30, "A long reply about love.")
        assert result == "A shorter reply."
        mock_chain_instance.invoke.assert_called_once()
