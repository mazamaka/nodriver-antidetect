"""
nodriver-antidetect - Stealth antidetect browser for nodriver.

Provides undetectable fingerprint spoofing for web automation.
"""

from .browser import AntidetectBrowser
from .cdp_handler import CDPOverridesHandler
from .chrome_args import ChromeArgsBuilder
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
from .session import SessionManager, SessionMetadata
from .stealth import apply_stealth, apply_stealth_to_page, build_stealth_script

__version__ = "2.7.0"
__all__ = [
    # Browser
    "AntidetectBrowser",
    # Config
    "AntidetectConfig",
    # Advanced (for custom implementations)
    "CDPOverridesHandler",
    "ChromeArgsBuilder",
    "FingerprintProfile",
    # Sessions
    "SessionManager",
    "SessionMetadata",
    # Stealth
    "apply_stealth",
    "apply_stealth_to_page",
    "build_stealth_script",
    "get_chrome_version",
    "get_profile",
    "list_available_profiles",
    "list_profiles",
    "load_profile_from_dict",
    # Profile loaders
    "load_profile_from_json",
    "save_profile_to_json",
]
