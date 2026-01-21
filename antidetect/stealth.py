"""
Stealth fingerprint injection for nodriver.

Key principles:
1. Inject BEFORE page scripts execute (via CDP)
2. Preserve native function signatures (toString)
3. Make overrides undetectable by antifraud
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import nodriver.cdp as cdp
from loguru import logger

if TYPE_CHECKING:
    import nodriver as uc
    from .config import FingerprintProfile


def build_stealth_script(profile: "FingerprintProfile") -> str:
    """Build undetectable fingerprint spoofing script."""

    nav = profile.navigator
    scr = profile.screen
    wgl = profile.webgl
    tz = profile.timezone
    media = profile.media_devices

    # Generate fake device list
    import secrets
    devices = []
    for kind, count in [("audioinput", media.audio_inputs),
                        ("audiooutput", media.audio_outputs),
                        ("videoinput", media.video_inputs)]:
        for i in range(count):
            devices.append({
                "deviceId": secrets.token_hex(32),
                "kind": kind,
                "label": "",  # Empty label = no permission granted (realistic)
                "groupId": secrets.token_hex(32),
            })

    config = {
        "navigator": {
            "platform": nav.platform,
            "appVersion": nav.app_version,
            "userAgent": nav.user_agent,
            "vendor": nav.vendor,
            "language": nav.languages[0] if nav.languages else "en-US",
            "languages": nav.languages,
            "hardwareConcurrency": nav.hardware_concurrency,
            "deviceMemory": nav.device_memory,
            "maxTouchPoints": nav.max_touch_points,
        },
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
            "innerHeight": scr.avail_height,
            "outerWidth": scr.width,
            "outerHeight": scr.height,
        },
        "webgl": {
            "vendor": wgl.vendor,
            "renderer": wgl.renderer,
        },
        "timezone": {
            "zone": tz.timezone,
            "offset": tz.offset,
            "locale": tz.locale,
        },
        "media": {
            "devices": devices,
        },
        "noise": {
            "canvas": profile.canvas_noise,
            "audio": profile.audio_noise,
        },
    }

    return f"""(function() {{
'use strict';

// Stealth marker for debugging
window.__stealth_applied = true;
window.__stealth_profile = '{profile.name}';

const C = {json.dumps(config)};

// === Utils: Make overrides undetectable ===
const defineProperty = (obj, prop, desc) => {{
    try {{
        Object.defineProperty(obj, prop, {{ ...desc, configurable: true }});
    }} catch (e) {{}}
}};

const wrapFn = (original, replacement) => {{
    // Preserve toString to avoid detection
    replacement.toString = () => original.toString();
    Object.defineProperty(replacement, 'name', {{ value: original.name }});
    return replacement;
}};

const wrapGetter = (proto, prop, getter) => {{
    const original = Object.getOwnPropertyDescriptor(proto, prop);
    if (!original?.get) return;
    const wrapped = wrapFn(original.get, getter);
    defineProperty(proto, prop, {{ get: wrapped, enumerable: original.enumerable }});
}};

// === Navigator ===
for (const [k, v] of Object.entries(C.navigator)) {{
    if (k === 'languages') {{
        wrapGetter(Navigator.prototype, k, function() {{ return Object.freeze([...v]); }});
    }} else {{
        wrapGetter(Navigator.prototype, k, function() {{ return v; }});
    }}
}}
// Remove webdriver
delete Object.getPrototypeOf(navigator).webdriver;

// === Screen ===
for (const [k, v] of Object.entries(C.screen)) {{
    wrapGetter(Screen.prototype, k, function() {{ return v; }});
}}

// === Window dimensions ===
for (const [k, v] of Object.entries(C.window)) {{
    defineProperty(window, k, {{ get: () => v, configurable: true }});
}}

// === WebGL ===
const glParams = {{ 37445: C.webgl.vendor, 37446: C.webgl.renderer, 7936: 'WebKit', 7937: 'WebKit WebGL' }};
const patchGL = (proto) => {{
    const orig = proto.getParameter;
    proto.getParameter = wrapFn(orig, function(p) {{
        return glParams[p] ?? orig.call(this, p);
    }});
}};
if (typeof WebGLRenderingContext !== 'undefined') patchGL(WebGLRenderingContext.prototype);
if (typeof WebGL2RenderingContext !== 'undefined') patchGL(WebGL2RenderingContext.prototype);

// === Timezone ===
Date.prototype.getTimezoneOffset = wrapFn(
    Date.prototype.getTimezoneOffset,
    function() {{ return C.timezone.offset; }}
);

// Intl with proper locale
const patchIntl = (Ctor) => {{
    const Orig = Ctor;
    const Patched = function(locales, options) {{
        locales = locales || C.timezone.locale;
        if (Ctor === Intl.DateTimeFormat) {{
            options = {{ ...(options || {{}}), timeZone: options?.timeZone || C.timezone.zone }};
        }}
        return new Orig(locales, options);
    }};
    Patched.prototype = Orig.prototype;
    Patched.supportedLocalesOf = Orig.supportedLocalesOf;

    // Patch resolvedOptions
    const origResolved = Orig.prototype.resolvedOptions;
    Orig.prototype.resolvedOptions = wrapFn(origResolved, function() {{
        const r = origResolved.call(this);
        return {{ ...r, locale: C.timezone.locale, ...(Ctor === Intl.DateTimeFormat ? {{ timeZone: C.timezone.zone }} : {{}}) }};
    }});

    return Patched;
}};
Intl.DateTimeFormat = patchIntl(Intl.DateTimeFormat);
Intl.NumberFormat = patchIntl(Intl.NumberFormat);

// === Media Devices ===
if (navigator.mediaDevices) {{
    const fakeDevices = C.media.devices.map(d => ({{
        deviceId: d.deviceId,
        kind: d.kind,
        label: d.label,
        groupId: d.groupId,
        toJSON() {{ return {{ deviceId: this.deviceId, kind: this.kind, label: this.label, groupId: this.groupId }}; }}
    }}));

    const origEnum = navigator.mediaDevices.enumerateDevices;
    navigator.mediaDevices.enumerateDevices = wrapFn(origEnum, async function() {{
        return fakeDevices;
    }});
}}

// === Canvas noise (subtle, per-session) ===
const canvasSeed = Math.random();
const addNoise = (data, noise) => {{
    for (let i = 0; i < data.length; i += 4) {{
        const n = ((canvasSeed * (i + 1) * 9999) % 1 - 0.5) * noise * 255;
        data[i] = Math.max(0, Math.min(255, data[i] + n | 0));
    }}
}};

const origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
CanvasRenderingContext2D.prototype.getImageData = wrapFn(origGetImageData, function(...args) {{
    const data = origGetImageData.apply(this, args);
    if (C.noise.canvas > 0) addNoise(data.data, C.noise.canvas);
    return data;
}});

const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
HTMLCanvasElement.prototype.toDataURL = wrapFn(origToDataURL, function(...args) {{
    if (C.noise.canvas > 0) {{
        const ctx = this.getContext('2d');
        if (ctx) {{
            const img = ctx.getImageData(0, 0, this.width || 1, this.height || 1);
            addNoise(img.data, C.noise.canvas);
            ctx.putImageData(img, 0, 0);
        }}
    }}
    return origToDataURL.apply(this, args);
}});

// === Audio context noise ===
if (typeof AudioContext !== 'undefined' || typeof webkitAudioContext !== 'undefined') {{
    const AC = typeof AudioContext !== 'undefined' ? AudioContext : webkitAudioContext;
    const origCreateOsc = AC.prototype.createOscillator;
    AC.prototype.createOscillator = wrapFn(origCreateOsc, function() {{
        const osc = origCreateOsc.call(this);
        const origConnect = osc.connect.bind(osc);
        osc.connect = wrapFn(osc.connect, function(dest, ...args) {{
            if (C.noise.audio > 0 && dest instanceof AnalyserNode) {{
                // Add minimal noise to audio fingerprint
                const gain = this.context.createGain();
                gain.gain.value = 1 + (Math.random() - 0.5) * C.noise.audio;
                origConnect(gain);
                gain.connect(dest);
                return dest;
            }}
            return origConnect(dest, ...args);
        }});
        return osc;
    }});
}}

// === WebRTC IP masking ===
if (typeof RTCPeerConnection !== 'undefined') {{
    const OrigRTC = RTCPeerConnection;
    window.RTCPeerConnection = wrapFn(OrigRTC, function(config, ...args) {{
        // Force relay-only ICE (hides local IP)
        config = config || {{}};
        config.iceTransportPolicy = 'relay';
        return new OrigRTC(config, ...args);
    }});
    window.RTCPeerConnection.prototype = OrigRTC.prototype;
}}

// === Clean up automation traces ===
const deleteProps = [
    'cdc_adoQpoasnfa76pfcZLmcfl_Array',
    'cdc_adoQpoasnfa76pfcZLmcfl_Promise',
    'cdc_adoQpoasnfa76pfcZLmcfl_Symbol',
    '__webdriver_evaluate',
    '__selenium_evaluate',
    '__webdriver_script_function',
    '__webdriver_script_func',
    '__webdriver_script_fn',
    '__fxdriver_evaluate',
    '__driver_unwrapped',
    '__webdriver_unwrapped',
    '__driver_evaluate',
    '__selenium_unwrapped',
    '__fxdriver_unwrapped',
    '$chrome_asyncScriptInfo',
    '$cdc_asdjflasutopfhvcZLmcfl_',
];
deleteProps.forEach(p => {{ try {{ delete window[p]; }} catch {{}} }});

// Prevent detection via Error stack
const origError = Error;
window.Error = function(...args) {{
    const err = new origError(...args);
    if (err.stack) {{
        err.stack = err.stack.replace(/\\n.*?(puppeteer|playwright|selenium|webdriver|automation).*?\\n/gi, '\\n');
    }}
    return err;
}};
window.Error.prototype = origError.prototype;

}})();"""


async def apply_stealth(browser: "uc.Browser", profile: "FingerprintProfile") -> None:
    """
    Register stealth script for all pages in this browser.

    Call once at browser start. Each page navigation will need
    apply_stealth_to_page() call as CDP registration is unreliable.
    """
    tabs = browser.tabs
    if not tabs:
        return

    script = build_stealth_script(profile)

    # Register for future documents (may not trigger reliably)
    try:
        await tabs[0].send(cdp.page.add_script_to_evaluate_on_new_document(source=script))
    except Exception:
        pass

    # Apply to initial tab
    await tabs[0].evaluate(script)
    logger.info(f"Stealth initialized: {profile.name}")


async def apply_stealth_to_page(page: "uc.Tab", profile: "FingerprintProfile") -> None:
    """Inject stealth script into page context."""
    script = build_stealth_script(profile)
    try:
        await page.evaluate(script)
    except Exception as e:
        logger.warning(f"Stealth injection failed: {e}")
