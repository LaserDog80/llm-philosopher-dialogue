# core/models.py — Typed state model replacing the flat session-state dict.

from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class ConversationMode(str, Enum):
    PHILOSOPHY = "Philosophy"
    BIO = "Bio"


class ModeratorControl(str, Enum):
    AI = "AI Moderator"
    USER_GUIDANCE = "User as Moderator (Guidance)"


@dataclass
class Turn:
    """A single turn in the conversation."""

    role: str  # "user", "Socrates", "Confucius", "system"
    content: str
    monologue: Optional[str] = None
    original_content: Optional[str] = None  # preserves pre-translation text

    def to_dict(self) -> dict:
        """Convert to the dict format gui.py and logging expect."""
        return {
            "role": self.role,
            "content": self.content,
            "monologue": self.monologue,
        }


@dataclass
class ConversationState:
    """All conversation-related state."""

    messages: List[Turn] = field(default_factory=list)
    current_status: str = "Ready."
    conversation_completed: bool = False
    awaiting_user_guidance: bool = False
    ai_summary_for_guidance_input: Optional[str] = None
    next_speaker_for_guidance: Optional[str] = None
    num_rounds: int = 3
    starting_philosopher: str = "Socrates"
    conversation_mode: ConversationMode = ConversationMode.PHILOSOPHY
    moderator_control: ModeratorControl = ModeratorControl.AI
    bypass_moderator: bool = False


@dataclass
class ResumeState:
    """Serializable resume state for user-guided conversations.

    Chain objects are NOT stored here — they are recreated on resume
    via _load_chains_for_mode().
    """

    current_round_num: int = 1
    num_rounds_total: int = 3
    actor_1_name: str = ""
    actor_2_name: str = ""
    next_speaker_name: str = ""
    other_speaker_name: str = ""
    mode: str = "Philosophy"
    run_moderated: bool = True
    moderator_type: str = "ai"
    input_for_next_speaker: str = ""
    ai_summary_from_last_mod: Optional[str] = None
    ai_guidance_from_last_mod: Optional[str] = None
    previous_philosopher_actual_response: str = ""
    messages_log: List[dict] = field(default_factory=list)
    memory_turns: List[dict] = field(default_factory=list)


@dataclass
class LogState:
    """In-memory log state."""

    content: Optional[List[str]] = None
    filename: Optional[str] = None


@dataclass
class DisplaySettings:
    """UI display preferences."""

    show_monologue: bool = False
    show_moderator: bool = False
    output_style: str = "Original Text"
