# core/memory.py — Sliding-window conversation memory.

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict

from langchain_core.messages import HumanMessage, BaseMessage

logger = logging.getLogger(__name__)

DEFAULT_WINDOW_SIZE = 6


@dataclass
class ConversationMemory:
    """Sliding-window memory for philosopher dialogue.

    Stores all dialogue turns for posterity, but only returns the last
    ``window_size`` turns when building the chat_history for a chain.
    Moderator and system turns are never stored — only philosopher and
    user dialogue.
    """

    window_size: int = DEFAULT_WINDOW_SIZE
    _turns: List[Dict[str, str]] = field(default_factory=list)

    def add_turn(self, speaker: str, content: str, round_number: int) -> None:
        """Record a dialogue turn (philosopher or user, NOT moderator/system)."""
        self._turns.append({
            "speaker": speaker,
            "content": content,
            "round": round_number,
        })

    def get_history_for_chain(self) -> List[BaseMessage]:
        """Return the last ``window_size`` turns as LangChain messages.

        All turns are formatted as HumanMessage objects with a
        ``[Speaker, Round N]:`` prefix. The chain template places these
        before the current ``{input}``.
        """
        window = self._turns[-self.window_size:] if len(self._turns) > self.window_size else self._turns[:]
        messages: List[BaseMessage] = []
        for turn in window:
            formatted = f"[{turn['speaker']}, Round {turn['round']}]: {turn['content']}"
            messages.append(HumanMessage(content=formatted))
        return messages

    def get_context_string(self, max_turns: Optional[int] = None) -> str:
        """Return a plain-text summary of recent turns for the moderator."""
        n = max_turns or self.window_size
        window = self._turns[-n:] if len(self._turns) > n else self._turns[:]
        lines = []
        for turn in window:
            lines.append(f"[{turn['speaker']}, Round {turn['round']}]: {turn['content']}")
        return "\n".join(lines)

    def to_list(self) -> List[Dict[str, str]]:
        """Serialize turns for storage in ResumeState."""
        return list(self._turns)

    @classmethod
    def from_list(cls, turns: List[Dict[str, str]], window_size: int = DEFAULT_WINDOW_SIZE) -> "ConversationMemory":
        """Restore memory from serialized turns."""
        mem = cls(window_size=window_size)
        mem._turns = list(turns)
        return mem

    @property
    def turn_count(self) -> int:
        return len(self._turns)

    def clear(self) -> None:
        self._turns.clear()
