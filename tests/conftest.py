import pytest
import os


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Ensure LLM API keys are set but never hit real endpoints in tests."""
    monkeypatch.setenv("NEBIUS_API_KEY", "test-key-fake")
    monkeypatch.setenv("NEBIUS_API_BASE", "https://fake.api.test/v1")


@pytest.fixture
def sample_messages():
    """Standard conversation message list for testing."""
    return [
        {"role": "user", "content": "What is virtue?", "monologue": None},
        {
            "role": "Socrates",
            "content": "I believed virtue was knowledge.",
            "monologue": "thinking about it",
        },
        {
            "role": "system",
            "content": (
                "MODERATOR CONTEXT (for Confucius):\n"
                "SUMMARY: Socrates equated virtue with knowledge.\n"
                "AI Guidance: Ask for elaboration."
            ),
            "monologue": None,
        },
        {
            "role": "Confucius",
            "content": "I taught that virtue came from ritual and propriety.",
            "monologue": None,
        },
    ]
