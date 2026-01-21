# nodriver-antidetect

Antidetect browser based on [nodriver](https://github.com/ultrafunkamsterdam/nodriver) with fingerprint spoofing for Docker environments.

## Features

- **Fingerprint Spoofing**
  - Navigator (platform, userAgent, languages, hardwareConcurrency, deviceMemory)
  - Screen (resolution, colorDepth, devicePixelRatio)
  - WebGL (vendor, renderer)
  - Canvas (noise injection)
  - Audio (noise injection)
  - Timezone & Locale
  - Media Devices (fake camera, microphone, speakers)
  - WebRTC (local IP hiding)

- **Predefined Profiles**
  - `windows_chrome` - Windows 10 + Chrome
  - `macos_chrome` - macOS + Chrome
  - `linux_chrome` - Linux + Chrome

- **Docker Ready**
  - Xvfb for headless display
  - All fonts and dependencies included
  - Non-root user for security

## Quick Start

### Using Docker

```bash
# Build
docker build -t nodriver-antidetect .

# Run fingerprint test
docker run --rm -v $(pwd)/output:/output nodriver-antidetect \
    python /app/examples/test_fingerprint.py --output /output

# Run with custom profile
docker run --rm \
    -e AD_TIMEZONE=America/New_York \
    -e AD_LOCALE=en-US \
    -e AD_SCREEN_WIDTH=2560 \
    -e AD_SCREEN_HEIGHT=1440 \
    -e AD_DEVICE_MEMORY=16 \
    -e AD_HARDWARE_CONCURRENCY=8 \
    -v $(pwd)/output:/output \
    nodriver-antidetect \
    python /app/examples/test_fingerprint.py
```

### Using Docker Compose

```bash
# Run default test
docker-compose up antidetect

# Run Windows profile
docker-compose --profile windows up antidetect-windows
```

### Using as Python Module

```python
import asyncio
from antidetect import AntidetectBrowser

async def main():
    async with AntidetectBrowser() as browser:
        page = await browser.get("https://example.com")
        await page.save_screenshot("screenshot.png")

asyncio.run(main())
```

## Configuration

All settings can be configured via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `AD_TIMEZONE` | `Europe/Berlin` | Timezone (e.g., `America/New_York`) |
| `AD_LOCALE` | `en-US` | Locale for Intl API |
| `AD_SCREEN_WIDTH` | `1920` | Screen width |
| `AD_SCREEN_HEIGHT` | `1080` | Screen height |
| `AD_DEVICE_MEMORY` | `8` | Device memory in GB |
| `AD_HARDWARE_CONCURRENCY` | `8` | CPU cores |
| `AD_PLATFORM` | `Linux x86_64` | Navigator platform |
| `AD_WEBGL_VENDOR` | `Google Inc. (NVIDIA)` | WebGL vendor |
| `AD_WEBGL_RENDERER` | `ANGLE (NVIDIA...)` | WebGL renderer |
| `AD_LANGUAGES` | `en-US,en` | Languages (comma-separated) |
| `AD_USER_AGENT` | auto | Custom user agent |
| `PROXY_URL` | none | Proxy URL (socks5://user:pass@host:port) |

## Fingerprint Testing

Test your fingerprint on these sites:
- [CreepJS](https://abrahamjuliot.github.io/creepjs/)
- [BrowserLeaks](https://browserleaks.com/)
- [Bot Detector](https://bot.sannysoft.com/)
- [Pixelscan](https://pixelscan.net/)

## API Reference

### AntidetectBrowser

```python
from antidetect import AntidetectBrowser, FingerprintProfile

# Default config from environment
browser = AntidetectBrowser()

# With predefined profile
browser = AntidetectBrowser(profile="windows_chrome")

# With custom profile
profile = FingerprintProfile(
    name="custom",
    navigator=NavigatorConfig(
        platform="Win32",
        hardware_concurrency=16,
    ),
)
browser = AntidetectBrowser(profile=profile)

# With proxy
browser = AntidetectBrowser(proxy="socks5://user:pass@host:port")
```

### Methods

```python
async with AntidetectBrowser() as browser:
    # Navigate to URL
    page = await browser.get("https://example.com")

    # Open new tab
    page2 = await browser.new_page()

    # Take screenshot
    await browser.screenshot("screenshot.png")

    # Wait
    await browser.wait(5)
```

## Directory Structure

```
nodriver-antidetect/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── entrypoint.sh
├── antidetect/
│   ├── __init__.py
│   ├── browser.py      # AntidetectBrowser class
│   ├── config.py       # Configuration models
│   └── spoofing.py     # Fingerprint spoofing JS
├── examples/
│   ├── test_fingerprint.py
│   └── basic_usage.py
└── scripts/
```

## Known Limitations

1. **WebRTC IP Leak** - Local IPs are hidden but STUN/TURN servers may reveal real IP. Use a proxy with WebRTC disabled if needed.

2. **Canvas/Audio Noise** - Adding too much noise can make fingerprint suspicious. Default values are conservative.

3. **GPU Rendering** - In Docker, GPU acceleration is limited. WebGL may show software renderer in some tests.

## Comparison with Standard nodriver

| Feature | nodriver | nodriver-antidetect |
|---------|----------|---------------------|
| Headless Detection | ~0% | ~0% |
| Like Headless | 25-45% | <15% |
| Stealth | 0% | 0% |
| Devices | 0 | Fake devices |
| Timezone | UTC | Configurable |
| WebGL | Default | Spoofed |
| Canvas | Default | Noise injected |

## License

MIT

## Credits

- [nodriver](https://github.com/ultrafunkamsterdam/nodriver) - Undetected Chrome automation
- [CreepJS](https://github.com/AbrahamJuliot/creepjs) - Fingerprint testing
