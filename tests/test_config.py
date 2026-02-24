# tests/test_config.py — Tests for core/config.py

import json
import os
import pytest
from unittest.mock import patch

from core.config import (
    load_default_prompt_text,
    load_llm_params,
    load_llm_config_for_persona,
)


@pytest.fixture(autouse=True)
def clear_lru_caches():
    """Clear lru_cache between tests to avoid cross-test pollution."""
    load_default_prompt_text.cache_clear()
    load_llm_params.cache_clear()
    yield
    load_default_prompt_text.cache_clear()
    load_llm_params.cache_clear()


class TestLoadDefaultPromptText:
    def test_load_from_temp_file(self, tmp_path):
        prompt_dir = tmp_path / "prompts"
        prompt_dir.mkdir()
        prompt_file = prompt_dir / "test_persona_philosophy.txt"
        prompt_file.write_text("You are a test philosopher.")

        with patch("os.getcwd", return_value=str(tmp_path)):
            result = load_default_prompt_text("test_persona", "philosophy")
        assert result == "You are a test philosopher."

    def test_missing_file_returns_none(self, tmp_path):
        with patch("os.getcwd", return_value=str(tmp_path)):
            result = load_default_prompt_text("nonexistent", "philosophy")
        assert result is None


class TestLoadLlmParams:
    def test_merges_defaults_with_persona(self, tmp_path):
        config = {
            "defaults": {"temperature": 0.7, "max_tokens": 400},
            "socrates": {"temperature": 0.5, "max_tokens": 250},
        }
        config_file = tmp_path / "llm_config.json"
        config_file.write_text(json.dumps(config))

        with patch("os.getcwd", return_value=str(tmp_path)):
            params = load_llm_params("socrates", config_path="llm_config.json")

        # Persona values override defaults
        assert params["temperature"] == 0.5
        assert params["max_tokens"] == 250

    def test_defaults_used_for_unknown_persona(self, tmp_path):
        config = {
            "defaults": {"temperature": 0.7, "max_tokens": 400},
        }
        config_file = tmp_path / "llm_config.json"
        config_file.write_text(json.dumps(config))

        with patch("os.getcwd", return_value=str(tmp_path)):
            params = load_llm_params("unknown_persona", config_path="llm_config.json")

        assert params["temperature"] == 0.7
        assert params["max_tokens"] == 400

    def test_missing_config_returns_empty(self, tmp_path):
        with patch("os.getcwd", return_value=str(tmp_path)):
            params = load_llm_params("socrates", config_path="nonexistent.json")
        assert params == {}


class TestLoadLlmConfigForPersona:
    def test_missing_api_key_returns_none(self, tmp_path):
        """Without NEBIUS_API_KEY, should return (None, None)."""
        config = {
            "defaults": {"temperature": 0.7},
            "socrates": {"temperature": 0.5},
        }
        config_file = tmp_path / "llm_config.json"
        config_file.write_text(json.dumps(config))

        prompt_dir = tmp_path / "prompts"
        prompt_dir.mkdir()
        (prompt_dir / "socrates_philosophy.txt").write_text("You are Socrates.")

        with patch("os.getcwd", return_value=str(tmp_path)), \
             patch.dict(os.environ, {"NEBIUS_API_KEY": "", "NEBIUS_API_BASE": ""}, clear=False):
            llm, prompt = load_llm_config_for_persona("socrates", mode="philosophy", config_path="llm_config.json")

        assert llm is None
        assert prompt is None
