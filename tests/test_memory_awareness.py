# tests/test_memory_awareness.py — Tests for memory awareness improvements.

import pytest
from unittest.mock import patch, MagicMock

from langchain_core.messages import HumanMessage

from core.memory import ConversationMemory, DEFAULT_WINDOW_SIZE
from core.graph import philosopher_node, _record_positions, DialogueState
from core.utils import robust_invoke, MAX_RETRIES
from translator import format_conversation_for_translation


# ---------------------------------------------------------------------------
# ConversationMemory: full history method
# ---------------------------------------------------------------------------

class TestFullHistory:
    def test_get_full_history_returns_all_turns(self):
        """get_full_history_for_chain should return every turn regardless of window_size."""
        mem = ConversationMemory(window_size=3)
        for i in range(10):
            mem.add_turn("Speaker", f"Turn {i}", round_number=(i // 2) + 1)
        full = mem.get_full_history_for_chain()
        assert len(full) == 10

    def test_get_full_history_format(self):
        mem = ConversationMemory()
        mem.add_turn("Socrates", "Virtue is knowledge.", 1)
        full = mem.get_full_history_for_chain()
        assert len(full) == 1
        assert isinstance(full[0], HumanMessage)
        assert full[0].content == "[Socrates, Round 1]: Virtue is knowledge."

    def test_full_history_empty_memory(self):
        mem = ConversationMemory()
        assert mem.get_full_history_for_chain() == []

    def test_default_window_size_is_large(self):
        """DEFAULT_WINDOW_SIZE should be large enough for full conversations."""
        assert DEFAULT_WINDOW_SIZE >= 20


# ---------------------------------------------------------------------------
# Topic injection: philosopher always sees original topic
# ---------------------------------------------------------------------------

class TestTopicInjection:
    @patch("core.graph.PhilosopherMemory")
    @patch("core.graph.create_chain")
    def test_topic_included_on_first_turn(self, mock_create_chain, mock_phil_mem):
        """On turn 0, input_content should be the topic itself."""
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = "Response text."
        mock_create_chain.return_value = mock_chain

        mock_mem_instance = MagicMock()
        mock_mem_instance.get_context_for_prompt.return_value = ""
        mock_phil_mem.return_value = mock_mem_instance

        state = _make_base_state(turn_count=0)
        philosopher_node(state)

        call_args = mock_chain.invoke.call_args[0][0]
        assert "What is virtue?" in call_args["input"]

    @patch("core.graph.PhilosopherMemory")
    @patch("core.graph.create_chain")
    def test_topic_included_on_subsequent_turns(self, mock_create_chain, mock_phil_mem):
        """On turn > 0, input_content should contain 'Original topic:'."""
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = "Response text."
        mock_create_chain.return_value = mock_chain

        mock_mem_instance = MagicMock()
        mock_mem_instance.get_context_for_prompt.return_value = ""
        mock_phil_mem.return_value = mock_mem_instance

        state = _make_base_state(turn_count=3)
        state["last_response"] = "Previous philosopher said something."
        philosopher_node(state)

        call_args = mock_chain.invoke.call_args[0][0]
        assert "Original topic: What is virtue?" in call_args["input"]
        assert "Previous philosopher said something." in call_args["input"]

    @patch("core.graph.PhilosopherMemory")
    @patch("core.graph.create_chain")
    def test_full_history_used_not_windowed(self, mock_create_chain, mock_phil_mem):
        """philosopher_node should use get_full_history_for_chain, passing all turns."""
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = "Response."
        mock_create_chain.return_value = mock_chain

        mock_mem_instance = MagicMock()
        mock_mem_instance.get_context_for_prompt.return_value = ""
        mock_phil_mem.return_value = mock_mem_instance

        # Create state with many memory turns
        turns = [
            {"speaker": f"Speaker{i}", "content": f"Turn {i}", "round": (i // 2) + 1}
            for i in range(12)
        ]
        state = _make_base_state(turn_count=12)
        state["memory_turns"] = turns

        philosopher_node(state)

        call_args = mock_chain.invoke.call_args[0][0]
        # All 12 turns should be in chat_history
        assert len(call_args["chat_history"]) == 12


# ---------------------------------------------------------------------------
# Long-term memory context includes usage instructions
# ---------------------------------------------------------------------------

class TestLongTermMemoryContext:
    @patch("core.graph.PhilosopherMemory")
    @patch("core.graph.create_chain")
    def test_long_term_memory_includes_instructions(self, mock_create_chain, mock_phil_mem):
        """When long-term memory is present, instructions should be included."""
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = "Response."
        mock_create_chain.return_value = mock_chain

        mock_mem_instance = MagicMock()
        mock_mem_instance.get_context_for_prompt.return_value = (
            "[Previous discussions on related topics:]\n"
            "- On 'virtue': Virtue is knowledge."
        )
        mock_phil_mem.return_value = mock_mem_instance

        state = _make_base_state(turn_count=0)
        philosopher_node(state)

        call_args = mock_chain.invoke.call_args[0][0]
        assert "recalled positions" in call_args["input"].lower() or \
               "consistency" in call_args["input"].lower()


# ---------------------------------------------------------------------------
# Position recording: deduplicated and not truncated at 200 chars
# ---------------------------------------------------------------------------

class TestPositionRecording:
    @patch("core.graph.PhilosopherMemory")
    def test_records_only_last_message_per_philosopher(self, mock_phil_mem):
        """Should only record the final message from each philosopher."""
        mock_mem_instance = MagicMock()
        mock_phil_mem.return_value = mock_mem_instance

        state = DialogueState(
            messages=[
                {"role": "Socrates", "content": "Early thought.", "monologue": None},
                {"role": "Confucius", "content": "Early wisdom.", "monologue": None},
                {"role": "Socrates", "content": "Final thought.", "monologue": None},
                {"role": "Confucius", "content": "Final wisdom.", "monologue": None},
            ],
            philosopher_1_id="socrates",
            philosopher_2_id="confucius",
            topic="What is virtue?",
        )

        _record_positions(state, "What is virtue?", "session-123")

        # Should have recorded exactly 2 positions (one per philosopher)
        assert mock_mem_instance.record_position.call_count == 2
        # Verify the recorded content is from the LAST messages
        calls = mock_mem_instance.record_position.call_args_list
        recorded_positions = [c[0][1] for c in calls]  # position_summary arg
        assert any("Final thought" in p for p in recorded_positions)
        assert any("Final wisdom" in p for p in recorded_positions)

    @patch("core.graph.PhilosopherMemory")
    def test_does_not_truncate_at_200_chars(self, mock_phil_mem):
        """Positions longer than 200 chars should not be truncated at 200."""
        mock_mem_instance = MagicMock()
        mock_phil_mem.return_value = mock_mem_instance

        long_content = "A" * 300
        state = DialogueState(
            messages=[
                {"role": "Socrates", "content": long_content, "monologue": None},
            ],
            philosopher_1_id="socrates",
            philosopher_2_id="confucius",
            topic="Test",
        )

        _record_positions(state, "Test", "session-123")

        recorded = mock_mem_instance.record_position.call_args[0][1]
        assert len(recorded) >= 300  # Not truncated at 200


# ---------------------------------------------------------------------------
# Translator: handles all 6 philosophers
# ---------------------------------------------------------------------------

class TestTranslatorAllPhilosophers:
    def test_includes_all_registered_philosophers(self):
        """Translator should not skip any registered philosopher."""
        messages = [
            {"role": "user", "content": "What is history?"},
            {"role": "Socrates", "content": "History teaches..."},
            {"role": "Confucius", "content": "The ancients..."},
            {"role": "Aristotle", "content": "Observation shows..."},
            {"role": "Nietzsche", "content": "Will to power..."},
            {"role": "Herodotus", "content": "I inquired..."},
            {"role": "Sima Qian", "content": "The records show..."},
        ]
        result = format_conversation_for_translation(messages)
        assert "INITIAL PROMPT" in result
        assert "SOCRATES" in result
        assert "CONFUCIUS" in result
        assert "ARISTOTLE" in result
        assert "NIETZSCHE" in result
        assert "HERODOTUS" in result
        assert "SIMA QIAN" in result

    def test_still_excludes_system_messages(self):
        messages = [
            {"role": "system", "content": "Moderator context"},
            {"role": "Aristotle", "content": "My view is..."},
        ]
        result = format_conversation_for_translation(messages)
        assert "Moderator" not in result
        assert "ARISTOTLE" in result


# ---------------------------------------------------------------------------
# Shared robust_invoke
# ---------------------------------------------------------------------------

class TestSharedRobustInvoke:
    def test_success(self):
        chain = MagicMock()
        chain.invoke.return_value = "Hello world"
        result, monologue = robust_invoke(chain, {"input": "test"}, "TestActor", 1)
        assert result == "Hello world"
        assert monologue is None

    def test_none_chain(self):
        result, monologue = robust_invoke(None, {"input": "test"}, "TestActor", 1)
        assert result is None

    def test_with_think_block(self):
        chain = MagicMock()
        chain.invoke.return_value = "<think>thinking</think>Visible"
        result, monologue = robust_invoke(chain, {"input": "test"}, "TestActor", 1)
        assert result == "Visible"
        assert monologue == "thinking"

    @patch("core.utils.time.sleep")
    def test_retries_on_failure(self, mock_sleep):
        chain = MagicMock()
        chain.invoke.side_effect = [Exception("fail"), "recovered"]
        result, monologue = robust_invoke(chain, {"input": "test"}, "TestActor", 1)
        assert result == "recovered"

    @patch("core.utils.time.sleep")
    def test_permanent_failure(self, mock_sleep):
        chain = MagicMock()
        chain.invoke.side_effect = [Exception("fail")] * MAX_RETRIES
        result, monologue = robust_invoke(chain, {"input": "test"}, "TestActor", 1)
        assert result is None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_base_state(turn_count: int = 0) -> DialogueState:
    return DialogueState(
        messages=[],
        memory_turns=[],
        current_round=1,
        total_rounds=3,
        philosopher_1_id="socrates",
        philosopher_2_id="confucius",
        philosopher_1_name="Socrates",
        philosopher_2_name="Confucius",
        last_speaker_id="",
        last_response="",
        next_speaker_id="socrates",
        speaker_intent="",
        addressed_to="",
        mode="philosophy",
        topic="What is virtue?",
        turn_count=turn_count,
        is_complete=False,
        error="",
    )
