"""
Stealth fingerprint injection for nodriver.

Key principles:
1. CDP-level first: Use CDP for what it supports (UA, timezone, locale)
2. JS injection only for what CDP can't do (WebGL, plugins, canvas)
3. Preserve native behavior: toString, prototype chain, instanceof
4. No debug markers, no detectable patterns
"""

from __future__ import annotations

import json
import secrets
from typing import TYPE_CHECKING

import nodriver.cdp as cdp
from loguru import logger

from .js import load_js

if TYPE_CHECKING:
    import nodriver as uc
    from .config import FingerprintProfile


# Browser chrome height (toolbar, tabs, etc.)
BROWSER_CHROME_HEIGHT = 40


def _generate_plugins_config() -> list[dict]:
    """Generate realistic Chrome plugins list (PDF viewers only in modern Chrome)."""
    # Modern Chrome only has PDF plugins
    return [
        {
            "name": "PDF Viewer",
            "description": "Portable Document Format",
            "filename": "internal-pdf-viewer",
            "mimeTypes": [
                {"type": "application/pdf", "suffixes": "pdf", "description": "Portable Document Format"},
                {"type": "text/pdf", "suffixes": "pdf", "description": "Portable Document Format"},
            ],
        },
        {
            "name": "Chrome PDF Viewer",
            "description": "Portable Document Format",
            "filename": "internal-pdf-viewer",
            "mimeTypes": [
                {"type": "application/pdf", "suffixes": "pdf", "description": "Portable Document Format"},
                {"type": "text/pdf", "suffixes": "pdf", "description": "Portable Document Format"},
            ],
        },
        {
            "name": "Chromium PDF Viewer",
            "description": "Portable Document Format",
            "filename": "internal-pdf-viewer",
            "mimeTypes": [
                {"type": "application/pdf", "suffixes": "pdf", "description": "Portable Document Format"},
                {"type": "text/pdf", "suffixes": "pdf", "description": "Portable Document Format"},
            ],
        },
        {
            "name": "Microsoft Edge PDF Viewer",
            "description": "Portable Document Format",
            "filename": "internal-pdf-viewer",
            "mimeTypes": [
                {"type": "application/pdf", "suffixes": "pdf", "description": "Portable Document Format"},
                {"type": "text/pdf", "suffixes": "pdf", "description": "Portable Document Format"},
            ],
        },
        {
            "name": "WebKit built-in PDF",
            "description": "Portable Document Format",
            "filename": "internal-pdf-viewer",
            "mimeTypes": [
                {"type": "application/pdf", "suffixes": "pdf", "description": "Portable Document Format"},
                {"type": "text/pdf", "suffixes": "pdf", "description": "Portable Document Format"},
            ],
        },
    ]


def _build_config(profile: "FingerprintProfile") -> dict:
    """Build configuration object for stealth script."""
    scr = profile.screen
    wgl = profile.webgl
    media = profile.media_devices
    nav = profile.navigator

    # Generate fake device list (empty labels = no permission granted, realistic)
    devices = []
    for kind, count in [("audioinput", media.audio_inputs),
                        ("audiooutput", media.audio_outputs),
                        ("videoinput", media.video_inputs)]:
        for _ in range(count):
            devices.append({
                "deviceId": secrets.token_hex(32),
                "kind": kind,
                "label": "",  # Empty until getUserMedia permission
                "groupId": secrets.token_hex(32),
            })

    return {
        # Screen (CDP setDeviceMetricsOverride is detectable, so we use JS)
        "screen": {
            "width": scr.width,
            "height": scr.height,
            "availWidth": scr.avail_width,
            "availHeight": scr.avail_height,
            "colorDepth": scr.color_depth,
            "pixelDepth": scr.pixel_depth,
        },
        "window": {
            "devicePixelRatio": scr.device_pixel_ratio,
            "innerWidth": scr.avail_width,
            "innerHeight": scr.avail_height - BROWSER_CHROME_HEIGHT,
            "outerWidth": scr.width,
            "outerHeight": scr.height,
        },
        # WebGL (CDP cannot spoof)
        "webgl": {
            "vendor": wgl.vendor,
            "renderer": wgl.renderer,
        },
        # Media devices (CDP cannot spoof)
        "media": {
            "devices": devices,
        },
        # Canvas/audio noise for fingerprint uniqueness
        "noise": {
            "canvas": profile.canvas_noise,
            "audio": profile.audio_noise,
        },
        # Plugins (CDP cannot spoof)
        "plugins": _generate_plugins_config(),
        # Navigator properties (doNotTrack)
        # Note: WebGPU disabled via Chrome flags, not JS
        "navigator": {
            "doNotTrack": nav.do_not_track,
        },
    }


def build_stealth_script(profile: "FingerprintProfile") -> str:
    """
    Build stealth script for things CDP cannot do.

    NOTE: UA, timezone, locale are handled by CDP in browser.py
    This script only handles: WebGL, plugins, screen, canvas, media devices, etc.

    JS modules are loaded from antidetect/js/ directory for better maintainability.
    """
    config = _build_config(profile)

    # Load JS modules
    js_utils = load_js("utils")
    js_webdriver = load_js("webdriver")
    js_plugins = load_js("plugins")
    js_screen = load_js("screen")
    js_webgl = load_js("webgl")
    js_media = load_js("media")
    js_canvas = load_js("canvas")
    js_battery = load_js("battery")
    js_network = load_js("network")
    js_permissions = load_js("permissions")
    js_navigator = load_js("navigator")
    js_cleanup = load_js("cleanup")

    return f"""(function() {{
'use strict';

const C = {json.dumps(config)};

{js_utils}

{js_webdriver}

{js_plugins}

{js_screen}

{js_webgl}

{js_media}

{js_canvas}

{js_battery}

{js_network}

{js_permissions}

{js_navigator}

{js_cleanup}

}})();"""


async def apply_stealth(browser: "uc.Browser", profile: "FingerprintProfile") -> None:
    """
    Register stealth script for all pages in this browser.

    NOTE: This is a fallback. Primary stealth is applied via CDP in browser.py
    """
    tabs = browser.tabs
    if not tabs:
        logger.warning("No tabs available for stealth injection")
        return

    script = build_stealth_script(profile)

    try:
        await tabs[0].send(cdp.page.add_script_to_evaluate_on_new_document(source=script))
    except (ConnectionError, TimeoutError) as e:
        logger.debug(f"CDP script registration skipped: {e}")
    except RuntimeError as e:
        logger.debug(f"CDP script registration failed: {e}")

    try:
        await tabs[0].evaluate(script)
        logger.info(f"Stealth initialized: {profile.name}")
    except (ConnectionError, TimeoutError) as e:
        logger.warning(f"Stealth injection failed: {e}")


async def apply_stealth_to_page(page: "uc.Tab", profile: "FingerprintProfile") -> None:
    """Inject stealth script into page context (fallback method)."""
    script = build_stealth_script(profile)
    try:
        await page.evaluate(script)
    except Exception as e:
        logger.warning(f"Stealth injection failed: {e}")
