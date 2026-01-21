"""Fingerprint spoofing JavaScript injection."""

from __future__ import annotations

import json
import random
import string
from typing import TYPE_CHECKING

import nodriver.cdp as cdp
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
    primary_language = nav.languages[0] if nav.languages else "en-US"

    return f"""
    // Navigator spoofing via Navigator.prototype (more reliable)
    const navOverrides = {{
        platform: '{nav.platform}',
        appVersion: '{nav.app_version}',
        userAgent: '{user_agent}',
        vendor: '{nav.vendor}',
        language: '{primary_language}',
        hardwareConcurrency: {nav.hardware_concurrency},
        deviceMemory: {nav.device_memory},
        maxTouchPoints: {nav.max_touch_points},
        webdriver: false,
        doNotTrack: {f'"{nav.do_not_track}"' if nav.do_not_track else 'null'},
    }};

    // Override via prototype for better compatibility
    for (const [key, value] of Object.entries(navOverrides)) {{
        if (value !== null && value !== undefined) {{
            try {{
                Object.defineProperty(Navigator.prototype, key, {{
                    get: function() {{ return value; }},
                    configurable: true
                }});
            }} catch (e1) {{
                // Fallback to navigator instance
                try {{
                    Object.defineProperty(navigator, key, {{
                        get: () => value,
                        configurable: true
                    }});
                }} catch (e2) {{}}
            }}
        }}
    }}

    // Override navigator.languages (frozen array)
    const frozenLanguages = Object.freeze({languages_json});
    try {{
        Object.defineProperty(Navigator.prototype, 'languages', {{
            get: function() {{ return frozenLanguages; }},
            configurable: true
        }});
    }} catch (e) {{
        Object.defineProperty(navigator, 'languages', {{
            get: () => frozenLanguages,
            configurable: true
        }});
    }}
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
    // Timezone and Locale spoofing
    const targetTimezone = '{tz.timezone}';
    const targetOffset = {tz.offset};
    const targetLocale = '{tz.locale}';

    // Override Date.prototype.getTimezoneOffset
    Date.prototype.getTimezoneOffset = function() {{
        return targetOffset;
    }};

    // Override Intl.DateTimeFormat
    const originalDateTimeFormat = Intl.DateTimeFormat;
    Intl.DateTimeFormat = function(locales, options) {{
        // Force locale if not explicitly specified
        if (!locales || (Array.isArray(locales) && locales.length === 0)) {{
            locales = targetLocale;
        }}
        options = options || {{}};
        options.timeZone = options.timeZone || targetTimezone;
        return new originalDateTimeFormat(locales, options);
    }};
    Intl.DateTimeFormat.prototype = originalDateTimeFormat.prototype;
    Intl.DateTimeFormat.supportedLocalesOf = originalDateTimeFormat.supportedLocalesOf;

    // Override resolvedOptions to return our locale and timezone
    const originalResolvedOptions = Intl.DateTimeFormat.prototype.resolvedOptions;
    Intl.DateTimeFormat.prototype.resolvedOptions = function() {{
        const result = originalResolvedOptions.call(this);
        // Create new object to bypass read-only properties
        return {{
            ...result,
            locale: targetLocale,
            timeZone: targetTimezone
        }};
    }};

    // Override Intl.NumberFormat for locale consistency
    const originalNumberFormat = Intl.NumberFormat;
    Intl.NumberFormat = function(locales, options) {{
        if (!locales || (Array.isArray(locales) && locales.length === 0)) {{
            locales = targetLocale;
        }}
        return new originalNumberFormat(locales, options);
    }};
    Intl.NumberFormat.prototype = originalNumberFormat.prototype;
    Intl.NumberFormat.supportedLocalesOf = originalNumberFormat.supportedLocalesOf;

    const originalNFResolvedOptions = Intl.NumberFormat.prototype.resolvedOptions;
    Intl.NumberFormat.prototype.resolvedOptions = function() {{
        const result = originalNFResolvedOptions.call(this);
        return {{ ...result, locale: targetLocale }};
    }};

    // Override Intl.Collator for locale consistency
    const originalCollator = Intl.Collator;
    Intl.Collator = function(locales, options) {{
        if (!locales || (Array.isArray(locales) && locales.length === 0)) {{
            locales = targetLocale;
        }}
        return new originalCollator(locales, options);
    }};
    Intl.Collator.prototype = originalCollator.prototype;
    Intl.Collator.supportedLocalesOf = originalCollator.supportedLocalesOf;

    const originalCollatorResolvedOptions = Intl.Collator.prototype.resolvedOptions;
    Intl.Collator.prototype.resolvedOptions = function() {{
        const result = originalCollatorResolvedOptions.call(this);
        return {{ ...result, locale: targetLocale }};
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
        "window.__antidetect_applied = true;",
        f"window.__antidetect_profile = '{profile.name}';",
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
        # Method 1: CDP addScriptToEvaluateOnNewDocument (for future navigations)
        await page.send(cdp.page.add_script_to_evaluate_on_new_document(
            source=script,
        ))
        logger.debug(f"Registered spoofing script via CDP for future documents")
    except Exception as e:
        logger.warning(f"Failed to register CDP script: {e}")

    try:
        # Method 2: Direct evaluate (for current page context)
        await page.evaluate(script)
        logger.info(f"Applied fingerprint profile: {profile.name}")
    except Exception as e:
        logger.error(f"Failed to apply fingerprint spoofing: {e}")
        raise


async def inject_spoofing_on_navigation(page: "uc.Tab", profile: FingerprintProfile) -> None:
    """
    Re-inject spoofing script after navigation.

    Call this after each page.get() to ensure spoofing is applied.
    """
    script = build_spoofing_script(profile)
    try:
        await page.evaluate(script)
    except Exception as e:
        logger.warning(f"Failed to re-inject spoofing after navigation: {e}")
