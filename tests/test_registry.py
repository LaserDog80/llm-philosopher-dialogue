# tests/test_registry.py — Tests for core/registry.py

import json
import pytest
from unittest.mock import patch

from core.registry import (
    load_registry,
    get_philosopher_ids,
    get_philosopher,
    get_display_names,
    get_speaker_styles,
    PhilosopherConfig,
)


@pytest.fixture(autouse=True)
def clear_cache():
    load_registry.cache_clear()
    yield
    load_registry.cache_clear()


@pytest.fixture
def config_file(tmp_path):
    data = {
        "philosophers": [
            {
                "id": "socrates",
                "display_name": "Socrates",
                "initials": "S",
                "color": "#5B8DEF",
                "bg": "#f0f5ff",
                "text_color": "#2D5FC4",
                "description": "Athenian philosopher",
            },
            {
                "id": "confucius",
                "display_name": "Confucius",
                "initials": "C",
                "color": "#D4A03C",
                "bg": "#fdf6e3",
                "text_color": "#8B6914",
                "description": "Chinese philosopher",
            },
        ],
        "moderator": {
            "id": "moderator",
            "display_name": "Moderator",
            "initials": "M",
            "color": "#8B8B8B",
            "bg": "#f5f5f5",
            "text_color": "#555555",
        },
    }
    path = tmp_path / "philosophers.json"
    path.write_text(json.dumps(data))
    return str(path)


class TestLoadRegistry:
    def test_loads_from_file(self, config_file):
        reg = load_registry(config_file)
        assert "socrates" in reg
        assert "confucius" in reg
        assert "moderator" in reg
        assert isinstance(reg["socrates"], PhilosopherConfig)

    def test_philosopher_fields(self, config_file):
        reg = load_registry(config_file)
        s = reg["socrates"]
        assert s.display_name == "Socrates"
        assert s.initials == "S"
        assert s.color == "#5B8DEF"

    def test_missing_file_returns_empty(self):
        reg = load_registry("/nonexistent/path.json")
        assert reg == {}


class TestGetPhilosopherIds:
    def test_excludes_moderator(self, config_file):
        ids = get_philosopher_ids(config_file)
        assert "moderator" not in ids
        assert "socrates" in ids
        assert "confucius" in ids


class TestGetPhilosopher:
    def test_known_id(self, config_file):
        p = get_philosopher("socrates", config_file)
        assert p is not None
        assert p.display_name == "Socrates"

    def test_unknown_id(self, config_file):
        p = get_philosopher("aristotle", config_file)
        assert p is None


class TestGetDisplayNames:
    def test_returns_display_names(self, config_file):
        names = get_display_names(config_file)
        assert "Socrates" in names
        assert "Confucius" in names
        assert "Moderator" not in names


class TestGetSpeakerStyles:
    def test_has_all_philosophers(self, config_file):
        styles = get_speaker_styles(config_file)
        assert "socrates" in styles
        assert "confucius" in styles
        assert "moderator" in styles

    def test_has_user_and_system_fallbacks(self, config_file):
        styles = get_speaker_styles(config_file)
        assert "user" in styles
        assert "system" in styles
        assert styles["user"]["display_name"] == "You"

    def test_style_structure(self, config_file):
        styles = get_speaker_styles(config_file)
        for key in ("color", "bg", "text_color", "initials", "display_name"):
            assert key in styles["socrates"]
