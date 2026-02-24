# Next Steps

Ideas and priorities for the next update, organized by theme.

---

## Under the Hood

### Conversation Memory

Right now, each philosopher only sees what the previous speaker just said. By round three or four, neither philosopher remembers anything from the opening of the conversation. The single highest-impact improvement would be a **sliding-window memory** that feeds each philosopher a condensed view of the last several turns. This alone would make conversations feel dramatically more coherent and less repetitive.

### Typed State Model

The conversation state is currently a plain dictionary with string keys. A typo in a key name silently produces a `None` instead of raising an error, and nothing prevents invalid states. Replacing this with proper Python dataclasses (`Speaker`, `Turn`, `ConversationState`) would catch bugs earlier, make the code easier to navigate, and allow IDE autocomplete to work.

### Single Chain Factory

There are three nearly identical files for building the Socrates, Confucius, and Moderator chains. They differ by a single string. Collapsing them into one factory function would eliminate duplication and make adding new philosophers trivial.

### Decouple Core Logic from the UI

Several core modules import Streamlit at the top level, which means you cannot test the conversation engine or configuration loader without a running Streamlit server. Extracting all non-UI logic into a clean `core/` package with zero Streamlit dependencies would open the door to proper automated testing and alternative interfaces (CLI, API, etc.).

---

## Efficiency

### Token Budget Tuning

The moderator's output is constrained to 200 tokens. While this is an improvement from earlier settings, it can still clip if the summary includes a long quoted sentence. Monitoring actual token usage and adjusting budgets per-persona based on observed output lengths would reduce wasted calls and truncation artifacts.

### Retry and Timeout Strategy

LLM calls currently use a synchronous retry with `time.sleep()`, which blocks the entire Streamlit server thread. Moving to an async retry pattern (or at least a non-blocking delay) would keep the app responsive for other users during transient API failures.

### Caching

Prompt files and configuration are re-read from disk on various calls. Introducing a lightweight caching layer (e.g., `functools.lru_cache` for pure-Python code, reserving `@st.cache_data` only for the UI layer) would reduce redundant I/O without complicating the architecture.

---

## Newer Methods

### Streaming Responses

All LLM calls currently block until the full response arrives. Switching to LangChain's `chain.stream()` would let users see each philosopher's words appear token by token, which is both faster-feeling and more engaging to watch.

### Conversation Persistence

Conversations vanish on page refresh. Adding lightweight persistence -- even just writing completed conversations to a local SQLite database or JSON file -- would let users browse, reload, and compare past dialogues.

### Multi-Provider Support

The app is currently locked to Nebius as its LLM provider. Abstracting the LLM construction behind a provider interface would make it straightforward to swap in OpenAI, Anthropic, Ollama (for fully local models), or LiteLLM as alternatives. This could be configured per-persona in the existing `llm_config.json`.

### Data-Driven Philosopher Registry

Adding a new philosopher currently requires creating new source files and modifying the Director, GUI, and main app. A `philosophers.json` registry would let you define new philosophers entirely through configuration -- just add a JSON entry, a prompt file, and an LLM config block. Zero code changes.

---

## More User Control

### User-as-Moderator Enhancements

The user guidance mode is functional but basic. Possible improvements:

- **Guided suggestions**: Instead of a blank text box, offer the user two or three AI-generated guidance options to choose from (with the option to write their own).
- **Mid-conversation topic shifts**: Let the user inject a new question or redirect the conversation at any point, not just at designated pause points.
- **Speaker selection**: Let the user choose which philosopher speaks next rather than enforcing strict alternation.

### Preserve Original After Translation

When the user translates a conversation to casual language, the original formal dialogue is overwritten and lost. Both versions should be stored separately, with a toggle to switch between them. Both should be available for download.

### Prompt Customization Persistence

Prompt overrides made on the Settings page are lost when the browser tab closes. Saving them to a local file or browser storage would let users build up and reuse their preferred prompt tweaks across sessions.

### Input Validation and Guardrails

There is currently no validation on user input -- empty prompts, extremely long text, or prompt-injection attempts all pass through unchecked. Adding basic length checks, empty-input rejection, and content sanitization would make the app more robust in shared or public deployments.

### Real-Time Progress Indicators

During a multi-round conversation, users see only a generic spinner. Replacing this with turn-by-turn status updates (e.g., "Socrates is thinking... Round 2 of 5") would give users a much clearer sense of progress.

---

## Code Health

### Test Suite

The project has no automated tests. Adding unit tests for configuration loading, chain construction, moderator output parsing, and memory window formatting -- plus integration tests for the conversation engine with a mocked LLM -- would catch regressions early and make refactoring safe.

### Logging Cleanup

`logging.basicConfig()` is called in multiple files, but only the first call takes effect in Python. Centralizing logging configuration to a single entry point and having all other modules use `logging.getLogger(__name__)` would make log output consistent and filterable.

### Dead Code Removal

There are several blocks of dead code (`pass` statements in conditionals, unused imports, deprecated directories containing old versions). Cleaning these out would reduce confusion for anyone reading or contributing to the codebase.

---

## Summary of Priorities

| Priority | Area | Item |
|---|---|---|
| High | Under the Hood | Conversation memory (sliding window) |
| High | Under the Hood | Typed state model (dataclasses) |
| High | Under the Hood | Single chain factory |
| High | Efficiency | Token budget monitoring and tuning |
| Medium | Newer Methods | Streaming responses |
| Medium | Newer Methods | Data-driven philosopher registry |
| Medium | More User Control | Preserve original after translation |
| Medium | More User Control | User guidance enhancements |
| Medium | Code Health | Test suite |
| Lower | Newer Methods | Multi-provider support |
| Lower | Newer Methods | Conversation persistence |
| Lower | More User Control | Prompt customization persistence |
| Lower | Code Health | Logging and dead code cleanup |
