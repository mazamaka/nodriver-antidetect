"""Antidetect browser wrapper for nodriver."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import nodriver as uc
from loguru import logger

from .config import AntidetectConfig, FingerprintProfile, get_profile
from .profiles import load_profile_from_json
from .stealth import apply_stealth, apply_stealth_to_page

if TYPE_CHECKING:
    pass


class AntidetectBrowser:
    """
    Antidetect browser with stealth fingerprint spoofing.

    Usage:
        async with AntidetectBrowser() as browser:
            page = await browser.get("https://example.com")
    """

    def __init__(
        self,
        profile: FingerprintProfile | str | None = None,
        config: AntidetectConfig | None = None,
        proxy: str | None = None,
        headless: bool = False,
        browser_args: list[str] | None = None,
    ) -> None:
        self.config = config or AntidetectConfig()
        self.profile = self._resolve_profile(profile)
        self.proxy = proxy or self.config.proxy_url or None
        self.headless = headless or self.config.headless
        self.browser_args = browser_args or []

        self._browser: uc.Browser | None = None

    def _resolve_profile(self, profile: FingerprintProfile | str | None) -> FingerprintProfile:
        """Resolve profile from various input types."""
        if profile is None:
            return self.config.to_profile()
        if isinstance(profile, str):
            if profile.endswith(".json") or Path(profile).exists():
                return load_profile_from_json(profile)
            return get_profile(profile)
        return profile

    async def __aenter__(self) -> "AntidetectBrowser":
        await self.start()
        return self

    async def __aexit__(self, *_) -> None:
        await self.stop()

    def _build_args(self) -> list[str]:
        """Build Chrome arguments for stealth."""
        p = self.profile
        return [
            # Core stealth
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",

            # Sandbox (required for Docker)
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",

            # UI
            "--disable-infobars",
            "--disable-extensions",

            # Fingerprint alignment
            f"--lang={p.navigator.languages[0]}",
            f"--window-size={p.screen.width},{p.screen.height}",

            # Custom args
            *self.browser_args,
        ]

    async def start(self) -> "AntidetectBrowser":
        """Start browser with stealth enabled."""
        logger.info("Starting antidetect browser...")

        # Start browser
        self._browser = await uc.start(
            headless=self.headless,
            browser_args=self._build_args(),
        )

        # Initialize stealth
        await apply_stealth(self._browser, self.profile)

        logger.info(f"Browser ready: {self.profile.name}")
        return self

    async def stop(self) -> None:
        """Stop browser."""
        if self._browser:
            try:
                self._browser.stop()
            except Exception as e:
                logger.warning(f"Stop error: {e}")
            finally:
                self._browser = None

    async def get(self, url: str, new_tab: bool = False) -> uc.Tab:
        """Navigate to URL with stealth applied."""
        if not self._browser:
            raise RuntimeError("Browser not started")

        if new_tab:
            page = await self._browser.get(url, new_tab=True)
        else:
            tabs = self._browser.tabs
            page = tabs[0] if tabs else await self._browser.get(url, new_tab=True)
            await page.get(url)

        # Inject stealth (CDP registration doesn't reliably trigger)
        await apply_stealth_to_page(page, self.profile)
        return page

    async def new_tab(self, url: str = "about:blank") -> uc.Tab:
        """Open new tab with stealth."""
        if not self._browser:
            raise RuntimeError("Browser not started")
        return await self._browser.get(url, new_tab=True)

    @property
    def browser(self) -> uc.Browser | None:
        """Underlying nodriver browser."""
        return self._browser

    async def screenshot(self, path: str, page: uc.Tab | None = None) -> None:
        """Take screenshot."""
        if page is None:
            tabs = self._browser.tabs  # sync property
            page = tabs[0] if tabs else None
        if page:
            await page.save_screenshot(path)

    async def wait(self, seconds: float) -> None:
        """Wait helper."""
        await asyncio.sleep(seconds)
