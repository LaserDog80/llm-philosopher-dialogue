# Agent Handover: Memory Awareness & Codebase Improvement Plan

## Branch

All work MUST be done on branch `claude/enhance-memory-awareness-Z7ZyM`.

---

## Executive Summary

This is a Streamlit-based application where two AI philosopher personas hold a multi-round dialogue on user-provided topics. It uses LangChain with a Nebius-hosted LLM (Qwen3-235B) and has two conversation engines: a legacy `Director` class (`direction.py`) and a newer LangGraph-based agentic engine (`core/graph.py`). The main app (`app.py`) uses the LangGraph engine exclusively.

**The core problem:** Philosophers only see the last 6 turns of conversation history due to a sliding window in `ConversationMemory`, meaning in longer conversations they lose track of the original topic, earlier arguments, and the flow of the discussion. The `max_tokens` setting (250 tokens per response) is also very tight, which compounds context issues. Performance is not a concern — thoroughness is.

---

## Task 1: Investigate and Fix the Core Memory/Context Problem

### 1.1 The Sliding Window Problem (CRITICAL)

**File:** `core/memory.py`
**Lines:** 14, 38-49

`DEFAULT_WINDOW_SIZE = 6` means `get_history_for_chain()` only returns the last 6 turns. In a 5-round conversation (10 philosopher turns + the user prompt = 11 entries), the philosopher on turn 10 can only see turns 5-10. They have **no visibility** of:
- The original user question/topic
- The first 4 turns of the dialogue
- How the conversation evolved from its starting point

**What to investigate:**
1. Trace exactly what each philosopher sees at each turn. In `core/graph.py:philosopher_node()` (lines 106-128), the input is built from `memory.get_history_for_chain()` (sliding window) plus `state["last_response"]` (just the previous turn's text). The original `state["topic"]` is ONLY used on `turn_count == 0` (line 109-110). After the first turn, the topic is never referenced again.

2. In `direction.py:run_conversation_streamlit()` (lines 286-287), the same pattern occurs: `memory.get_history_for_chain()` provides limited history, and `input_for_next_speaker` is just the previous response (or response + moderator context).

**Recommended fixes (investigate each, implement what makes sense):**

a) **Always include the original topic in every prompt.** In `philosopher_node()`, the `input_content` on subsequent turns (line 113) should prepend the topic:
   ```python
   # Instead of just: input_content = last_response
   # Do: input_content = f"Original topic: {state['topic']}\n\n{last_response}"
   ```

b) **Add a conversation summary mechanism.** Rather than (or in addition to) expanding the window, generate a running summary of the full conversation. This could be:
   - A simple concatenation of all speaker positions so far (not the full text, just key points)
   - A periodic summarization step (e.g., every 4 turns, summarize what's happened)
   - A structured "conversation state" that tracks: topic, key positions taken by each philosopher, unresolved questions

c) **Expand or remove the window size for the chain history.** The window of 6 is very conservative. Since the user says performance/time is not a concern, consider:
   - Increasing `DEFAULT_WINDOW_SIZE` to cover the full conversation (e.g., set it to `total_rounds * 2 + 1`)
   - Or making it configurable per conversation based on `num_rounds`
   - The Qwen3-235B model has a large context window, so this shouldn't be a problem

d) **Inject the full conversation context, not just the sliding window.** Modify `get_history_for_chain()` to return ALL turns, or create a new method like `get_full_history_for_chain()` that doesn't apply windowing.

e) **Fix `philosopher_node` to always carry context forward.** Currently on subsequent turns (line 112-113), only `last_response` is passed as input. The philosopher gets no structured recap of what happened before.

### 1.2 The Moderator Context Gap

**File:** `core/memory.py` line 25, `core/graph.py`

The `ConversationMemory` docstring says "Moderator and system turns are never stored." This means the moderator's summaries and guidance — which contain valuable context about the conversation's direction — are completely invisible to the memory system.

In the LangGraph engine (`core/graph.py`), there IS no moderator at all (routing is rule-based, line 5-6). This means the only context between turns is the sliding window of raw philosopher dialogue plus the `last_response`.

**What to investigate:** Should moderator summaries (from the Director path) or some equivalent structured context be incorporated into what philosophers see? In the LangGraph path, should the router node generate a brief context summary?

### 1.3 Long-Term Memory Is Never Queried Effectively

**File:** `core/graph.py` lines 116-124

`PhilosopherMemory` is queried for the topic, but:
- It uses `LIKE '%topic%'` matching (line 147-148 of `core/memory.py`), which is crude
- Position summaries are truncated to 200 characters (line 414 of `core/graph.py`) — very lossy
- The context is prepended to `input_content` but there's no instruction to the philosopher about what to do with it
- The philosopher's system prompt has NO mention of long-term memory or how to use recalled positions

**What to fix:** At minimum, if long-term memory context is injected, the system prompts should tell the philosopher how to use it. Better: improve the summary quality and matching.

### 1.4 Token Limit Constraints

**File:** `llm_config.json`

All philosophers have `max_tokens: 250`. The prompts ask for 1-3 sentences, which fits. But if you expand context (more history, summaries, etc.), you may want to increase `max_tokens` slightly to give the model room to process the additional context and still produce quality output. Investigate whether 250 is sufficient after expanding context. Consider increasing to 350-400.

Also note: `request_timeout: 90` seconds — with more context, responses may take longer. Ensure this is sufficient.

---

## Task 2: Identify and Fix Other Inefficiencies and Problems

### 2.1 Duplicate Code: `_robust_invoke` Exists in Two Places

**Files:** `direction.py` lines 23-49, `core/graph.py` lines 62-86

These are nearly identical functions. The one in `direction.py` is a method; the one in `graph.py` is a standalone function. They should be consolidated into a shared utility (e.g., in `core/utils.py` or a new `core/invoke.py`).

### 2.2 Chain Recreation on Every Turn (LangGraph path)

**File:** `core/graph.py` line 101

In `philosopher_node()`, `create_chain(next_id, mode=mode)` is called on **every single turn**. This means every philosopher turn:
1. Reads the prompt file from disk
2. Calls `load_dotenv()`
3. Instantiates a new `ChatOpenAI` object
4. Builds a new `ChatPromptTemplate`

This is wasteful. While `load_default_prompt_text` and `load_llm_params` are `@lru_cache`'d (in `core/config.py`), the `ChatOpenAI` instantiation and `load_llm_config_for_persona` are NOT cached (it calls `load_dotenv()` every time — line 79 of `core/config.py`).

**Fix:** Cache chains at the conversation level. Options:
- Store chain objects in the graph state (though they're not serializable for checkpointing)
- Use a module-level cache keyed by `(persona_id, mode)`
- At minimum, `load_dotenv()` should be called once at startup, not on every persona config load

### 2.3 The `direction.py` Director Is Likely Dead Code

**File:** `direction.py`

The main `app.py` exclusively uses `run_agentic_conversation` from `core/graph.py`. The `Director` class in `direction.py` is only used if someone manually invokes it. However, it's still imported in the codebase structure and may confuse maintainers.

**What to do:** Verify that `direction.py` is not imported anywhere in the active code paths. If it's truly dead code, consider marking it as deprecated or moving it to `v1_archive/`. Do NOT delete it without confirming with the user.

### 2.4 Translator Only Handles Socrates and Confucius

**File:** `translator.py` lines 43-48

```python
if role not in ["USER", "SOCRATES", "CONFUCIUS"]:
    continue
```

This hard-codes only two philosophers. The application now supports 6 philosophers (Socrates, Confucius, Aristotle, Nietzsche, Herodotus, Sima Qian). The translator will silently skip dialogue from Aristotle, Nietzsche, Herodotus, and Sima Qian.

**Fix:** Use the philosopher registry to determine which roles to include:
```python
from core.registry import get_display_names
valid_roles = {"USER"} | {name.upper() for name in get_display_names()}
if role not in valid_roles:
    continue
```

### 2.5 Settings Page Only Lists 3 Personas

**File:** `pages/2_⚙️_Settings.py` line 64

```python
PERSONAS = ["Socrates", "Confucius", "Moderator"]
```

This should use the registry:
```python
from core.registry import get_display_names
PERSONAS = get_display_names() + ["Moderator"]
```

The Direct Chat page (`pages/1_🤖_Direct_Chat.py` line 54) already does this correctly.

### 2.6 `lru_cache` on Mutable Config Won't Invalidate

**File:** `core/config.py` lines 25-26, 48-49

`load_default_prompt_text` and `load_llm_params` use `@lru_cache`. This means:
- If the user edits a prompt file or `llm_config.json` while the app is running, changes won't be picked up
- The cache persists for the lifetime of the process

This may be intentional for performance, but it's worth noting. For a Streamlit app that reruns frequently, it's probably fine. But if prompt hot-reloading is desired, the cache would need to be cleared.

### 2.7 The `conversation_completed` Logic Has a Bug

**File:** `app.py` line 185

```python
st.session_state.conversation_completed = True if success else True
```

This always sets `conversation_completed = True` regardless of success. It should be:
```python
st.session_state.conversation_completed = True
```
Or if the intent was to differentiate:
```python
st.session_state.conversation_completed = success
```

This is a logic bug — investigate the intent and fix.

### 2.8 SQLite Connection Leak in `PhilosopherMemory`

**File:** `core/memory.py` lines 101-103, 127-158

`PhilosopherMemory._get_conn()` creates a new `sqlite3.connect()` on every call, and the callers (`record_position`, `recall_positions`, `get_all_topics`) manually close the connection. If an exception occurs between `connect()` and `close()`, the connection leaks. Use context managers:

```python
with self._get_conn() as conn:
    conn.execute(...)
```

Or better, use a single connection per instance.

### 2.9 No Error Handling for Missing Prompt Files in LangGraph Path

**File:** `core/config.py` lines 92-95

When a prompt file is not found, the system falls back to `DEFAULT_FALLBACK_PROMPT = "You are a helpful AI assistant."` This is a generic prompt that would completely break the philosopher persona. This should at least log a WARNING-level message (it logs ERROR, which is good) but should also potentially prevent the conversation from starting rather than silently degrading.

### 2.10 `PhilosopherMemory` Position Recording Is Too Lossy

**File:** `core/graph.py` lines 400-420, `_record_positions()`

Every message from every philosopher gets stored as a "position" — but the summary is just the first 200 characters of their response. This means:
- A philosopher who says "Well, that's an interesting point. Let me think about what you've said regarding..." would have their position recorded as that preamble, not their actual philosophical position
- There's no deduplication — the same topic discussed multiple times creates redundant entries

**Consider:** Either improving the summarization (perhaps using the LLM to extract a one-line position) or at minimum, not truncating blindly at 200 characters.

---

## Task 3: Verification and Testing

After making changes, you MUST verify your work:

### 3.1 Run Existing Tests

```bash
cd /home/user/llm-philosopher-dialogue
python -m pytest tests/ -v
```

All existing tests must pass. Key test files:
- `tests/test_memory.py` — Tests for ConversationMemory (you'll likely need to update these if you change the memory system)
- `tests/test_graph.py` — Tests for the LangGraph engine (update if you change philosopher_node)
- `tests/test_utils.py` — Tests for utility functions
- `tests/test_config.py` — Tests for config loading
- `tests/test_validation.py` — Input validation tests

### 3.2 Write New Tests for Your Changes

For any new functionality (e.g., expanded memory, topic injection, conversation summaries), write corresponding tests in the `tests/` directory. Follow the existing test patterns:
- Use `pytest` with classes grouping related tests
- Mock LLM calls using `unittest.mock.patch`
- Use the `conftest.py` fixtures (especially `mock_env_vars`)

Specifically, you should test:
- That the original topic is always visible to philosophers on every turn
- That expanded memory correctly provides full conversation history
- That any new summary mechanism produces sensible output
- That the translator handles all 6 philosophers
- That the Settings page lists all philosophers

### 3.3 Manual Verification Checks

After code changes, verify:
1. **Import chains work:** `python -c "from core.memory import ConversationMemory; print('OK')"` (and similar for changed modules)
2. **No circular imports:** `python -c "import app"` should not error (may fail without Streamlit context, so verify via `python -c "from core.graph import run_agentic_conversation; print('OK')"`)
3. **Prompt files still load:** Verify that prompt loading works for all 6 philosophers + moderator in both modes

### 3.4 Commit and Push

After all tests pass and verifications complete:
```bash
git add <changed files>
git commit -m "Descriptive message about your changes"
git push -u origin claude/enhance-memory-awareness-Z7ZyM
```

---

## File Reference

| File | Purpose | Relevance |
|------|---------|-----------|
| `core/memory.py` | Sliding-window memory + PhilosopherMemory (SQLite) | **PRIMARY TARGET** — the memory system |
| `core/graph.py` | LangGraph conversation engine | **PRIMARY TARGET** — how context is passed between turns |
| `core/persona.py` | Chain factory (creates LangChain chains) | May need modification for context injection |
| `core/config.py` | LLM config loading, prompt loading | Review for caching issues |
| `core/utils.py` | Think-block extraction, direction tag parsing | May need new utilities |
| `core/registry.py` | Philosopher registry from JSON | Reference for dynamic philosopher lookup |
| `core/validation.py` | Input validation | No changes expected |
| `core/models.py` | Typed state models | May need updates for new state fields |
| `direction.py` | Legacy Director class | Check if dead code; DO NOT delete without asking |
| `app.py` | Main Streamlit app (uses LangGraph engine) | Fix `conversation_completed` bug |
| `gui.py` | UI rendering (HTML/CSS) | No changes expected |
| `translator.py` | Conversation translation | Fix hard-coded philosopher list |
| `llm_loader.py` | Backward-compatible config wrapper | No changes expected |
| `llm_config.json` | LLM parameters (model, tokens, temp) | May need `max_tokens` adjustment |
| `philosophers.json` | Philosopher display config | Reference only |
| `pages/2_⚙️_Settings.py` | Prompt settings page | Fix hard-coded persona list |
| `prompts/*.txt` | System prompts for each philosopher | May need updates to reference memory context |
| `tests/` | Test suite | Must update and extend |

---

## Priority Order

1. **Fix the core memory/context issue** (Task 1.1) — this is the main ask
2. **Always inject the original topic** (Task 1.1a) — quick win, high impact
3. **Fix the `conversation_completed` bug** (Task 2.7) — trivial but real bug
4. **Fix the translator philosopher list** (Task 2.4) — easy fix, user-facing bug
5. **Fix the Settings page persona list** (Task 2.5) — easy fix, user-facing bug
6. **Address chain recreation inefficiency** (Task 2.2) — performance improvement
7. **Fix SQLite connection handling** (Task 2.8) — robustness improvement
8. **Consolidate duplicate `_robust_invoke`** (Task 2.1) — code quality
9. **Improve long-term memory integration** (Task 1.3) — enhances conversation quality
10. **Everything else** — based on your judgment

---

## Important Notes

- This is NOT a real-time application. The user explicitly stated they don't care about latency. Prioritize thoroughness and conversation quality over speed.
- The LLM is Qwen3-235B hosted on Nebius. It has a large context window. Don't be afraid to send more context.
- The app has two conversation engines. The active one is `core/graph.py` (LangGraph). The `direction.py` Director is legacy. Focus your memory fixes on the LangGraph path, but also fix the Director if you have time since it's still in the codebase.
- DO NOT delete files or remove features without checking with the user first.
- Run ALL tests after making changes. Write new tests for new functionality.
- Commit and push to `claude/enhance-memory-awareness-Z7ZyM` when done.
