"""CDP-level fingerprint overrides.

Handles User-Agent, Client Hints, Timezone, Locale via Chrome DevTools Protocol.
These are applied BEFORE any page code runs, making them more reliable than JS injection.
"""

from __future__ import annotations

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

    def __init__(self, profile: "FingerprintProfile") -> None:
        """Initialize handler with fingerprint profile.

        Args:
            profile: FingerprintProfile with spoofing values
        """
        self.profile = profile

    async def apply(self, page: "uc.Tab") -> None:
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
        await self._apply_stealth_script(page)

    async def _enable_page_domain(self, page: "uc.Tab") -> None:
        """Enable Page domain - required for script injection on navigation."""
        try:
            await page.send(cdp.page.enable())
            logger.debug("CDP: Page domain enabled")
        except Exception as e:
            logger.debug(f"CDP Page.enable: {e}")

    async def _apply_user_agent(self, page: "uc.Tab") -> None:
        """Set User-Agent and Client Hints via CDP."""
        from .config import get_chrome_version

        nav = self.profile.navigator

        try:
            # Get FULL Chrome version for Client Hints (userAgentData)
            # userAgent string uses reduced version (144.0.0.0)
            # but userAgentData shows full version (144.0.7559.59)
            full_chrome_version = get_chrome_version()
            major_version = full_chrome_version.split(".")[0] if full_chrome_version else "144"

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
                            cdp.emulation.UserAgentBrandVersion(brand="Chromium", version=major_version),
                            cdp.emulation.UserAgentBrandVersion(brand="Google Chrome", version=major_version),
                            cdp.emulation.UserAgentBrandVersion(brand="Not-A.Brand", version="24"),
                        ],
                        full_version_list=[
                            cdp.emulation.UserAgentBrandVersion(brand="Chromium", version=full_chrome_version),
                            cdp.emulation.UserAgentBrandVersion(brand="Google Chrome", version=full_chrome_version),
                            cdp.emulation.UserAgentBrandVersion(brand="Not-A.Brand", version="24.0.0.0"),
                        ],
                        full_version=full_chrome_version,
                        bitness="64" if "64" in nav.platform else "32",
                        wow64=False,
                    )
                )
            )
            logger.debug("CDP: User-Agent + Client Hints set")
        except Exception as e:
            logger.debug(f"CDP User-Agent override: {e}")

    async def _apply_timezone(self, page: "uc.Tab") -> None:
        """Set timezone via CDP."""
        try:
            await page.send(
                cdp.emulation.set_timezone_override(timezone_id=self.profile.timezone.timezone)
            )
            logger.debug(f"CDP: Timezone set to {self.profile.timezone.timezone}")
        except Exception as e:
            logger.debug(f"CDP Timezone override: {e}")

    async def _apply_locale(self, page: "uc.Tab") -> None:
        """Set locale via CDP."""
        try:
            # Convert locale format: "en-US" -> "en_US"
            locale_id = self.profile.timezone.locale.replace("-", "_")
            await page.send(
                cdp.emulation.set_locale_override(locale=locale_id)
            )
            logger.debug(f"CDP: Locale set to {locale_id}")
        except Exception as e:
            logger.debug(f"CDP Locale override: {e}")

    async def _apply_color_scheme(self, page: "uc.Tab") -> None:
        """Set prefers-color-scheme to dark via CDP.

        Real browsers typically have dark scheme. CreepJS checks this
        as 'prefersLightColor' - should be false for real browser.
        """
        try:
            await page.send(
                cdp.emulation.set_emulated_media(
                    features=[
                        cdp.emulation.MediaFeature(name="prefers-color-scheme", value="dark")
                    ]
                )
            )
            logger.debug("CDP: Color scheme set to dark")
        except Exception as e:
            logger.debug(f"CDP Color scheme override: {e}")

    async def _apply_stealth_script(self, page: "uc.Tab") -> None:
        """Register stealth script for things CDP can't do.

        This handles: WebGL, plugins, canvas noise, media devices, etc.
        """
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


async def ensure_stealth_registered(page: "uc.Tab", profile: "FingerprintProfile") -> None:
    """Ensure stealth script is registered for next document load.

    Args:
        page: Browser tab
        profile: FingerprintProfile for stealth script
    """
    try:
        script = build_stealth_script(profile)
        await page.send(
            cdp.page.add_script_to_evaluate_on_new_document(source=script)
        )
    except Exception as e:
        logger.debug(f"Stealth re-registration: {e}")
