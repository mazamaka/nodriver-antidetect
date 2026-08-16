"""JSON Profile Loader for antidetect browser fingerprints.

Load fingerprint profiles from JSON files.
Allows easy profile switching without code changes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger

from ..config import (
    FingerprintProfile,
    MediaDevicesConfig,
    NavigatorConfig,
    ScreenConfig,
    TimezoneConfig,
    WebGLConfig,
    build_app_version,
    build_user_agent,
    get_chrome_version,
)

# Browser chrome height for avail_height calculation
_BROWSER_CHROME_HEIGHT = 40

# Cached defaults to avoid creating new instances repeatedly
_DEFAULTS: dict[str, Any] = {}


def _get_defaults(config_class: type) -> Any:
    """Get or create cached default instance of config class."""
    name = config_class.__name__
    if name not in _DEFAULTS:
        _DEFAULTS[name] = config_class()
    return _DEFAULTS[name]


def _get(data: dict, *keys: str, default: Any = None) -> Any:
    """Get value from dict trying multiple keys (snake_case, camelCase).

    Args:
        data: Source dictionary
        *keys: Keys to try in order (first found wins)
        default: Default value if no key found

    Returns:
        Value from dict or default
    """
    for key in keys:
        if key in data:
            return data[key]
    return default


def load_profile_from_json(path: str | Path) -> FingerprintProfile:
    """
    Load fingerprint profile from JSON file.

    Args:
        path: Path to JSON profile file

    Returns:
        FingerprintProfile instance

    Raises:
        FileNotFoundError: If file not found
        json.JSONDecodeError: If JSON is invalid
        ValueError: If JSON structure is incorrect
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Profile not found: {path}")

    logger.info(f"Loading fingerprint profile from: {path}")

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    return _parse_profile(data, path.stem)


def load_profile_from_dict(data: dict[str, Any], name: str = "custom") -> FingerprintProfile:
    """
    Create profile from dictionary.

    Args:
        data: Dictionary with profile data
        name: Profile name

    Returns:
        FingerprintProfile instance
    """
    return _parse_profile(data, name)


def _parse_profile(data: dict[str, Any], name: str) -> FingerprintProfile:
    """Parse profile data into FingerprintProfile."""
    # Cached defaults
    wgl_def = _get_defaults(WebGLConfig)
    scr_def = _get_defaults(ScreenConfig)
    nav_def = _get_defaults(NavigatorConfig)
    media_def = _get_defaults(MediaDevicesConfig)
    tz_def = _get_defaults(TimezoneConfig)
    fp_def = _get_defaults(FingerprintProfile)

    profile_name = data.get("name", name)

    # WebGL
    wgl = data.get("webgl", {})
    vendor = _get(wgl, "vendor", default=wgl_def.vendor)
    renderer = _get(wgl, "renderer", default=wgl_def.renderer)
    webgl = WebGLConfig(
        mode=_get(wgl, "mode", default=wgl_def.mode),
        vendor=vendor,
        renderer=renderer,
        unmasked_vendor=_get(wgl, "unmasked_vendor", default=vendor),
        unmasked_renderer=_get(wgl, "unmasked_renderer", default=renderer),
    )

    # Screen
    scr = data.get("screen", {})
    width = _get(scr, "width", default=scr_def.width)
    height = _get(scr, "height", default=scr_def.height)
    screen = ScreenConfig(
        width=width,
        height=height,
        avail_width=_get(scr, "avail_width", "availWidth", default=width),
        avail_height=_get(
            scr, "avail_height", "availHeight", default=height - _BROWSER_CHROME_HEIGHT
        ),
        color_depth=_get(scr, "color_depth", "colorDepth", default=scr_def.color_depth),
        pixel_depth=_get(scr, "pixel_depth", "pixelDepth", default=scr_def.pixel_depth),
        device_pixel_ratio=_get(
            scr, "device_pixel_ratio", "devicePixelRatio", default=scr_def.device_pixel_ratio
        ),
    )

    # Navigator
    nav = data.get("navigator", {})
    languages = _get(nav, "languages", default=nav_def.languages)
    if isinstance(languages, str):
        languages = [lang.strip() for lang in languages.split(",")]

    # Get platform from profile
    platform = _get(nav, "platform", default=nav_def.platform)

    # DYNAMIC UA: Always generate UA from real Chrome version
    # This ensures UA matches the actual installed browser
    chrome_version = get_chrome_version()
    user_agent = build_user_agent(platform, chrome_version)
    app_version = build_app_version(platform, chrome_version)

    logger.debug(f"Dynamic UA generated: Chrome/{chrome_version} for {platform}")

    navigator = NavigatorConfig(
        platform=platform,
        app_version=app_version,
        user_agent=user_agent,
        vendor=_get(nav, "vendor", default=nav_def.vendor),
        languages=languages,
        hardware_concurrency=_get(
            nav, "hardware_concurrency", "hardwareConcurrency", default=nav_def.hardware_concurrency
        ),
        device_memory=_get(nav, "device_memory", "deviceMemory", default=nav_def.device_memory),
        max_touch_points=_get(
            nav, "max_touch_points", "maxTouchPoints", default=nav_def.max_touch_points
        ),
        do_not_track=_get(nav, "do_not_track", "doNotTrack", default=None),
        webdriver=_get(nav, "webdriver", default=False),
    )

    # Media devices
    media = _get(data, "media_devices", "mediaDevices", default={})
    media_devices = MediaDevicesConfig(
        has_audio_input=_get(
            media, "has_audio_input", "hasAudioInput", default=media_def.has_audio_input
        ),
        has_audio_output=_get(
            media, "has_audio_output", "hasAudioOutput", default=media_def.has_audio_output
        ),
        has_video_input=_get(
            media, "has_video_input", "hasVideoInput", default=media_def.has_video_input
        ),
        audio_inputs=_get(media, "audio_inputs", "audioInputs", default=media_def.audio_inputs),
        audio_outputs=_get(media, "audio_outputs", "audioOutputs", default=media_def.audio_outputs),
        video_inputs=_get(media, "video_inputs", "videoInputs", default=media_def.video_inputs),
    )

    # Timezone
    tz = data.get("timezone", {})
    timezone = TimezoneConfig(
        timezone=_get(tz, "timezone", "name", default=tz_def.timezone),
        locale=_get(tz, "locale", default=tz_def.locale),
        offset=_get(tz, "offset", default=tz_def.offset),
    )

    # Profile
    profile = FingerprintProfile(
        name=profile_name,
        webgl=webgl,
        screen=screen,
        navigator=navigator,
        media_devices=media_devices,
        timezone=timezone,
        canvas_noise=_get(data, "canvas_noise", "canvasNoise", default=fp_def.canvas_noise),
        audio_noise=_get(data, "audio_noise", "audioNoise", default=fp_def.audio_noise),
        webrtc_enabled=_get(data, "webrtc_enabled", "webrtcEnabled", default=fp_def.webrtc_enabled),
        webrtc_local_ips_hidden=_get(
            data,
            "webrtc_local_ips_hidden",
            "webrtcLocalIpsHidden",
            default=fp_def.webrtc_local_ips_hidden,
        ),
    )

    logger.info(f"Loaded profile: {profile_name}")
    return profile


def save_profile_to_json(profile: FingerprintProfile, path: str | Path) -> None:
    """
    Save fingerprint profile to JSON file.

    Args:
        profile: FingerprintProfile instance
        path: Path to save JSON file
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = profile_to_dict(profile)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved profile to: {path}")


def profile_to_dict(profile: FingerprintProfile) -> dict[str, Any]:
    """Convert profile to dictionary for JSON serialization."""
    return {
        "name": profile.name,
        "webgl": {
            "vendor": profile.webgl.vendor,
            "renderer": profile.webgl.renderer,
            "unmasked_vendor": profile.webgl.unmasked_vendor,
            "unmasked_renderer": profile.webgl.unmasked_renderer,
        },
        "screen": {
            "width": profile.screen.width,
            "height": profile.screen.height,
            "avail_width": profile.screen.avail_width,
            "avail_height": profile.screen.avail_height,
            "color_depth": profile.screen.color_depth,
            "pixel_depth": profile.screen.pixel_depth,
            "device_pixel_ratio": profile.screen.device_pixel_ratio,
        },
        "navigator": {
            "platform": profile.navigator.platform,
            "app_version": profile.navigator.app_version,
            "user_agent": profile.navigator.user_agent,
            "vendor": profile.navigator.vendor,
            "languages": profile.navigator.languages,
            "hardware_concurrency": profile.navigator.hardware_concurrency,
            "device_memory": profile.navigator.device_memory,
            "max_touch_points": profile.navigator.max_touch_points,
            "do_not_track": profile.navigator.do_not_track,
            "webdriver": profile.navigator.webdriver,
        },
        "media_devices": {
            "has_audio_input": profile.media_devices.has_audio_input,
            "has_audio_output": profile.media_devices.has_audio_output,
            "has_video_input": profile.media_devices.has_video_input,
            "audio_inputs": profile.media_devices.audio_inputs,
            "audio_outputs": profile.media_devices.audio_outputs,
            "video_inputs": profile.media_devices.video_inputs,
        },
        "timezone": {
            "timezone": profile.timezone.timezone,
            "locale": profile.timezone.locale,
            "offset": profile.timezone.offset,
        },
        "canvas_noise": profile.canvas_noise,
        "audio_noise": profile.audio_noise,
        "webrtc_enabled": profile.webrtc_enabled,
        "webrtc_local_ips_hidden": profile.webrtc_local_ips_hidden,
    }


def list_profiles(profiles_dir: str | Path | None = None) -> list[str]:
    """
    List available JSON profiles.

    Args:
        profiles_dir: Profiles directory (default: ./profiles)

    Returns:
        List of profile names (without .json extension)
    """
    if profiles_dir is None:
        profiles_dir = Path(__file__).parent.parent.parent / "profiles"

    profiles_dir = Path(profiles_dir)

    if not profiles_dir.exists():
        return []

    profiles = []
    for f in profiles_dir.glob("*.json"):
        profiles.append(f.stem)

    return sorted(profiles)


def get_profile_path(name: str, profiles_dir: str | Path | None = None) -> Path:
    """
    Get path to JSON profile by name.

    Args:
        name: Profile name (without .json)
        profiles_dir: Profiles directory

    Returns:
        Full path to JSON file
    """
    if profiles_dir is None:
        profiles_dir = Path(__file__).parent.parent.parent / "profiles"

    return Path(profiles_dir) / f"{name}.json"
