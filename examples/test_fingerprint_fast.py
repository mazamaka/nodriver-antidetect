#!/usr/bin/env python3
"""
Fast fingerprint testing with parallel execution and metric extraction.

Optimizations:
- Wait for specific elements instead of fixed delays
- Extract metrics from DOM instead of just screenshots
- Parallel page loading where possible
- Single full-page screenshot
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from antidetect import AntidetectBrowser, AntidetectConfig
from loguru import logger


async def wait_for_element(page, selector: str, timeout: float = 30.0) -> bool:
    """Wait for element to appear with timeout."""
    start = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start < timeout:
        result = await page.evaluate(f"document.querySelector('{selector}') !== null")
        if result:
            return True
        await asyncio.sleep(0.5)
    return False


async def extract_creepjs_metrics(page) -> dict[str, Any]:
    """Extract comprehensive metrics from CreepJS page (based on ipqs-checker patterns)."""
    import re

    metrics: dict[str, Any] = {
        "fp_id": None,
        "like_headless": None,
        "headless": None,
        "stealth": None,
        "chromium": None,
        "lies_count": None,
        "plugins_count": None,
        "mimetypes_count": None,
        # WebGL
        "webgl_confidence": None,
        "webgl_images": None,
        "webgl_pixels": None,
        "webgl_params": None,
        "webgl_exts": None,
        "gpu_vendor": None,
        "gpu_renderer": None,
        # Screen
        "screen_resolution": None,
        "screen_avail": None,
        "screen_touch": None,
        "screen_depth": None,
        # Other
        "timezone": None,
        "platform": None,
        "cores": None,
        "memory": None,
        "user_agent": None,
    }

    # Wait for FP ID to appear - main indicator that analysis is complete
    logger.debug("Waiting for FP ID (CreepJS analysis completion indicator)...")

    max_wait = 60  # seconds
    start = asyncio.get_event_loop().time()

    while asyncio.get_event_loop().time() - start < max_wait:
        try:
            # Check for FP ID - 64 char hex hash
            fp_check = await page.evaluate("""
            (() => {
                const fpApp = document.getElementById('fp-app');
                if (!fpApp) return null;
                const text = fpApp.innerText || '';
                const match = text.match(/FP ID:\\s*([a-f0-9]{64})/i);
                return match ? match[1] : null;
            })()
            """)

            if fp_check:
                metrics["fp_id"] = fp_check[:16] + "..."
                logger.debug(f"FP ID found: {metrics['fp_id']}")

                # Check if Headless section is loaded (usually last important section)
                headless_check = await page.evaluate("""
                    document.body.innerText.includes('like headless') ||
                    document.body.innerText.includes('% Headless')
                """)

                if headless_check:
                    # Give extra 2s for final render
                    await asyncio.sleep(2)
                    break

        except Exception:
            pass

        await asyncio.sleep(1)

    # Extract all metrics from page text
    try:
        page_text = await page.evaluate("""
        (() => {
            const fpApp = document.getElementById('fp-app');
            return fpApp ? fpApp.innerText : document.body.innerText;
        })()
        """)

        if not page_text:
            logger.warning("No page text found")
            return metrics

        logger.debug(f"Page text length: {len(page_text)}")

        # === HEADLESS DETECTION ===
        headless_section = re.search(
            r'Headless([a-f0-9]*)\s*([\s\S]*?)(?=\d+\.\d+ms\s+Resistance|$)',
            page_text, re.I
        )
        if headless_section:
            h_text = headless_section.group(2)

            # Chromium detection
            chromium = re.search(r'chromium:\s*(true|false)', h_text, re.I)
            if chromium:
                metrics["chromium"] = chromium.group(1).lower() == "true"

            # Like headless %
            like_h = re.search(r'(\d+)%\s*like headless', h_text, re.I)
            if like_h:
                metrics["like_headless"] = like_h.group(1) + "%"

            # Headless %
            headless = re.search(r'(\d+)%\s*headless:', h_text, re.I)
            if headless:
                metrics["headless"] = headless.group(1) + "%"

            # Stealth %
            stealth = re.search(r'(\d+)%\s*stealth:', h_text, re.I)
            if stealth:
                metrics["stealth"] = stealth.group(1) + "%"

        # === WORKER / GPU ===
        worker_section = re.search(
            r'Worker([a-f0-9]+)\s*([\s\S]*?)(?=\d+\.\d+ms\s+WebGL|$)',
            page_text, re.I
        )
        if worker_section:
            w_text = worker_section.group(2)

            # GPU
            gpu = re.search(r'gpu:\s*\n*([^\n]+)\n*([^\n]+)', w_text, re.I)
            if gpu:
                metrics["gpu_vendor"] = gpu.group(1).strip()
                metrics["gpu_renderer"] = gpu.group(2).strip()

            # User Agent
            ua = re.search(r'userAgent:\s*\n*(?:ua reduction\n*)?([^\n]+)', w_text, re.I)
            if ua:
                metrics["user_agent"] = ua.group(1).strip()[:80]

            # Cores and RAM
            cores = re.search(r'cores:\s*(\d+)', w_text, re.I)
            if cores:
                metrics["cores"] = int(cores.group(1))

            ram = re.search(r'ram:\s*(\d+)', w_text, re.I)
            if ram:
                metrics["memory"] = int(ram.group(1))

        # === WebGL ===
        webgl_section = re.search(
            r'WebGL([a-f0-9]*)\s*([\s\S]*?)(?=\d+\.\d+ms\s+Screen|$)',
            page_text, re.I
        )
        if webgl_section:
            wgl_text = webgl_section.group(2)

            # Confidence
            conf = re.search(r'confidence:\s*(\w+)', wgl_text, re.I)
            if conf:
                metrics["webgl_confidence"] = conf.group(1)

            # Images hash
            images = re.search(r'images:\s*([a-f0-9]+)', wgl_text, re.I)
            if images:
                metrics["webgl_images"] = images.group(1)

            # Pixels hash
            pixels = re.search(r'pixels:\s*([a-f0-9]+)', wgl_text, re.I)
            if pixels:
                metrics["webgl_pixels"] = pixels.group(1)

            # Params (count): hash
            params = re.search(r'params\s*\((\d+)\):\s*([a-f0-9]+)', wgl_text, re.I)
            if params:
                metrics["webgl_params"] = f"({params.group(1)}): {params.group(2)}"

            # Exts (count): hash
            exts = re.search(r'exts\s*\((\d+)\):\s*([a-f0-9]+)', wgl_text, re.I)
            if exts:
                metrics["webgl_exts"] = f"({exts.group(1)}): {exts.group(2)}"

            # Backup GPU from WebGL if not found in Worker
            if not metrics["gpu_vendor"]:
                gpu_wgl = re.search(r'gpu:[^\n]*confidence:\s*\w+\s*\n*([^\n]+)\n*([^\n]+)', wgl_text, re.I)
                if gpu_wgl:
                    metrics["gpu_vendor"] = gpu_wgl.group(1).strip()
                    metrics["gpu_renderer"] = gpu_wgl.group(2).strip()

        # === Screen ===
        screen_section = re.search(
            r'Screen([a-f0-9]*)\s*([\s\S]*?)(?=\d+\.\d+ms\s+Canvas|$)',
            page_text, re.I
        )
        if screen_section:
            scr_text = screen_section.group(2)

            # Screen resolution
            screen_res = re.search(r'screen:\s*(\d+\s*x\s*\d+)', scr_text, re.I)
            if screen_res:
                metrics["screen_resolution"] = screen_res.group(1).replace(' ', '')

            # Avail resolution
            avail = re.search(r'avail:\s*(\d+\s*x\s*\d+)', scr_text, re.I)
            if avail:
                metrics["screen_avail"] = avail.group(1).replace(' ', '')

            # Touch
            touch = re.search(r'touch:\s*(\w+)', scr_text, re.I)
            if touch:
                metrics["screen_touch"] = touch.group(1)

            # Depth
            depth = re.search(r'depth:\s*(\d+\|\d+)', scr_text, re.I)
            if depth:
                metrics["screen_depth"] = depth.group(1)

        # === NAVIGATOR ===
        nav_section = re.search(
            r'Navigator([a-f0-9]*)\s*([\s\S]*?)(?=\nStatus[a-f0-9]|$)',
            page_text, re.I
        )
        if nav_section:
            nav_text = nav_section.group(2)

            # Plugins
            plugins = re.search(r'plugins\s*\((\d+)\)', nav_text, re.I)
            if plugins:
                metrics["plugins_count"] = int(plugins.group(1))

            # MimeTypes
            mimes = re.search(r'mimeTypes\s*\((\d+)\)', nav_text, re.I)
            if mimes:
                metrics["mimetypes_count"] = int(mimes.group(1))

            # Platform
            platform = re.search(r'platform:\s*([^\n]+)', nav_text, re.I)
            if platform:
                metrics["platform"] = platform.group(1).strip()

        # === TIMEZONE ===
        tz_section = re.search(
            r'Timezone([a-f0-9]*)\s*([\s\S]*?)(?=\d+\.\d+ms\s+Intl|$)',
            page_text, re.I
        )
        if tz_section:
            tz_lines = tz_section.group(2).split('\n')
            for line in tz_lines:
                line = line.strip()
                if '/' in line and len(line) < 50:  # Likely timezone like "Europe/Budapest"
                    metrics["timezone"] = line
                    break

        # === LIES ===
        lies = re.search(r'lies\s*\((\d+)\)', page_text, re.I)
        if lies and int(lies.group(1)) > 0:
            metrics["lies_count"] = int(lies.group(1))

    except Exception as e:
        metrics["error"] = str(e)
        logger.error(f"Failed to extract CreepJS metrics: {e}")

    return metrics


async def extract_browserleaks_metrics(page, test_type: str) -> dict[str, Any]:
    """Extract metrics from BrowserLeaks page based on test type."""
    metrics = {"type": test_type}

    await asyncio.sleep(2)  # Minimal wait for page load

    try:
        if test_type == "webgl":
            metrics.update(await page.evaluate("""
            (() => {
                const result = {};
                const canvas = document.createElement('canvas');
                const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
                if (gl) {
                    const dbg = gl.getExtension('WEBGL_debug_renderer_info');
                    if (dbg) {
                        result.vendor = gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL);
                        result.renderer = gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL);
                    }
                }
                // Also try to get from page
                const vendorEl = document.querySelector('[data-vendor], .webgl-vendor');
                const rendererEl = document.querySelector('[data-renderer], .webgl-renderer');
                if (vendorEl) result.page_vendor = vendorEl.textContent.trim();
                if (rendererEl) result.page_renderer = rendererEl.textContent.trim();
                return result;
            })()
            """))

        elif test_type == "canvas":
            metrics.update(await page.evaluate("""
            (() => {
                const result = {};
                const hashEl = document.querySelector('.canvas-hash, [data-hash]');
                if (hashEl) result.hash = hashEl.textContent.trim().slice(0, 32);
                return result;
            })()
            """))

        elif test_type == "js":
            metrics.update(await page.evaluate("""
            (() => {
                return {
                    user_agent: navigator.userAgent,
                    platform: navigator.platform,
                    languages: navigator.languages.join(', '),
                    hardware_concurrency: navigator.hardwareConcurrency,
                    device_memory: navigator.deviceMemory,
                    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
                };
            })()
            """))

        elif test_type == "webrtc":
            metrics.update(await page.evaluate("""
            (() => {
                const result = { local_ip: null, public_ip: null };
                const ipEls = document.querySelectorAll('.ip-address, [data-ip]');
                ipEls.forEach(el => {
                    const text = el.textContent;
                    if (text.match(/192\\.168|10\\.|172\\./)) result.local_ip = text.trim();
                    else if (text.match(/\\d+\\.\\d+\\.\\d+\\.\\d+/)) result.public_ip = text.trim();
                });
                return result;
            })()
            """))

    except Exception as e:
        metrics["error"] = str(e)

    return metrics


async def take_full_screenshot(page, path: str) -> None:
    """Take full page screenshot."""
    await page.save_screenshot(path)
    logger.info(f"Screenshot: {path}")


async def test_creepjs_fast(browser: AntidetectBrowser, output_dir: str) -> dict[str, Any]:
    """Fast CreepJS test with metric extraction."""
    logger.info("🔍 Testing CreepJS...")

    page = await browser.get("https://abrahamjuliot.github.io/creepjs/")

    # Extract metrics (this includes waiting)
    metrics = await extract_creepjs_metrics(page)

    # Scroll to top for screenshot (multiple methods for reliability)
    await page.evaluate("window.scrollTo({top: 0, left: 0, behavior: 'instant'})")
    await page.evaluate("document.documentElement.scrollTop = 0")
    await asyncio.sleep(0.3)

    # Take screenshot
    await take_full_screenshot(page, f"{output_dir}/creepjs.png")

    return {"creepjs": metrics}


async def test_browserleaks_fast(browser: AntidetectBrowser, output_dir: str) -> dict[str, Any]:
    """Fast BrowserLeaks tests."""
    logger.info("🔍 Testing BrowserLeaks...")

    tests = [
        ("https://browserleaks.com/javascript", "js"),
        ("https://browserleaks.com/canvas", "canvas"),
        ("https://browserleaks.com/webgl", "webgl"),
    ]

    results = {}

    for url, name in tests:
        page = await browser.get(url)
        await asyncio.sleep(2)  # Minimal wait

        metrics, _ = await asyncio.gather(
            extract_browserleaks_metrics(page, name),
            take_full_screenshot(page, f"{output_dir}/browserleaks_{name}.png")
        )
        results[f"browserleaks_{name}"] = metrics

    return results


async def test_sannysoft_fast(browser: AntidetectBrowser, output_dir: str) -> dict[str, Any]:
    """Fast bot.sannysoft.com test."""
    logger.info("🔍 Testing Sannysoft...")

    page = await browser.get("https://bot.sannysoft.com/")
    await asyncio.sleep(3)

    # Extract test results
    metrics = await page.evaluate("""
    (() => {
        const results = {};
        const rows = document.querySelectorAll('tr');
        rows.forEach(row => {
            const cells = row.querySelectorAll('td');
            if (cells.length >= 2) {
                const name = cells[0].textContent.trim();
                const value = cells[1].textContent.trim();
                const passed = cells[1].classList.contains('passed') ||
                              cells[1].style.backgroundColor === 'green' ||
                              value.toLowerCase().includes('ok');
                results[name] = { value, passed };
            }
        });
        return results;
    })()
    """)

    await take_full_screenshot(page, f"{output_dir}/sannysoft.png")

    return {"sannysoft": metrics}


async def test_pixelscan_fast(browser: AntidetectBrowser, output_dir: str) -> dict[str, Any]:
    """Fast pixelscan.net test."""
    logger.info("🔍 Testing Pixelscan...")

    page = await browser.get("https://pixelscan.net/")
    await asyncio.sleep(5)  # Needs a bit more time

    # Try to get overall score
    metrics = await page.evaluate("""
    (() => {
        const result = { score: null, status: null };
        const scoreEl = document.querySelector('.score, [data-score], .result-score');
        if (scoreEl) result.score = scoreEl.textContent.trim();

        const statusEl = document.querySelector('.status, .result-status');
        if (statusEl) result.status = statusEl.textContent.trim();

        return result;
    })()
    """)

    await take_full_screenshot(page, f"{output_dir}/pixelscan.png")

    return {"pixelscan": metrics}


async def run_fast_tests(output_dir: str = "/output", tests: list[str] | None = None) -> dict[str, Any]:
    """Run optimized fingerprint tests."""
    os.makedirs(output_dir, exist_ok=True)

    all_tests = tests or ["creepjs", "browserleaks", "sannysoft", "pixelscan"]
    results: dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "tests": {}
    }

    config = AntidetectConfig()
    logger.info(f"Config: timezone={config.timezone}, locale={config.locale}")

    start_time = asyncio.get_event_loop().time()

    async with AntidetectBrowser(config=config, sandbox=False) as browser:
        if "creepjs" in all_tests:
            results["tests"].update(await test_creepjs_fast(browser, output_dir))

        if "browserleaks" in all_tests:
            results["tests"].update(await test_browserleaks_fast(browser, output_dir))

        if "sannysoft" in all_tests:
            results["tests"].update(await test_sannysoft_fast(browser, output_dir))

        if "pixelscan" in all_tests:
            results["tests"].update(await test_pixelscan_fast(browser, output_dir))

    elapsed = asyncio.get_event_loop().time() - start_time
    results["elapsed_seconds"] = round(elapsed, 1)

    # Save JSON results
    results_path = f"{output_dir}/results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    logger.info(f"Results saved: {results_path}")

    # Print summary
    print("\n" + "=" * 60)
    print("📊 FINGERPRINT TEST RESULTS")
    print("=" * 60)

    if "creepjs" in results["tests"]:
        creep = results["tests"]["creepjs"]
        if isinstance(creep, dict):
            print(f"\n🔍 CreepJS:")
            print(f"   FP ID:          {creep.get('fp_id', 'N/A')}")
            print(f"   Like Headless:  {creep.get('like_headless', 'N/A')}")
            print(f"   Headless:       {creep.get('headless', 'N/A')}")
            print(f"   Stealth:        {creep.get('stealth', 'N/A')}")
            print(f"   Chromium:       {creep.get('chromium', 'N/A')}")
            print(f"   Lies:           {creep.get('lies_count', 0)}")
            print(f"   Plugins:        {creep.get('plugins_count', 'N/A')}")
            print(f"   MimeTypes:      {creep.get('mimetypes_count', 'N/A')}")
            print(f"\n🎮 WebGL:")
            print(f"   Confidence:     {creep.get('webgl_confidence', 'N/A')}")
            print(f"   Images:         {creep.get('webgl_images', 'N/A')}")
            print(f"   Pixels:         {creep.get('webgl_pixels', 'N/A')}")
            print(f"   Params:         {creep.get('webgl_params', 'N/A')}")
            print(f"   Exts:           {creep.get('webgl_exts', 'N/A')}")
            print(f"   GPU:            {creep.get('gpu_renderer', 'N/A')[:60] if creep.get('gpu_renderer') else 'N/A'}")
            print(f"\n🖥️  Screen:")
            print(f"   Resolution:     {creep.get('screen_resolution', 'N/A')}")
            print(f"   Available:      {creep.get('screen_avail', 'N/A')}")
            print(f"   Touch:          {creep.get('screen_touch', 'N/A')}")
            print(f"   Depth:          {creep.get('screen_depth', 'N/A')}")
            print(f"\n⚙️  System:")
            print(f"   Platform:       {creep.get('platform', 'N/A')}")
            print(f"   Cores/RAM:      {creep.get('cores', 'N/A')} / {creep.get('memory', 'N/A')}GB")
            print(f"   Timezone:       {creep.get('timezone', 'N/A')}")
        else:
            print(f"\n🔍 CreepJS: Unable to parse metrics")

    if "browserleaks_webgl" in results["tests"]:
        webgl = results["tests"]["browserleaks_webgl"]
        print(f"\n🎮 WebGL:")
        print(f"   Vendor:   {webgl.get('vendor', 'N/A')}")
        print(f"   Renderer: {webgl.get('renderer', 'N/A')}")

    if "browserleaks_js" in results["tests"]:
        js = results["tests"]["browserleaks_js"]
        print(f"\n📜 JavaScript:")
        print(f"   Platform:  {js.get('platform', 'N/A')}")
        print(f"   Cores:     {js.get('hardware_concurrency', 'N/A')}")
        print(f"   Memory:    {js.get('device_memory', 'N/A')}GB")
        print(f"   Timezone:  {js.get('timezone', 'N/A')}")

    print(f"\n⏱️  Total time: {results['elapsed_seconds']}s")
    print(f"📁 Screenshots: {output_dir}/")
    print("=" * 60)

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Fast fingerprint testing")
    parser.add_argument(
        "--tests",
        nargs="+",
        choices=["creepjs", "browserleaks", "sannysoft", "pixelscan", "all"],
        default=["all"],
        help="Tests to run",
    )
    parser.add_argument(
        "--output",
        default="/output",
        help="Output directory",
    )

    args = parser.parse_args()

    tests = None if "all" in args.tests else args.tests

    asyncio.run(run_fast_tests(args.output, tests))
