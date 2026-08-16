#!/usr/bin/env python3
"""Fingerprint benchmark: plain nodriver vs AntidetectBrowser.

Runs the same probes against both setups so the numbers can be compared:

    baseline    - nodriver as-is, no profile, no stealth script
    antidetect  - AntidetectBrowser with a fingerprint profile

Probes:
    headers   - local HTTP server, records what Chrome actually sends
    js        - navigator/screen/WebGL in the page AND inside a Worker
    sannysoft - bot.sannysoft.com pass/fail table
    creepjs   - CreepJS headless/stealth percentages
    pixelscan - pixelscan.net bot check verdict + fingerprint report

Usage:
    python tools/benchmark.py --profile macos_chrome
    python tools/benchmark.py --setups antidetect --probes creepjs --output docs/img
"""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import nodriver as uc
import nodriver.cdp as cdp
from loguru import logger

from antidetect import AntidetectBrowser, get_chrome_version, get_profile

# Headers we care about: everything the antidetect layer claims to control.
TRACKED_HEADERS = (
    "user-agent",
    "accept-language",
    "sec-ch-ua",
    "sec-ch-ua-platform",
    "sec-ch-ua-platform-version",
    "sec-ch-ua-mobile",
    "sec-ch-ua-full-version-list",
)

PROBE_PAGE = b"""<!doctype html><html><head><title>probe</title></head>
<body><h1>probe</h1></body></html>"""

# Collected in the main JS context.
JS_AUDIT = """
(async () => {
    const glInfo = () => {
        try {
            const gl = document.createElement('canvas').getContext('webgl');
            const dbg = gl.getExtension('WEBGL_debug_renderer_info');
            return {
                vendor: gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL),
                renderer: gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL),
            };
        } catch (e) { return {vendor: null, renderer: null}; }
    };

    // Same questions asked inside a Worker - detectors compare both answers.
    const workerReport = await new Promise((resolve) => {
        try {
            const src = `self.onmessage = async () => {
                let renderer = null, vendor = null;
                try {
                    const gl = new OffscreenCanvas(1, 1).getContext('webgl');
                    const dbg = gl.getExtension('WEBGL_debug_renderer_info');
                    vendor = gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL);
                    renderer = gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL);
                } catch (e) {}
                postMessage({
                    renderer, vendor,
                    userAgent: navigator.userAgent,
                    platform: navigator.platform,
                    cores: navigator.hardwareConcurrency,
                    memory: navigator.deviceMemory,
                    languages: navigator.languages.join(','),
                    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                });
            }`;
            const w = new Worker(URL.createObjectURL(new Blob([src], {type: 'text/javascript'})));
            const timer = setTimeout(() => resolve({error: 'timeout'}), 5000);
            w.onmessage = (e) => { clearTimeout(timer); w.terminate(); resolve(e.data); };
            w.onerror = (e) => { clearTimeout(timer); resolve({error: String(e.message || e)}); };
            w.postMessage('go');
        } catch (e) { resolve({error: String(e)}); }
    });

    const canvas = document.createElement('canvas');
    canvas.width = 200; canvas.height = 50;
    const ctx = canvas.getContext('2d');
    ctx.textBaseline = 'top';
    ctx.font = '14px Arial';
    ctx.fillText('antidetect benchmark', 2, 2);

    return JSON.stringify({
        page: {
            userAgent: navigator.userAgent,
            platform: navigator.platform,
            languages: navigator.languages.join(','),
            cores: navigator.hardwareConcurrency,
            memory: navigator.deviceMemory,
            maxTouchPoints: navigator.maxTouchPoints,
            webdriver: String(navigator.webdriver),
            webdriverType: (() => {
                const d = Object.getOwnPropertyDescriptor(Navigator.prototype, 'webdriver');
                return d ? (d.get ? 'getter' : 'value') : 'absent';
            })(),
            plugins: navigator.plugins.length,
            pluginsClass: Object.prototype.toString.call(navigator.plugins),
            mimeTypes: navigator.mimeTypes.length,
            screen: `${screen.width}x${screen.height}`,
            screenAvail: `${screen.availWidth}x${screen.availHeight}`,
            colorDepth: screen.colorDepth,
            devicePixelRatio: devicePixelRatio,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
            locale: Intl.DateTimeFormat().resolvedOptions().locale,
            webgpu: typeof navigator.gpu,
            uaDataPlatform: navigator.userAgentData ? navigator.userAgentData.platform : null,
            uaDataBrands: navigator.userAgentData
                ? navigator.userAgentData.brands.map(b => `${b.brand}/${b.version}`).join(' ')
                : null,
            canvasHash: canvas.toDataURL().slice(-32),
            ...glInfo(),
        },
        worker: workerReport,
    });
})()
"""

SANNYSOFT_PARSE = """
(() => {
    const rows = [...document.querySelectorAll('table tr')];
    const out = {passed: 0, failed: 0, failures: [], values: {}};
    for (const row of rows) {
        const cells = row.querySelectorAll('td');
        if (cells.length < 2) continue;
        const name = cells[0].innerText.trim().replace(/\\s+/g, ' ');
        const cell = cells[1];
        const value = cell.innerText.trim().replace(/\\s+/g, ' ').slice(0, 70);
        const cls = cell.className || '';
        if (cls.includes('failed') || cls.includes('warn')) {
            out.failed++; out.failures.push(`${name}: ${value}`);
        } else if (cls.includes('passed')) {
            out.passed++;
        }
        out.values[name] = value;
    }
    return JSON.stringify(out);
})()
"""


class HeaderProbeHandler(BaseHTTPRequestHandler):
    """Records request headers, serves a blank page."""

    captured: dict[str, str] = {}

    def do_GET(self) -> None:  # noqa: N802 - stdlib naming
        HeaderProbeHandler.captured = {
            k.lower(): v for k, v in self.headers.items() if k.lower() in TRACKED_HEADERS
        }
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(PROBE_PAGE)))
        self.end_headers()
        self.wfile.write(PROBE_PAGE)

    def log_message(self, *_args) -> None:
        pass


def in_container() -> bool:
    """Chrome needs --no-sandbox inside Docker."""
    return Path("/.dockerenv").exists()


def default_profile() -> str:
    """Profile matching the host OS - a Linux profile on macOS is inconsistent."""
    return {
        "Darwin": "macos_chrome",
        "Windows": "windows_chrome",
    }.get(platform.system(), "mazamaka_local")


def start_header_server() -> tuple[HTTPServer, str]:
    """Start the local header probe, return (server, url)."""
    server = HTTPServer(("127.0.0.1", 0), HeaderProbeHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    logger.debug("Header probe listening on port {}", port)
    return server, f"http://127.0.0.1:{port}/probe"


async def viewport_screenshot(page, path: Path) -> None:
    """Screenshot the visible viewport, scrolled to the top of the page.

    Used for pages whose hidden nav panels get painted into a full-page capture:
    capture_beyond_viewport re-renders them mid-transition.
    """
    import base64

    await page.evaluate("scrollTo({top: 0, behavior: 'instant'})")
    await asyncio.sleep(0.4)
    data = await page.send(cdp.page.capture_screenshot(format_="png"))
    path.write_bytes(base64.b64decode(data))
    logger.info("Screenshot: {}", path)


async def clip_screenshot(
    page, selector: str, path: Path, padding: int = 12, max_height: int | None = None
) -> bool:
    """Screenshot one element: a CSS selector, or `text:<anchor>` to locate the
    smallest block containing that text.

    Keeps README images readable: no 8000px full-page dumps.
    """
    # Park the pointer in the bottom-left corner: left hovering over a nav bar it
    # opens dropdowns that then land in the screenshot.
    try:
        viewport = await page.evaluate("JSON.stringify([innerWidth, innerHeight])")
        _, view_height = json.loads(viewport)
        await page.send(
            cdp.input_.dispatch_mouse_event(type_="mouseMoved", x=8, y=view_height - 8)
        )
        await asyncio.sleep(0.8)  # let any open dropdown collapse
    except Exception as e:
        logger.debug("Pointer reset skipped: {}", e)

    if selector.startswith("text:"):
        finder = f"""
            const anchor = {json.dumps(selector[5:])};
            const hits = [...document.querySelectorAll('div, section, fieldset')]
                .filter(e => e.textContent.includes(anchor));
            // Deepest match, then walk up until the block is big enough to read.
            let el = hits[hits.length - 1];
            while (el && el.getBoundingClientRect().height < 80 && el.parentElement) {{
                el = el.parentElement;
            }}
        """
    else:
        finder = f"const el = document.querySelector({json.dumps(selector)});"

    # Locate the element, hide any sticky/fixed overlay (capture_beyond_viewport
    # re-renders those on top of the clip), and measure it in document coordinates.
    box = await page.evaluate(
        f"""
        (() => {{
            {finder}
            if (!el) return null;

            // Anything positioned that overlaps the target - sticky headers, open
            // mega-menus, cookie bars - gets painted over the clipped region.
            // Hidden for the shot, restored right after.
            const t = el.getBoundingClientRect();
            const overlaps = (r) => r.width > 0 && r.height > 0
                && r.left < t.right && r.right > t.left
                && r.top < t.bottom && r.bottom > t.top;
            document.querySelectorAll('body *').forEach(node => {{
                if (node.contains(el) || el.contains(node)) return;
                if (getComputedStyle(node).position === 'static') return;
                if (!overlaps(node.getBoundingClientRect())) return;
                node.setAttribute('data-bench-hidden', node.style.visibility || '');
                node.style.visibility = 'hidden';
            }});

            const r = el.getBoundingClientRect();
            // Shrink to the actual content: a grid cell is often as wide as the
            // whole row, which would drag the neighbouring column into frame.
            const kids = [...el.children].map(k => k.getBoundingClientRect())
                                         .filter(b => b.width > 0 && b.height > 0);
            const right = kids.length ? Math.max(...kids.map(b => b.right)) : r.right;
            const bottom = kids.length ? Math.max(...kids.map(b => b.bottom)) : r.bottom;
            return JSON.stringify({{
                x: r.left + scrollX, y: r.top + scrollY,
                w: Math.min(r.width, right - r.left),
                h: Math.min(r.height, bottom - r.top)
            }});
        }})()
        """
    )
    if not box:
        logger.warning("Selector not found for screenshot: {}", selector)
        return False

    b = json.loads(box)
    if b["w"] < 10 or b["h"] < 10:
        logger.warning("Element too small for screenshot: {}", selector)
        return False

    height = min(b["h"], max_height) if max_height else b["h"]

    try:
        data = await page.send(
            cdp.page.capture_screenshot(
                format_="png",
                clip=cdp.page.Viewport(
                    x=max(b["x"] - padding, 0),
                    y=max(b["y"] - padding, 0),
                    width=b["w"] + padding * 2,
                    height=height + padding * 2,
                    scale=1,
                ),
                capture_beyond_viewport=True,
            )
        )
    finally:
        await page.evaluate(
            """
            document.querySelectorAll('[data-bench-hidden]').forEach(node => {
                node.style.visibility = node.getAttribute('data-bench-hidden');
                node.removeAttribute('data-bench-hidden');
            });
            """
        )

    import base64

    path.write_bytes(base64.b64decode(data))
    logger.info("Screenshot: {}", path)
    return True


async def probe_js(page) -> dict[str, Any]:
    """Page + Worker fingerprint surface."""
    raw = await page.evaluate(JS_AUDIT, await_promise=True)
    return json.loads(raw)


async def probe_sannysoft(page, output_dir: Path, tag: str) -> dict[str, Any]:
    await page.get("https://bot.sannysoft.com/")
    await asyncio.sleep(4)
    result = json.loads(await page.evaluate(SANNYSOFT_PARSE))
    await clip_screenshot(page, "table", output_dir / f"sannysoft-{tag}.png")
    return result


PIXELSCAN_BOT_PARSE = """
(() => {
    const text = document.body.innerText;
    const verdict = /You're Definitely a Human/.test(text) ? 'human'
        : /Bot Behavior Detected/.test(text) ? 'bot' : 'unknown';
    const checks = {};
    document.querySelectorAll('div').forEach(d => {
        const m = (d.innerText || '').trim().match(
            /^(Navigator|Webdriver|CDP|User Agent|Plugins|Languages|DoNotTrack|VendorSub|ProductSub)\\n(Detected|Clear)/);
        if (m) checks[m[1]] = m[2];
    });
    return JSON.stringify({verdict, checks, detected: Object.entries(checks)
        .filter(([, v]) => v === 'Detected').map(([k]) => k)});
})()
"""

PIXELSCAN_FP_PARSE = """
(() => {
    // The report is a flat list of "label\\nvalue" pairs.
    const lines = document.body.innerText.split('\\n').map(s => s.trim());
    const pick = (label) => {
        const i = lines.indexOf(label);
        return i === -1 ? null : lines[i + 1];
    };
    return JSON.stringify({
        platform: pick('Platform'),
        do_not_track: pick('DoNotTrack'),
        hardware_concurrency: pick('HardwareConcurency'),
        webgl_vendor: pick('WebGL Vendor'),
        webgl_renderer: pick('WebGL Renderer'),
        webgl_hash: pick('WebGL Hash'),
        canvas_hash: pick('Canvas Hash'),
        audio_hash: pick('AudioContext Hash'),
    });
})()
"""


async def _wait_for_text(page, needles: tuple[str, ...], timeout: float) -> str:
    """Poll page text until one of `needles` shows up (or timeout)."""
    deadline = asyncio.get_event_loop().time() + timeout
    text = ""
    while asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(2)
        text = await page.evaluate("document.body.innerText") or ""
        if any(n in text for n in needles):
            await asyncio.sleep(1.5)
            break
    return text


async def probe_pixelscan(page, output_dir: Path, tag: str) -> dict[str, Any]:
    """pixelscan.net bot detection + fingerprint report."""
    await page.get("https://pixelscan.net/bot-check")
    await _wait_for_text(page, ("Definitely a Human", "Bot Behavior Detected"), timeout=90)
    bot = json.loads(await page.evaluate(PIXELSCAN_BOT_PARSE))
    # Verdict + headline signal cards, as the visitor sees them.
    await viewport_screenshot(page, output_dir / f"pixelscan-bot-{tag}.png")

    await page.get("https://pixelscan.net/fingerprint-check")
    await _wait_for_text(page, ("Canvas Hash", "WebGL Renderer"), timeout=90)
    fingerprint = json.loads(await page.evaluate(PIXELSCAN_FP_PARSE))
    await clip_screenshot(page, "text:HardwareConcurency", output_dir / f"pixelscan-fingerprint-{tag}.png")

    return {"bot_check": bot, "fingerprint_check": fingerprint}


async def probe_creepjs(page, output_dir: Path, tag: str, timeout: float = 90.0) -> dict[str, Any]:
    import re

    await page.get("https://abrahamjuliot.github.io/creepjs/")
    text = await _wait_for_text(page, ("like headless",), timeout=timeout)

    def pct(pattern: str) -> str | None:
        m = re.search(pattern, text, re.I)
        return f"{m.group(1)}%" if m else None

    fp = re.search(r"FP ID:\s*([a-f0-9]{16})", text, re.I)
    lies = re.search(r"lies\s*\((\d+)\)", text, re.I)
    worker_gpu = re.search(r"gpu:\s*\n(.+)\n(.+)", text)

    metrics = {
        "fp_id": fp.group(1) if fp else None,
        "like_headless": pct(r"(\d+)%\s*like headless"),
        "headless": pct(r"(\d+)%\s*headless:"),
        "stealth": pct(r"(\d+)%\s*stealth:"),
        "chromium": bool(re.search(r"chromium:\s*true", text, re.I)),
        "lies": int(lies.group(1)) if lies else 0,
        "worker_gpu": worker_gpu.group(2).strip() if worker_gpu else None,
    }

    # Two sections worth showing: the headless verdict, and the worker section
    # where lang/timezone/GPU are cross-checked against the main context.
    await clip_screenshot(page, "text:like headless", output_dir / f"creepjs-headless-{tag}.png")
    await asyncio.sleep(0.3)
    await clip_screenshot(page, "text:lang/timezone", output_dir / f"creepjs-worker-{tag}.png")
    return metrics


async def run_setup(
    setup: str,
    profile_name: str,
    probes: list[str],
    output_dir: Path,
    header_url: str,
) -> dict[str, Any]:
    """Run all probes against one browser setup."""
    logger.info("=== {} ===", setup)
    loop = asyncio.get_event_loop()
    result: dict[str, Any] = {"setup": setup}

    start = loop.time()
    if setup == "antidetect":
        browser = AntidetectBrowser(profile=profile_name, sandbox=not in_container())
        await browser.start()
        result["profile"] = browser.profile.name
        page = browser.browser.tabs[0]
        get_page = browser.get
        stop = browser.stop
    else:
        raw = await uc.start(config=uc.Config(headless=False, sandbox=not in_container()))
        page = raw.tabs[0]

        async def get_page(url: str):
            return await raw.get(url)

        async def stop() -> None:
            raw.stop()

    result["startup_seconds"] = round(loop.time() - start, 2)

    try:
        if "headers" in probes:
            HeaderProbeHandler.captured = {}
            nav_start = loop.time()
            page = await get_page(header_url)
            result["navigation_seconds"] = round(loop.time() - nav_start, 2)
            await asyncio.sleep(0.4)
            result["headers"] = dict(HeaderProbeHandler.captured)
            if "js" in probes:
                result["js"] = await probe_js(page)
        elif "js" in probes:
            page = await get_page("https://example.com")
            await asyncio.sleep(1)
            result["js"] = await probe_js(page)

        if "sannysoft" in probes:
            result["sannysoft"] = await probe_sannysoft(page, output_dir, setup)
        if "creepjs" in probes:
            result["creepjs"] = await probe_creepjs(page, output_dir, setup)
        if "pixelscan" in probes:
            result["pixelscan"] = await probe_pixelscan(page, output_dir, setup)
    finally:
        await stop()
        await asyncio.sleep(0.5)

    return result


def render_markdown(report: dict[str, Any]) -> str:
    """Human-readable comparison table."""
    setups = report["setups"]
    names = list(setups)
    lines = [
        f"# Fingerprint benchmark — {report['date']}",
        "",
        f"Host: {report['host']} · Chrome {report['chrome_version']} · nodriver {report['nodriver_version']}",
        f"Profile: `{report['profile']}`",
        "",
    ]

    def row(label: str, getter) -> str:
        cells = []
        for name in names:
            try:
                value = getter(setups[name])
            except (KeyError, TypeError, AttributeError):
                value = None
            cells.append(str(value) if value not in (None, "") else "—")
        return f"| {label} | " + " | ".join(cells) + " |"

    if any("js" in s for s in setups.values()):
        lines += [
            "## What the page sees",
            "",
            "| | " + " | ".join(names) + " |",
            "|---|" + "---|" * len(names),
            row("navigator.platform", lambda s: s["js"]["page"]["platform"]),
            row("screen", lambda s: s["js"]["page"]["screen"]),
            row("hardwareConcurrency", lambda s: s["js"]["page"]["cores"]),
            row("deviceMemory", lambda s: s["js"]["page"]["memory"]),
            row("languages", lambda s: s["js"]["page"]["languages"]),
            row("timezone", lambda s: s["js"]["page"]["timezone"]),
            row("WebGL renderer", lambda s: s["js"]["page"]["renderer"]),
            row("WebGL renderer (Worker)", lambda s: s["js"]["worker"].get("renderer")),
            row("navigator.webdriver", lambda s: s["js"]["page"]["webdriver"]),
            row("plugins", lambda s: s["js"]["page"]["plugins"]),
            "",
        ]

    if any("headers" in s for s in setups.values()):
        lines += [
            "## What Chrome sends (HTTP)",
            "",
            "| | " + " | ".join(names) + " |",
            "|---|" + "---|" * len(names),
            row("User-Agent", lambda s: s["headers"].get("user-agent")),
            row("Accept-Language", lambda s: s["headers"].get("accept-language")),
            row("Sec-CH-UA-Platform", lambda s: s["headers"].get("sec-ch-ua-platform")),
            "",
        ]

    if any("creepjs" in s for s in setups.values()):
        lines += [
            "## CreepJS",
            "",
            "| | " + " | ".join(names) + " |",
            "|---|" + "---|" * len(names),
            row("like headless", lambda s: s["creepjs"]["like_headless"]),
            row("headless", lambda s: s["creepjs"]["headless"]),
            row("stealth", lambda s: s["creepjs"]["stealth"]),
            row("lies", lambda s: s["creepjs"]["lies"]),
            "",
        ]

    if any("pixelscan" in s for s in setups.values()):
        lines += [
            "## pixelscan.net",
            "",
            "| | " + " | ".join(names) + " |",
            "|---|" + "---|" * len(names),
            row("bot check", lambda s: s["pixelscan"]["bot_check"]["verdict"]),
            row("flagged signals", lambda s: ", ".join(s["pixelscan"]["bot_check"]["detected"]) or "none"),
            row("reported platform", lambda s: s["pixelscan"]["fingerprint_check"]["platform"]),
            row("reported cores", lambda s: s["pixelscan"]["fingerprint_check"]["hardware_concurrency"]),
            "",
        ]

    if any("sannysoft" in s for s in setups.values()):
        lines += [
            "## bot.sannysoft.com",
            "",
            "| | " + " | ".join(names) + " |",
            "|---|" + "---|" * len(names),
            row("passed", lambda s: s["sannysoft"]["passed"]),
            row("failed", lambda s: s["sannysoft"]["failed"]),
            "",
        ]

    lines += [
        "## Timing",
        "",
        "| | " + " | ".join(names) + " |",
        "|---|" + "---|" * len(names),
        row("browser startup, s", lambda s: s["startup_seconds"]),
        row("first navigation, s", lambda s: s["navigation_seconds"]),
        "",
    ]
    return "\n".join(lines)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--profile",
        default=default_profile(),
        help="fingerprint profile for the antidetect setup (default: matches host OS)",
    )
    parser.add_argument(
        "--setups",
        nargs="+",
        default=["baseline", "antidetect"],
        choices=["baseline", "antidetect"],
    )
    parser.add_argument(
        "--probes",
        nargs="+",
        default=["headers", "js", "sannysoft", "creepjs", "pixelscan"],
        choices=["headers", "js", "sannysoft", "creepjs", "pixelscan"],
    )
    parser.add_argument(
        "--output",
        default="output",
        help="report goes to <output>/benchmark.{md,json}, screenshots to <output>/img/",
    )
    args = parser.parse_args()

    report_dir = Path(args.output)
    output_dir = report_dir / "img"
    output_dir.mkdir(parents=True, exist_ok=True)

    server, header_url = start_header_server()
    report: dict[str, Any] = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "host": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "chrome_version": get_chrome_version(),
        "nodriver_version": getattr(uc, "__version__", "unknown"),
        "profile": args.profile,
        "profile_target": get_profile(args.profile).model_dump(mode="json"),
        "setups": {},
    }

    try:
        for setup in args.setups:
            report["setups"][setup] = await run_setup(
                setup, args.profile, args.probes, output_dir, header_url
            )
    finally:
        server.shutdown()

    (report_dir / "benchmark.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    markdown = render_markdown(report)
    (report_dir / "benchmark.md").write_text(markdown)

    print("\n" + markdown)
    logger.info("Report: {} · screenshots: {}", report_dir / "benchmark.md", output_dir)


if __name__ == "__main__":
    asyncio.run(main())
