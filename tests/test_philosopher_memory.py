# tests/test_philosopher_memory.py — Tests for PhilosopherMemory persistence.

import os
import pytest

from core.memory import PhilosopherMemory


@pytest.fixture
def memory_db(tmp_path):
    """Create a temporary database for testing."""
    db_path = str(tmp_path / "test_memory.db")
    return db_path


@pytest.fixture
def socrates_memory(memory_db):
    """PhilosopherMemory instance for Socrates."""
    return PhilosopherMemory("socrates", db_path=memory_db)


class TestPhilosopherMemory:
    def test_record_and_recall(self, socrates_memory):
        """Should record a position and recall it."""
        socrates_memory.record_position("justice", "Justice was doing one's own work.", "session-1")
        positions = socrates_memory.recall_positions("justice")
        assert len(positions) == 1
        assert "Justice was doing one's own work." in positions[0]["position"]
        assert positions[0]["topic"] == "justice"

    def test_recall_empty(self, socrates_memory):
        """Should return empty list when no positions recorded."""
        positions = socrates_memory.recall_positions("unknown topic")
        assert positions == []

    def test_fuzzy_match(self, socrates_memory):
        """Should match partial topic strings via LIKE."""
        socrates_memory.record_position("nature of justice", "Justice was harmony.", "s1")
        positions = socrates_memory.recall_positions("justice")
        assert len(positions) == 1

    def test_multiple_positions(self, socrates_memory):
        """Should store and recall multiple positions."""
        socrates_memory.record_position("virtue", "Virtue was knowledge.", "s1")
        socrates_memory.record_position("virtue", "No one erred willingly.", "s2")
        positions = socrates_memory.recall_positions("virtue")
        assert len(positions) == 2

    def test_limit_recall(self, socrates_memory):
        """Should respect the limit parameter."""
        for i in range(10):
            socrates_memory.record_position("ethics", f"Position {i}", f"s{i}")
        positions = socrates_memory.recall_positions("ethics", limit=3)
        assert len(positions) == 3

    def test_get_all_topics(self, socrates_memory):
        """Should return all unique topics."""
        socrates_memory.record_position("justice", "Justice is...", "s1")
        socrates_memory.record_position("virtue", "Virtue is...", "s1")
        socrates_memory.record_position("justice", "More on justice.", "s2")
        topics = socrates_memory.get_all_topics()
        assert set(topics) == {"justice", "virtue"}

    def test_get_context_for_prompt(self, socrates_memory):
        """Should build prompt-ready context string."""
        socrates_memory.record_position("courage", "Courage was endurance of the soul.", "s1")
        ctx = socrates_memory.get_context_for_prompt("courage")
        assert "Previous discussions" in ctx
        assert "courage" in ctx.lower()

    def test_empty_context(self, socrates_memory):
        """Should return empty string when no positions found."""
        ctx = socrates_memory.get_context_for_prompt("unknown")
        assert ctx == ""

    def test_isolation_between_philosophers(self, memory_db):
        """Different philosopher IDs should not share memory."""
        soc = PhilosopherMemory("socrates", db_path=memory_db)
        conf = PhilosopherMemory("confucius", db_path=memory_db)
        soc.record_position("virtue", "Virtue is knowledge.", "s1")
        conf.record_position("virtue", "Virtue is ren.", "s1")

        soc_positions = soc.recall_positions("virtue")
        conf_positions = conf.recall_positions("virtue")
        assert len(soc_positions) == 1
        assert len(conf_positions) == 1
        assert "knowledge" in soc_positions[0]["position"]
        assert "ren" in conf_positions[0]["position"]
