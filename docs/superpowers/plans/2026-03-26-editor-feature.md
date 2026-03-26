# Editor Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-message "Shorter" / "Longer" editor buttons that rewrite a philosopher's response using an LLM, preserving voice and conversation context.

**Architecture:** After a conversation completes, each philosopher message gets Shorter/Longer buttons rendered via Streamlit. When clicked, an Editor chain (same Qwen model, dedicated system prompt) rewrites just that message given the full conversation context and the philosopher's voice profile. The rewritten message replaces the original in session state and the UI re-renders.

**Tech Stack:** Python, Streamlit, LangChain (ChatOpenAI + ChatPromptTemplate + StrOutputParser), existing `core/config.py` infrastructure.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `core/editor.py` | **Create** | Editor chain factory + rewrite function |
| `prompts/editor_main.txt` | **Create** | System prompt for the editor LLM |
| `llm_config.json` | **Modify** | Add `"editor"` config entry (same model as philosophers) |
| `gui.py` | **Modify** | Add Shorter/Longer buttons to each philosopher message |
| `app.py` | **Modify** | Handle editor button clicks, call rewrite, update session state |
| `tests/test_editor.py` | **Create** | Unit tests for editor module |

---

## Context: Key Existing Patterns

- **Chain creation:** `core/config.py::load_llm_config_for_persona()` loads LLM + prompt by persona name and mode. The editor will use this same function with persona `"editor"` and mode `"main"`.
- **Translator pattern:** `translator.py` is the closest analog — it creates a chain via `load_llm_config_for_persona("translator", mode="main")`, formats input, invokes, returns text. The editor follows the same pattern.
- **Message format:** Messages in `st.session_state.messages` are dicts: `{"role": "Herodotus", "content": "...", "monologue": "...", "intent": "address"}`.
- **Conversation rendering:** `gui.py::display_conversation()` iterates `messages`, calling `_render_message()` for each philosopher turn. It uses raw HTML, not `st.chat_message`. Buttons must be Streamlit widgets rendered alongside the HTML.
- **Model:** Currently `Qwen/Qwen3-235B-A22B-Instruct-2507`. The editor uses the same model (can be changed later via `llm_config.json`).
- **Voice profiles:** Available via `core/registry.py::get_philosopher()` — returns `PhilosopherConfig` with `voice_profile` dict containing `style_keywords`, `personality_summary`, `example_utterances`.
- **Name-to-ID resolution:** `gui.py` has a module-private `_DISPLAY_NAME_TO_KEY` dict. The registry can be iterated via `get_philosopher_ids()` + `get_philosopher(pid).display_name` to resolve display names to IDs. The editor must use this approach (not naive `lower().replace(" ", "")`).

---

### Task 1: Create the Editor System Prompt

**Files:**
- Create: `prompts/editor_main.txt`

- [ ] **Step 1: Write the editor system prompt**

```text
You are an editor. Your job is to rewrite a single philosopher's response to be SHORTER or LONGER, as instructed.

You will receive:
1. The philosopher's name and voice description
2. The full conversation so far (for context)
3. The specific message to rewrite
4. The direction: "shorter" or "longer"

Rules:
- PRESERVE the philosopher's voice, tone, and personality exactly.
- PRESERVE the philosophical content and key points.
- PRESERVE the past tense (all philosophers speak in past tense).
- Do NOT add a direction tag like [NEXT: ...] — those are handled separately.
- Do NOT add any prefix like "Herodotus:" — just output the rewritten text.
- If direction is "shorter": condense to fewer sentences while keeping the core insight. Cut anecdotes, asides, and repetition. Aim for roughly half the original length.
- If direction is "longer": expand with additional detail, anecdotes, or reflection in the philosopher's style. Aim for roughly double the original length, but stay natural — do not pad.
- Output ONLY the rewritten message text. No commentary, no explanation.
```

Write this to `prompts/editor_main.txt`.

- [ ] **Step 2: Commit**

```bash
git add prompts/editor_main.txt
git commit -m "feat(editor): add editor system prompt"
```

---

### Task 2: Add Editor Config to llm_config.json

**Files:**
- Modify: `llm_config.json`

- [ ] **Step 1: Add editor entry to llm_config.json**

Add after the `"translator"` entry:

```json
"editor": {
    "model_name": "Qwen/Qwen3-235B-A22B-Instruct-2507",
    "temperature": 0.6,
    "max_tokens": 1200,
    "top_p": 0.95,
    "request_timeout": 120
}
```

Note: `max_tokens` is 1200 to accommodate "longer" rewrites of already-long messages (e.g. Herodotus at 600 tokens doubled). Temperature 0.6 for faithful rewrites.

- [ ] **Step 2: Commit**

```bash
git add llm_config.json
git commit -m "feat(editor): add editor LLM config"
```

---

### Task 3: Create core/editor.py — Editor Chain and Rewrite Function

**Files:**
- Create: `core/editor.py`
- Test: `tests/test_editor.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_editor.py`:

```python
# tests/test_editor.py — Unit tests for the editor module.

import pytest
from unittest.mock import patch, MagicMock


class TestFormatEditorInput:
    """Tests for format_editor_input()."""

    def test_formats_shorter_request(self):
        from core.editor import format_editor_input

        messages = [
            {"role": "user", "content": "What is love?"},
            {"role": "Herodotus", "content": "A long response about love.", "intent": "address"},
            {"role": "Sima Qian", "content": "A reply about love.", "intent": "challenge"},
        ]
        result = format_editor_input(
            messages=messages,
            message_index=1,
            direction="shorter",
            philosopher_name="Herodotus",
            voice_description="Discursive, anecdotal, wondering, chatty",
        )
        assert "shorter" in result.lower()
        assert "Herodotus" in result
        assert "A long response about love." in result
        assert "What is love?" in result
        assert "Discursive" in result

    def test_formats_longer_request(self):
        from core.editor import format_editor_input

        messages = [
            {"role": "user", "content": "What is virtue?"},
            {"role": "Socrates", "content": "Short reply.", "intent": "address"},
        ]
        result = format_editor_input(
            messages=messages,
            message_index=1,
            direction="longer",
            philosopher_name="Socrates",
            voice_description="Probing, ironic, questioning",
        )
        assert "longer" in result.lower()
        assert "Socrates" in result
        assert "Short reply." in result

    def test_invalid_index_raises(self):
        from core.editor import format_editor_input

        with pytest.raises(ValueError):
            format_editor_input(
                messages=[{"role": "user", "content": "hi"}],
                message_index=5,
                direction="shorter",
                philosopher_name="Socrates",
                voice_description="probing",
            )

    def test_invalid_direction_raises(self):
        from core.editor import format_editor_input

        with pytest.raises(ValueError):
            format_editor_input(
                messages=[
                    {"role": "user", "content": "hi"},
                    {"role": "Socrates", "content": "reply", "intent": "address"},
                ],
                message_index=1,
                direction="sideways",
                philosopher_name="Socrates",
                voice_description="probing",
            )


class TestGetEditorChain:
    """Tests for get_editor_chain()."""

    @patch("core.editor.load_llm_config_for_persona")
    def test_returns_chain_when_config_loads(self, mock_load):
        mock_llm = MagicMock()
        mock_load.return_value = (mock_llm, "You are an editor.")
        from core.editor import get_editor_chain

        chain = get_editor_chain()
        assert chain is not None
        mock_load.assert_called_once_with("editor", mode="main")

    @patch("core.editor.load_llm_config_for_persona")
    def test_returns_none_when_config_fails(self, mock_load):
        mock_load.return_value = (None, None)
        from core.editor import get_editor_chain

        chain = get_editor_chain()
        assert chain is None


class TestBuildVoiceDescription:
    """Tests for build_voice_description()."""

    @patch("core.editor.get_philosopher")
    def test_builds_description_from_voice_profile(self, mock_get):
        mock_cfg = MagicMock()
        mock_cfg.voice_profile = {
            "style_keywords": ["probing", "ironic"],
            "personality_summary": "Charismatic and provocative.",
        }
        mock_get.return_value = mock_cfg
        from core.editor import build_voice_description

        desc = build_voice_description("socrates")
        assert "probing" in desc
        assert "Charismatic" in desc

    @patch("core.editor.get_philosopher")
    def test_returns_fallback_when_no_profile(self, mock_get):
        mock_get.return_value = None
        from core.editor import build_voice_description

        desc = build_voice_description("unknown")
        assert len(desc) > 0  # Returns a fallback string


class TestRewriteMessage:
    """Tests for rewrite_message()."""

    def test_rejects_user_message(self):
        from core.editor import rewrite_message

        messages = [
            {"role": "user", "content": "What is love?"},
            {"role": "Socrates", "content": "A reply.", "intent": "address"},
        ]
        result = rewrite_message(messages, 0, "shorter")
        assert result is None  # Should refuse to rewrite user messages

    @patch("core.editor.get_editor_chain")
    @patch("core.editor._resolve_philosopher_id")
    @patch("core.editor.build_voice_description")
    def test_calls_chain_and_returns_cleaned(self, mock_voice, mock_resolve, mock_chain):
        mock_resolve.return_value = "socrates"
        mock_voice.return_value = "probing, ironic"
        mock_chain_instance = MagicMock()
        mock_chain_instance.invoke.return_value = "A shorter reply."
        mock_chain.return_value = mock_chain_instance
        from core.editor import rewrite_message

        messages = [
            {"role": "user", "content": "What is love?"},
            {"role": "Socrates", "content": "A long reply about love.", "intent": "address"},
        ]
        result = rewrite_message(messages, 1, "shorter")
        assert result == "A shorter reply."
        mock_chain_instance.invoke.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_editor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.editor'`

- [ ] **Step 3: Write the implementation**

Create `core/editor.py`:

```python
# core/editor.py — Per-message editor: rewrite a philosopher's response shorter or longer.

import logging
from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from core.config import load_llm_config_for_persona
from core.registry import get_philosopher, get_philosopher_ids
from core.utils import extract_and_clean

logger = logging.getLogger(__name__)

VALID_DIRECTIONS = {"shorter", "longer"}


def _resolve_philosopher_id(display_name: str) -> str:
    """Resolve a philosopher display name to their registry ID.

    Iterates the registry rather than using naive string manipulation,
    so names like 'Sima Qian' -> 'simaqian' are handled correctly.
    """
    for pid in get_philosopher_ids():
        pcfg = get_philosopher(pid)
        if pcfg and pcfg.display_name.lower() == display_name.lower():
            return pid
    # Fallback: naive lowering (better than nothing)
    return display_name.lower().replace(" ", "")


def get_editor_chain() -> Optional[Any]:
    """Create and return the editor LangChain chain."""
    llm, system_prompt = load_llm_config_for_persona("editor", mode="main")
    if not llm or not system_prompt:
        logger.error("Failed to load editor chain.")
        return None
    try:
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", "{editor_input}"),
        ])
        chain = prompt | llm | StrOutputParser()
        return chain
    except Exception as e:
        logger.error(f"Error creating editor chain: {e}", exc_info=True)
        return None


def build_voice_description(philosopher_id: str) -> str:
    """Build a voice description string from the philosopher's registry entry."""
    pcfg = get_philosopher(philosopher_id)
    if not pcfg or not pcfg.voice_profile:
        return "Speak in the philosopher's natural voice."
    vp = pcfg.voice_profile
    parts = []
    if vp.get("style_keywords"):
        parts.append(f"Style: {', '.join(vp['style_keywords'])}.")
    if vp.get("personality_summary"):
        parts.append(f"Personality: {vp['personality_summary']}")
    return " ".join(parts) if parts else "Speak in the philosopher's natural voice."


def format_editor_input(
    messages: List[Dict[str, Any]],
    message_index: int,
    direction: str,
    philosopher_name: str,
    voice_description: str,
) -> str:
    """Format the input for the editor chain.

    Args:
        messages: Full conversation messages list.
        message_index: Index of the message to rewrite.
        direction: "shorter" or "longer".
        philosopher_name: Display name of the philosopher.
        voice_description: Voice/style description string.

    Returns:
        Formatted input string for the editor chain.

    Raises:
        ValueError: If message_index is out of range or direction is invalid.
    """
    if message_index < 0 or message_index >= len(messages):
        raise ValueError(f"message_index {message_index} out of range (0-{len(messages) - 1})")
    if direction not in VALID_DIRECTIONS:
        raise ValueError(f"direction must be one of {VALID_DIRECTIONS}, got '{direction}'")

    target_msg = messages[message_index]
    target_content = target_msg.get("content", "")

    # Build conversation context (everything before the target message)
    context_lines = []
    for i, msg in enumerate(messages):
        if i >= message_index:
            break
        role = msg.get("role", "system").upper()
        content = msg.get("content", "")
        if role == "USER":
            context_lines.append(f"USER: {content}")
        elif role != "SYSTEM":
            context_lines.append(f"{role}: {content}")
    context = "\n\n".join(context_lines) if context_lines else "(This is the first response.)"

    return (
        f"PHILOSOPHER: {philosopher_name}\n"
        f"VOICE: {voice_description}\n"
        f"DIRECTION: Make this {direction}\n\n"
        f"--- CONVERSATION CONTEXT ---\n{context}\n\n"
        f"--- MESSAGE TO REWRITE ---\n{target_content}"
    )


def rewrite_message(
    messages: List[Dict[str, Any]],
    message_index: int,
    direction: str,
) -> Optional[str]:
    """Rewrite a single message shorter or longer.

    Args:
        messages: Full conversation messages list.
        message_index: Index of the message to rewrite.
        direction: "shorter" or "longer".

    Returns:
        The rewritten message text, or None on failure.
    """
    target_msg = messages[message_index]
    philosopher_name = target_msg.get("role", "")

    # Guard: don't rewrite user or system messages
    if philosopher_name.lower() in ("user", "system"):
        logger.warning(f"Editor refused to rewrite non-philosopher message (role={philosopher_name})")
        return None

    # Resolve philosopher ID for voice lookup via registry
    philosopher_id = _resolve_philosopher_id(philosopher_name)
    voice_desc = build_voice_description(philosopher_id)

    editor_input = format_editor_input(
        messages=messages,
        message_index=message_index,
        direction=direction,
        philosopher_name=philosopher_name,
        voice_description=voice_desc,
    )

    chain = get_editor_chain()
    if chain is None:
        return None

    try:
        logger.info(f"Editor rewriting message {message_index} ({direction}) for {philosopher_name}")
        raw_result = chain.invoke({"editor_input": editor_input})
        cleaned, _ = extract_and_clean(raw_result)
        return cleaned if cleaned else None
    except Exception as e:
        logger.error(f"Editor rewrite failed: {e}", exc_info=True)
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_editor.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/editor.py tests/test_editor.py
git commit -m "feat(editor): add editor chain and rewrite logic"
```

---

### Task 4: Add Editor Buttons to Conversation UI

**Files:**
- Modify: `gui.py` — `display_conversation()` function (lines ~889-976)
- Modify: `app.py` — handle editor button state and rewrite calls

This is the trickiest task because `display_conversation()` renders HTML but buttons must be Streamlit widgets. The approach: render each philosopher message as HTML, then immediately follow it with a Streamlit column layout containing the Shorter/Longer buttons. This interleaves HTML and widgets naturally.

- [ ] **Step 1: Modify `gui.py::display_conversation()` to render edit buttons**

The current code renders philosopher messages as pure HTML via `html_parts.append(_render_message(...))`. We need to flush the HTML buffer before each button pair, render buttons as Streamlit widgets, then continue accumulating HTML.

Change the `for msg in messages:` loop to use `enumerate`: `for msg_idx, msg in enumerate(messages):`. Then replace the `if _is_philosopher:` block (approximately lines 921-933) with:

```python
        if _is_philosopher:
            philosopher_turn_count += 1
            round_num = (philosopher_turn_count - 1) // 2 + 1

            if round_num != current_round:
                current_round = round_num
                html_parts.append(_render_round_separator(round_num))

            intent = msg.get("intent", "")
            html_parts.append(_render_message(role, content, round_num, intent=intent))

            # Flush HTML buffer before rendering Streamlit buttons.
            # Close the container div so each fragment is self-contained.
            if html_parts:
                html_parts.append('</div>')
                st.markdown("".join(html_parts), unsafe_allow_html=True)
                html_parts = ['<div class="phd-container">']

            # Editor buttons (only after conversation is complete, not on translated view)
            if conversation_completed and not _is_translated_view:
                _bcol1, _bcol2, _bcol3 = st.columns([1, 1, 10])
                with _bcol1:
                    if st.button("Shorter", key=f"edit_shorter_{msg_idx}",
                                 type="tertiary"):
                        st.session_state[f"_editor_request"] = {
                            "index": msg_idx, "direction": "shorter"
                        }
                        st.rerun()
                with _bcol2:
                    if st.button("Longer", key=f"edit_longer_{msg_idx}",
                                 type="tertiary"):
                        st.session_state[f"_editor_request"] = {
                            "index": msg_idx, "direction": "longer"
                        }
                        st.rerun()

            continue
```

**Important notes:**
- Each HTML flush is now self-contained (`<div class="phd-container">...</div>`), fixing the unclosed div problem.
- The `_is_translated_view` flag must be passed as a new parameter to `display_conversation()`. Set it from `app.py` based on whether the translated view is active. This hides editor buttons when viewing translations (since edits only affect originals).
- The `for` loop must use `enumerate` (`for msg_idx, msg in enumerate(messages)`) instead of `messages.index(msg)` to avoid incorrect index resolution with duplicate dicts.

- [ ] **Step 2: Commit**

```bash
git add gui.py
git commit -m "feat(editor): add shorter/longer buttons to conversation messages"
```

---

### Task 5: Handle Editor Requests in app.py

**Files:**
- Modify: `app.py` — add editor request handler before the conversation display block

- [ ] **Step 1: Add editor request handling**

Add this block in `app.py` after the `_display_messages` assignment (around line 299) and before `gui.display_conversation(...)`:

```python
# ---------------------------------------------------------------------------
# Handle editor rewrite requests
# ---------------------------------------------------------------------------
_editor_req = st.session_state.pop("_editor_request", None)
if _editor_req and st.session_state.get("conversation_completed"):
    msg_idx = _editor_req["index"]
    direction = _editor_req["direction"]
    messages = st.session_state.messages

    if 0 <= msg_idx < len(messages):
        thinking_placeholder = st.empty()
        thinking_placeholder.markdown(
            gui.render_thinking_indicator(f"Editor rewriting ({direction})..."),
            unsafe_allow_html=True,
        )
        try:
            from core.editor import rewrite_message
            rewritten = rewrite_message(messages, msg_idx, direction)
            if rewritten:
                st.session_state.messages[msg_idx]["content"] = rewritten
                logger.info(f"Editor rewrote message {msg_idx} ({direction})")
            else:
                st.warning("Editor could not rewrite the message.")
        except Exception as e:
            logger.error(f"Editor error: {e}", exc_info=True)
            st.error(f"Editor error: {e}")
        finally:
            thinking_placeholder.empty()

    # Re-derive display messages after edit
    _display_messages = st.session_state.messages
    if (
        st.session_state.get("output_style") == "Translated Text"
        and st.session_state.get("translated_messages")
    ):
        _display_messages = st.session_state.translated_messages
```

- [ ] **Step 2: Commit**

```bash
git add app.py
git commit -m "feat(editor): handle editor rewrite requests in app.py"
```

---

### Task 6: Integration Test and Polish

**Files:**
- All files from tasks 1-5

- [ ] **Step 1: Run the full test suite**

Run: `python3 -m pytest tests/ -x -q --ignore=tests/test_graph.py --ignore=tests/test_memory_awareness.py`
Expected: All tests PASS (117 existing + 9 new editor tests)

- [ ] **Step 2: Manual smoke test**

1. Start the app: `streamlit run app.py`
2. Run a conversation with default settings
3. After completion, verify Shorter/Longer buttons appear under each philosopher message
4. Click "Shorter" on a long Herodotus message — verify it gets rewritten shorter in the same voice
5. Click "Longer" on a short message — verify it expands naturally
6. Verify the rewritten message stays when scrolling / interacting with the page
7. Verify the buttons do NOT appear during an active conversation (only after completion)

- [ ] **Step 3: Commit any polish fixes**

```bash
git add -A
git commit -m "feat(editor): integration polish and fixes"
```

---

## Notes

- **Model choice:** The editor currently uses the same Qwen model as the philosophers. This can be changed to a smaller/faster model later by updating the `"editor"` entry in `llm_config.json`.
- **Verbosity slider:** The existing slider remains as a best-effort hint to the philosopher model. The editor buttons are the reliable fallback when the model doesn't follow length instructions.
- **Future enhancements:** Could add "Change tone" or other editor directions. The `VALID_DIRECTIONS` set in `core/editor.py` and the system prompt would need updating.
