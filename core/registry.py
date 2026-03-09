# core/registry.py — Data-driven philosopher registry.
#
# Reads philosophers.json so that adding a philosopher requires only a JSON
# entry, a prompt file, and an llm_config.json entry — zero code changes.

import json
import os
import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = "philosophers.json"


@dataclass(frozen=True)
class PhilosopherConfig:
    id: str
    display_name: str
    initials: str
    color: str
    bg: str
    text_color: str
    description: str = ""


def _find_config_file(config_path: str) -> Optional[str]:
    """Locate the config file in CWD or relative to this package."""
    for base in [os.getcwd(), os.path.dirname(os.path.dirname(__file__)) or "."]:
        full = os.path.join(base, config_path)
        if os.path.exists(full):
            return full
    return None


@lru_cache(maxsize=4)
def load_registry(config_path: str = DEFAULT_CONFIG_PATH) -> Dict[str, PhilosopherConfig]:
    """Load the philosopher registry from JSON.

    Returns a dict mapping philosopher id -> PhilosopherConfig.
    The moderator is included under the key ``"moderator"``.
    """
    path = _find_config_file(config_path)
    if path is None:
        logger.error(f"Philosopher config not found: {config_path}")
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Error reading philosopher config: {e}")
        return {}

    registry: Dict[str, PhilosopherConfig] = {}
    for entry in data.get("philosophers", []):
        cfg = PhilosopherConfig(**entry)
        registry[cfg.id] = cfg

    mod = data.get("moderator")
    if mod:
        registry["moderator"] = PhilosopherConfig(**mod)

    return registry


def get_philosopher_ids(config_path: str = DEFAULT_CONFIG_PATH) -> List[str]:
    """Return the ordered list of philosopher ids (excludes moderator)."""
    reg = load_registry(config_path)
    return [pid for pid in reg if pid != "moderator"]


def get_philosopher(pid: str, config_path: str = DEFAULT_CONFIG_PATH) -> Optional[PhilosopherConfig]:
    """Look up a single philosopher by id."""
    return load_registry(config_path).get(pid)


def get_display_names(config_path: str = DEFAULT_CONFIG_PATH) -> List[str]:
    """Return display names for all philosophers (excludes moderator)."""
    reg = load_registry(config_path)
    return [reg[pid].display_name for pid in reg if pid != "moderator"]


def get_speaker_styles(config_path: str = DEFAULT_CONFIG_PATH) -> Dict[str, dict]:
    """Build a speaker-styles dict compatible with gui.py's SPEAKER_STYLES.

    Always includes ``user`` and ``system`` entries as fallbacks.
    """
    styles: Dict[str, dict] = {}
    for pid, cfg in load_registry(config_path).items():
        styles[pid] = {
            "color": cfg.color,
            "bg": cfg.bg,
            "text_color": cfg.text_color,
            "initials": cfg.initials,
            "display_name": cfg.display_name,
        }

    # Hardcoded fallbacks for non-philosopher roles
    styles.setdefault("user", {
        "color": "#2ECC71",
        "bg": "#e8faf0",
        "text_color": "#1B8A4A",
        "initials": "U",
        "display_name": "You",
    })
    styles.setdefault("system", {
        "color": "#8B8B8B",
        "bg": "#f5f5f5",
        "text_color": "#555555",
        "initials": "S",
        "display_name": "System",
    })
    return styles
