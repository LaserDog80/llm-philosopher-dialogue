# tests/test_graph.py — Tests for the LangGraph agentic conversation engine.

import pytest
from unittest.mock import patch, MagicMock

from core.graph import (
    DialogueState,
    philosopher_node,
    router_node,
    _should_continue,
    build_dialogue_graph,
    run_agentic_conversation,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def base_state():
    """Minimal DialogueState for testing."""
    return DialogueState(
        messages=[],
        memory_turns=[],
        current_round=1,
        total_rounds=2,
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
        turn_count=0,
        is_complete=False,
        error="",
    )


# ---------------------------------------------------------------------------
# Router node tests
# ---------------------------------------------------------------------------

class TestRouterNode:
    def test_first_turn_routes_to_philosopher_1(self, base_state):
        """Router should set next_speaker_id on first turn."""
        result = router_node(base_state)
        assert result["is_complete"] is False
        # First turn: next speaker is philosopher_1 (already set)
        assert "next_speaker_id" in result

    def test_alternates_speakers(self, base_state):
        """After philosopher_1 speaks, router should select philosopher_2."""
        base_state["last_speaker_id"] = "socrates"
        base_state["turn_count"] = 1
        result = router_node(base_state)
        assert result["next_speaker_id"] == "confucius"

    def test_alternates_back(self, base_state):
        """After philosopher_2 speaks, router should select philosopher_1."""
        base_state["last_speaker_id"] = "confucius"
        base_state["turn_count"] = 2
        result = router_node(base_state)
        assert result["next_speaker_id"] == "socrates"

    def test_completes_after_max_turns(self, base_state):
        """Router should mark complete when turn_count >= total_rounds * 2."""
        base_state["turn_count"] = 4  # 2 rounds * 2 turns each
        result = router_node(base_state)
        assert result["is_complete"] is True

    def test_advances_round_counter(self, base_state):
        """Round counter should advance after both philosophers speak."""
        base_state["turn_count"] = 2
        base_state["current_round"] = 1
        base_state["last_speaker_id"] = "confucius"
        result = router_node(base_state)
        assert result["current_round"] == 2


# ---------------------------------------------------------------------------
# Should-continue conditional edge
# ---------------------------------------------------------------------------

class TestShouldContinue:
    def test_continues_when_not_complete(self, base_state):
        assert _should_continue(base_state) == "continue"

    def test_ends_when_complete(self, base_state):
        base_state["is_complete"] = True
        assert _should_continue(base_state) == "end"

    def test_ends_on_error(self, base_state):
        base_state["error"] = "Something went wrong"
        assert _should_continue(base_state) == "end"


# ---------------------------------------------------------------------------
# Philosopher node tests (mocked LLM)
# ---------------------------------------------------------------------------

class TestPhilosopherNode:
    @patch("core.graph.PhilosopherMemory")
    @patch("core.graph.create_chain")
    def test_basic_invocation(self, mock_create_chain, mock_phil_mem, base_state):
        """Philosopher node should invoke chain and return updated state."""
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = (
            "I believed virtue was knowledge.\n[NEXT: Confucius | INTENT: address]"
        )
        mock_create_chain.return_value = mock_chain

        mock_mem_instance = MagicMock()
        mock_mem_instance.get_context_for_prompt.return_value = ""
        mock_phil_mem.return_value = mock_mem_instance

        result = philosopher_node(base_state)

        assert len(result["messages"]) == 1
        assert result["messages"][0]["role"] == "Socrates"
        assert "virtue was knowledge" in result["messages"][0]["content"]
        assert result["last_speaker_id"] == "socrates"
        assert result["speaker_intent"] == "address"
        assert result["turn_count"] == 1

    @patch("core.graph.PhilosopherMemory")
    @patch("core.graph.create_chain")
    def test_strips_direction_tag(self, mock_create_chain, mock_phil_mem, base_state):
        """Direction tag should be removed from displayed content."""
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = (
            "Virtue is knowledge.\n[NEXT: Confucius | INTENT: challenge]"
        )
        mock_create_chain.return_value = mock_chain

        mock_mem_instance = MagicMock()
        mock_mem_instance.get_context_for_prompt.return_value = ""
        mock_phil_mem.return_value = mock_mem_instance

        result = philosopher_node(base_state)
        assert "[NEXT:" not in result["messages"][0]["content"]
        assert result["speaker_intent"] == "challenge"

    @patch("core.graph.PhilosopherMemory")
    @patch("core.graph.create_chain")
    def test_handles_no_direction_tag(self, mock_create_chain, mock_phil_mem, base_state):
        """Should default to addressing the other philosopher when no tag present."""
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = "Simply a response without any tag."
        mock_create_chain.return_value = mock_chain

        mock_mem_instance = MagicMock()
        mock_mem_instance.get_context_for_prompt.return_value = ""
        mock_phil_mem.return_value = mock_mem_instance

        result = philosopher_node(base_state)
        assert result["speaker_intent"] == "address"
        assert result["turn_count"] == 1

    @patch("core.graph.PhilosopherMemory")
    @patch("core.graph.create_chain")
    def test_handles_chain_failure(self, mock_create_chain, mock_phil_mem, base_state):
        """Should return error state when chain fails."""
        mock_create_chain.return_value = None

        result = philosopher_node(base_state)
        assert result["is_complete"] is True
        assert "error" in result


# ---------------------------------------------------------------------------
# Graph compilation test
# ---------------------------------------------------------------------------

class TestGraphCompilation:
    def test_builds_without_checkpointer(self):
        """Graph should compile without a checkpointer."""
        graph = build_dialogue_graph()
        assert graph is not None

    def test_builds_with_checkpointer(self, tmp_path):
        """Graph should compile with a SQLite checkpointer."""
        from langgraph.checkpoint.sqlite import SqliteSaver
        import sqlite3

        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path, check_same_thread=False)
        checkpointer = SqliteSaver(conn=conn)
        graph = build_dialogue_graph(checkpointer=checkpointer)
        assert graph is not None
        conn.close()


# ---------------------------------------------------------------------------
# Integration test (mocked LLM)
# ---------------------------------------------------------------------------

class TestRunAgenticConversation:
    @patch("core.graph.PhilosopherMemory")
    @patch("core.graph.create_chain")
    def test_full_conversation(self, mock_create_chain, mock_phil_mem, tmp_path):
        """Full conversation should produce messages and a thread ID."""
        call_count = 0

        def fake_invoke(input_dict):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 1:
                return "I believed virtue was knowledge.\n[NEXT: Confucius | INTENT: address]"
            else:
                return "I taught that virtue came from ritual.\n[NEXT: Socrates | INTENT: challenge]"

        mock_chain = MagicMock()
        mock_chain.invoke.side_effect = fake_invoke
        mock_create_chain.return_value = mock_chain

        mock_mem_instance = MagicMock()
        mock_mem_instance.get_context_for_prompt.return_value = ""
        mock_phil_mem.return_value = mock_mem_instance

        db_path = str(tmp_path / "test_conv.db")
        messages, status, success, thread_id = run_agentic_conversation(
            topic="What is virtue?",
            philosopher_1="Socrates",
            philosopher_2="Confucius",
            num_rounds=1,
            mode="philosophy",
            db_path=db_path,
        )

        assert success is True
        assert len(messages) == 2  # 1 round = 2 turns
        assert messages[0]["role"] == "Socrates"
        assert messages[1]["role"] == "Confucius"
        assert thread_id  # Should have a UUID
        assert "[NEXT:" not in messages[0]["content"]
