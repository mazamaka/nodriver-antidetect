"""Antidetect browser wrapper for nodriver.

Key principle: Use CDP-level spoofing where possible, JS injection only for what CDP can't do.
CDP is more reliable because it works at browser level before any page code executes.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import TYPE_CHECKING

import nodriver as uc
import nodriver.cdp as cdp
from loguru import logger

from .config import AntidetectConfig, FingerprintProfile, get_profile
from .profiles import load_profile_from_json
from .stealth import build_stealth_script

if TYPE_CHECKING:
    from .session import SessionManager


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
        sandbox: bool = True,  # Set False for Docker
        session: str | None = None,  # Session name for persistence
        sessions_dir: str | Path | None = None,  # Custom sessions directory
    ) -> None:
        self.config = config or AntidetectConfig()
        self.profile = self._resolve_profile(profile)
        self.proxy = proxy or self.config.proxy_url or None
        self.headless = headless or self.config.headless
        self.browser_args = browser_args or []
        self.sandbox = sandbox  # True = no warning, False = needed for Docker

        self._browser: uc.Browser | None = None

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
            )

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
        """Build Chrome arguments for maximum stealth.

        Strategy: Use Chrome flags that make browser behave like real user browser.
        Avoid flags that are detectable or change fingerprint in suspicious ways.
        """
        p = self.profile
        lang = p.navigator.languages[0] if p.navigator.languages else "en-US"

        args = [
            # === CRITICAL: Hide automation markers ===
            "--disable-blink-features=AutomationControlled",

            # === Suppress warnings ===
            "--test-type",
            "--no-default-browser-check",
            "--no-first-run",

            # === Language/locale at browser level ===
            f"--lang={lang}",
            f"--accept-lang={','.join(p.navigator.languages)}",

            # === Window size (real browser has this) ===
            f"--window-size={p.screen.width},{p.screen.height}",

            # === Disable automation-related features ===
            "--disable-background-networking",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",

            # === Make browser behave more like real ===
            "--disable-ipc-flooding-protection",
            "--disable-hang-monitor",
            "--disable-prompt-on-repost",
            "--disable-sync",

            # === GPU/WebGL - use real hardware ===
            "--enable-webgl",
            "--enable-webgl2",
            "--ignore-gpu-blocklist",

            # Custom args from user
            *self.browser_args,
        ]

        # === Sandbox flags (only for Docker/rootless) ===
        # These cause yellow "unsupported flag" warning!
        if not self.sandbox:
            args.extend([
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
            ])

        return args

    async def start(self) -> "AntidetectBrowser":
        """Start browser with stealth enabled at CDP level."""
        logger.info("Starting antidetect browser...")

        # Lock session if using one
        if self._session_manager and self._session_name:
            if not self._session_manager.lock(self._session_name):
                raise RuntimeError(
                    f"Session '{self._session_name}' is already in use by another browser"
                )

        # Start browser with stealth flags
        self._browser = await uc.start(
            headless=self.headless,
            browser_args=self._build_args(),
            user_data_dir=self._user_data_dir,
        )

        # Apply CDP-level overrides to first tab
        tabs = self._browser.tabs
        if tabs:
            await self._apply_cdp_overrides(tabs[0])

        session_info = f", session={self._session_name}" if self._session_name else ""
        logger.info(f"Browser ready: {self.profile.name}{session_info}")
        return self

    async def _apply_cdp_overrides(self, page: uc.Tab) -> None:
        """Apply browser-level spoofing via CDP (more reliable than JS injection).

        This sets values at browser level BEFORE any page code can check them.
        """
        p = self.profile
        nav = p.navigator
        scr = p.screen
        tz = p.timezone

        # === 1. User-Agent + Client Hints at HTTP level ===
        try:
            # Extract Chrome version for Client Hints
            chrome_version = self._extract_chrome_version(nav.user_agent)
            major_version = chrome_version.split(".")[0] if chrome_version else "132"

            await page.send(
                cdp.network.set_user_agent_override(
                    user_agent=nav.user_agent,
                    accept_language=",".join(nav.languages),
                    platform=nav.platform,
                    user_agent_metadata=cdp.emulation.UserAgentMetadata(
                        platform=self._get_platform_name(nav.platform),
                        platform_version=self._get_platform_version(nav.platform),
                        architecture="x64" if "64" in nav.platform else "x86",
                        model="",
                        mobile=False,
                        brands=[
                            cdp.emulation.UserAgentBrandVersion(brand="Chromium", version=major_version),
                            cdp.emulation.UserAgentBrandVersion(brand="Google Chrome", version=major_version),
                            cdp.emulation.UserAgentBrandVersion(brand="Not-A.Brand", version="24"),
                        ],
                        full_version_list=[
                            cdp.emulation.UserAgentBrandVersion(brand="Chromium", version=chrome_version),
                            cdp.emulation.UserAgentBrandVersion(brand="Google Chrome", version=chrome_version),
                            cdp.emulation.UserAgentBrandVersion(brand="Not-A.Brand", version="24.0.0.0"),
                        ],
                        full_version=chrome_version,
                        bitness="64" if "64" in nav.platform else "32",
                        wow64=False,
                    )
                )
            )
            logger.debug("CDP: User-Agent + Client Hints set")
        except Exception as e:
            logger.debug(f"CDP User-Agent override: {e}")

        # === 2. Device metrics ===
        # NOTE: setDeviceMetricsOverride enables "emulation mode" which can be detected
        # by some antifraud systems. Instead, we use --window-size flag in _build_args()
        # and let the real browser handle screen metrics.
        # Screen values are also spoofed via JS stealth script for consistency.

        # === 3. Timezone at browser level ===
        try:
            await page.send(
                cdp.emulation.set_timezone_override(timezone_id=tz.timezone)
            )
            logger.debug(f"CDP: Timezone set to {tz.timezone}")
        except Exception as e:
            logger.debug(f"CDP Timezone override: {e}")

        # === 4. Locale at browser level ===
        try:
            # Convert locale format: "en-US" -> "en_US"
            locale_id = tz.locale.replace("-", "_")
            await page.send(
                cdp.emulation.set_locale_override(locale=locale_id)
            )
            logger.debug(f"CDP: Locale set to {locale_id}")
        except Exception as e:
            logger.debug(f"CDP Locale override: {e}")

        # === 5. Register stealth script for things CDP can't do ===
        # (WebGL, plugins, window.chrome, canvas noise, etc.)
        try:
            script = build_stealth_script(self.profile)
            await page.send(
                cdp.page.add_script_to_evaluate_on_new_document(source=script)
            )
            # Also inject immediately for current context
            await page.evaluate(script)
            logger.debug("CDP: Stealth script registered")
        except Exception as e:
            logger.debug(f"CDP Stealth script: {e}")

    def _extract_chrome_version(self, user_agent: str) -> str:
        """Extract Chrome version from User-Agent string."""
        match = re.search(r"Chrome/(\d+\.\d+\.\d+\.\d+)", user_agent)
        return match.group(1) if match else "132.0.6834.83"

    def _get_platform_name(self, platform: str) -> str:
        """Get platform name for Client Hints."""
        if "Linux" in platform:
            return "Linux"
        elif "Win" in platform:
            return "Windows"
        elif "Mac" in platform:
            return "macOS"
        return "Linux"

    def _get_platform_version(self, platform: str) -> str:
        """Get platform version for Client Hints."""
        if "Linux" in platform:
            return "6.5.0"  # Realistic Linux kernel version
        elif "Win" in platform:
            return "10.0.0"
        elif "Mac" in platform:
            return "14.0.0"
        return "6.5.0"

    async def stop(self) -> None:
        """Stop browser."""
        if self._browser:
            try:
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
            # Create new tab and apply CDP overrides
            page = await self._browser.get("about:blank", new_tab=True)
            await self._apply_cdp_overrides(page)
        else:
            tabs = self._browser.tabs
            if tabs:
                page = tabs[0]
                # Re-register stealth script for this navigation
                await self._ensure_stealth_registered(page)
            else:
                page = await self._browser.get("about:blank", new_tab=True)
                await self._apply_cdp_overrides(page)

        # Navigate to the actual URL (CDP overrides already active)
        await page.get(url)
        return page

    async def _ensure_stealth_registered(self, page: uc.Tab) -> None:
        """Ensure stealth script is registered for next document load."""
        try:
            script = build_stealth_script(self.profile)
            await page.send(
                cdp.page.add_script_to_evaluate_on_new_document(source=script)
            )
        except Exception as e:
            logger.debug(f"Stealth re-registration: {e}")

    async def new_tab(self, url: str = "about:blank") -> uc.Tab:
        """Open new tab with stealth applied."""
        if not self._browser:
            raise RuntimeError("Browser not started")
        # Use get() to ensure stealth is applied
        return await self.get(url, new_tab=True)

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

    @property
    def session_name(self) -> str | None:
        """Current session name."""
        return self._session_name

    @property
    def session_path(self) -> Path | None:
        """Path to session directory (user_data_dir)."""
        return self._user_data_dir
