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

if TYPE_CHECKING:
    import nodriver as uc
    from .config import FingerprintProfile


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


def build_stealth_script(profile: "FingerprintProfile") -> str:
    """
    Build stealth script for things CDP cannot do.

    NOTE: UA, timezone, locale are handled by CDP in browser.py
    This script only handles: WebGL, plugins, screen, canvas, media devices, etc.
    """
    scr = profile.screen
    wgl = profile.webgl
    media = profile.media_devices

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

    plugins = _generate_plugins_config()

    config = {
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
            "innerHeight": scr.avail_height - 40,  # Realistic: browser chrome takes space
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
        "plugins": plugins,
    }

    return f"""(function() {{
'use strict';

const C = {json.dumps(config)};

// === Utility: Proper property definition ===
const defineProperty = (obj, prop, desc) => {{
    try {{
        Object.defineProperty(obj, prop, {{ ...desc, configurable: true }});
    }} catch (e) {{}}
}};

// === Utility: Wrap function preserving native appearance ===
const wrapFn = (original, replacement) => {{
    if (!original) return replacement;

    // Match toString exactly
    const origStr = original.toString();
    replacement.toString = function() {{ return origStr; }};

    // Match name
    try {{
        Object.defineProperty(replacement, 'name', {{
            value: original.name,
            configurable: true
        }});
    }} catch (e) {{}}

    // Match length (number of arguments)
    try {{
        Object.defineProperty(replacement, 'length', {{
            value: original.length,
            configurable: true
        }});
    }} catch (e) {{}}

    return replacement;
}};

// === Utility: Wrap getter on prototype ===
const wrapGetter = (proto, prop, getter) => {{
    const desc = Object.getOwnPropertyDescriptor(proto, prop);
    if (!desc?.get) return;

    const wrapped = wrapFn(desc.get, getter);
    defineProperty(proto, prop, {{
        get: wrapped,
        enumerable: desc.enumerable,
        configurable: true
    }});
}};

// === Remove webdriver flag (critical) ===
try {{
    // Delete from prototype
    const proto = Object.getPrototypeOf(navigator);
    if ('webdriver' in proto) {{
        delete proto.webdriver;
    }}
    // Also override getter
    defineProperty(Navigator.prototype, 'webdriver', {{
        get: () => undefined,
        enumerable: true,
        configurable: true
    }});
}} catch (e) {{}}

// === Navigator: pdfViewerEnabled (standard Chrome property) ===
defineProperty(Navigator.prototype, 'pdfViewerEnabled', {{
    get: () => true,
    enumerable: true,
    configurable: true
}});

// === Navigator: Plugins & MimeTypes ===
// These MUST be spoofed via JS as CDP has no API for this
(function() {{
    const createPlugin = (data) => {{
        const plugin = {{}};
        const mimes = [];

        data.mimeTypes.forEach((mt, i) => {{
            const mimeType = {{
                type: mt.type,
                suffixes: mt.suffixes,
                description: mt.description,
                enabledPlugin: plugin
            }};
            mimes.push(mimeType);
            plugin[i] = mimeType;
            plugin[mt.type] = mimeType;
        }});

        Object.defineProperties(plugin, {{
            name: {{ value: data.name, enumerable: true, configurable: true }},
            description: {{ value: data.description, enumerable: true, configurable: true }},
            filename: {{ value: data.filename, enumerable: true, configurable: true }},
            length: {{ value: mimes.length, enumerable: true, configurable: true }},
            item: {{ value: function(i) {{ return this[i] || null; }}, configurable: true }},
            namedItem: {{ value: function(n) {{ return this[n] || null; }}, configurable: true }},
            [Symbol.iterator]: {{ value: function*() {{ for (let i = 0; i < this.length; i++) yield this[i]; }}, configurable: true }}
        }});

        return plugin;
    }};

    const plugins = C.plugins.map(createPlugin);
    const pluginArray = {{}};
    const mimeTypes = {{}};
    let mimeIdx = 0;

    plugins.forEach((p, i) => {{
        pluginArray[i] = p;
        pluginArray[p.name] = p;

        for (let j = 0; j < p.length; j++) {{
            const mt = p[j];
            if (!mimeTypes[mt.type]) {{
                mimeTypes[mt.type] = mt;
                mimeTypes[mimeIdx++] = mt;
            }}
        }}
    }});

    Object.defineProperties(pluginArray, {{
        length: {{ value: plugins.length, enumerable: true, configurable: true }},
        item: {{ value: function(i) {{ return this[i] || null; }}, configurable: true }},
        namedItem: {{ value: function(n) {{ return this[n] || null; }}, configurable: true }},
        refresh: {{ value: function() {{}}, configurable: true }},
        [Symbol.iterator]: {{ value: function*() {{ for (let i = 0; i < this.length; i++) yield this[i]; }}, configurable: true }}
    }});

    Object.defineProperties(mimeTypes, {{
        length: {{ value: mimeIdx, enumerable: true, configurable: true }},
        item: {{ value: function(i) {{ return this[i] || null; }}, configurable: true }},
        namedItem: {{ value: function(n) {{ return this[n] || null; }}, configurable: true }},
        [Symbol.iterator]: {{ value: function*() {{ for (let i = 0; i < this.length; i++) yield this[i]; }}, configurable: true }}
    }});

    defineProperty(Navigator.prototype, 'plugins', {{
        get: function() {{ return pluginArray; }},
        enumerable: true,
        configurable: true
    }});

    defineProperty(Navigator.prototype, 'mimeTypes', {{
        get: function() {{ return mimeTypes; }},
        enumerable: true,
        configurable: true
    }});
}})();

// === Screen properties (CDP setDeviceMetricsOverride is detectable!) ===
for (const [k, v] of Object.entries(C.screen)) {{
    wrapGetter(Screen.prototype, k, function() {{ return v; }});
}}

// === Window dimensions ===
for (const [k, v] of Object.entries(C.window)) {{
    defineProperty(window, k, {{
        get: () => v,
        enumerable: true,
        configurable: true
    }});
}}

// === WebGL vendor/renderer (CDP cannot spoof) ===
const glParams = {{
    37445: C.webgl.vendor,    // UNMASKED_VENDOR_WEBGL
    37446: C.webgl.renderer,  // UNMASKED_RENDERER_WEBGL
    7936: 'WebKit',           // VENDOR (standard)
    7937: 'WebKit WebGL'      // RENDERER (standard)
}};

const patchGL = (proto) => {{
    const orig = proto.getParameter;
    if (!orig) return;

    proto.getParameter = wrapFn(orig, function(param) {{
        const spoofed = glParams[param];
        return spoofed !== undefined ? spoofed : orig.call(this, param);
    }});
}};

if (typeof WebGLRenderingContext !== 'undefined') {{
    patchGL(WebGLRenderingContext.prototype);
}}
if (typeof WebGL2RenderingContext !== 'undefined') {{
    patchGL(WebGL2RenderingContext.prototype);
}}

// === Media Devices (CDP cannot spoof) ===
if (navigator.mediaDevices?.enumerateDevices) {{
    const fakeDevices = C.media.devices.map(d => ({{
        deviceId: d.deviceId,
        kind: d.kind,
        label: d.label,
        groupId: d.groupId,
        toJSON() {{
            return {{
                deviceId: this.deviceId,
                kind: this.kind,
                label: this.label,
                groupId: this.groupId
            }};
        }}
    }}));

    const orig = navigator.mediaDevices.enumerateDevices;
    navigator.mediaDevices.enumerateDevices = wrapFn(orig, async function() {{
        return fakeDevices;
    }});
}}

// === Canvas noise (subtle, deterministic per-session) ===
if (C.noise.canvas > 0) {{
    const seed = Math.random();

    const addNoise = (data, noise) => {{
        for (let i = 0; i < data.length; i += 4) {{
            // Deterministic noise based on position and seed
            const n = ((seed * (i + 1) * 9999) % 1 - 0.5) * noise * 255;
            data[i] = Math.max(0, Math.min(255, data[i] + n | 0));
        }}
    }};

    const origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
    CanvasRenderingContext2D.prototype.getImageData = wrapFn(origGetImageData, function(...args) {{
        const result = origGetImageData.apply(this, args);
        addNoise(result.data, C.noise.canvas);
        return result;
    }});

    const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = wrapFn(origToDataURL, function(...args) {{
        const ctx = this.getContext('2d');
        if (ctx) {{
            try {{
                const img = ctx.getImageData(0, 0, this.width || 1, this.height || 1);
                addNoise(img.data, C.noise.canvas);
                ctx.putImageData(img, 0, 0);
            }} catch (e) {{}}
        }}
        return origToDataURL.apply(this, args);
    }});
}}

// === Battery API (realistic desktop values) ===
if (navigator.getBattery) {{
    const battery = {{
        charging: true,
        chargingTime: 0,
        dischargingTime: Infinity,
        level: 1.0,
        onchargingchange: null,
        onchargingtimechange: null,
        ondischargingtimechange: null,
        onlevelchange: null,
        addEventListener: function() {{}},
        removeEventListener: function() {{}},
        dispatchEvent: function() {{ return true; }}
    }};

    const orig = navigator.getBattery;
    navigator.getBattery = wrapFn(orig, function() {{
        return Promise.resolve(battery);
    }});
}}

// === Network Information API ===
(function() {{
    const connection = {{
        effectiveType: '4g',
        rtt: 100,
        downlink: 1.35,
        saveData: false,
        type: 'wifi',
        onchange: null,
        addEventListener: function() {{}},
        removeEventListener: function() {{}},
        dispatchEvent: function() {{ return true; }}
    }};

    defineProperty(Navigator.prototype, 'connection', {{
        get: function() {{ return connection; }},
        enumerable: true,
        configurable: true
    }});
}})();

// === Permissions API (realistic responses) ===
if (navigator.permissions?.query) {{
    const orig = navigator.permissions.query;
    navigator.permissions.query = wrapFn(orig, function(desc) {{
        // Return 'prompt' for notifications (realistic default)
        if (desc.name === 'notifications') {{
            return Promise.resolve({{ state: 'prompt', onchange: null }});
        }}
        return orig.call(this, desc);
    }});
}}

// === Clean automation traces ===
const automationProps = [
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
    '__nightmare',
    '_phantom',
    '_selenium',
    'callPhantom',
    'domAutomation',
    'domAutomationController'
];

automationProps.forEach(p => {{
    try {{ delete window[p]; }} catch {{}}
}});

try {{
    if (document.$cdc_asdjflasutopfhvcZLmcfl_) {{
        delete document.$cdc_asdjflasutopfhvcZLmcfl_;
    }}
}} catch (e) {{}}

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
