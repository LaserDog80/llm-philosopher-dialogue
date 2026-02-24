# tests/test_direction.py — Integration tests for the Director (direction.py).

import time
import pytest
from unittest.mock import patch, MagicMock, call

from direction import Director, MAX_RETRIES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_chain(responses):
    """Create a mock chain that returns responses in order.
    Each response is the raw string the chain would return."""
    chain = MagicMock()
    chain.invoke = MagicMock(side_effect=responses)
    return chain


def _philosopher_response(text):
    """Simulate a raw philosopher response (no think block)."""
    return text


def _moderator_response(summary, guidance):
    """Simulate a raw moderator response with SUMMARY/GUIDANCE markers."""
    return f"SUMMARY: {summary}\nGUIDANCE: {guidance}"


# ---------------------------------------------------------------------------
# TestRobustInvoke
# ---------------------------------------------------------------------------

class TestRobustInvoke:
    def setup_method(self):
        self.director = Director()

    def test_success(self):
        chain = _make_mock_chain(["Hello world"])
        result, monologue = self.director._robust_invoke(chain, {"input": "test"}, "TestActor", 1)
        assert result == "Hello world"
        assert monologue is None

    def test_with_think_block(self):
        chain = _make_mock_chain(["<think>internal</think>Visible response"])
        result, monologue = self.director._robust_invoke(chain, {"input": "test"}, "TestActor", 1)
        assert result == "Visible response"
        assert monologue == "internal"

    @patch("direction.time.sleep")  # skip actual sleep in tests
    def test_retry_then_success(self, mock_sleep):
        chain = _make_mock_chain([Exception("timeout"), "recovered"])
        result, monologue = self.director._robust_invoke(chain, {"input": "test"}, "TestActor", 1)
        assert result == "recovered"

    @patch("direction.time.sleep")
    def test_permanent_failure(self, mock_sleep):
        chain = _make_mock_chain([Exception("fail")] * MAX_RETRIES)
        result, monologue = self.director._robust_invoke(chain, {"input": "test"}, "TestActor", 1)
        assert result is None
        assert monologue is None

    def test_none_chain(self):
        result, monologue = self.director._robust_invoke(None, {"input": "test"}, "TestActor", 1)
        assert result is None
        assert monologue is None

    def test_empty_response_raises_retries(self):
        """An empty string response returns ('', None), not a retry."""
        chain = _make_mock_chain([""])
        result, monologue = self.director._robust_invoke(chain, {"input": "test"}, "TestActor", 1)
        assert result == ""
        assert monologue is None


# ---------------------------------------------------------------------------
# TestInvokeModeratorText
# ---------------------------------------------------------------------------

class TestInvokeModeratorText:
    def setup_method(self):
        self.director = Director()

    def test_correct_parsing(self):
        chain = _make_mock_chain([_moderator_response("Good debate", "Ask about ethics")])
        summary, guidance, raw = self.director._invoke_moderator_text(
            chain, "Socrates", "response text", "Confucius", 1
        )
        assert summary == "Good debate"
        assert guidance == "Ask about ethics"
        assert raw is not None

    def test_no_markers_fallback(self):
        chain = _make_mock_chain(["Just some plain text without markers"])
        summary, guidance, raw = self.director._invoke_moderator_text(
            chain, "Socrates", "response", "Confucius", 1
        )
        # Falls back to using raw output as summary
        assert summary == "Just some plain text without markers"
        assert guidance == "Continue the discussion naturally."

    def test_only_summary_marker(self):
        chain = _make_mock_chain(["SUMMARY: Only a summary here"])
        summary, guidance, raw = self.director._invoke_moderator_text(
            chain, "Socrates", "response", "Confucius", 1
        )
        assert summary == "Only a summary here"
        assert guidance == "Continue the discussion naturally."

    def test_only_guidance_marker(self):
        chain = _make_mock_chain(["GUIDANCE: Only guidance here"])
        summary, guidance, raw = self.director._invoke_moderator_text(
            chain, "Socrates", "response", "Confucius", 1
        )
        assert summary == "N/A"
        assert guidance == "Only guidance here"

    def test_none_chain_returns_error(self):
        summary, guidance, raw = self.director._invoke_moderator_text(
            None, "Socrates", "response", "Confucius", 1
        )
        assert summary is None
        assert "Error" in guidance
        assert raw is None

    def test_conversation_context_included(self):
        chain = _make_mock_chain([_moderator_response("sum", "guide")])
        self.director._invoke_moderator_text(
            chain, "Socrates", "response", "Confucius", 1,
            conversation_context="Some prior context"
        )
        # Verify the context was passed in the input
        call_args = chain.invoke.call_args[0][0]
        assert "Some prior context" in call_args["input"]


# ---------------------------------------------------------------------------
# TestRunConversation
# ---------------------------------------------------------------------------

class TestRunConversation:
    def setup_method(self):
        self.director = Director()

    @patch.object(Director, "_load_chains_for_mode")
    def test_ai_mode_full_loop(self, mock_load):
        """AI moderator mode completes 2 rounds (4 philosopher turns)."""
        s_chain = _make_mock_chain([
            _philosopher_response("Socrates R1"),
            _philosopher_response("Socrates R2"),
        ])
        c_chain = _make_mock_chain([
            _philosopher_response("Confucius R1"),
            _philosopher_response("Confucius R2"),
        ])
        m_chain = _make_mock_chain([
            _moderator_response("sum1", "guide1"),
            _moderator_response("sum2", "guide2"),
            _moderator_response("sum3", "guide3"),
        ])
        mock_load.return_value = (s_chain, c_chain, m_chain, True)

        msgs, status, success, resume, guidance = self.director.run_conversation_streamlit(
            initial_input="What is virtue?",
            num_rounds=2,
            starting_philosopher="Socrates",
            run_moderated=True,
            mode="philosophy",
            moderator_type="ai",
        )

        assert success is True
        assert resume is None
        # Should have philosopher messages + moderator system messages
        philosopher_msgs = [m for m in msgs if m["role"] in ("Socrates", "Confucius")]
        assert len(philosopher_msgs) == 4  # 2 rounds × 2 speakers

    @patch.object(Director, "_load_chains_for_mode")
    def test_direct_mode_no_moderator(self, mock_load):
        """Direct mode (bypass moderator) runs without moderator chain."""
        s_chain = _make_mock_chain([_philosopher_response("S1")])
        c_chain = _make_mock_chain([_philosopher_response("C1")])
        mock_load.return_value = (s_chain, c_chain, None, True)

        msgs, status, success, resume, guidance = self.director.run_conversation_streamlit(
            initial_input="What is justice?",
            num_rounds=1,
            run_moderated=False,
            mode="philosophy",
            moderator_type="ai",
        )

        assert success is True
        philosopher_msgs = [m for m in msgs if m["role"] in ("Socrates", "Confucius")]
        assert len(philosopher_msgs) == 2
        # No moderator system messages
        system_msgs = [m for m in msgs if m["role"] == "system"]
        assert len(system_msgs) == 0

    @patch.object(Director, "_load_chains_for_mode")
    def test_user_guidance_pauses(self, mock_load):
        """User guidance mode pauses after first speaker + moderator."""
        s_chain = _make_mock_chain([_philosopher_response("Socrates speaks")])
        c_chain = _make_mock_chain([])  # Won't be called yet
        m_chain = _make_mock_chain([_moderator_response("summary", "guidance")])
        mock_load.return_value = (s_chain, c_chain, m_chain, True)

        msgs, status, success, resume, guidance = self.director.run_conversation_streamlit(
            initial_input="Question?",
            num_rounds=2,
            run_moderated=True,
            mode="philosophy",
            moderator_type="user_guidance",
        )

        assert status == "WAITING_FOR_USER_GUIDANCE"
        assert success is False  # Not yet complete
        assert resume is not None
        assert guidance is not None
        assert guidance["next_speaker_name"] == "Confucius"

    @patch.object(Director, "_load_chains_for_mode")
    def test_chain_load_failure(self, mock_load):
        mock_load.return_value = (None, None, None, False)

        msgs, status, success, resume, guidance = self.director.run_conversation_streamlit(
            initial_input="Test",
            num_rounds=1,
        )

        assert success is False
        assert "Error" in status
        assert msgs == []


# ---------------------------------------------------------------------------
# TestResumeConversation
# ---------------------------------------------------------------------------

class TestResumeConversation:
    def setup_method(self):
        self.director = Director()

    @patch.object(Director, "_load_chains_for_mode")
    def test_resume_executes_next_turn(self, mock_load):
        """Resume recreates chains from serialized state and executes next turn."""
        c_chain = _make_mock_chain([_philosopher_response("Confucius responds")])
        s_chain = _make_mock_chain([])
        m_chain = _make_mock_chain([_moderator_response("sum", "guide")])
        mock_load.return_value = (s_chain, c_chain, m_chain, True)

        # Simulate a serialized resume state (no chain objects)
        resume_state = {
            "messages_log": [
                {"role": "Socrates", "content": "Previous response", "monologue": None}
            ],
            "current_round_num": 1,
            "num_rounds_total": 2,
            "actor_1_name": "Socrates",
            "actor_2_name": "Confucius",
            "next_speaker_name": "Confucius",
            "other_speaker_name": "Socrates",
            "mode": "philosophy",
            "run_moderated": True,
            "moderator_type": "user_guidance",
            "input_for_next_speaker": "",
            "ai_summary_from_last_mod": "Previous summary",
            "ai_guidance_from_last_mod": "Previous guidance",
            "previous_philosopher_actual_response": "Previous response",
            "user_guidance_for_current_turn": None,
            "memory_turns": [
                {"speaker": "User", "content": "Question?", "round": 0},
                {"speaker": "Socrates", "content": "Previous response", "round": 1},
            ],
        }

        msgs, status, success, new_resume, guidance = self.director.resume_conversation_streamlit(
            resume_state, user_provided_guidance="Focus on ethics"
        )

        # Should have produced a Confucius message
        confucius_msgs = [m for m in msgs if m["role"] == "Confucius"]
        assert len(confucius_msgs) >= 1

    @patch.object(Director, "_load_chains_for_mode")
    def test_resume_chain_reload_failure(self, mock_load):
        mock_load.return_value = (None, None, None, False)

        resume_state = {
            "mode": "philosophy",
            "run_moderated": True,
            "actor_1_name": "Socrates",
        }

        msgs, status, success, resume, guidance = self.director.resume_conversation_streamlit(
            resume_state, user_provided_guidance="auto"
        )
        assert success is False
        assert "Error" in status


# ---------------------------------------------------------------------------
# TestSerializedState
# ---------------------------------------------------------------------------

class TestSerializedState:
    def setup_method(self):
        self.director = Director()

    @patch.object(Director, "_load_chains_for_mode")
    def test_serialized_state_has_no_chain_objects(self, mock_load):
        """Serialized resume state must not contain chain objects."""
        s_chain = _make_mock_chain([_philosopher_response("S1")])
        c_chain = _make_mock_chain([])
        m_chain = _make_mock_chain([_moderator_response("sum", "guide")])
        mock_load.return_value = (s_chain, c_chain, m_chain, True)

        msgs, status, success, resume, guidance = self.director.run_conversation_streamlit(
            initial_input="Question?",
            num_rounds=2,
            run_moderated=True,
            mode="philosophy",
            moderator_type="user_guidance",
        )

        assert resume is not None
        # These chain-related keys should NOT be in serialized state
        for forbidden_key in ("actor_1_chain", "actor_2_chain", "moderator_chain", "next_speaker_chain"):
            assert forbidden_key not in resume, f"Found chain key '{forbidden_key}' in serialized state"

    @patch.object(Director, "_load_chains_for_mode")
    def test_serialized_state_has_memory_turns(self, mock_load):
        """Serialized resume state must contain memory_turns list."""
        s_chain = _make_mock_chain([_philosopher_response("S1")])
        c_chain = _make_mock_chain([])
        m_chain = _make_mock_chain([_moderator_response("sum", "guide")])
        mock_load.return_value = (s_chain, c_chain, m_chain, True)

        msgs, status, success, resume, guidance = self.director.run_conversation_streamlit(
            initial_input="Question?",
            num_rounds=2,
            run_moderated=True,
            mode="philosophy",
            moderator_type="user_guidance",
        )

        assert resume is not None
        assert "memory_turns" in resume
        assert isinstance(resume["memory_turns"], list)
        # Should have at least the user prompt + first speaker
        assert len(resume["memory_turns"]) >= 2
