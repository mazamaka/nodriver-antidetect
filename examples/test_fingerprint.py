#!/usr/bin/env python3
"""
Test fingerprint using CreepJS.

This script opens CreepJS and takes screenshots for fingerprint analysis.
"""

import asyncio
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from antidetect import AntidetectBrowser, AntidetectConfig
from loguru import logger


async def test_fingerprint(output_dir: str = "/output") -> None:
    """Test fingerprint via CreepJS."""

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    logger.info("Starting fingerprint test...")

    # Load config from environment
    config = AntidetectConfig()
    logger.info(f"Config: timezone={config.timezone}, locale={config.locale}")

    async with AntidetectBrowser(config=config, sandbox=False) as browser:
        logger.info("Navigating to CreepJS...")
        page = await browser.get("https://abrahamjuliot.github.io/creepjs/")

        # Wait for analysis to complete
        logger.info("Waiting for CreepJS analysis (45 seconds)...")
        await asyncio.sleep(45)

        # Take screenshots with scroll
        for i in range(5):
            screenshot_path = f"{output_dir}/fingerprint_{i}.png"
            await page.save_screenshot(screenshot_path)
            logger.info(f"Screenshot saved: {screenshot_path}")

            # Scroll down
            await page.scroll_down(500)
            await asyncio.sleep(1)

    logger.info("Fingerprint test completed!")
    logger.info(f"Screenshots saved to: {output_dir}")


async def test_browserleaks(output_dir: str = "/output") -> None:
    """Test fingerprint via BrowserLeaks."""

    os.makedirs(output_dir, exist_ok=True)

    logger.info("Starting BrowserLeaks test...")

    async with AntidetectBrowser() as browser:
        # Test different leak pages
        pages = [
            ("https://browserleaks.com/javascript", "js"),
            ("https://browserleaks.com/canvas", "canvas"),
            ("https://browserleaks.com/webgl", "webgl"),
            ("https://browserleaks.com/webrtc", "webrtc"),
        ]

        for url, name in pages:
            logger.info(f"Testing {name}...")
            page = await browser.get(url)
            await asyncio.sleep(10)

            screenshot_path = f"{output_dir}/browserleaks_{name}.png"
            await page.save_screenshot(screenshot_path)
            logger.info(f"Screenshot: {screenshot_path}")

    logger.info("BrowserLeaks test completed!")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test browser fingerprint")
    parser.add_argument(
        "--test",
        choices=["creepjs", "browserleaks", "all"],
        default="creepjs",
        help="Test to run",
    )
    parser.add_argument(
        "--output",
        default="/output",
        help="Output directory for screenshots",
    )

    args = parser.parse_args()

    if args.test == "creepjs":
        asyncio.run(test_fingerprint(args.output))
    elif args.test == "browserleaks":
        asyncio.run(test_browserleaks(args.output))
    else:
        asyncio.run(test_fingerprint(args.output))
        asyncio.run(test_browserleaks(args.output))
