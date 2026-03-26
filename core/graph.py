# core/graph.py — LangGraph-based agentic conversation engine.
#
# Replaces the imperative Director class with a StateGraph where
# philosopher agents self-organize turn-taking via direction tags.
# No moderator LLM call is needed — routing is rule-based.

import logging
import os
import sqlite3
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple, TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from core.persona import create_chain
from core.utils import extract_and_clean, parse_direction_tag, robust_invoke
from core.memory import ConversationMemory, PhilosopherMemory
from core.registry import get_philosopher_ids, get_philosopher

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "conversations.db"
)


# ---------------------------------------------------------------------------
# Graph State
# ---------------------------------------------------------------------------

class DialogueState(TypedDict, total=False):
    """State that flows through the LangGraph conversation graph."""
    messages: list           # List of message dicts (role, content, monologue)
    memory_turns: list       # Serialized ConversationMemory turns
    current_round: int
    total_rounds: int
    philosopher_1_id: str
    philosopher_2_id: str
    philosopher_1_name: str
    philosopher_2_name: str
    last_speaker_id: str
    last_response: str
    next_speaker_id: str
    speaker_intent: str      # address, challenge, yield, reflect
    addressed_to: str        # Who the last speaker directed response to
    mode: str                # philosophy or bio
    topic: str               # Original user question
    turn_count: int          # Total turns taken so far
    max_tokens_p1: int       # Per-philosopher max_tokens override
    max_tokens_p2: int       # Per-philosopher max_tokens override
    personality_notes_p1: str  # User character notes for philosopher 1
    personality_notes_p2: str  # User character notes for philosopher 2
    is_complete: bool
    error: str


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------

def philosopher_node(state: DialogueState) -> Dict:
    """Invoke the next speaker's chain and parse direction signals."""
    next_id = state["next_speaker_id"]
    mode = state["mode"]
    turn_count = state.get("turn_count", 0)
    current_round = state.get("current_round", 1)

    # Resolve display name
    pcfg = get_philosopher(next_id)
    speaker_name = pcfg.display_name if pcfg else next_id

    # Load chain with per-philosopher max_tokens and personality notes
    if next_id == state["philosopher_1_id"]:
        max_tokens = state.get("max_tokens_p1", 0) or None
        personality_notes = state.get("personality_notes_p1", "")
    else:
        max_tokens = state.get("max_tokens_p2", 0) or None
        personality_notes = state.get("personality_notes_p2", "")
    chain = create_chain(
        next_id, mode=mode, max_tokens_override=max_tokens,
        personality_notes=personality_notes or None,
    )
    if chain is None:
        return {"error": f"Failed to load chain for {speaker_name}", "is_complete": True}

    # Build memory from serialized turns
    memory = ConversationMemory.from_list(state.get("memory_turns", []))

    # Build input content — always include the original topic for context
    topic = state["topic"]
    if turn_count == 0:
        input_content = topic
    else:
        last_response = state.get("last_response", "")
        input_content = f"Original topic: {topic}\n\n{last_response}"

    # Inject long-term memory context with usage instructions
    long_term_ctx = ""
    try:
        phil_mem = PhilosopherMemory(next_id)
        long_term_ctx = phil_mem.get_context_for_prompt(topic, limit=3)
    except Exception as e:
        logger.warning(f"Long-term memory lookup failed for {next_id}: {e}")

    if long_term_ctx:
        input_content = (
            f"{long_term_ctx}\n"
            f"(Use the above recalled positions to maintain consistency "
            f"with your prior views, or explain how your thinking has evolved.)\n\n"
            f"{input_content}"
        )

    # Invoke with full conversation history (no sliding window)
    history = memory.get_full_history_for_chain()
    invoke_input = {"input": input_content, "chat_history": history}

    response, monologue = robust_invoke(chain, invoke_input, speaker_name, current_round)

    if response is None:
        return {
            "error": f"{speaker_name} failed in round {current_round}",
            "is_complete": True,
            "messages": state.get("messages", []) + [
                {"role": "system", "content": f"Error: {speaker_name} failed to respond.", "monologue": None}
            ],
        }

    # Parse direction tag from response
    cleaned_response, direction = parse_direction_tag(response)

    # Also strip any remaining direction tag from think-cleaned response
    if not direction:
        # Fallback: default to addressing the other philosopher
        other_id = (
            state["philosopher_2_id"]
            if next_id == state["philosopher_1_id"]
            else state["philosopher_1_id"]
        )
        other_cfg = get_philosopher(other_id)
        direction = {
            "next": other_cfg.display_name if other_cfg else other_id,
            "intent": "address",
        }

    # Update memory
    memory.add_turn(speaker_name, cleaned_response, current_round)

    # Build message (include intent for UI display)
    intent = direction.get("intent", "address")
    msg = {"role": speaker_name, "content": cleaned_response, "monologue": monologue, "intent": intent}
    messages = state.get("messages", []) + [msg]

    return {
        "messages": messages,
        "memory_turns": memory.to_list(),
        "last_speaker_id": next_id,
        "last_response": cleaned_response,
        "speaker_intent": direction.get("intent", "address"),
        "addressed_to": direction.get("next", ""),
        "turn_count": turn_count + 1,
    }


def router_node(state: DialogueState) -> Dict:
    """Decide who speaks next and whether the conversation is complete.

    Rule-based — no LLM call. Reads intent from the philosopher's
    direction tag and advances the round counter.
    """
    turn_count = state.get("turn_count", 0)
    total_rounds = state.get("total_rounds", 3)
    current_round = state.get("current_round", 1)
    p1_id = state["philosopher_1_id"]
    p2_id = state["philosopher_2_id"]
    last_speaker = state.get("last_speaker_id", p1_id)

    # Each round = 2 turns (one per philosopher)
    max_turns = total_rounds * 2
    if turn_count >= max_turns:
        return {"is_complete": True, "current_round": current_round}

    # Determine next speaker
    # By default, alternate between philosophers
    if last_speaker == p1_id:
        next_id = p2_id
    else:
        next_id = p1_id

    # If the philosopher addressed someone specific, respect that
    addressed = state.get("addressed_to", "")
    if addressed:
        # Try to resolve addressed name to an ID
        for pid in [p1_id, p2_id]:
            pcfg = get_philosopher(pid)
            if pcfg and pcfg.display_name.lower() == addressed.lower():
                next_id = pid
                break

    # Advance round after both philosophers have spoken
    new_round = current_round
    if turn_count > 0 and turn_count % 2 == 0:
        new_round = (turn_count // 2) + 1

    return {
        "next_speaker_id": next_id,
        "current_round": new_round,
        "is_complete": False,
    }


def _should_continue(state: DialogueState) -> str:
    """Conditional edge: continue or end."""
    if state.get("is_complete", False) or state.get("error"):
        return "end"
    return "continue"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_dialogue_graph(checkpointer=None):
    """Build and compile the LangGraph conversation graph.

    If a checkpointer is provided, conversation state is persisted
    automatically after every node.
    """
    workflow = StateGraph(DialogueState)

    # Add nodes
    workflow.add_node("philosopher", philosopher_node)
    workflow.add_node("router", router_node)

    # Edges
    workflow.add_edge(START, "router")       # Router decides first speaker
    workflow.add_edge("philosopher", "router")  # After speaking, route again

    # Conditional edge from router
    workflow.add_conditional_edges(
        "router",
        _should_continue,
        {
            "continue": "philosopher",
            "end": END,
        },
    )

    return workflow.compile(checkpointer=checkpointer)


# ---------------------------------------------------------------------------
# Checkpointer management
# ---------------------------------------------------------------------------

def get_checkpointer(db_path: str = DEFAULT_DB_PATH):
    """Create a SqliteSaver checkpointer for conversation persistence."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    return SqliteSaver(conn=conn)


# ---------------------------------------------------------------------------
# Conversation history browser
# ---------------------------------------------------------------------------

def list_saved_conversations(db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, str]]:
    """List all saved conversation threads from the checkpoint DB.

    Returns a list of dicts with thread_id and metadata.
    """
    if not os.path.exists(db_path):
        return []
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT DISTINCT thread_id FROM checkpoints ORDER BY thread_id"
        )
        threads = [{"thread_id": row[0]} for row in cursor.fetchall()]
        conn.close()
        return threads
    except Exception as e:
        logger.warning(f"Failed to list conversations: {e}")
        return []


# ---------------------------------------------------------------------------
# High-level conversation runner (called from app.py)
# ---------------------------------------------------------------------------

def run_agentic_conversation(
    topic: str,
    philosopher_1: str,
    philosopher_2: str,
    num_rounds: int = 3,
    mode: str = "philosophy",
    db_path: str = DEFAULT_DB_PATH,
    thread_id: Optional[str] = None,
    on_status: Optional[Callable] = None,
    max_tokens_p1: int = 0,
    max_tokens_p2: int = 0,
    personality_notes_p1: str = "",
    personality_notes_p2: str = "",
) -> Tuple[List[Dict[str, Any]], str, bool, str]:
    """Run a self-organizing philosopher conversation.

    Args:
        topic: The user's question/topic.
        philosopher_1: Display name of first philosopher.
        philosopher_2: Display name of second philosopher.
        num_rounds: Number of rounds (each = 2 turns).
        mode: "philosophy" or "bio".
        db_path: Path to SQLite checkpoint DB.
        thread_id: Optional thread ID to resume a conversation.
        on_status: Optional callback for status updates.
        max_tokens_p1: Max tokens override for philosopher 1.
        max_tokens_p2: Max tokens override for philosopher 2.
        personality_notes_p1: User character notes for philosopher 1.
        personality_notes_p2: User character notes for philosopher 2.

    Returns:
        (messages, final_status, success, thread_id)
    """
    # Resolve display names to IDs
    all_ids = get_philosopher_ids()
    name_to_id = {}
    for pid in all_ids:
        pcfg = get_philosopher(pid)
        if pcfg:
            name_to_id[pcfg.display_name] = pid

    p1_id = name_to_id.get(philosopher_1)
    p2_id = name_to_id.get(philosopher_2)

    if not p1_id or not p2_id:
        return [], "Error: Could not resolve philosopher names to IDs.", False, ""

    # Create checkpointer and graph
    checkpointer = get_checkpointer(db_path)
    graph = build_dialogue_graph(checkpointer=checkpointer)

    # Generate or reuse thread ID
    if not thread_id:
        thread_id = str(uuid.uuid4())

    config = {"configurable": {"thread_id": thread_id}}

    # Initial state
    initial_state: DialogueState = {
        "messages": [],
        "memory_turns": [],
        "current_round": 1,
        "total_rounds": num_rounds,
        "philosopher_1_id": p1_id,
        "philosopher_2_id": p2_id,
        "philosopher_1_name": philosopher_1,
        "philosopher_2_name": philosopher_2,
        "last_speaker_id": "",
        "last_response": "",
        "next_speaker_id": p1_id,  # First speaker
        "speaker_intent": "",
        "addressed_to": "",
        "mode": mode.lower(),
        "topic": topic,
        "turn_count": 0,
        "max_tokens_p1": max_tokens_p1,
        "max_tokens_p2": max_tokens_p2,
        "personality_notes_p1": personality_notes_p1,
        "personality_notes_p2": personality_notes_p2,
        "is_complete": False,
        "error": "",
    }

    if on_status:
        on_status(f"Philosophers conferring ({mode} mode)...")

    try:
        # Run the graph to completion
        final_state = graph.invoke(initial_state, config)

        messages = final_state.get("messages", [])
        error = final_state.get("error", "")

        if error:
            return messages, f"Error: {error}", False, thread_id

        # Record positions in long-term memory
        _record_positions(final_state, topic, thread_id)

        status = (
            f"Self-directed conversation ('{mode}' mode) "
            f"completed after {num_rounds} round{'s' if num_rounds != 1 else ''}."
        )
        return messages, status, True, thread_id

    except Exception as e:
        logger.exception("Agentic conversation error.")
        return [], f"Error: {e}", False, thread_id


def _record_positions(state: DialogueState, topic: str, session_id: str) -> None:
    """After a conversation, record each philosopher's final position in long-term memory.

    Only records the last message from each philosopher to avoid redundant entries.
    Stores the full response (up to 500 chars) rather than blindly truncating.
    """
    try:
        # Collect last message per philosopher to avoid duplicates
        last_msg_by_role: Dict[str, str] = {}
        for msg in state.get("messages", []):
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "system" or not content:
                continue
            last_msg_by_role[role] = content

        for role, content in last_msg_by_role.items():
            for pid in get_philosopher_ids():
                pcfg = get_philosopher(pid)
                if pcfg and pcfg.display_name == role:
                    mem = PhilosopherMemory(pid)
                    summary = content[:500].strip()
                    if len(content) > 500:
                        summary += "..."
                    mem.record_position(topic, summary, session_id)
                    break
    except Exception as e:
        logger.warning(f"Failed to record positions: {e}")
