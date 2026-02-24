"""Tests for core/memory.py — sliding-window conversation memory."""

from langchain_core.messages import HumanMessage

from core.memory import ConversationMemory, DEFAULT_WINDOW_SIZE


class TestConversationMemory:
    def test_empty_memory_returns_empty_list(self):
        mem = ConversationMemory()
        assert mem.get_history_for_chain() == []
        assert mem.turn_count == 0

    def test_add_single_turn(self):
        mem = ConversationMemory()
        mem.add_turn("Socrates", "Virtue is knowledge.", 1)
        assert mem.turn_count == 1

    def test_window_size_respected(self):
        mem = ConversationMemory(window_size=3)
        for i in range(10):
            mem.add_turn("Speaker", f"Turn {i}", round_number=(i // 2) + 1)
        history = mem.get_history_for_chain()
        assert len(history) == 3

    def test_get_history_format(self):
        mem = ConversationMemory()
        mem.add_turn("Socrates", "Virtue is knowledge.", 1)
        history = mem.get_history_for_chain()
        assert len(history) == 1
        assert isinstance(history[0], HumanMessage)
        assert history[0].content == "[Socrates, Round 1]: Virtue is knowledge."

    def test_get_context_string(self):
        mem = ConversationMemory()
        mem.add_turn("Socrates", "Hello.", 1)
        mem.add_turn("Confucius", "Greetings.", 1)
        ctx = mem.get_context_string()
        assert "[Socrates, Round 1]: Hello." in ctx
        assert "[Confucius, Round 1]: Greetings." in ctx

    def test_clear_resets(self):
        mem = ConversationMemory()
        mem.add_turn("Socrates", "text", 1)
        mem.clear()
        assert mem.turn_count == 0
        assert mem.get_history_for_chain() == []

    def test_fewer_turns_than_window(self):
        mem = ConversationMemory(window_size=10)
        mem.add_turn("Socrates", "One turn only.", 1)
        history = mem.get_history_for_chain()
        assert len(history) == 1

    def test_chronological_order(self):
        mem = ConversationMemory()
        mem.add_turn("Socrates", "First", 1)
        mem.add_turn("Confucius", "Second", 1)
        mem.add_turn("Socrates", "Third", 2)
        history = mem.get_history_for_chain()
        assert "First" in history[0].content
        assert "Second" in history[1].content
        assert "Third" in history[2].content

    def test_default_window_size(self):
        mem = ConversationMemory()
        assert mem.window_size == DEFAULT_WINDOW_SIZE

    def test_serialize_roundtrip(self):
        mem = ConversationMemory(window_size=4)
        mem.add_turn("Socrates", "Hello", 1)
        mem.add_turn("Confucius", "Hi", 1)
        serialized = mem.to_list()
        restored = ConversationMemory.from_list(serialized, window_size=4)
        assert restored.turn_count == 2
        assert restored.window_size == 4
        h1 = mem.get_history_for_chain()
        h2 = restored.get_history_for_chain()
        assert len(h1) == len(h2)
        for a, b in zip(h1, h2):
            assert a.content == b.content
