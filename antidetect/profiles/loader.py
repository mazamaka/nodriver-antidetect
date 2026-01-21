"""
JSON Profile Loader for antidetect browser fingerprints.

Загрузка профилей фингерпринтов из JSON файлов.
Позволяет легко подставлять новые профили без изменения кода.
"""

from __future__ import annotations

import json
import os
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
)


def load_profile_from_json(path: str | Path) -> FingerprintProfile:
    """
    Загрузить профиль фингерпринта из JSON файла.

    Args:
        path: Путь к JSON файлу с профилем

    Returns:
        FingerprintProfile объект

    Raises:
        FileNotFoundError: Если файл не найден
        json.JSONDecodeError: Если JSON невалидный
        ValueError: Если структура JSON некорректная
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Profile not found: {path}")

    logger.info(f"Loading fingerprint profile from: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return _parse_profile(data, path.stem)


def load_profile_from_dict(data: dict[str, Any], name: str = "custom") -> FingerprintProfile:
    """
    Создать профиль из словаря (dict).

    Args:
        data: Словарь с данными профиля
        name: Имя профиля

    Returns:
        FingerprintProfile объект
    """
    return _parse_profile(data, name)


def _parse_profile(data: dict[str, Any], name: str) -> FingerprintProfile:
    """Парсинг данных профиля в FingerprintProfile."""

    # Получаем имя профиля
    profile_name = data.get("name", name)

    # WebGL конфигурация
    webgl_data = data.get("webgl", {})
    webgl = WebGLConfig(
        vendor=webgl_data.get("vendor", WebGLConfig().vendor),
        renderer=webgl_data.get("renderer", WebGLConfig().renderer),
        unmasked_vendor=webgl_data.get("unmasked_vendor", webgl_data.get("vendor", WebGLConfig().unmasked_vendor)),
        unmasked_renderer=webgl_data.get("unmasked_renderer", webgl_data.get("renderer", WebGLConfig().unmasked_renderer)),
    )

    # Screen конфигурация
    screen_data = data.get("screen", {})
    screen = ScreenConfig(
        width=screen_data.get("width", ScreenConfig().width),
        height=screen_data.get("height", ScreenConfig().height),
        avail_width=screen_data.get("avail_width", screen_data.get("availWidth", screen_data.get("width", ScreenConfig().avail_width))),
        avail_height=screen_data.get("avail_height", screen_data.get("availHeight", screen_data.get("height", ScreenConfig().avail_height) - 40)),
        color_depth=screen_data.get("color_depth", screen_data.get("colorDepth", ScreenConfig().color_depth)),
        pixel_depth=screen_data.get("pixel_depth", screen_data.get("pixelDepth", ScreenConfig().pixel_depth)),
        device_pixel_ratio=screen_data.get("device_pixel_ratio", screen_data.get("devicePixelRatio", ScreenConfig().device_pixel_ratio)),
    )

    # Navigator конфигурация
    nav_data = data.get("navigator", {})
    languages = nav_data.get("languages", NavigatorConfig().languages)
    if isinstance(languages, str):
        languages = [lang.strip() for lang in languages.split(",")]

    navigator = NavigatorConfig(
        platform=nav_data.get("platform", NavigatorConfig().platform),
        app_version=nav_data.get("app_version", nav_data.get("appVersion", NavigatorConfig().app_version)),
        user_agent=nav_data.get("user_agent", nav_data.get("userAgent", NavigatorConfig().user_agent)),
        vendor=nav_data.get("vendor", NavigatorConfig().vendor),
        languages=languages,
        hardware_concurrency=nav_data.get("hardware_concurrency", nav_data.get("hardwareConcurrency", NavigatorConfig().hardware_concurrency)),
        device_memory=nav_data.get("device_memory", nav_data.get("deviceMemory", NavigatorConfig().device_memory)),
        max_touch_points=nav_data.get("max_touch_points", nav_data.get("maxTouchPoints", NavigatorConfig().max_touch_points)),
        do_not_track=nav_data.get("do_not_track", nav_data.get("doNotTrack")),
        webdriver=nav_data.get("webdriver", False),
    )

    # Media devices конфигурация
    media_data = data.get("media_devices", data.get("mediaDevices", {}))
    media_devices = MediaDevicesConfig(
        has_audio_input=media_data.get("has_audio_input", media_data.get("hasAudioInput", MediaDevicesConfig().has_audio_input)),
        has_audio_output=media_data.get("has_audio_output", media_data.get("hasAudioOutput", MediaDevicesConfig().has_audio_output)),
        has_video_input=media_data.get("has_video_input", media_data.get("hasVideoInput", MediaDevicesConfig().has_video_input)),
        audio_inputs=media_data.get("audio_inputs", media_data.get("audioInputs", MediaDevicesConfig().audio_inputs)),
        audio_outputs=media_data.get("audio_outputs", media_data.get("audioOutputs", MediaDevicesConfig().audio_outputs)),
        video_inputs=media_data.get("video_inputs", media_data.get("videoInputs", MediaDevicesConfig().video_inputs)),
    )

    # Timezone конфигурация
    tz_data = data.get("timezone", {})
    timezone = TimezoneConfig(
        timezone=tz_data.get("timezone", tz_data.get("name", TimezoneConfig().timezone)),
        locale=tz_data.get("locale", TimezoneConfig().locale),
        offset=tz_data.get("offset", TimezoneConfig().offset),
    )

    # Создаём профиль
    profile = FingerprintProfile(
        name=profile_name,
        webgl=webgl,
        screen=screen,
        navigator=navigator,
        media_devices=media_devices,
        timezone=timezone,
        canvas_noise=data.get("canvas_noise", data.get("canvasNoise", FingerprintProfile().canvas_noise)),
        audio_noise=data.get("audio_noise", data.get("audioNoise", FingerprintProfile().audio_noise)),
        webrtc_enabled=data.get("webrtc_enabled", data.get("webrtcEnabled", FingerprintProfile().webrtc_enabled)),
        webrtc_local_ips_hidden=data.get("webrtc_local_ips_hidden", data.get("webrtcLocalIpsHidden", FingerprintProfile().webrtc_local_ips_hidden)),
    )

    logger.info(f"Loaded profile: {profile_name}")
    return profile


def save_profile_to_json(profile: FingerprintProfile, path: str | Path) -> None:
    """
    Сохранить профиль фингерпринта в JSON файл.

    Args:
        profile: FingerprintProfile объект
        path: Путь для сохранения JSON файла
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = profile_to_dict(profile)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved profile to: {path}")


def profile_to_dict(profile: FingerprintProfile) -> dict[str, Any]:
    """Конвертировать профиль в словарь для JSON."""
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


def list_profiles(profiles_dir: str | Path = None) -> list[str]:
    """
    Получить список доступных JSON профилей.

    Args:
        profiles_dir: Папка с профилями (по умолчанию ./profiles)

    Returns:
        Список имён профилей (без .json)
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


def get_profile_path(name: str, profiles_dir: str | Path = None) -> Path:
    """
    Получить путь к JSON профилю по имени.

    Args:
        name: Имя профиля (без .json)
        profiles_dir: Папка с профилями

    Returns:
        Полный путь к JSON файлу
    """
    if profiles_dir is None:
        profiles_dir = Path(__file__).parent.parent.parent / "profiles"

    return Path(profiles_dir) / f"{name}.json"
