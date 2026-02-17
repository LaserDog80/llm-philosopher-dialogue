# v1 Archive

This directory contains the complete, unmodified source code of
LLM-Philosopher-Dialogue v1 as it existed at the end of the
initial experimental build.

**Do not modify files in this directory.** They are preserved as
a historical record of the original experiment.

All v2 development happens outside this directory.

## Contents (31 files)

- `app.py` — Main Streamlit application (475 lines)
- `direction.py` — Conversation Director (376 lines)
- `llm_loader.py` — LLM config + prompt loading
- `gui.py` — UI sidebar and chat display
- `auth.py` — Password authentication
- `socrates.py` — Socrates chain factory
- `confucius.py` — Confucius chain factory
- `moderator.py` — Moderator chain factory
- `translator.py` — Dialogue translation
- `llm_config.json` — LLM parameters per persona
- `requirements.txt` — Dependencies (unpinned)
- `README.md` — Original readme
- `PLAN.md` — Original analysis and upgrade plan
- `pages/` — Streamlit multi-page app (Direct Chat, Settings)
- `prompts/` — System prompts including Versions/ history
- `DEPRECATED/` — Earlier iterations of the code
- `USEFUL/` — Reference material (rules_of_conversation.json)
- `.devcontainer/` — Dev container configuration
