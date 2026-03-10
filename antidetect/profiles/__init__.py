"""Fingerprint profiles management.

Supports loading profiles from JSON files.
All profiles are stored in the profiles/ directory at the project root.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from .loader import (
    get_profile_path,
    list_profiles,
    load_profile_from_dict,
    load_profile_from_json,
    profile_to_dict,
    save_profile_to_json,
)

if TYPE_CHECKING:
    from ..config import FingerprintProfile

# Profiles directory
PROFILES_DIR = Path(__file__).parent.parent.parent / "profiles"


@lru_cache(maxsize=1)
def get_default_profile() -> FingerprintProfile | None:
    """Load default profile from JSON."""
    default_path = PROFILES_DIR / "mazamaka_local.json"
    if default_path.exists():
        return load_profile_from_json(default_path)
    # Fallback - если JSON не найден, вернём None
    return None


# Целевые метрики для тестирования (из реального браузера)
TARGET_METRICS = {
    "like_headless": 31,  # Цель: <= 31%
    "headless": 0,
    "stealth": 0,
}


__all__ = [
    "PROFILES_DIR",
    "TARGET_METRICS",
    # Helpers
    "get_default_profile",
    "get_profile_path",
    "list_profiles",
    "load_profile_from_dict",
    # JSON loader
    "load_profile_from_json",
    "profile_to_dict",
    "save_profile_to_json",
]
