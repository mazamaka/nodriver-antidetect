#!/usr/bin/env python3
"""Session management example for nodriver-antidetect.

Demonstrates:
1. Creating persistent sessions that save cookies/localStorage
2. Reusing sessions across browser restarts
3. Using SessionManager for advanced session operations
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from antidetect import AntidetectBrowser, SessionManager
from loguru import logger


async def simple_session_example() -> None:
    """Simple usage: just pass session name."""
    logger.info("=== Simple Session Example ===")

    # First run: create session and set cookie
    async with AntidetectBrowser(session="my_session") as browser:
        logger.info(f"Session path: {browser.session_path}")

        # Set a cookie via httpbin
        page = await browser.get("https://httpbin.org/cookies/set?session_test=hello")
        await browser.wait(2)

        # Verify cookie is set
        page = await browser.get("https://httpbin.org/cookies")
        await browser.wait(2)
        await browser.screenshot("output/session_cookies_1.png")
        logger.info("First run: cookie set")

    # Second run: session should persist
    async with AntidetectBrowser(session="my_session") as browser:
        page = await browser.get("https://httpbin.org/cookies")
        await browser.wait(2)
        await browser.screenshot("output/session_cookies_2.png")
        logger.info("Second run: cookies should be preserved")


async def session_with_profile_example() -> None:
    """Session with specific fingerprint profile."""
    logger.info("=== Session + Profile Example ===")

    async with AntidetectBrowser(
        session="work_session",
        profile="windows_chrome",  # Use Windows fingerprint
    ) as browser:
        page = await browser.get("https://bot.sannysoft.com/")
        await browser.wait(5)
        await browser.screenshot("output/session_with_profile.png")
        logger.info("Session with Windows profile created")


async def session_manager_example() -> None:
    """Advanced usage with SessionManager."""
    logger.info("=== SessionManager Example ===")

    manager = SessionManager(base_dir="./sessions")

    # List all sessions
    sessions = manager.list()
    logger.info(f"Available sessions: {[s.name for s in sessions]}")

    # Create session explicitly
    if not manager.exists("managed_session"):
        manager.create(
            "managed_session",
            profile_name="mazamaka_local",
            notes="Created via SessionManager",
        )

    # Get metadata
    meta = manager.get_metadata("managed_session")
    if meta:
        logger.info(f"Session: {meta.name}")
        logger.info(f"  Profile: {meta.profile_name}")
        logger.info(f"  Created: {meta.created_at}")
        logger.info(f"  Last used: {meta.last_used_at}")

    # Clone session
    if not manager.exists("managed_session_backup"):
        manager.clone("managed_session", "managed_session_backup")
        logger.info("Session cloned")

    # Use the session
    async with AntidetectBrowser(session="managed_session") as browser:
        page = await browser.get("https://example.com")
        await browser.wait(2)
        logger.info("Used managed session")


async def session_lock_example() -> None:
    """Demonstrate session locking (one session = one browser)."""
    logger.info("=== Session Lock Example ===")

    manager = SessionManager()

    # Ensure session exists
    if not manager.exists("locked_session"):
        manager.create("locked_session")

    # Check if locked
    logger.info(f"Is locked before: {manager.is_locked('locked_session')}")

    async with AntidetectBrowser(session="locked_session") as browser:
        logger.info(f"Is locked during: {manager.is_locked('locked_session')}")

        # Try to open same session (should fail)
        try:
            async with AntidetectBrowser(session="locked_session") as browser2:
                pass
        except RuntimeError as e:
            logger.info(f"Expected error: {e}")

    logger.info(f"Is locked after: {manager.is_locked('locked_session')}")


async def cleanup_sessions() -> None:
    """Clean up test sessions."""
    manager = SessionManager()

    for name in ["my_session", "work_session", "managed_session",
                 "managed_session_backup", "locked_session"]:
        if manager.exists(name):
            manager.delete(name, force=True)
            logger.info(f"Deleted: {name}")


async def main() -> None:
    """Run all examples."""
    os.makedirs("output", exist_ok=True)

    await simple_session_example()
    await session_with_profile_example()
    await session_manager_example()
    await session_lock_example()

    # Uncomment to clean up
    # await cleanup_sessions()


if __name__ == "__main__":
    asyncio.run(main())
