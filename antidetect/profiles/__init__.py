"""Fingerprint profiles management.

Поддержка загрузки профилей из JSON файлов и предопределённых профилей.
"""

from .loader import (
    get_profile_path,
    list_profiles,
    load_profile_from_dict,
    load_profile_from_json,
    profile_to_dict,
    save_profile_to_json,
)
from .mazamaka_local import MAZAMAKA_LOCAL_PROFILE, TARGET_METRICS

__all__ = [
    # JSON loader
    "load_profile_from_json",
    "load_profile_from_dict",
    "save_profile_to_json",
    "profile_to_dict",
    "list_profiles",
    "get_profile_path",
    # Predefined profiles
    "MAZAMAKA_LOCAL_PROFILE",
    "TARGET_METRICS",
]
