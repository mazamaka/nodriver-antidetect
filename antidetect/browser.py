"""Antidetect browser wrapper for nodriver."""

from __future__ import annotations

import asyncio
from typing import Any

import nodriver as uc
from loguru import logger

from .config import AntidetectConfig, FingerprintProfile, get_profile
from .spoofing import apply_fingerprint_spoofing, generate_fingerprint


class AntidetectBrowser:
    """
    Antidetect browser wrapper for nodriver.

    Provides fingerprint spoofing, proxy support, and stealth capabilities.

    Usage:
        async with AntidetectBrowser() as browser:
            page = await browser.get("https://example.com")
            # ... do stuff
    """

    def __init__(
        self,
        profile: FingerprintProfile | str | None = None,
        config: AntidetectConfig | None = None,
        proxy: str | None = None,
        headless: bool = False,
        browser_args: list[str] | None = None,
    ) -> None:
        """
        Initialize antidetect browser.

        Args:
            profile: Fingerprint profile (FingerprintProfile, profile name, or None for random)
            config: AntidetectConfig from environment variables
            proxy: Proxy URL (socks5://user:pass@host:port)
            headless: Run in headless mode (not recommended for antidetect)
            browser_args: Additional Chrome arguments
        """
        self.config = config or AntidetectConfig()

        # Resolve profile
        if profile is None:
            self.profile = self.config.to_profile()
        elif isinstance(profile, str):
            self.profile = get_profile(profile)
        else:
            self.profile = profile

        # Generate unique fingerprint variations
        self.profile = generate_fingerprint(self.profile)

        # Proxy
        self.proxy = proxy or self.config.proxy_url or None

        # Headless mode
        self.headless = headless or self.config.headless

        # Browser arguments
        self.browser_args = browser_args or []

        # Browser instance
        self._browser: uc.Browser | None = None
        self._main_page: uc.Tab | None = None

    async def __aenter__(self) -> "AntidetectBrowser":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()

    def _build_browser_args(self) -> list[str]:
        """Build Chrome arguments for antidetect."""
        args = [
            # Security
            "--no-sandbox",
            "--disable-setuid-sandbox",

            # Disable automation detection
            "--disable-blink-features=AutomationControlled",

            # GPU and rendering
            "--disable-dev-shm-usage",
            "--disable-gpu-sandbox",

            # Disable infobars
            "--disable-infobars",

            # Disable extensions except useful ones
            "--disable-extensions",

            # Media
            "--use-fake-device-for-media-stream",
            "--use-fake-ui-for-media-stream",

            # Timezone (if set)
            f"--timezone={self.profile.timezone.timezone}",

            # Language
            f"--lang={self.profile.navigator.languages[0]}",

            # Window size
            f"--window-size={self.profile.screen.width},{self.profile.screen.height}",
        ]

        # Add custom args
        args.extend(self.browser_args)

        return args

    async def start(self) -> "AntidetectBrowser":
        """Start the browser."""
        logger.info("Starting antidetect browser...")

        # Prepare browser arguments
        browser_args = self._build_browser_args()

        # Prepare proxy if set
        proxy_config = None
        if self.proxy:
            # Convert socks5:// to socks:// for nodriver
            proxy_url = self.proxy.replace("socks5://", "socks://")
            logger.info(f"Using proxy: {proxy_url[:30]}...")

        # Start browser
        self._browser = await uc.start(
            headless=self.headless,
            browser_args=browser_args,
        )

        # Get main page
        self._main_page = await self._browser.get("about:blank")

        # Apply fingerprint spoofing
        await apply_fingerprint_spoofing(self._main_page, self.profile)

        logger.info(f"Browser started with profile: {self.profile.name}")
        return self

    async def stop(self) -> None:
        """Stop the browser."""
        if self._browser:
            try:
                self._browser.stop()
                logger.info("Browser stopped")
            except Exception as e:
                logger.warning(f"Error stopping browser: {e}")
            finally:
                self._browser = None
                self._main_page = None

    async def get(self, url: str, new_tab: bool = False) -> uc.Tab:
        """
        Navigate to URL.

        Args:
            url: URL to navigate to
            new_tab: Open in new tab

        Returns:
            Page/Tab object
        """
        if not self._browser:
            raise RuntimeError("Browser not started. Call start() first.")

        if new_tab:
            page = await self._browser.get(url, new_tab=True)
            # Apply spoofing to new tab
            await apply_fingerprint_spoofing(page, self.profile)
        else:
            page = await self._main_page.get(url)

        return page

    async def new_page(self) -> uc.Tab:
        """Create new page/tab with fingerprint spoofing applied."""
        if not self._browser:
            raise RuntimeError("Browser not started. Call start() first.")

        page = await self._browser.get("about:blank", new_tab=True)
        await apply_fingerprint_spoofing(page, self.profile)
        return page

    @property
    def browser(self) -> uc.Browser | None:
        """Get underlying nodriver browser instance."""
        return self._browser

    @property
    def main_page(self) -> uc.Tab | None:
        """Get main page/tab."""
        return self._main_page

    async def screenshot(self, path: str) -> None:
        """Take screenshot of main page."""
        if self._main_page:
            await self._main_page.save_screenshot(path)

    async def wait(self, seconds: float) -> None:
        """Wait for specified seconds."""
        await asyncio.sleep(seconds)
