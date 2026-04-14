# STORY MODE — Kickoff Document

**Purpose:** A self-contained brief so a fresh Claude session can execute this work without reading prior chat history. Read this end-to-end before starting Phase 1. Verify file paths with `ls` / `Read` before editing anything — a week-old file layout reference may be stale.

---

## 1. Goal

Replace the deprecated **BIO mode** with a new **STORY mode** for Herodotus. In STORY mode, Herodotus tells stories from his *Histories* when they fit the conversation, retold in his own voice. To avoid shoving the full 278k-word text into every prompt, stories are pre-extracted into a curated library and retrieved per-turn by a small "librarian" LLM call.

The voice Herodotus speaks in must not regress. Recent work tightened his cadence (parataxis, named sources, modernised-not-archaic English); STORY mode must carry that forward.

---

## 2. Current state (already done — don't redo)

- Voice rules added to `prompts/herodotus_bio.txt` and `prompts/herodotus_philosophy.txt`. Both include structural directives + one modernised Herodotus voice sample (Book 2 §46 in bio, Book 1 §1 in philosophy).
- The post-hoc colloquialiser already exists: `translator.py` + `prompts/translator_main.txt`. **Do not rebuild it.** It is the answer to "modernise the register" — a separate axis from STORY mode.
- Source text staged at: `/Users/colinbyrne/Documents/WORKSPACE/LITTLE SHADOW/Great Historians/07_References/herodotus_english.txt` (Macaulay translation, ~278k words, 9 books).

---

## 3. Client context (why this exists)

- **Sarah** has repeatedly flagged that philosopher characters "sound too formal / like philosophers." She has been pasting outputs into ChatGPT to colloquialise them.
- Root cause: two separable problems. (a) *Cadence* — voice structure doesn't match the historical figure. (b) *Register* — the English itself feels formal. These need different fixes.
- Architecture decision (locked): cadence = prompt edit (the voice work already done); register = post-hoc translator pass (already exists). **No "chattiness" slider.** The two axes must not be conflated.
- **Anna** sent a sample retelling of the Polycrates/ring story as a reference. It is **not** in Herodotus's voice — it's a modern cinematic retelling (present tense, no source-naming, no hedging). It was written before we analysed the source. **Do not model voice on Anna's sample.** Model voice on the rules in §5 below.

---

## 4. Architecture

Per BIO-mode → STORY-mode turn:

1. **Librarian pass.** A small LLM call reads the recent conversation plus a compact story index (id + title + themes + summary, ~1.5k tokens total) and returns 0–3 story IDs.
2. **Injection.** The full `passage` (verbatim source text) for the selected stories is injected into Herodotus's system prompt as grounding material.
3. **Generation.** Herodotus generates his response. If a story fits, he retells it in his voice, grounded on the injected passage. If none fits, he speaks normally.

Why this architecture and not alternatives:

- **Not full-text RAG / embeddings.** Overkill for ~50–80 discrete stories. Risk of retrieving fragments rather than whole stories. Extra infra for one feature.
- **Not tag-matching alone.** Too crude for thematic resonance — "hubris" matches half the Histories.
- **Not single-pass with just titles.** Without the full passage injected, the model hallucinates a fake version of its own source.

---

## 5. Voice rules — CARRY FORWARD INTO STORY MODE (non-negotiable)

These are already in `herodotus_bio.txt` / `herodotus_philosophy.txt`. They derive from a structural analysis of the Histories and are load-bearing. Copy the block verbatim into the new STORY prompt.

### Structural rules
- Chain events with "and" and "so" — parataxis, not subordination. Not "because X, Y happened" — rather "X happened, and so Y."
- Name sources like a gossip comparing notes: "the priests at Memphis told me", "the Scythians say", "the Corinthians disagree — they say…" Do not hedge abstractly.
- Signpost digressions ("but I should mention…", "as for that…") and return with a time-bridge ("meanwhile…", "now, back to…"). Do not apologise for tangents.
- Vary sentence length sharply. A long winding sentence that gathers detail upon detail — then a short one.
- Report strange or absurd things matter-of-factly. Hedge on disputed claims. **Doubt the marvellous; state the political flatly.**
- No sustained philosophical passages. Brief gnomic asides only, dropped into narrative. He is a storyteller who sometimes reflects, not a philosopher.
- **Modern English.** The voice lives in structure, not archaic vocabulary. No "thou", "thee", "forthwith". Contractions fine.

### Why these rules
- His actual writing is heavy in parataxis and epistemic hedging ("they say", "I was told"). ~445 first-person epistemic markers across the text.
- The Solon-on-happiness speech (Book 1 §32) is the ONE outlier passage where he sounds philosophical. LLM training weights it too heavily. Counteract explicitly.
- Macaulay's English is 19thC archaic; the client does NOT want more of that.

### Voice sample (Book 1 §1, modernised — good for STORY mode)
> "The Persians who know their history say the Phoenicians began the quarrel. These, they say, came from the Red Sea to ours, settled where they still live, and set themselves at once to long voyages. They were carrying Egyptian and Assyrian goods when they put in at Argos — then the chief city of what is now Hellas. On the fifth or sixth day, when their cargo was nearly sold, a company of women came down to the shore, and among them the king's daughter — her name, as the Hellenes also agree, was Io. The Phoenicians rushed at them; most escaped, but Io and a few others were carried off, and they sailed away to Egypt. That is what the Persians say. The Hellenes do not agree."

---

## 6. Per-turn mandatory conventions (ALL philosopher responses, including STORY mode)

These are codebase-wide rules. STORY mode must not break either.

1. **Past tense.** All philosopher speech is framed as looking back. "I thought", "my challenge was", "I recorded", "the Phoenicians rushed at them." The current `_bio.txt` and `_philosophy.txt` enforce this with a "CRITICAL INSTRUCTION" block — STORY prompt must include the same.
2. **Direction tag.** Every response ends with a tag on a new line:
   ```
   [NEXT: <other philosopher name> | INTENT: <address|challenge|yield|reflect>]
   ```
   Intent meanings: address = direct point/question; challenge = push back; yield = make point, let other continue; reflect = closing thought.
   Handled in `direction.py` — check how it's parsed before touching the format.

---

## 7. Source text & extraction mechanics

**Path:** `/Users/colinbyrne/Documents/WORKSPACE/LITTLE SHADOW/Great Historians/07_References/herodotus_english.txt`

**Size:** ~278,000 words, 1,956 lines, 9 books. **`Read` tool rejects full-file reads (exceeds 10k-token limit).** Must chunk.

**Book line offsets (confirmed):**
- Book 1 (Clio) @ line 1
- Book 2 (Euterpe) @ line 285
- Book 3 (Thaleia) @ line 513
- Book 4 (Melpomene) @ line 698
- Book 5 (Terpsichore) @ line 945
- Book 6 (Erato) @ line 1115
- Book 7 (Polymnia) @ line 1294
- Book 8 (Urania) @ line 1634
- Book 9 (Calliope) @ line 1813
- End of file @ line 1956

**Section numbering:** paragraphs inside each book are numbered (e.g. "§40"). Preserve these in the `source` field for citation.

**Extraction approach:** spawn Explore-type subagents per book (or book-pair for thinner books), each returning a JSON fragment of story cards. Merge, deduplicate, quality-check. One pass per agent — don't try to do the whole text in one agent.

---

## 8. Execution plan

### Phase 1 — Extraction pass (Claude)
- Confirm the controlled theme vocabulary before starting: *hubris, fortune, gods, oracles, omens, kings, tyranny, exile, foreign customs, war, strategy, trickery, courage, madness, vengeance, loyalty, marriage, burial, origins, marvels*.
- Spawn subagents per book. Each returns JSON story cards.
- Merge into `data/herodotus_stories.json`.
- Schema per card:
  ```json
  {
    "id": "polycrates-ring",
    "title": "Polycrates and the ring",
    "source": "Book 3 §40-43",
    "characters": ["Polycrates", "Amasis"],
    "themes": ["hubris", "fortune", "gods", "omens"],
    "summary": "Polycrates's luck was too great; Amasis warned him to discard what he loved most. He threw a ring into the sea; it returned in a fish's belly — the gods had refused his sacrifice.",
    "passage": "<verbatim Macaulay text, typically 200-800 words>"
  }
  ```
- Target: 50–80 stories. Err toward *tellable* — skip tribute lists, pure geography, catalogue passages.
- Deliverable for Colin: the JSON + a one-page index (titles grouped by theme) for redline.

### Phase 2 — Library review (Colin)
- Colin reviews the index, spot-checks cards.
- Flags: remove, reassign theme, missing expected stories, passages too long/short.
- Claude applies notes.

### Phase 3 — Librarian module (Claude) — may run in parallel with Phase 2
- New file: `core/librarian.py`.
- Function: `select_stories(conversation_history: list[dict], k: int = 3) -> list[str]` returning 0–k story IDs.
- Uses existing persona-loading pattern: `load_llm_config_for_persona("librarian", mode="main")`.
- Register `librarian` in `llm_config.json` (model: **Llama 3.3 70B Instruct** — same as moderator/translator; this is pattern-matching, not creative writing).
- New prompt: `prompts/librarian_main.txt` — instruct the model to read the conversation, select up to `k` stories whose themes/characters resonate, or return empty if none fit.
- Index passed to the librarian: built from the library, containing ONLY id + title + themes + summary (never the passage). Rebuild at startup or lazy-load.

### Phase 4 — STORY mode prompt (Claude)
- New file: `prompts/herodotus_story.txt`.
- Carry over verbatim from `herodotus_bio.txt`: the CRITICAL past-tense instruction, the full structural voice rules block, the voice sample, the direction tag block at the end.
- **Replace** the old biographical "Your life, in brief" paragraph with a new purpose statement:

  > "You are telling stories from your work, the Histories, to another historical thinker. You have been brought back to this moment in time to share what you witnessed, heard, and recorded. When a story from your work fits the current conversation, tell it in your own voice — grounded in what you actually wrote. When no story fits, speak as normal."

- Add an injection section marker (e.g. `{story_passages}`) where the librarian's selected passages land each turn. If no stories selected, this block should render as empty or "(no story pulled this turn)".
- Archive old `herodotus_bio.txt` → `prompts/Versions/` with a dated suffix.

### Phase 5 — Integration (Claude)
- Wire STORY mode through the persona loader. Inspect `core/config.py` and `core/registry.py` to see how existing modes are loaded; the pattern is `load_llm_config_for_persona(persona, mode=...)` reading `prompts/{persona}_{mode}.txt`.
- Before a Herodotus STORY-mode turn: call `librarian.select_stories(...)` → resolve story IDs to full passages → format and inject into the system prompt.
- UI: find the mode selector (likely `gui.py` or `pages/`). Replace "BIO" label with "STORY". Verify Herodotus is the only philosopher offered STORY mode (Sima Qian joins when his source text arrives).
- **Token ceiling:** Herodotus's `default_max_tokens` in `philosophers.json` is 600 and in `llm_config.json` is 600. A full 300–800-word retelling may be clipped. Add a STORY-mode-specific override bumping to ~1000–1200, either in the loader or via a new config key. Do not raise the default across all modes.
- Leave `philosophy` mode untouched.
- Interaction with verbosity system: recent commit `df5e213` was a "verbosity refactor" — check `direction.py` / related for any code path that trims long responses. STORY mode responses must be allowed the extra length when a story is being told.

### Phase 6 — Test (Colin + Claude)
- Start app, run a Herodotus ↔ Sima Qian conversation with Herodotus in STORY mode (Sima Qian on his current mode).
- Verify:
  - Stories emerge in Herodotus's voice — parataxis, source-naming, no "thou"/"thee", sentence length swings.
  - Selected stories are thematically relevant to what's being discussed.
  - When no story fits, Herodotus responds normally — no forced story-shoehorning.
  - Direction tag still appears and parses.
  - Past tense preserved.
  - Transcript display clean (injection block doesn't leak).
- Iterate.

### Phase 7 — Memory update (Claude)
- Update `/Users/colinbyrne/.claude/projects/-Users-colinbyrne-Documents-WORKSPACE-Coding-Projects-Applications-llm-philosopher-dialogue/memory/project_prompt_detail_concern.md`: the biographical-detail concern is now obsolete for Herodotus — STORY mode intentionally does not carry life-detail.
- Add a new memory capturing the librarian architecture for when Sima Qian gets the same treatment.

---

## 9. Gotchas (have bitten me before)

- **278k-word source file cannot be read whole** with the `Read` tool. Chunk by book using line offsets in §7. Never attempt `Read` on the full file.
- **Macaulay is 19thC archaic.** The `passage` fields in the library will contain "thou"/"thee"/"forthwith" etc. This is fine — the library stores *material*, not the final retelling. The STORY prompt explicitly instructs Herodotus to modernise in delivery.
- **Anna's Polycrates sample** (modern cinematic retelling) circulated early. Do not use it as a voice reference. Voice reference is the rules in §5 + the sample passage there.
- **Verbosity refactor** (commit `df5e213`) may trim long responses. STORY mode retellings need headroom — check this doesn't silently clip them.
- **Direction tag is mandatory** and handled in `direction.py`. Any new prompt must preserve the exact tag format: `[NEXT: <name> | INTENT: <intent>]`.
- **Past tense is mandatory.** The CRITICAL instruction block in existing prompts enforces it. STORY prompt must include the same block — even though the stories themselves are naturally past-tense, the framing around them must stay consistent.
- **STORY mode is Herodotus-only for now.** Don't register it for other philosophers. Sima Qian will come later when the Shiji text is supplied.

---

## 10. File-layout pointers

- `prompts/{philosopher}_{mode}.txt` — persona+mode prompts. `mode` is currently `bio` or `philosophy`. STORY adds a new mode value: `story`.
- `prompts/translator_main.txt` — post-hoc colloquialiser. Leave alone.
- `prompts/editor_main.txt` — editor persona (inspect if touching, but shouldn't need to).
- `prompts/Versions/` — archive convention for retired prompts.
- `philosophers.json` — per-philosopher display/voice config. Herodotus entry at lines ~80–98. Contains `voice_profile.default_max_tokens = 600` — STORY mode needs a larger ceiling.
- `llm_config.json` — per-persona model/temperature/token config. Add a `librarian` entry here. Existing persona pattern is the template.
- `core/config.py` → `load_llm_config_for_persona(persona, mode=...)` — persona + mode loader. Used by `translator.py` as precedent.
- `core/registry.py` → `get_display_names()` — referenced by translator; probably the canonical list of philosophers.
- `direction.py` — direction tag parsing.
- `gui.py`, `pages/` — UI; mode selector lives somewhere here.
- `translator.py` — precedent for a post-hoc LLM pass. Librarian follows its shape.
- `data/` — currently contains SQLite DBs (`conversations.db`, `philosopher_memory.db`). Add `herodotus_stories.json` here.

All paths relative to project root: `/Users/colinbyrne/Documents/WORKSPACE/Coding Projects/Applications/llm-philosopher-dialogue/`.

---

## 11. Memory state

Two existing memories will auto-load via `MEMORY.md`:

- `project_voice_work_approach.md` — documents the two-layer (cadence vs register) architecture and the rule "no chattiness slider." Still accurate.
- `project_prompt_detail_concern.md` — 18-day-old concern that biographical specifics were lost in a prompt rewrite. **Will become partially obsolete** once STORY mode ships — Herodotus's STORY prompt intentionally drops biographical life-detail because the mode is about his *work*, not his *life*. Update this memory in Phase 7.

---

## 12. Open decisions (Claude to apply defaults unless Colin overrides)

- **Librarian model:** Llama 3.3 70B Instruct (default — consistent with moderator/translator, cheap, good at pattern-matching). Override if Colin wants a stronger model.
- **Max stories per turn:** `k = 3`, Herodotus picks one or none. Override if retellings are too long / too crowded in testing.
- **STORY-mode max_tokens:** 1200 (default). Override down if responses become bloated.
- **Other philosophers' `_bio.txt` files:** leave as-is (default). Don't archive unless Colin asks.
- **If `direction.py` token-trims STORY output:** add a mode-aware bypass. Document the change.

---

## 13. Kick-off message

To start a fresh session:

> "Read `STORY_MODE_KICKOFF.md` at project root end-to-end before doing anything. Verify file paths with `ls`/`Read`. Then execute Phase 1 — confirm the theme vocabulary, run the extraction pass, and deliver `data/herodotus_stories.json` plus a one-page theme index for my review."
