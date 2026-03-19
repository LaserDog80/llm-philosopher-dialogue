# core/memory.py — Sliding-window conversation memory + persistent philosopher memory.

import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict

from langchain_core.messages import HumanMessage, BaseMessage

logger = logging.getLogger(__name__)

DEFAULT_WINDOW_SIZE = 50  # Large enough to cover full conversations


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

    def get_full_history_for_chain(self) -> List[BaseMessage]:
        """Return ALL turns as LangChain messages, ignoring window_size.

        Use this when full conversation context is needed, e.g. for
        philosopher nodes that need to see the entire conversation.
        """
        messages: List[BaseMessage] = []
        for turn in self._turns:
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


# ---------------------------------------------------------------------------
# PhilosopherMemory — persistent cross-session memory per philosopher
# ---------------------------------------------------------------------------

DEFAULT_MEMORY_DB = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "philosopher_memory.db"
)


class PhilosopherMemory:
    """Long-term memory for a philosopher across sessions.

    Stores topic-position pairs in SQLite so philosophers can recall
    what they discussed in previous conversations.
    """

    def __init__(self, philosopher_id: str, db_path: str = DEFAULT_MEMORY_DB):
        self.philosopher_id = philosopher_id
        self.db_path = db_path
        self._ensure_table()

    def _get_conn(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        return sqlite3.connect(self.db_path)

    def _ensure_table(self) -> None:
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS philosopher_memory (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        philosopher_id TEXT NOT NULL,
                        topic TEXT NOT NULL,
                        position TEXT NOT NULL,
                        session_id TEXT,
                        created_at TEXT NOT NULL
                    )
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_phil_topic
                    ON philosopher_memory (philosopher_id, topic)
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"PhilosopherMemory table creation failed: {e}")

    def record_position(self, topic: str, position_summary: str, session_id: str = "") -> None:
        """Record a philosopher's position on a topic."""
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT INTO philosopher_memory (philosopher_id, topic, position, session_id, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (self.philosopher_id, topic, position_summary, session_id, datetime.now().isoformat()),
                )
                conn.commit()
            logger.info(f"Recorded position for {self.philosopher_id} on '{topic}'")
        except Exception as e:
            logger.error(f"Failed to record position: {e}")

    def recall_positions(self, topic: str, limit: int = 5) -> List[Dict[str, str]]:
        """Recall previous positions on a topic (fuzzy match via LIKE)."""
        try:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "SELECT topic, position, created_at FROM philosopher_memory "
                    "WHERE philosopher_id = ? AND topic LIKE ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (self.philosopher_id, f"%{topic}%", limit),
                )
                results = [
                    {"topic": row[0], "position": row[1], "created_at": row[2]}
                    for row in cursor.fetchall()
                ]
            return results
        except Exception as e:
            logger.error(f"Failed to recall positions: {e}")
            return []

    def get_all_topics(self) -> List[str]:
        """Return all unique topics this philosopher has discussed."""
        try:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "SELECT DISTINCT topic FROM philosopher_memory WHERE philosopher_id = ? ORDER BY topic",
                    (self.philosopher_id,),
                )
                topics = [row[0] for row in cursor.fetchall()]
            return topics
        except Exception as e:
            logger.error(f"Failed to get topics: {e}")
            return []

    def get_context_for_prompt(self, topic: str, limit: int = 3) -> str:
        """Build a prompt-ready context string from recalled positions."""
        positions = self.recall_positions(topic, limit=limit)
        if not positions:
            return ""
        lines = ["[Previous discussions on related topics:]"]
        for p in positions:
            lines.append(f"- On '{p['topic']}': {p['position']}")
        return "\n".join(lines)
