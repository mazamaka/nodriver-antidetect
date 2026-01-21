"""Configuration models for antidetect browser."""

from __future__ import annotations

import os
import random
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class WebGLConfig(BaseModel):
    """WebGL fingerprint configuration."""

    vendor: str = "Google Inc. (NVIDIA)"
    renderer: str = "ANGLE (NVIDIA, NVIDIA GeForce GTX 1080/PCIe/SSE2, OpenGL 4.5)"
    unmasked_vendor: str = "Google Inc. (NVIDIA)"
    unmasked_renderer: str = "ANGLE (NVIDIA, NVIDIA GeForce GTX 1080/PCIe/SSE2, OpenGL 4.5)"


class ScreenConfig(BaseModel):
    """Screen configuration."""

    width: int = 1920
    height: int = 1080
    avail_width: int = 1920
    avail_height: int = 1040
    color_depth: int = 24
    pixel_depth: int = 24
    device_pixel_ratio: float = 1.0


class NavigatorConfig(BaseModel):
    """Navigator properties configuration."""

    platform: str = "Linux x86_64"
    app_version: str = "5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    user_agent: str = ""  # Auto-generated if empty
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
    audio_outputs: int = 2
    video_inputs: int = 1


class TimezoneConfig(BaseModel):
    """Timezone configuration."""

    timezone: str = "Europe/Berlin"
    locale: str = "en-US"
    offset: int = -60  # Minutes from UTC


class FingerprintProfile(BaseModel):
    """Complete fingerprint profile."""

    name: str = "default"
    webgl: WebGLConfig = Field(default_factory=WebGLConfig)
    screen: ScreenConfig = Field(default_factory=ScreenConfig)
    navigator: NavigatorConfig = Field(default_factory=NavigatorConfig)
    media_devices: MediaDevicesConfig = Field(default_factory=MediaDevicesConfig)
    timezone: TimezoneConfig = Field(default_factory=TimezoneConfig)

    # Canvas noise
    canvas_noise: float = 0.0001  # Small noise to randomize canvas fingerprint

    # Audio context noise
    audio_noise: float = 0.0001

    # WebRTC
    webrtc_enabled: bool = True
    webrtc_local_ips_hidden: bool = True  # Hide local IPs


class AntidetectConfig(BaseSettings):
    """Main antidetect configuration from environment variables."""

    # Timezone
    timezone: str = Field(default="Europe/Berlin", alias="AD_TIMEZONE")
    locale: str = Field(default="en-US", alias="AD_LOCALE")

    # Screen
    screen_width: int = Field(default=1920, alias="AD_SCREEN_WIDTH")
    screen_height: int = Field(default=1080, alias="AD_SCREEN_HEIGHT")

    # Hardware
    device_memory: int = Field(default=8, alias="AD_DEVICE_MEMORY")
    hardware_concurrency: int = Field(default=8, alias="AD_HARDWARE_CONCURRENCY")
    platform: str = Field(default="Linux x86_64", alias="AD_PLATFORM")

    # WebGL
    webgl_vendor: str = Field(
        default="Google Inc. (NVIDIA)", alias="AD_WEBGL_VENDOR"
    )
    webgl_renderer: str = Field(
        default="ANGLE (NVIDIA, NVIDIA GeForce GTX 1080/PCIe/SSE2, OpenGL 4.5)",
        alias="AD_WEBGL_RENDERER",
    )

    # User Agent
    user_agent: str = Field(default="", alias="AD_USER_AGENT")
    languages: str = Field(default="en-US,en", alias="AD_LANGUAGES")

    # Proxy
    proxy_url: str = Field(default="", alias="PROXY_URL")

    # Browser behavior
    headless: bool = Field(default=False, alias="AD_HEADLESS")

    class Config:
        env_prefix = ""
        extra = "ignore"

    def to_profile(self) -> FingerprintProfile:
        """Convert config to fingerprint profile."""
        languages = [lang.strip() for lang in self.languages.split(",")]

        # Calculate timezone offset based on timezone
        offset = self._get_timezone_offset(self.timezone)

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
                user_agent=self.user_agent,
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

    @staticmethod
    def _get_timezone_offset(timezone: str) -> int:
        """Get timezone offset in minutes from UTC."""
        # Common timezone offsets
        offsets = {
            "UTC": 0,
            "Europe/London": 0,
            "Europe/Berlin": -60,
            "Europe/Paris": -60,
            "Europe/Moscow": -180,
            "Europe/Budapest": -60,
            "America/New_York": 300,
            "America/Los_Angeles": 480,
            "Asia/Tokyo": -540,
            "Asia/Shanghai": -480,
            "Australia/Sydney": -660,
        }
        return offsets.get(timezone, 0)


# Predefined profiles for different scenarios
PROFILES: dict[str, FingerprintProfile] = {
    "windows_chrome": FingerprintProfile(
        name="windows_chrome",
        navigator=NavigatorConfig(
            platform="Win32",
            app_version="5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            hardware_concurrency=8,
            device_memory=8,
        ),
        screen=ScreenConfig(width=1920, height=1080),
        webgl=WebGLConfig(
            vendor="Google Inc. (NVIDIA)",
            renderer="ANGLE (NVIDIA, NVIDIA GeForce RTX 3060/PCIe/SSE2, OpenGL 4.5)",
        ),
    ),
    "macos_chrome": FingerprintProfile(
        name="macos_chrome",
        navigator=NavigatorConfig(
            platform="MacIntel",
            app_version="5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            hardware_concurrency=10,
            device_memory=8,
        ),
        screen=ScreenConfig(
            width=2560, height=1440, device_pixel_ratio=2.0
        ),
        webgl=WebGLConfig(
            vendor="Google Inc. (Apple)",
            renderer="ANGLE (Apple, ANGLE Metal Renderer: Apple M1 Pro, Version 14.0)",
        ),
    ),
    "linux_chrome": FingerprintProfile(
        name="linux_chrome",
        navigator=NavigatorConfig(
            platform="Linux x86_64",
            app_version="5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            hardware_concurrency=12,
            device_memory=16,
        ),
        screen=ScreenConfig(width=1920, height=1080),
        webgl=WebGLConfig(
            vendor="Google Inc. (NVIDIA)",
            renderer="ANGLE (NVIDIA, NVIDIA GeForce GTX 1080 Ti/PCIe/SSE2, OpenGL 4.5)",
        ),
    ),
}


def get_profile(name: str) -> FingerprintProfile:
    """Get predefined profile by name."""
    if name not in PROFILES:
        raise ValueError(f"Unknown profile: {name}. Available: {list(PROFILES.keys())}")
    return PROFILES[name].model_copy(deep=True)


def get_random_profile() -> FingerprintProfile:
    """Get random predefined profile."""
    return random.choice(list(PROFILES.values())).model_copy(deep=True)
