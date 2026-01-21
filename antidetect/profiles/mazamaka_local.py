"""
Эталонный профиль на основе локального браузера mazamaka.

Цель: like_headless <= 31%, headless = 0%, stealth = 0%
"""

from ..config import (
    FingerprintProfile,
    MediaDevicesConfig,
    NavigatorConfig,
    ScreenConfig,
    TimezoneConfig,
    WebGLConfig,
)

# Эталонный профиль локального браузера
MAZAMAKA_LOCAL_PROFILE = FingerprintProfile(
    name="mazamaka_local",

    # WebGL - RTX 3060
    webgl=WebGLConfig(
        vendor="Google Inc. (NVIDIA Corporation)",
        renderer="ANGLE (NVIDIA Corporation, NVIDIA GeForce RTX 3060/PCIe/SSE2, OpenGL 4.5.0)",
        unmasked_vendor="Google Inc. (NVIDIA Corporation)",
        unmasked_renderer="ANGLE (NVIDIA Corporation, NVIDIA GeForce RTX 3060/PCIe/SSE2, OpenGL 4.5.0)",
    ),

    # Screen - 3440x1440 ultrawide
    screen=ScreenConfig(
        width=3440,
        height=1440,
        avail_width=3374,
        avail_height=1408,
        color_depth=24,
        pixel_depth=24,
        device_pixel_ratio=1.0,
    ),

    # Navigator
    navigator=NavigatorConfig(
        platform="Linux x86_64",
        app_version="5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
        vendor="Google Inc.",
        languages=["ru", "en-US", "en", "uk"],
        hardware_concurrency=12,
        device_memory=8,
        max_touch_points=0,
        do_not_track=None,
        webdriver=False,
    ),

    # Media devices - 3 устройства
    media_devices=MediaDevicesConfig(
        has_audio_input=True,
        has_audio_output=True,
        has_video_input=True,
        audio_inputs=1,
        audio_outputs=1,
        video_inputs=1,
    ),

    # Timezone - Europe/Budapest
    timezone=TimezoneConfig(
        timezone="Europe/Budapest",
        locale="ru",
        offset=-60,
    ),

    # Canvas noise - минимальный
    canvas_noise=0.00001,

    # Audio noise - минимальный
    audio_noise=0.00001,

    # WebRTC
    webrtc_enabled=True,
    webrtc_local_ips_hidden=True,
)

# Целевые метрики (из локального браузера)
TARGET_METRICS = {
    "like_headless": 31,  # Цель: <= 31%
    "headless": 0,
    "stealth": 0,
    "canvas_hash": "47b9dcbf",
    "webgl_images": "35278053",
    "webgl_pixels": "0a28f046",
    "audio_sum": 124.04347527516074,
    "fonts_count": 8,
}
