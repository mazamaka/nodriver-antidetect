"""CDP-level fingerprint overrides.

Handles User-Agent, Client Hints, Timezone, Locale via Chrome DevTools Protocol.
These are applied BEFORE any page code runs, making them more reliable than JS injection.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import nodriver.cdp as cdp
from loguru import logger

from .constants import MACOS_VERSION, WINDOWS_VERSION
from .stealth import build_stealth_script

if TYPE_CHECKING:
    import nodriver as uc

    from .config import FingerprintProfile


class CDPOverridesHandler:
    """Apply browser-level spoofing via Chrome DevTools Protocol.

    CDP overrides are more reliable than JS injection because they work
    at browser level before any page code executes.
    """

    def __init__(self, profile: FingerprintProfile) -> None:
        """Initialize handler with fingerprint profile.

        Args:
            profile: FingerprintProfile with spoofing values
        """
        self.profile = profile
        # Targets where the stealth script is already registered.
        # Re-registering would run the script once per registration on every load.
        self._registered: set[str] = set()

    async def apply(self, page: uc.Tab) -> None:
        """Apply all CDP overrides to a page.

        Args:
            page: Browser tab to apply overrides to
        """
        # Enable Page domain first - required for add_script_to_evaluate_on_new_document
        await self._enable_page_domain(page)
        await self._apply_user_agent(page)
        await self._apply_timezone(page)
        await self._apply_locale(page)
        await self._apply_color_scheme(page)
        await self._apply_device_metrics(page)
        await self._apply_hardware(page)
        await self._apply_stealth_script(page)

    async def ensure_registered(self, page: uc.Tab) -> None:
        """Register the stealth script on a tab unless it already is."""
        if str(page.target.target_id) in self._registered:
            return
        await self._apply_stealth_script(page)

    async def _enable_page_domain(self, page: uc.Tab) -> None:
        """Enable Page domain - required for script injection on navigation."""
        try:
            await page.send(cdp.page.enable())
            logger.debug("CDP: Page domain enabled")
        except Exception as e:
            logger.debug(f"CDP Page.enable: {e}")

    async def _apply_user_agent(self, page: uc.Tab) -> None:
        """Set User-Agent and Client Hints via CDP."""
        from .config import get_chrome_version

        nav = self.profile.navigator

        try:
            # Get FULL Chrome version for Client Hints (userAgentData)
            # userAgent string uses reduced version (144.0.0.0)
            # but userAgentData shows full version (144.0.7559.59)
            full_chrome_version = get_chrome_version()
            major_version = full_chrome_version.split(".")[0]
            brands = await self._brand_list(page, major_version)

            await page.send(
                cdp.network.set_user_agent_override(
                    user_agent=nav.user_agent,  # This has reduced version
                    accept_language=",".join(nav.languages),
                    platform=nav.platform,
                    user_agent_metadata=cdp.emulation.UserAgentMetadata(
                        platform=self._get_platform_name(nav.platform),
                        platform_version=self._get_platform_version(nav.platform),
                        architecture="x86",  # Always x86, bitness indicates 32/64
                        model="",
                        mobile=False,
                        brands=[
                            cdp.emulation.UserAgentBrandVersion(brand=brand, version=version)
                            for brand, version in brands
                        ],
                        full_version_list=[
                            cdp.emulation.UserAgentBrandVersion(
                                brand=brand,
                                version=full_chrome_version if version == major_version else f"{version}.0.0.0",
                            )
                            for brand, version in brands
                        ],
                        full_version=full_chrome_version,
                        bitness="64" if "64" in nav.platform else "32",
                        wow64=False,
                    ),
                )
            )
            logger.debug("CDP: User-Agent + Client Hints set")
        except Exception as e:
            logger.debug(f"CDP User-Agent override: {e}")


    async def _brand_list(self, page: uc.Tab, major_version: str) -> list[tuple[str, str]]:
        """Brand list for Client Hints, reusing Chrome's own GREASE entry.

        Chrome randomises the fake brand ("Not=A?Brand";v="99" and friends) per
        release; a hardcoded one from an older Chrome is a giveaway. We read what
        this Chrome really sends and only fix up the versions.
        """
        fallback = [("Chromium", major_version), ("Google Chrome", major_version)]
        try:
            raw = await page.evaluate(
                "JSON.stringify((navigator.userAgentData?.brands || [])"
                ".map(b => [b.brand, b.version]))"
            )
            real = json.loads(raw) if raw else []
        except Exception as e:
            logger.debug(f"Client Hints brands read failed: {e}")
            return fallback

        if not real:
            return fallback
        # Keep Chrome's order and GREASE brand, restamp the real browser brands.
        known = ("Chromium", "Google Chrome")
        return [(brand, major_version if brand in known else version) for brand, version in real]

    async def _apply_timezone(self, page: uc.Tab) -> None:
        """Set timezone via CDP."""
        try:
            await page.send(
                cdp.emulation.set_timezone_override(timezone_id=self.profile.timezone.timezone)
            )
            logger.debug(f"CDP: Timezone set to {self.profile.timezone.timezone}")
        except Exception as e:
            logger.debug(f"CDP Timezone override: {e}")

    async def _apply_locale(self, page: uc.Tab) -> None:
        """Set locale via CDP."""
        try:
            # Convert locale format: "en-US" -> "en_US"
            locale_id = self.profile.timezone.locale.replace("-", "_")
            await page.send(cdp.emulation.set_locale_override(locale=locale_id))
            logger.debug(f"CDP: Locale set to {locale_id}")
        except Exception as e:
            logger.debug(f"CDP Locale override: {e}")

    async def _apply_color_scheme(self, page: uc.Tab) -> None:
        """Set prefers-color-scheme to dark via CDP.

        Real browsers typically have dark scheme. CreepJS checks this
        as 'prefersLightColor' - should be false for real browser.
        """
        try:
            await page.send(
                cdp.emulation.set_emulated_media(
                    features=[cdp.emulation.MediaFeature(name="prefers-color-scheme", value="dark")]
                )
            )
            logger.debug("CDP: Color scheme set to dark")
        except Exception as e:
            logger.debug(f"CDP Color scheme override: {e}")

    async def _apply_device_metrics(self, page: uc.Tab) -> None:
        """Spoof screen.* at browser level.

        width/height/deviceScaleFactor = 0 leave the viewport override disabled,
        so window.inner*/devicePixelRatio keep reporting the real window and CSS
        media queries stay consistent with them. Only screen.* is overridden, and
        the Screen getters stay native - nothing for a detector to notice.
        """
        scr = self.profile.screen
        try:
            await page.send(
                cdp.emulation.set_device_metrics_override(
                    width=0,
                    height=0,
                    device_scale_factor=0,
                    mobile=False,
                    screen_width=scr.width,
                    screen_height=scr.height,
                )
            )
            logger.debug(f"CDP: Screen set to {scr.width}x{scr.height}")
        except Exception as e:
            logger.debug(f"CDP device metrics override: {e}")

    async def _apply_hardware(self, page: uc.Tab) -> None:
        """Spoof hardwareConcurrency and maxTouchPoints at browser level."""
        nav = self.profile.navigator
        try:
            await page.send(
                cdp.emulation.set_hardware_concurrency_override(
                    hardware_concurrency=nav.hardware_concurrency
                )
            )
            logger.debug(f"CDP: hardwareConcurrency set to {nav.hardware_concurrency}")
        except Exception as e:
            logger.debug(f"CDP hardwareConcurrency override: {e}")

        try:
            await page.send(
                cdp.emulation.set_touch_emulation_enabled(
                    enabled=nav.max_touch_points > 0,
                    max_touch_points=nav.max_touch_points or None,
                )
            )
        except Exception as e:
            logger.debug(f"CDP touch emulation: {e}")

    async def _apply_stealth_script(self, page: uc.Tab) -> None:
        """Register stealth script for things CDP can't do.

        This handles: WebGL, plugins, canvas noise, media devices, etc.
        """
        try:
            script = build_stealth_script(self.profile)
            # Page.enable is REQUIRED: without it addScriptToEvaluateOnNewDocument
            # returns an identifier but the script is never injected.
            await page.send(cdp.page.enable())
            await page.send(cdp.page.add_script_to_evaluate_on_new_document(source=script))
            self._registered.add(str(page.target.target_id))
            # Also inject immediately for current context
            await page.evaluate(script)
            logger.debug("CDP: Stealth script registered")
        except Exception as e:
            logger.debug(f"CDP Stealth script: {e}")

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
        """Get platform version for Client Hints.

        Note: On Linux, Chrome returns empty string for platformVersion.
        Only Windows/macOS have meaningful platform versions.
        """
        if "Linux" in platform:
            return ""  # Chrome on Linux returns empty platformVersion
        elif "Win" in platform:
            return WINDOWS_VERSION
        elif "Mac" in platform:
            return MACOS_VERSION
        return ""
