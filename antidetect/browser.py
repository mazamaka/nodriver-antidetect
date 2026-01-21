"""Antidetect browser wrapper for nodriver.

Key principle: Use CDP-level spoofing where possible, JS injection only for what CDP can't do.
CDP is more reliable because it works at browser level before any page code executes.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import nodriver as uc
from loguru import logger

from .cdp_handler import CDPOverridesHandler, ensure_stealth_registered
from .chrome_args import ChromeArgsBuilder
from .config import AntidetectConfig, FingerprintProfile, get_profile
from .profiles import load_profile_from_json

if TYPE_CHECKING:
    from .session import SessionManager


class AntidetectBrowser:
    """
    Antidetect browser with stealth fingerprint spoofing.

    Usage:
        async with AntidetectBrowser() as browser:
            page = await browser.get("https://example.com")

    Args:
        profile: Fingerprint profile. Can be:
            - FingerprintProfile instance
            - Profile name (str) to load from profiles/
            - Path to JSON file (str ending with .json)
            - None to use default profile from config
        config: AntidetectConfig with environment overrides
        proxy: Proxy URL (http://user:pass@host:port)
        headless: Run in headless mode
        browser_args: Additional Chrome arguments
        sandbox: Use sandbox (set False for Docker)
        session: Session name for cookie persistence
        sessions_dir: Custom sessions directory
    """

    def __init__(
        self,
        profile: FingerprintProfile | str | None = None,
        config: AntidetectConfig | None = None,
        proxy: str | None = None,
        headless: bool = False,
        browser_args: list[str] | None = None,
        sandbox: bool = True,
        session: str | None = None,
        sessions_dir: str | Path | None = None,
    ) -> None:
        self.config = config or AntidetectConfig()
        self.profile = self._resolve_profile(profile)
        self.proxy = proxy or self.config.proxy_url or None
        self.headless = headless or self.config.headless
        self.browser_args = browser_args or []
        self.sandbox = sandbox

        self._browser: uc.Browser | None = None

        # CDP and Chrome args handlers
        self._cdp_handler = CDPOverridesHandler(self.profile)
        self._args_builder = ChromeArgsBuilder(self.profile, sandbox)

        # Session management
        self._session_name = session
        self._session_manager: "SessionManager | None" = None
        self._user_data_dir: Path | None = None

        if session:
            from .session import SessionManager

            self._session_manager = SessionManager(sessions_dir)
            self._user_data_dir = self._session_manager.get_or_create(
                session,
                profile_name=self.profile.name if self.profile else None,
                user_agent=self.profile.navigator.user_agent if self.profile else None,
            ).resolve()

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

    async def start(self) -> "AntidetectBrowser":
        """Start browser with stealth enabled at CDP level."""
        logger.info("Starting antidetect browser...")

        # Lock session if using one
        if self._session_manager and self._session_name:
            if not self._session_manager.lock(self._session_name):
                raise RuntimeError(
                    f"Session '{self._session_name}' is already in use by another browser"
                )

        # Build Chrome arguments
        chrome_args = self._args_builder.build(self.browser_args)

        # Start browser with stealth flags
        self._browser = await uc.start(
            headless=self.headless,
            browser_args=chrome_args,
            user_data_dir=self._user_data_dir,
        )

        # Apply CDP-level overrides to first tab
        tabs = self._browser.tabs
        if tabs:
            await self._cdp_handler.apply(tabs[0])

        session_info = f", session={self._session_name}" if self._session_name else ""
        logger.info(f"Browser ready: {self.profile.name}{session_info}")
        return self

    async def stop(self) -> None:
        """Stop browser with graceful shutdown to ensure cookies are saved."""
        if self._browser:
            try:
                # Graceful shutdown: close all tabs first (flushes cookies)
                for tab in self._browser.tabs:
                    try:
                        await tab.close()
                    except Exception:
                        pass

                # Wait for Chrome to flush data to disk
                await asyncio.sleep(0.5)

                # Then stop the browser process
                self._browser.stop()
            except Exception as e:
                logger.warning(f"Stop error: {e}")
            finally:
                self._browser = None

        # Unlock session
        if self._session_manager and self._session_name:
            self._session_manager.unlock(self._session_name)

    async def get(self, url: str, new_tab: bool = False) -> uc.Tab:
        """Navigate to URL with CDP-level stealth applied BEFORE page loads.

        CDP overrides are applied BEFORE navigation so the page sees
        "real" browser values from the start.
        """
        if not self._browser:
            raise RuntimeError("Browser not started")

        if new_tab:
            page = await self._browser.get("about:blank", new_tab=True)
            await self._cdp_handler.apply(page)
        else:
            tabs = self._browser.tabs
            if tabs:
                page = tabs[0]
                await ensure_stealth_registered(page, self.profile)
            else:
                page = await self._browser.get("about:blank", new_tab=True)
                await self._cdp_handler.apply(page)

        await page.get(url)
        return page

    async def new_tab(self, url: str = "about:blank") -> uc.Tab:
        """Open new tab with stealth applied."""
        if not self._browser:
            raise RuntimeError("Browser not started")
        return await self.get(url, new_tab=True)

    @property
    def browser(self) -> uc.Browser | None:
        """Underlying nodriver browser."""
        return self._browser

    async def screenshot(self, path: str, page: uc.Tab | None = None) -> None:
        """Take screenshot."""
        if self._browser is None:
            raise RuntimeError("Browser not started")
        if page is None:
            tabs = self._browser.tabs
            page = tabs[0] if tabs else None
        if page:
            await page.save_screenshot(path)

    async def wait(self, seconds: float) -> None:
        """Wait helper."""
        await asyncio.sleep(seconds)

    @property
    def session_name(self) -> str | None:
        """Current session name."""
        return self._session_name

    @property
    def session_path(self) -> Path | None:
        """Path to session directory (user_data_dir)."""
        return self._user_data_dir
