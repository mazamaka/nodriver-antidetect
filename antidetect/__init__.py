"""
nodriver-antidetect - Antidetect browser module for nodriver.

Provides fingerprint spoofing and stealth capabilities for web scraping.
"""

from .browser import AntidetectBrowser
from .config import AntidetectConfig, FingerprintProfile
from .spoofing import (
    apply_fingerprint_spoofing,
    generate_fingerprint,
    get_random_profile,
)

__version__ = "1.0.0"
__all__ = [
    "AntidetectBrowser",
    "AntidetectConfig",
    "FingerprintProfile",
    "apply_fingerprint_spoofing",
    "generate_fingerprint",
    "get_random_profile",
]
