#!/usr/bin/env python3
"""Integration test runner — drives 4 conversation scenarios through the same
pipeline that the Streamlit app uses, saves logs to tests/test_logs/.

Usage:
    python tests/run_conversation_tests.py

Requires: venv active with API keys in .env
"""

import datetime
import os
import sys

# Ensure project root is on path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
os.chdir(project_root)

from dotenv import load_dotenv
load_dotenv()

from core.graph import run_agentic_conversation

PROMPT = "What is love?"
OUTPUT_DIR = os.path.join(project_root, "tests", "test_logs")

# ---------------------------------------------------------------------------
# Test scenarios
# ---------------------------------------------------------------------------
TESTS = [
    {
        "name": "1_defaults",
        "description": "Default settings — Herodotus & Sima Qian, default verbosity",
        "philosopher_1": "Herodotus",
        "philosopher_2": "Sima Qian",
        "num_rounds": 3,
        "max_tokens_p1": 600,
        "max_tokens_p2": 350,
        "personality_notes_p1": "",
        "personality_notes_p2": "",
    },
    {
        "name": "2_herodotus_low_sima_high",
        "description": "Herodotus very low verbosity (100), Sima Qian very high (800)",
        "philosopher_1": "Herodotus",
        "philosopher_2": "Sima Qian",
        "num_rounds": 3,
        "max_tokens_p1": 100,
        "max_tokens_p2": 800,
        "personality_notes_p1": "",
        "personality_notes_p2": "",
    },
    {
        "name": "3_herodotus_high_sima_low",
        "description": "Herodotus very high verbosity (800), Sima Qian very low (100)",
        "philosopher_1": "Herodotus",
        "philosopher_2": "Sima Qian",
        "num_rounds": 3,
        "max_tokens_p1": 800,
        "max_tokens_p2": 100,
        "personality_notes_p1": "",
        "personality_notes_p2": "",
    },
    {
        "name": "4_prompt_injection",
        "description": "Herodotus as American rapper, Sima Qian speaks French",
        "philosopher_1": "Herodotus",
        "philosopher_2": "Sima Qian",
        "num_rounds": 3,
        "max_tokens_p1": 600,
        "max_tokens_p2": 350,
        "personality_notes_p1": "Speak like an American rapper. Use slang, rhythm, and rhyme.",
        "personality_notes_p2": "Speak entirely in French.",
    },
]


def write_log(test_config: dict, messages: list, status: str, output_dir: str) -> str:
    """Write a conversation log file matching the Streamlit app format."""
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"test_{test_config['name']}_{ts}.txt"
    filepath = os.path.join(output_dir, filename)

    lines = [
        f"Conversation Log — {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Test: {test_config['name']}",
        f"Description: {test_config['description']}",
        f"Prompt: {PROMPT}",
        f"Philosophers: {test_config['philosopher_1']} vs {test_config['philosopher_2']}",
        f"Rounds: {test_config['num_rounds']}",
        f"Max Tokens P1: {test_config['max_tokens_p1']}",
        f"Max Tokens P2: {test_config['max_tokens_p2']}",
        f"Personality Notes P1: {test_config['personality_notes_p1'] or '(none)'}",
        f"Personality Notes P2: {test_config['personality_notes_p2'] or '(none)'}",
        f"Status: {status}",
        "=" * 60,
        "",
    ]

    for msg in messages:
        role = msg.get("role", "system").upper()
        content = msg.get("content", "")
        word_count = len(content.split())
        if role == "USER":
            lines.append(f"USER PROMPT: {content}")
        else:
            lines.append(f"{role} ({word_count} words): {content}")
        lines.append("-" * 40)

    lines.append("\n--- Log End ---")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return filepath


def run_test(test_config: dict, output_dir: str) -> None:
    """Run a single test scenario."""
    name = test_config["name"]
    print(f"\n{'=' * 60}")
    print(f"  TEST: {name}")
    print(f"  {test_config['description']}")
    print(f"{'=' * 60}")

    messages, status, success, thread_id = run_agentic_conversation(
        topic=PROMPT,
        philosopher_1=test_config["philosopher_1"],
        philosopher_2=test_config["philosopher_2"],
        num_rounds=test_config["num_rounds"],
        mode="philosophy",
        max_tokens_p1=test_config["max_tokens_p1"],
        max_tokens_p2=test_config["max_tokens_p2"],
        personality_notes_p1=test_config["personality_notes_p1"],
        personality_notes_p2=test_config["personality_notes_p2"],
    )

    filepath = write_log(test_config, messages, status, output_dir)

    # Print summary
    print(f"  Status: {'OK' if success else 'FAILED'} — {status}")
    print(f"  Messages: {len(messages)}")
    for msg in messages:
        role = msg.get("role", "system")
        content = msg.get("content", "")
        words = len(content.split())
        preview = content[:80].replace("\n", " ")
        print(f"    {role} ({words}w): {preview}...")
    print(f"  Log: {filepath}")


def main():
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(OUTPUT_DIR, ts)
    os.makedirs(output_dir, exist_ok=True)

    print(f"\nConversation Integration Tests")
    print(f"Output: {output_dir}")
    print(f"Prompt: '{PROMPT}'")
    print(f"Tests: {len(TESTS)}")

    for test_config in TESTS:
        try:
            run_test(test_config, output_dir)
        except Exception as e:
            print(f"  EXCEPTION: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'=' * 60}")
    print(f"  ALL TESTS COMPLETE")
    print(f"  Logs in: {output_dir}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
