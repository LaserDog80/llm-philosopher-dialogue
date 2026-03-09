"""Tests for core/models.py — typed state model."""

import dataclasses

from core.models import (
    Turn,
    ConversationState,
    ResumeState,
    ConversationMode,
    ModeratorControl,
    LogState,
    DisplaySettings,
)


class TestTurn:
    def test_creation_defaults(self):
        t = Turn(role="Socrates", content="Virtue is knowledge.")
        assert t.role == "Socrates"
        assert t.content == "Virtue is knowledge."
        assert t.monologue is None
        assert t.original_content is None

    def test_with_monologue(self):
        t = Turn(role="Socrates", content="text", monologue="thinking")
        assert t.monologue == "thinking"

    def test_to_dict(self):
        t = Turn(role="Confucius", content="hello", monologue="hmm")
        d = t.to_dict()
        assert d == {"role": "Confucius", "content": "hello", "monologue": "hmm"}

    def test_original_content_preserved(self):
        t = Turn(role="user", content="translated", original_content="original")
        assert t.original_content == "original"


class TestConversationState:
    def test_defaults(self):
        cs = ConversationState()
        assert cs.messages == []
        assert cs.current_status == "Ready."
        assert cs.conversation_completed is False
        assert cs.num_rounds == 3
        assert cs.starting_philosopher == "Socrates"
        assert cs.conversation_mode == ConversationMode.PHILOSOPHY
        assert cs.moderator_control == ModeratorControl.AI
        assert cs.bypass_moderator is False

    def test_append_turn(self):
        cs = ConversationState()
        t = Turn(role="user", content="What is virtue?")
        cs.messages.append(t)
        assert len(cs.messages) == 1
        assert cs.messages[0].content == "What is virtue?"


class TestEnums:
    def test_conversation_mode_values(self):
        assert ConversationMode.PHILOSOPHY == "Philosophy"
        assert ConversationMode.BIO == "Bio"

    def test_moderator_control_values(self):
        assert ModeratorControl.AI == "AI Moderator"
        assert ModeratorControl.USER_GUIDANCE == "User as Moderator (Guidance)"


class TestResumeState:
    def test_serializable(self):
        """ResumeState must convert cleanly to a dict (no chain objects)."""
        rs = ResumeState(
            current_round_num=2,
            num_rounds_total=5,
            actor_1_name="Socrates",
            actor_2_name="Confucius",
            next_speaker_name="Confucius",
            other_speaker_name="Socrates",
            mode="Philosophy",
        )
        d = dataclasses.asdict(rs)
        assert isinstance(d, dict)
        assert d["current_round_num"] == 2
        assert d["actor_1_name"] == "Socrates"

    def test_roundtrip(self):
        rs = ResumeState(actor_1_name="Socrates", actor_2_name="Confucius")
        d = dataclasses.asdict(rs)
        rs2 = ResumeState(**d)
        assert rs == rs2


class TestLogState:
    def test_defaults(self):
        ls = LogState()
        assert ls.content is None
        assert ls.filename is None


class TestDisplaySettings:
    def test_defaults(self):
        ds = DisplaySettings()
        assert ds.show_monologue is False
        assert ds.show_moderator is False
        assert ds.output_style == "Original Text"
