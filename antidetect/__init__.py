"""
nodriver-antidetect - Antidetect browser module for nodriver.

Provides fingerprint spoofing and stealth capabilities for web scraping.
Supports loading fingerprint profiles from JSON files.
"""

from .browser import AntidetectBrowser
from .config import AntidetectConfig, FingerprintProfile
from .profiles import (
    load_profile_from_json,
    load_profile_from_dict,
    save_profile_to_json,
    list_profiles,
)
from .spoofing import (
    apply_fingerprint_spoofing,
    generate_fingerprint,
    get_random_profile,
)

__version__ = "1.1.0"
__all__ = [
    # Browser
    "AntidetectBrowser",
    "AntidetectConfig",
    "FingerprintProfile",
    # Profile loading
    "load_profile_from_json",
    "load_profile_from_dict",
    "save_profile_to_json",
    "list_profiles",
    # Spoofing
    "apply_fingerprint_spoofing",
    "generate_fingerprint",
    "get_random_profile",
]
