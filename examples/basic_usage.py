#!/usr/bin/env python3
"""
Basic usage example for nodriver-antidetect.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from antidetect import AntidetectBrowser, FingerprintProfile, get_profile, list_available_profiles
from antidetect.config import NavigatorConfig, ScreenConfig, TimezoneConfig
from loguru import logger


async def basic_example() -> None:
    """Basic usage with default settings."""
    async with AntidetectBrowser() as browser:
        page = await browser.get("https://httpbin.org/headers")
        await asyncio.sleep(2)
        await browser.screenshot("/output/basic_example.png")
        logger.info("Basic example completed!")


async def custom_profile_example() -> None:
    """Usage with custom fingerprint profile."""

    # Create custom profile programmatically
    profile = FingerprintProfile(
        name="custom",
        navigator=NavigatorConfig(
            platform="Win32",
            hardware_concurrency=16,
            device_memory=32,
            languages=["en-US", "en", "de"],
        ),
        screen=ScreenConfig(
            width=2560,
            height=1440,
        ),
        timezone=TimezoneConfig(
            timezone="America/New_York",
            locale="en-US",
            offset=300,
        ),
    )

    async with AntidetectBrowser(profile=profile) as browser:
        page = await browser.get("https://www.whatismybrowser.com/")
        await asyncio.sleep(3)
        await browser.screenshot("/output/custom_profile.png")
        logger.info("Custom profile example completed!")


async def json_profile_example() -> None:
    """Usage with JSON profile from profiles/ directory."""

    # List available profiles
    profiles = list_available_profiles()
    logger.info(f"Available profiles: {profiles}")

    # Load and use a profile by name
    async with AntidetectBrowser(profile="windows_chrome") as browser:
        page = await browser.get("https://bot.sannysoft.com/")
        await asyncio.sleep(5)
        await browser.screenshot("/output/windows_chrome.png")
        logger.info("JSON profile example completed!")


async def proxy_example() -> None:
    """Usage with proxy."""
    proxy_url = os.environ.get("PROXY_URL")

    if not proxy_url:
        logger.warning("PROXY_URL not set, skipping proxy example")
        return

    async with AntidetectBrowser(proxy=proxy_url) as browser:
        page = await browser.get("https://httpbin.org/ip")
        await asyncio.sleep(2)
        await browser.screenshot("/output/proxy_example.png")
        logger.info("Proxy example completed!")


async def main() -> None:
    """Run all examples."""
    os.makedirs("/output", exist_ok=True)

    await basic_example()
    await custom_profile_example()
    await json_profile_example()
    await proxy_example()


if __name__ == "__main__":
    asyncio.run(main())
