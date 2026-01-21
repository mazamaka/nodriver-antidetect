"""
nodriver-antidetect - Stealth antidetect browser for nodriver.

Provides undetectable fingerprint spoofing for web automation.
"""

from .browser import AntidetectBrowser
from .config import (
    AntidetectConfig,
    FingerprintProfile,
    get_chrome_version,
    get_profile,
    list_available_profiles,
)
from .profiles import (
    list_profiles,
    load_profile_from_dict,
    load_profile_from_json,
    save_profile_to_json,
)
from .stealth import apply_stealth, apply_stealth_to_page, build_stealth_script

__version__ = "2.3.0"
__all__ = [
    # Browser
    "AntidetectBrowser",
    # Config
    "AntidetectConfig",
    "FingerprintProfile",
    "get_profile",
    "list_available_profiles",
    "get_chrome_version",
    # Profile loaders
    "load_profile_from_json",
    "load_profile_from_dict",
    "save_profile_to_json",
    "list_profiles",
    # Stealth
    "apply_stealth",
    "apply_stealth_to_page",
    "build_stealth_script",
]
