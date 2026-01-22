"""Chrome command-line arguments builder.

Builds stealth Chrome launch arguments for maximum antidetect effectiveness.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import FingerprintProfile


class ChromeArgsBuilder:
    """Build Chrome arguments for stealth mode.

    Strategy: Use Chrome flags that make browser behave like real user browser.
    Avoid flags that are detectable or change fingerprint in suspicious ways.

    NOTE: Extensions are NOT handled here - they must be added via
    nodriver's config.add_extension() for proper flag handling.
    """

    def __init__(
        self,
        profile: "FingerprintProfile",
        sandbox: bool = True,
        hide_window: bool = False,
    ) -> None:
        """Initialize builder.

        Args:
            profile: FingerprintProfile for language/screen settings
            sandbox: Use sandbox (set False for Docker/rootless)
            hide_window: Move window off-screen (NOT headless, preserves fingerprint)
        """
        self.profile = profile
        self.sandbox = sandbox
        self.hide_window = hide_window

    def build(self, extra_args: list[str] | None = None) -> list[str]:
        """Build complete Chrome arguments list.

        Args:
            extra_args: Additional custom arguments to append

        Returns:
            List of Chrome command-line arguments
        """
        args = [
            # === CRITICAL: Hide automation markers ===
            "--disable-blink-features=AutomationControlled",

            # === Suppress warnings ===
            "--test-type",
            "--no-default-browser-check",
            "--no-first-run",

            # === Language/locale at browser level ===
            *self._language_args(),

            # === Window size (real browser has this) ===
            *self._window_args(),

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

            # === Disable WebGPU (not supported on most Linux systems) ===
            # Multiple methods to ensure WebGPU is fully disabled
            "--disable-features=WebGPU,WebGPUService,WebGPUExperimentalFeatures,Vulkan",
            "--use-angle=gl",  # Use OpenGL instead of Vulkan (WebGPU needs Vulkan)

            # === Storage: disable encryption for portable sessions ===
            "--password-store=basic",
        ]

        # === Sandbox flags (only for Docker/rootless) ===
        # These cause yellow "unsupported flag" warning!
        if not self.sandbox:
            args.extend(self._docker_args())

        # NOTE: Extensions are NOT added here!
        # They must be added via nodriver's config.add_extension()
        # which properly handles required flags like --enable-unsafe-extension-debugging

        # === Custom args from user ===
        if extra_args:
            args.extend(extra_args)

        return args

    def _language_args(self) -> list[str]:
        """Build language-related arguments."""
        p = self.profile
        lang = p.navigator.languages[0] if p.navigator.languages else "en-US"
        return [
            f"--lang={lang}",
            f"--accept-lang={','.join(p.navigator.languages)}",
        ]

    def _window_args(self) -> list[str]:
        """Build window size arguments."""
        p = self.profile
        args = [f"--window-size={p.screen.width},{p.screen.height}"]

        # Hide window by moving off-screen (NOT headless - preserves fingerprint!)
        if self.hide_window:
            args.append("--window-position=-32000,-32000")

        return args

    def _docker_args(self) -> list[str]:
        """Build Docker/rootless specific arguments."""
        return [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu-sandbox",
        ]
