"""Fingerprint spoofing JavaScript injection."""

from __future__ import annotations

import json
import random
import string
from typing import TYPE_CHECKING

from loguru import logger

from .config import FingerprintProfile, NavigatorConfig, get_random_profile

if TYPE_CHECKING:
    import nodriver as uc


def generate_device_id() -> str:
    """Generate random device ID."""
    return "".join(random.choices(string.hexdigits.lower(), k=32))


def generate_fingerprint(profile: FingerprintProfile | None = None) -> FingerprintProfile:
    """Generate fingerprint profile with random variations."""
    if profile is None:
        profile = get_random_profile()

    # Add small random variations
    profile.canvas_noise = random.uniform(0.00001, 0.0001)
    profile.audio_noise = random.uniform(0.00001, 0.0001)

    return profile


def _build_navigator_spoofing_js(nav: NavigatorConfig) -> str:
    """Build JavaScript for navigator spoofing."""
    user_agent = nav.user_agent
    if not user_agent:
        user_agent = f"Mozilla/5.0 ({nav.platform}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    languages_json = json.dumps(nav.languages)

    return f"""
    // Navigator spoofing
    const navigatorProps = {{
        platform: '{nav.platform}',
        appVersion: '{nav.app_version}',
        userAgent: '{user_agent}',
        vendor: '{nav.vendor}',
        language: '{nav.languages[0] if nav.languages else "en-US"}',
        languages: {languages_json},
        hardwareConcurrency: {nav.hardware_concurrency},
        deviceMemory: {nav.device_memory},
        maxTouchPoints: {nav.max_touch_points},
        webdriver: false,
        doNotTrack: {f'"{nav.do_not_track}"' if nav.do_not_track else 'null'},
    }};

    // Override navigator properties
    for (const [key, value] of Object.entries(navigatorProps)) {{
        if (value !== null && value !== undefined) {{
            try {{
                Object.defineProperty(navigator, key, {{
                    get: () => value,
                    configurable: true
                }});
            }} catch (e) {{}}
        }}
    }}

    // Override navigator.languages (needs special handling)
    Object.defineProperty(navigator, 'languages', {{
        get: () => Object.freeze({languages_json}),
        configurable: true
    }});
    """


def _build_screen_spoofing_js(screen: "FingerprintProfile.screen") -> str:
    """Build JavaScript for screen spoofing."""
    return f"""
    // Screen spoofing
    const screenProps = {{
        width: {screen.width},
        height: {screen.height},
        availWidth: {screen.avail_width},
        availHeight: {screen.avail_height},
        colorDepth: {screen.color_depth},
        pixelDepth: {screen.pixel_depth},
    }};

    for (const [key, value] of Object.entries(screenProps)) {{
        try {{
            Object.defineProperty(screen, key, {{
                get: () => value,
                configurable: true
            }});
        }} catch (e) {{}}
    }}

    // Window inner/outer dimensions
    Object.defineProperty(window, 'innerWidth', {{ get: () => {screen.avail_width}, configurable: true }});
    Object.defineProperty(window, 'innerHeight', {{ get: () => {screen.avail_height}, configurable: true }});
    Object.defineProperty(window, 'outerWidth', {{ get: () => {screen.width}, configurable: true }});
    Object.defineProperty(window, 'outerHeight', {{ get: () => {screen.height}, configurable: true }});
    Object.defineProperty(window, 'devicePixelRatio', {{ get: () => {screen.device_pixel_ratio}, configurable: true }});
    """


def _build_webgl_spoofing_js(webgl: "FingerprintProfile.webgl") -> str:
    """Build JavaScript for WebGL spoofing."""
    return f"""
    // WebGL spoofing
    const getParameterProxy = function(target) {{
        return new Proxy(target, {{
            apply: function(target, thisArg, args) {{
                const param = args[0];
                const gl = thisArg;

                // UNMASKED_VENDOR_WEBGL
                if (param === 37445) {{
                    return '{webgl.unmasked_vendor}';
                }}
                // UNMASKED_RENDERER_WEBGL
                if (param === 37446) {{
                    return '{webgl.unmasked_renderer}';
                }}
                // VENDOR
                if (param === 7936) {{
                    return '{webgl.vendor}';
                }}
                // RENDERER
                if (param === 7937) {{
                    return '{webgl.renderer}';
                }}

                return Reflect.apply(target, thisArg, args);
            }}
        }});
    }};

    // Override for WebGLRenderingContext
    if (typeof WebGLRenderingContext !== 'undefined') {{
        WebGLRenderingContext.prototype.getParameter = getParameterProxy(
            WebGLRenderingContext.prototype.getParameter
        );
    }}

    // Override for WebGL2RenderingContext
    if (typeof WebGL2RenderingContext !== 'undefined') {{
        WebGL2RenderingContext.prototype.getParameter = getParameterProxy(
            WebGL2RenderingContext.prototype.getParameter
        );
    }}
    """


def _build_media_devices_spoofing_js(media: "FingerprintProfile.media_devices") -> str:
    """Build JavaScript for media devices spoofing."""
    devices = []

    # Add audio inputs (microphones)
    for i in range(media.audio_inputs):
        devices.append({
            "deviceId": generate_device_id(),
            "kind": "audioinput",
            "label": f"Microphone {i + 1}" if i > 0 else "Default Microphone",
            "groupId": generate_device_id(),
        })

    # Add audio outputs (speakers)
    for i in range(media.audio_outputs):
        devices.append({
            "deviceId": generate_device_id(),
            "kind": "audiooutput",
            "label": f"Speaker {i + 1}" if i > 0 else "Default Speaker",
            "groupId": generate_device_id(),
        })

    # Add video inputs (cameras)
    for i in range(media.video_inputs):
        devices.append({
            "deviceId": generate_device_id(),
            "kind": "videoinput",
            "label": f"Camera {i + 1}" if i > 0 else "HD Webcam",
            "groupId": generate_device_id(),
        })

    devices_json = json.dumps(devices)

    return f"""
    // Media Devices spoofing
    if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {{
        const fakeDevices = {devices_json};

        navigator.mediaDevices.enumerateDevices = async function() {{
            return fakeDevices.map(d => ({{
                deviceId: d.deviceId,
                kind: d.kind,
                label: d.label,
                groupId: d.groupId,
                toJSON: function() {{ return this; }}
            }}));
        }};
    }}
    """


def _build_timezone_spoofing_js(tz: "FingerprintProfile.timezone") -> str:
    """Build JavaScript for timezone spoofing."""
    return f"""
    // Timezone spoofing
    const targetTimezone = '{tz.timezone}';
    const targetOffset = {tz.offset};

    // Override Date.prototype.getTimezoneOffset
    Date.prototype.getTimezoneOffset = function() {{
        return targetOffset;
    }};

    // Override Intl.DateTimeFormat
    const originalDateTimeFormat = Intl.DateTimeFormat;
    Intl.DateTimeFormat = function(locales, options) {{
        options = options || {{}};
        options.timeZone = options.timeZone || targetTimezone;
        return new originalDateTimeFormat(locales, options);
    }};
    Intl.DateTimeFormat.prototype = originalDateTimeFormat.prototype;
    Intl.DateTimeFormat.supportedLocalesOf = originalDateTimeFormat.supportedLocalesOf;

    // Override resolvedOptions
    const originalResolvedOptions = Intl.DateTimeFormat.prototype.resolvedOptions;
    Intl.DateTimeFormat.prototype.resolvedOptions = function() {{
        const result = originalResolvedOptions.call(this);
        result.timeZone = targetTimezone;
        return result;
    }};
    """


def _build_canvas_noise_js(noise: float) -> str:
    """Build JavaScript for canvas fingerprint noise."""
    return f"""
    // Canvas fingerprint noise
    const canvasNoise = {noise};

    const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function(type, quality) {{
        const ctx = this.getContext('2d');
        if (ctx) {{
            const imageData = ctx.getImageData(0, 0, this.width, this.height);
            for (let i = 0; i < imageData.data.length; i += 4) {{
                // Add small random noise to each pixel
                imageData.data[i] = Math.max(0, Math.min(255,
                    imageData.data[i] + Math.floor((Math.random() - 0.5) * canvasNoise * 255)
                ));
            }}
            ctx.putImageData(imageData, 0, 0);
        }}
        return originalToDataURL.call(this, type, quality);
    }};

    const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;
    CanvasRenderingContext2D.prototype.getImageData = function(sx, sy, sw, sh) {{
        const imageData = originalGetImageData.call(this, sx, sy, sw, sh);
        for (let i = 0; i < imageData.data.length; i += 4) {{
            imageData.data[i] = Math.max(0, Math.min(255,
                imageData.data[i] + Math.floor((Math.random() - 0.5) * canvasNoise * 255)
            ));
        }}
        return imageData;
    }};
    """


def _build_webrtc_spoofing_js(hide_local_ips: bool) -> str:
    """Build JavaScript for WebRTC spoofing."""
    if not hide_local_ips:
        return ""

    return """
    // WebRTC local IP hiding
    const originalRTCPeerConnection = window.RTCPeerConnection;

    window.RTCPeerConnection = function(...args) {
        const pc = new originalRTCPeerConnection(...args);

        const originalCreateOffer = pc.createOffer.bind(pc);
        pc.createOffer = async function(options) {
            const offer = await originalCreateOffer(options);
            // Remove local IP candidates
            offer.sdp = offer.sdp.replace(/a=candidate:.+typ host.+\\r\\n/g, '');
            return offer;
        };

        return pc;
    };

    window.RTCPeerConnection.prototype = originalRTCPeerConnection.prototype;
    """


def build_spoofing_script(profile: FingerprintProfile) -> str:
    """Build complete fingerprint spoofing script."""
    scripts = [
        "(function() {",
        "'use strict';",
        "",
        "// nodriver-antidetect fingerprint spoofing",
        f"// Profile: {profile.name}",
        "",
        _build_navigator_spoofing_js(profile.navigator),
        _build_screen_spoofing_js(profile.screen),
        _build_webgl_spoofing_js(profile.webgl),
        _build_media_devices_spoofing_js(profile.media_devices),
        _build_timezone_spoofing_js(profile.timezone),
        _build_canvas_noise_js(profile.canvas_noise),
        _build_webrtc_spoofing_js(profile.webrtc_local_ips_hidden),
        "",
        "// Remove automation indicators",
        "delete navigator.__proto__.webdriver;",
        "delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;",
        "delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;",
        "delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;",
        "",
        "console.log('[antidetect] Fingerprint spoofing applied');",
        "",
        "})();",
    ]

    return "\n".join(scripts)


async def apply_fingerprint_spoofing(
    page: "uc.Tab",
    profile: FingerprintProfile | None = None,
) -> None:
    """
    Apply fingerprint spoofing to a nodriver page.

    Args:
        page: nodriver Tab/Page object
        profile: Fingerprint profile to apply. If None, generates random profile.
    """
    if profile is None:
        profile = generate_fingerprint()

    script = build_spoofing_script(profile)

    try:
        # Inject script using CDP
        await page.send(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": script},
        )
        logger.info(f"Applied fingerprint profile: {profile.name}")
    except Exception as e:
        logger.warning(f"Failed to inject spoofing script via CDP: {e}")
        # Fallback: try direct evaluation
        try:
            await page.evaluate(script)
            logger.info(f"Applied fingerprint profile (fallback): {profile.name}")
        except Exception as e2:
            logger.error(f"Failed to apply fingerprint spoofing: {e2}")
            raise
