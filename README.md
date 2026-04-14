# LLM-Philosophers

A Streamlit web app that stages conversations between AI-powered historical thinkers — philosophers, historians, and a composer. You pick two figures and a topic; they discuss it. Or pick Herodotus alone and let him tell a story from the *Histories* drawn from a curated library of his own words.

---

## Table of Contents

1. [What This App Does](#what-this-app-does)
2. [The Cast](#the-cast)
3. [Modes](#modes)
4. [Installation](#installation)
5. [Running the App](#running-the-app)
6. [Using the App](#using-the-app)
7. [Other Pages](#other-pages)
8. [How It Works](#how-it-works-architecture)
9. [Configuration Files](#configuration-files)
10. [Troubleshooting](#troubleshooting)
11. [Quick Reference](#quick-reference)

---

## What This App Does

Each "philosopher" is a Qwen3-235B language model, fronted by:

- A **system prompt** that defines their voice, character, and structural speaking rules (where they trained, who they cite, how they hedge).
- A **voice profile** in `philosophers.json` (style keywords, sample utterances, default verbosity) that the loader appends to every prompt as voice directives.
- An optional **character notes** field where you nudge their style at runtime ("be more gossipy", "lean into brevity").

When two philosophers talk, the conversation runs as a LangGraph state machine: each turn is a fresh prompt to one persona, with the recent history passed as `chat_history`. After both have spoken, that's one *round*. Default is 3 rounds; configurable 1–10.

When **Herodotus speaks alone in Story mode**, a second smaller LLM (the **librarian**) reads your question and picks 0–3 stories from a curated 78-card library of passages from his *Histories*. Those passages are injected verbatim into Herodotus's system prompt, and he retells one in his own modern voice.

After any conversation, you can:

- Toggle **Casual** on any individual message to rewrite it in everyday English.
- Click **Translate All** to do the whole transcript at once.
- Use the **rewrite slider** on a message to ask the editor to redo it at a target length (e.g. 50% of the original).
- Toggle **Show Internal Monologue** to see the model's `<think>` blocks where present.
- **Download Log** to save a plain-text transcript.

---

## The Cast

| Philosopher | Era | Role | Notes |
|---|---|---|---|
| **Socrates** | 5th c. BCE Athens | Philosopher | Probing, ironic, deceptively simple |
| **Confucius** | Spring & Autumn period | Philosopher | Terse, morally demanding, occasionally wry |
| **Aristotle** | 4th c. BCE | Philosopher | Analytical, distinction-drawing, systematic |
| **Nietzsche** | 19th c. Germany | Philosopher | Aphoristic, explosive, psychologically penetrating |
| **Herodotus** | 5th c. BCE Halicarnassus | Historian | Discursive, anecdotal, the source for Story mode |
| **Sima Qian** | 2nd c. BCE Han China | Historian | Grave, measured, restrained intensity |

A **Moderator** persona exists in `philosophers.json` for legacy reasons but is not active in the current UI — turns alternate directly between the two selected philosophers.

The full voice profiles (style keywords, personality summaries, sample utterances) live in `philosophers.json`. The system prompts live in the `prompts/` folder, one per persona/mode.

---

## Modes

### Philosophy mode (default)

Two philosophers exchange turns over N rounds on a topic you supply. Each turn sees the recent history. Best for back-and-forth dialogue, argument, comparison. Available for any pair.

### Story mode (Herodotus only)

A single turn. You give Herodotus a prompt; he tells one story drawn from the *Histories* that fits, in his own voice. The mode option **only appears in the settings popover when Herodotus is one of the selected philosophers**. When you pick Story, the second-philosopher selector and rounds counter disappear — there's only one speaker, one turn.

How a Story turn is built:

1. The librarian LLM (Llama-3.3-70B) sees a compact index of all 78 stories (id + title + themes + 1-line summary) and the recent conversation.
2. It returns 0–3 story IDs that best fit your prompt.
3. The full text passages for those IDs are injected into Herodotus's system prompt via the `{story_passages}` placeholder.
4. Herodotus retells one in his modern voice — preserving names, places, sequence, but rendering the English in his structural rules (parataxis, source-naming, sentence-length swings).

If no story fits, the librarian returns nothing and Herodotus speaks a brief philosophical reflection. The token ceiling for Story mode is floored at **1200 tokens** (≈900 words) to give full retellings room.

---

## Installation

### Prerequisites

- A computer running Windows, macOS, or Linux.
- **Python 3.11 or newer**. Verify with `python --version` (or `python3 --version`).
- A **Nebius AI Studio** account and API key. The app currently uses Nebius as its model provider for both Qwen3-235B (the philosophers/editor) and Llama-3.3-70B (the librarian and translator).
- A **password** of your choosing for the app's login screen.

### 1. Get the code

```
git clone https://github.com/LaserDog80/llm-philosopher-dialogue.git
cd llm-philosopher-dialogue
```

### 2. Create and activate a virtual environment

```
python -m venv .venv
```

- **macOS / Linux:** `source .venv/bin/activate`
- **Windows:** `.venv\Scripts\activate`

You should see `(.venv)` at the start of your prompt.

### 3. Install dependencies

```
pip install -r requirements.txt
```

Installs `langchain`, `langchain-openai`, `langgraph`, `langgraph-checkpoint-sqlite`, `python-dotenv`, and `streamlit`.

### 4. Set credentials

Create a `.env` file in the project root:

```
NEBIUS_API_KEY=your-nebius-key
NEBIUS_API_BASE=https://api.studio.nebius.com/v1
APP_PASSWORD=any-password-you-choose
```

The `.env` file is gitignored. **Do not commit it.**

> **Deploying to Streamlit Community Cloud?** Skip the `.env` and put the same three values into the app's **Settings → Secrets** panel as TOML:
> ```toml
> NEBIUS_API_KEY = "..."
> NEBIUS_API_BASE = "https://api.studio.nebius.com/v1"
> app_password = "..."
> ```
> See `.streamlit/secrets.toml.example` for the format. `app.py` bridges these into `os.environ` automatically at startup.

---

## Running the App

```
streamlit run app.py
```

Streamlit prints `Local URL: http://localhost:8501` and usually opens your browser. Enter your password to log in.

To stop: `Ctrl+C` in the terminal. To deactivate the venv: `deactivate`.

---

## Using the App

### Top action bar

| Button | Behaviour |
|---|---|
| **Settings** | Opens a popover with mode, philosophers, character notes, display options, model info, and per-philosopher config viewer. |
| **Clear & Reset** | Wipes the current conversation and resets state. |
| **Translate All** | (appears after a conversation completes) Rewrites every philosopher message in casual English. |
| **Download Log** | (appears after a conversation completes) Plain-text transcript download. |
| **Logout** | Clears auth and session state, returns to the password screen. |

### Settings popover

- **Mode** — Philosophical or Story (Story only when Herodotus is selected).
- **Philosopher 1 / Philosopher 2** — dropdowns. P1 speaks first. (Hidden in Story mode; the speaker is forced to Herodotus.)
- **Number of Rounds** — 1 to 10. One round = one response from each philosopher. (Hidden in Story mode.)
- **Verbosity** — sliders are present but disabled in the current build; voice length is governed by each persona's `default_max_tokens` in `philosophers.json` and the verbosity hint inside the system prompt.
- **Character Notes** — free-text per philosopher. Injected into the system prompt above the voice directives, so notes carry strong weight ("HIGHEST PRIORITY" in the prompt). Story mode has its own notes field for Herodotus.
- **Show Internal Monologue** — when on, exposes any `<think>...</think>` content the model produced (most personas don't; the option is mainly for debugging).
- **Models** — caption of which model is wired to which role.
- **Config: \<Philosopher\>** — collapsible panel showing the current temperature, max tokens, top-p, penalties, style keywords, personality summary, and any active character notes.

### Starting a conversation

Type a topic into the chat box at the bottom and press Enter. Examples:

- "What is the purpose of education?"
- "How should a ruler treat dissent?"
- (Story mode, Herodotus) "Tell me about a king who tested the limits of fortune."

A "thinking" indicator appears while the model works. Each turn streams in as a card in the philosopher's signature colour.

### Per-message tools (after the conversation completes)

Every philosopher card sprouts a small toolbar:

- **Casual** toggle — flips that single message between its original and a casual-English rewrite. Cached after the first call, so a second click is instant.
- **Rewrite slider** — labelled "Rewrite length (% of original)". Drag to a target percentage; the editor LLM (Qwen3-235B) regenerates the message at that length while preserving voice. The original is stored, so you can reset to 100% to restore.

These tools are non-destructive: the original text is always recoverable.

---

## Other Pages

The sidebar is hidden in the main UI (`showSidebarNavigation = false` in `.streamlit/config.toml`), but two extra pages exist in `pages/` and load if you navigate to them directly via the URL (`?p=...`) or re-enable sidebar nav:

- **Direct Chat** (`pages/1_🤖_Direct_Chat.py`) — one-on-one with a single persona, useful for testing a system prompt in isolation.
- **Settings** (`pages/2_⚙️_Settings.py`) — manage system-prompt overrides per persona/mode for the current session. Edits do **not** persist to disk.

---

## How It Works (Architecture)

```
                        ┌─────────────────────────────────┐
                        │        app.py (Streamlit)       │
                        │  auth → settings → chat → logs  │
                        └──────────────┬──────────────────┘
                                       │
            ┌──────────────────────────┼─────────────────────────┐
            ▼                          ▼                         ▼
    ┌───────────────┐        ┌─────────────────┐        ┌─────────────────┐
    │ Philosophy    │        │   Story mode    │        │   Per-message   │
    │ (LangGraph)   │        │ (single turn)   │        │     tools       │
    │ N rounds,     │        │ librarian →     │        │ translator,     │
    │ alternates    │        │ herodotus       │        │ editor          │
    └───────┬───────┘        └────────┬────────┘        └────────┬────────┘
            │                         │                          │
            └─────────────┬───────────┴──────────────────────────┘
                          ▼
                ┌───────────────────┐
                │ core/persona.py   │
                │ create_chain()    │
                └─────────┬─────────┘
                          ▼
                ┌───────────────────┐
                │ core/config.py    │
                │ load_llm_config   │  reads philosophers.json,
                │ _for_persona()    │  llm_config.json, prompts/
                └─────────┬─────────┘
                          ▼
                  Nebius AI Studio
```

### Key modules

- **`app.py`** — Streamlit entrypoint. Owns session state, the action bar, the input box, and dispatches to either `_run_initial_conversation` (Philosophy) or `_run_story_turn` (Story). Also handles per-message editor and translator requests.
- **`gui.py`** — All rendering: the warm-study CSS, settings popover, message cards, completion banner, thinking indicator, monologue expander, conversation display.
- **`core/graph.py`** — LangGraph state machine for Philosophy mode. Defines the conversation state, the speaker-alternation node, the round counter, and the persistence layer (SQLite via `langgraph-checkpoint-sqlite`).
- **`core/persona.py`** — `create_chain()` is the single factory that builds a runnable for any persona/mode. For Herodotus-in-story it wraps the chain with the librarian pass; otherwise it's a plain `prompt | llm | parser`.
- **`core/config.py`** — Loads LLM params from `llm_config.json`, fetches the system prompt from `prompts/<persona>_<mode>.txt`, applies overrides, appends voice directives from the philosopher's voice profile, and returns a configured `ChatOpenAI` instance pointed at Nebius.
- **`core/librarian.py`** — Story mode's retrieval layer. `select_stories(history, k)` builds a compact index, asks the librarian model to pick story IDs, and `format_passages(ids)` returns the verbatim passage text ready to inject as `{story_passages}`.
- **`core/registry.py`** — Reads `philosophers.json` and exposes `get_philosopher(id)`, `get_display_names()`, etc.
- **`core/editor.py`** — Length-targeted single-message rewriter used by the rewrite slider.
- **`translator.py`** — Casual-English rewriter, used both for the per-message Casual toggle and the Translate All button.
- **`auth.py`** — Password gate. Reads `app_password` from `st.secrets` first, then `APP_PASSWORD` from env.

### State and persistence

- **Session state** is in-memory per browser tab (Streamlit's `st.session_state`). Everything resets on logout or browser refresh.
- **LangGraph checkpoints** (`data/conversations.db`) and **memory** (`data/philosopher_memory.db`) are SQLite files. Useful locally for resuming threads. **On Streamlit Community Cloud the filesystem is ephemeral**, so these reset on every redeploy — fine for demos, not durable storage.
- **Logs** of completed conversations are held in session state and offered as a plain-text download.

### Models in use

Configured in `llm_config.json`. All are served via the OpenAI-compatible Nebius endpoint.

| Role | Model | Why |
|---|---|---|
| Philosophers | `Qwen/Qwen3-235B-A22B-Instruct-2507` | Voice-rich, follows complex character prompts. |
| Editor | same Qwen3-235B | Faithful rewrites at target length. |
| Librarian | `meta-llama/Llama-3.3-70B-Instruct` | Cheap, fast, deterministic for ID selection. |
| Translator | `meta-llama/Llama-3.3-70B-Instruct` | Long-context casual rewrites. |
| Moderator | `meta-llama/Llama-3.3-70B-Instruct` | Vestigial — not active in current UI. |

---

## Configuration Files

| File | Purpose |
|---|---|
| `.env` | Local secrets (`NEBIUS_API_KEY`, `NEBIUS_API_BASE`, `APP_PASSWORD`). Gitignored. |
| `.streamlit/config.toml` | Theme (warm study palette) and server settings. |
| `.streamlit/secrets.toml.example` | Template for Streamlit Cloud secrets. |
| `llm_config.json` | Per-role model parameters: model_name, temperature, max_tokens, top_p, penalties, timeout. |
| `philosophers.json` | Persona registry: display name, colours, voice profile (style keywords, personality summary, default_max_tokens, sample utterances). |
| `prompts/<persona>_<mode>.txt` | System prompt per persona-mode pair (e.g. `herodotus_story.txt`, `socrates_philosophy.txt`). Falls back to `_philosophy.txt` if a mode-specific prompt is absent. |
| `prompts/librarian_main.txt` | Instructions to the librarian on how to pick story IDs. |
| `data/herodotus_stories.json` | The curated 78-card library extracted from Macaulay's translation of the *Histories*. |
| `data/herodotus_stories_index.md` | Human-readable index of the same library. |

To add a new philosopher: add an entry to `philosophers.json`, create `prompts/<id>_philosophy.txt`, and (optionally) tune `llm_config.json["<id>"]`.

---

## Troubleshooting

| Problem | What to Try |
|---|---|
| `python: command not found` | Try `python3` and `pip3`. |
| `Application Security Error: Password configuration is missing` | `.env` is missing or doesn't contain `APP_PASSWORD` (or, on Cloud, secrets aren't set). |
| `NEBIUS_API_KEY and NEBIUS_API_BASE must be set` in logs | Same — credentials not loaded. Check `.env` exists in project root and you started Streamlit from that directory. |
| Story mode option doesn't appear | Story is Herodotus-only. Pick Herodotus as Philosopher 1 or 2 in the settings popover. |
| Herodotus tells a story unrelated to my question | The librarian's choice is heuristic; if no card fits, it returns none and Herodotus speaks normally. The library is finite (78 cards) — broad questions tend to land better than narrow ones. |
| Replies feel cut off in Story mode | Check `STORY_MODE_MAX_TOKENS` in `core/persona.py` (default 1200). Bump if full retellings consistently clip. |
| Casual toggle does nothing | Translator chain failed to load — check the logs for a Nebius API error and verify your key has access to `meta-llama/Llama-3.3-70B-Instruct`. |
| SQLite "database is locked" | Stop all running Streamlit instances. The checkpoint DB doesn't tolerate concurrent processes. |
| On Streamlit Cloud, conversations reset between sessions | Expected — Cloud filesystem is ephemeral. The SQLite checkpoint and memory dbs do not persist across redeploys. |

---

## Quick Reference

| Action | Command |
|---|---|
| Install dependencies | `pip install -r requirements.txt` |
| Start the app | `streamlit run app.py` |
| Open in browser | `http://localhost:8501` |
| Stop the app | `Ctrl+C` in the terminal |
| Activate venv (macOS/Linux) | `source .venv/bin/activate` |
| Activate venv (Windows) | `.venv\Scripts\activate` |
| Deactivate venv | `deactivate` |
| Run tests | `pytest` |
