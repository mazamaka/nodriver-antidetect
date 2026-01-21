"""Fingerprint profiles management.

Поддержка загрузки профилей из JSON файлов.
Все профили хранятся в директории profiles/ в корне проекта.
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

# Директория с профилями
PROFILES_DIR = Path(__file__).parent.parent.parent / "profiles"


@lru_cache(maxsize=1)
def get_default_profile() -> "FingerprintProfile | None":
    """Загрузить профиль по умолчанию из JSON."""
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
    # JSON loader
    "load_profile_from_json",
    "load_profile_from_dict",
    "save_profile_to_json",
    "profile_to_dict",
    "list_profiles",
    "get_profile_path",
    # Helpers
    "get_default_profile",
    "TARGET_METRICS",
    "PROFILES_DIR",
]
