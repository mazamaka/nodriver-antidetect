"""Configuration models for antidetect browser."""

from __future__ import annotations

import re
import subprocess
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from loguru import logger
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

# === Chrome Version Detection ===


@lru_cache(maxsize=1)
def get_chrome_version() -> str:
    """
    Detect installed Chrome version.

    Returns version string like "132.0.6834.83" or default if not found.
    """
    # Default fallback version
    default_version = "132.0.6834.83"

    # Try common Chrome paths
    chrome_paths = [
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]

    for chrome_path in chrome_paths:
        try:
            result = subprocess.run(
                [chrome_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                # Parse version from "Google Chrome 132.0.6834.83" or similar
                match = re.search(r"(\d+\.\d+\.\d+\.\d+)", result.stdout)
                if match:
                    version = match.group(1)
                    logger.debug(f"Detected Chrome version: {version}")
                    return version
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            continue

    logger.debug(f"Chrome not found, using default version: {default_version}")
    return default_version


def get_reduced_chrome_version(full_version: str) -> str:
    """
    Get reduced Chrome version for UA reduction (Chrome 107+).

    Chrome UA reduction: 144.0.7559.59 -> 144.0.0.0
    Only major version is shown, rest are zeros.
    """
    parts = full_version.split(".")
    if len(parts) >= 1:
        return f"{parts[0]}.0.0.0"
    return full_version


def build_user_agent(platform: str, chrome_version: str | None = None) -> str:
    """Build User-Agent string for given platform and Chrome version.

    Note: Chrome 107+ uses UA reduction in the User-Agent string,
    showing only major version (144.0.0.0 instead of 144.0.7559.59).
    But userAgentData (Client Hints) still shows full version.
    """
    full_version = chrome_version or get_chrome_version()

    # UA reduction: use major.0.0.0 in User-Agent string
    reduced_version = get_reduced_chrome_version(full_version)

    # Platform-specific UA templates (with reduced version)
    templates = {
        "Linux x86_64": f"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{reduced_version} Safari/537.36",
        "Win32": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{reduced_version} Safari/537.36",
        "MacIntel": f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{reduced_version} Safari/537.36",
    }

    return templates.get(platform, templates["Linux x86_64"])


def build_app_version(platform: str, chrome_version: str | None = None) -> str:
    """Build appVersion string for given platform (uses reduced version)."""
    full_version = chrome_version or get_chrome_version()
    reduced_version = get_reduced_chrome_version(full_version)

    templates = {
        "Linux x86_64": f"5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{reduced_version} Safari/537.36",
        "Win32": f"5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{reduced_version} Safari/537.36",
        "MacIntel": f"5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{reduced_version} Safari/537.36",
    }

    return templates.get(platform, templates["Linux x86_64"])


# === Timezone Utilities ===


def get_timezone_offset(timezone: str) -> int:
    """
    Get timezone offset in minutes from UTC using zoneinfo.

    Args:
        timezone: IANA timezone name (e.g., "Europe/Budapest")

    Returns:
        Offset in minutes (negative for east of UTC, positive for west)
    """
    try:
        tz = ZoneInfo(timezone)
        now = datetime.now(tz)
        offset_seconds = now.utcoffset().total_seconds()
        # JavaScript getTimezoneOffset() returns positive for west, negative for east
        return -int(offset_seconds / 60)
    except (KeyError, AttributeError):
        logger.warning(f"Unknown timezone: {timezone}, using UTC")
        return 0


# === Pydantic Models ===


class WebGLConfig(BaseModel):
    """WebGL fingerprint configuration."""

    vendor: str = "Google Inc. (NVIDIA Corporation)"
    renderer: str = "ANGLE (NVIDIA Corporation, NVIDIA GeForce RTX 3060/PCIe/SSE2, OpenGL 4.5.0)"
    unmasked_vendor: str = "Google Inc. (NVIDIA Corporation)"
    unmasked_renderer: str = (
        "ANGLE (NVIDIA Corporation, NVIDIA GeForce RTX 3060/PCIe/SSE2, OpenGL 4.5.0)"
    )


class ScreenConfig(BaseModel):
    """Screen configuration."""

    width: int = 1920
    height: int = 1080
    avail_width: int = 1920
    avail_height: int = 1040  # Height minus taskbar
    color_depth: int = 24
    pixel_depth: int = 24
    device_pixel_ratio: float = 1.0


class NavigatorConfig(BaseModel):
    """Navigator properties configuration."""

    platform: str = "Linux x86_64"
    app_version: str = Field(default_factory=lambda: build_app_version("Linux x86_64"))
    user_agent: str = Field(default_factory=lambda: build_user_agent("Linux x86_64"))
    vendor: str = "Google Inc."
    languages: list[str] = Field(default_factory=lambda: ["en-US", "en"])
    hardware_concurrency: int = 8
    device_memory: int = 8
    max_touch_points: int = 0
    do_not_track: str | None = None
    webdriver: bool = False


class MediaDevicesConfig(BaseModel):
    """Media devices configuration for camera/microphone spoofing."""

    has_audio_input: bool = True
    has_audio_output: bool = True
    has_video_input: bool = True
    audio_inputs: int = 1
    audio_outputs: int = 1
    video_inputs: int = 1


class TimezoneConfig(BaseModel):
    """Timezone configuration."""

    timezone: str = "UTC"
    locale: str = "en-US"
    offset: int = 0  # Minutes from UTC (calculated automatically)


class FingerprintProfile(BaseModel):
    """Complete fingerprint profile."""

    name: str = "default"
    webgl: WebGLConfig = Field(default_factory=WebGLConfig)
    screen: ScreenConfig = Field(default_factory=ScreenConfig)
    navigator: NavigatorConfig = Field(default_factory=NavigatorConfig)
    media_devices: MediaDevicesConfig = Field(default_factory=MediaDevicesConfig)
    timezone: TimezoneConfig = Field(default_factory=TimezoneConfig)

    # Canvas noise (small value to randomize canvas fingerprint)
    canvas_noise: float = 0.00001

    # Audio context noise
    audio_noise: float = 0.00001

    # WebRTC settings
    webrtc_enabled: bool = True
    webrtc_local_ips_hidden: bool = True


# === Main Configuration ===


class AntidetectConfig(BaseSettings):
    """Main antidetect configuration from environment variables."""

    # Profile path - load from JSON file (takes priority)
    profile_path: str = Field(default="profiles/mazamaka_local.json", alias="AD_PROFILE_PATH")

    # Timezone
    timezone: str = Field(default="Europe/Budapest", alias="AD_TIMEZONE")
    locale: str = Field(default="ru", alias="AD_LOCALE")

    # Screen
    screen_width: int = Field(default=1920, alias="AD_SCREEN_WIDTH")
    screen_height: int = Field(default=1080, alias="AD_SCREEN_HEIGHT")

    # Hardware
    device_memory: int = Field(default=8, alias="AD_DEVICE_MEMORY")
    hardware_concurrency: int = Field(default=8, alias="AD_HARDWARE_CONCURRENCY")
    platform: str = Field(default="Linux x86_64", alias="AD_PLATFORM")

    # WebGL
    webgl_vendor: str = Field(
        default="Google Inc. (NVIDIA Corporation)",
        alias="AD_WEBGL_VENDOR",
    )
    webgl_renderer: str = Field(
        default="ANGLE (NVIDIA Corporation, NVIDIA GeForce RTX 3060/PCIe/SSE2, OpenGL 4.5.0)",
        alias="AD_WEBGL_RENDERER",
    )

    # User Agent (auto-detected if empty)
    user_agent: str = Field(default="", alias="AD_USER_AGENT")
    languages: str = Field(default="en-US,en", alias="AD_LANGUAGES")

    # Proxy
    proxy_url: str = Field(default="", alias="PROXY_URL")

    # Browser behavior
    headless: bool = Field(default=False, alias="AD_HEADLESS")

    model_config = {"env_prefix": "", "extra": "ignore"}

    def to_profile(self) -> FingerprintProfile:
        """
        Convert config to fingerprint profile.

        Priority:
        1. AD_PROFILE_PATH (JSON file)
        2. Environment variables
        """
        # Try to load from JSON file
        if self.profile_path:
            profile_path = Path(self.profile_path)
            if not profile_path.is_absolute():
                # Try relative to current dir, then to package
                if not profile_path.exists():
                    package_dir = Path(__file__).parent.parent
                    profile_path = package_dir / self.profile_path

            if profile_path.exists():
                from .profiles import load_profile_from_json

                return load_profile_from_json(profile_path)

        # Build from environment variables
        languages = [lang.strip() for lang in self.languages.split(",")]
        offset = get_timezone_offset(self.timezone)

        # Auto-detect Chrome version for UA if not specified
        user_agent = self.user_agent or build_user_agent(self.platform)
        app_version = build_app_version(self.platform)

        return FingerprintProfile(
            name="env_config",
            webgl=WebGLConfig(
                vendor=self.webgl_vendor,
                renderer=self.webgl_renderer,
                unmasked_vendor=self.webgl_vendor,
                unmasked_renderer=self.webgl_renderer,
            ),
            screen=ScreenConfig(
                width=self.screen_width,
                height=self.screen_height,
                avail_width=self.screen_width,
                avail_height=self.screen_height - 40,  # Taskbar
            ),
            navigator=NavigatorConfig(
                platform=self.platform,
                user_agent=user_agent,
                app_version=app_version,
                languages=languages,
                hardware_concurrency=self.hardware_concurrency,
                device_memory=self.device_memory,
            ),
            timezone=TimezoneConfig(
                timezone=self.timezone,
                locale=self.locale,
                offset=offset,
            ),
        )


# === Profile Loading Helpers ===


def get_profile(name: str) -> FingerprintProfile:
    """
    Get profile by name from JSON files in profiles/ directory.

    Args:
        name: Profile name (without .json extension)

    Returns:
        FingerprintProfile loaded from JSON
    """
    from .profiles import PROFILES_DIR, load_profile_from_json

    profile_path = PROFILES_DIR / f"{name}.json"
    if not profile_path.exists():
        available = [p.stem for p in PROFILES_DIR.glob("*.json")]
        raise ValueError(f"Unknown profile: {name}. Available: {available}")

    return load_profile_from_json(profile_path)


def list_available_profiles() -> list[str]:
    """List all available profile names from profiles/ directory."""
    from .profiles import PROFILES_DIR

    if not PROFILES_DIR.exists():
        return []

    return sorted(p.stem for p in PROFILES_DIR.glob("*.json"))
