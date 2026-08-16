"""Constants for antidetect browser.

Centralized constants to avoid magic numbers throughout the codebase.
"""

# =============================================================================
# Chrome defaults
# =============================================================================
DEFAULT_CHROME_VERSION = "151.0.7922.138"

# =============================================================================
# WebGL parameter codes (from WebGL spec)
# =============================================================================
WEBGL_VENDOR = 7936
WEBGL_RENDERER = 7937
WEBGL_UNMASKED_VENDOR = 37445  # WEBGL_debug_renderer_info extension
WEBGL_UNMASKED_RENDERER = 37446

# =============================================================================
# Screen defaults
# =============================================================================
DEFAULT_SCREEN_WIDTH = 1920
DEFAULT_SCREEN_HEIGHT = 1080
DEFAULT_COLOR_DEPTH = 24
DEFAULT_PIXEL_DEPTH = 24
DEFAULT_DEVICE_PIXEL_RATIO = 1.0

# =============================================================================
# Canvas noise
# =============================================================================
CANVAS_NOISE_MULTIPLIER = 9999  # Seed multiplier for deterministic noise

# =============================================================================
# Default hardware specs
# =============================================================================
DEFAULT_HARDWARE_CONCURRENCY = 8  # CPU cores
DEFAULT_DEVICE_MEMORY = 8  # GB

# =============================================================================
# Platform versions (for Client Hints)
# =============================================================================
LINUX_KERNEL_VERSION = "6.5.0"
WINDOWS_VERSION = "10.0.0"
MACOS_VERSION = "14.0.0"

# =============================================================================
# Timeouts
# =============================================================================
CHROME_VERSION_TIMEOUT = 5  # seconds for chrome --version command

# =============================================================================
# Session
# =============================================================================
SESSION_FLUSH_DELAY = 0.5  # seconds to wait for Chrome to flush data on shutdown
