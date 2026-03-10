<div align="center">

# nodriver-antidetect

**CDP-level fingerprint spoofing for undetectable browser automation**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-D7FF64.svg)](https://github.com/astral-sh/ruff)
[![Typing: mypy](https://img.shields.io/badge/typing-mypy-blue.svg)](https://mypy-lang.org/)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com/)

Antidetect browser built on top of [nodriver](https://github.com/ultrafunkamsterdam/nodriver) that applies fingerprint spoofing at the **Chrome DevTools Protocol level** -- before any page JavaScript executes. Passes CreepJS, BrowserLeaks, Sannysoft, and Pixelscan with results indistinguishable from a real user browser.

[Quick Start](#quick-start) |
[How It Works](#how-it-works) |
[Features](#what-gets-spoofed) |
[Docker](#docker) |
[API](#api-reference)

</div>

---

## Detection Test Results

Tested against major fingerprint detection services:

| Test Service | Metric | Result | Real Browser |
|:-------------|:-------|:------:|:------------:|
| **CreepJS** | like_headless | 31% | 31% |
| **CreepJS** | headless | 0% | 0% |
| **CreepJS** | stealth | 0% | 0% |
| **CreepJS** | lies detected | 0 | 0 |
| **Sannysoft** | all checks | PASS | PASS |
| **BrowserLeaks** | WebGL confidence | HIGH | HIGH |
| **Pixelscan** | bot detection | PASS | PASS |

## How It Works

Traditional stealth libraries inject JavaScript overrides **after** page load, which is detectable by antifraud systems that check for prototype tampering, native function modifications, or timing discrepancies.

`nodriver-antidetect` takes a fundamentally different approach:

```
                    +------------------+
                    |  JSON Profile    |  Fingerprint configuration
                    +--------+---------+
                             |
                    +--------v---------+
                    | FingerprintProfile|  Pydantic validation
                    +--------+---------+
                             |
              +--------------+--------------+
              |                             |
    +---------v----------+       +----------v---------+
    |   CDP Overrides    |       |   JS Injection     |
    |  (Browser-level)   |       |  (Page-level)      |
    +--------------------+       +--------------------+
    | User-Agent +       |       | WebGL vendor/      |
    |   Client Hints     |       |   renderer         |
    | Timezone           |       | Canvas noise       |
    | Locale             |       | Plugins/MimeTypes  |
    | Color scheme       |       | Screen dimensions  |
    |                    |       | Media devices      |
    |                    |       | Battery, Network   |
    |                    |       | Permissions API    |
    +--------------------+       +--------------------+
              |                             |
              +--+------ Applied BEFORE ----+--+
                 |      page navigation        |
                 v                             v
         +--------------------------------------+
         |          Page sees "real"            |
         |        browser values from           |
         |           the start                  |
         +--------------------------------------+
```

**Key principles:**

1. **CDP-first** -- User-Agent, Client Hints, timezone, and locale are set via Chrome DevTools Protocol (`Network.setUserAgentOverride`, `Emulation.setTimezoneOverride`). These operate at the HTTP header level, before any JavaScript runs.

2. **JS only for what CDP cannot do** -- WebGL parameters, plugins, canvas noise, and media devices require JavaScript, but the script is registered via `Page.addScriptToEvaluateOnNewDocument` so it runs before page code.

3. **Native function preservation** -- All overridden functions preserve their original `toString()` output and prototype chain, preventing lie detection through function signature analysis.

4. **No detectable artifacts** -- Zero debug markers, no `__stealth_applied` flags, no modified prototype chains that CreepJS or similar tools can detect.

## What Gets Spoofed

| Category | Properties | Method | Detection Risk |
|:---------|:-----------|:------:|:--------------:|
| **User-Agent** | UA string, Client Hints (Sec-CH-UA-*), appVersion | CDP | None |
| **Timezone** | Intl.DateTimeFormat, getTimezoneOffset() | CDP | None |
| **Locale** | navigator.language, Accept-Language header | CDP | None |
| **Color Scheme** | prefers-color-scheme media query | CDP | None |
| **WebGL** | UNMASKED_VENDOR/RENDERER, vendor, renderer | JS | Low |
| **Canvas** | toDataURL(), getImageData() with deterministic noise | JS | Low |
| **Audio** | AudioContext with session-stable noise | JS | Low |
| **Screen** | width, height, availWidth, availHeight, colorDepth | JS | Low |
| **Window** | devicePixelRatio, innerWidth, outerWidth | JS | Low |
| **Plugins** | navigator.plugins (5 PDF viewers), mimeTypes | JS | Low |
| **Navigator** | webdriver=false, pdfViewerEnabled, doNotTrack | JS | Low |
| **Media** | enumerateDevices() with realistic device IDs | JS | Low |
| **Battery** | getBattery() returns desktop values (charging, 100%) | JS | Low |
| **Network** | navigator.connection (4g, wifi, 100ms RTT) | JS | Low |
| **Permissions** | permissions.query() realistic responses | JS | Low |
| **WebRTC** | Local IP hidden via iceTransportPolicy: relay | JS | Low |
| **Automation** | cdc_*, __webdriver_*, __selenium_* markers removed | JS | None |

## Quick Start

### Installation

```bash
git clone https://github.com/mazamaka/nodriver-antidetect.git
cd nodriver-antidetect
pip install -r requirements.txt
```

### Basic Usage

```python
import asyncio
from antidetect import AntidetectBrowser

async def main():
    async with AntidetectBrowser() as browser:
        page = await browser.get("https://abrahamjuliot.github.io/creepjs/")
        await browser.wait(30)
        await browser.screenshot("creepjs_result.png")

asyncio.run(main())
```

### With a Fingerprint Profile

```python
# Load profile by name (from profiles/ directory)
async with AntidetectBrowser(profile="windows_chrome") as browser:
    page = await browser.get("https://example.com")

# Load from JSON file
async with AntidetectBrowser(profile="profiles/custom.json") as browser:
    page = await browser.get("https://example.com")

# Programmatic profile
from antidetect import FingerprintProfile
from antidetect.config import NavigatorConfig, ScreenConfig

profile = FingerprintProfile(
    name="custom",
    navigator=NavigatorConfig(platform="Win32", hardware_concurrency=16),
    screen=ScreenConfig(width=2560, height=1440),
)
async with AntidetectBrowser(profile=profile) as browser:
    page = await browser.get("https://example.com")
```

### Persistent Sessions

Sessions preserve cookies, localStorage, and cache across browser restarts:

```python
# First run -- login and save state
async with AntidetectBrowser(session="my_account") as browser:
    page = await browser.get("https://example.com/login")
    # ... perform login ...
    # Cookies saved automatically to ./sessions/my_account/

# Next run -- already logged in
async with AntidetectBrowser(session="my_account") as browser:
    page = await browser.get("https://example.com/dashboard")
```

### With Proxy

```python
async with AntidetectBrowser(proxy="socks5://user:pass@host:port") as browser:
    page = await browser.get("https://httpbin.org/ip")
```

## Docker

### Standard (Xvfb, software rendering)

```bash
docker compose up antidetect
```

### GPU-accelerated (NVIDIA, real WebGL)

```bash
# Headless with real GPU (recommended for production)
docker compose up antidetect-xorg

# Web-accessible via noVNC (http://localhost:6080)
docker compose up antidetect-novnc
```

| Docker Mode | GPU | WebGL Confidence | Requires |
|:------------|:---:|:----------------:|:---------|
| `antidetect` (Xvfb) | Software | LOW | Nothing |
| `antidetect-gpu` (X11) | NVIDIA | HIGH | xhost, display |
| `antidetect-xorg` | NVIDIA | HIGH | privileged |
| `antidetect-novnc` | NVIDIA | HIGH | privileged |

> **Warning:** Never use `AD_HEADLESS=true` -- Chrome's native headless mode is instantly detected by antifraud systems. Use Docker with a virtual display (Xvfb or Xorg) instead.

## Fingerprint Profiles

Profiles are JSON files in `profiles/`:

| Profile | Platform | Screen | GPU |
|:--------|:---------|:-------|:----|
| `mazamaka_local` | Linux x86_64 | 3440x1440 | RTX 3060 |
| `windows_chrome` | Win32 | 1920x1080 | RTX 3080 |
| `macos_chrome` | MacIntel | 2560x1440 | M1 |

### Profile Structure

```json
{
  "name": "my_profile",
  "navigator": {
    "platform": "Linux x86_64",
    "languages": ["en-US", "en"],
    "hardware_concurrency": 8,
    "device_memory": 8
  },
  "screen": {
    "width": 1920, "height": 1080,
    "avail_width": 1920, "avail_height": 1040
  },
  "webgl": {
    "vendor": "Google Inc. (NVIDIA Corporation)",
    "renderer": "ANGLE (NVIDIA Corporation, NVIDIA GeForce RTX 3060/PCIe/SSE2, OpenGL 4.5.0)"
  },
  "timezone": {
    "timezone": "Europe/Berlin",
    "locale": "en-US"
  },
  "canvas_noise": 0.00001,
  "audio_noise": 0.00001
}
```

User-Agent is **generated dynamically** from the installed Chrome version, ensuring consistency between the UA string and the real browser binary.

## API Reference

### AntidetectBrowser

```python
AntidetectBrowser(
    profile: str | FingerprintProfile | None = None,  # Profile name, path, or object
    config: AntidetectConfig | None = None,            # Environment-based config
    proxy: str | None = None,                          # Proxy URL
    headless: bool = False,                            # Headless mode (NOT recommended)
    sandbox: bool = True,                              # Set False for Docker
    session: str | None = None,                        # Session name for persistence
    sessions_dir: str | Path | None = None,            # Sessions directory
    browser_args: list[str] | None = None,             # Extra Chrome flags
)
```

### Methods

| Method | Description |
|:-------|:-----------|
| `await browser.get(url)` | Navigate to URL with stealth applied before load |
| `await browser.get(url, new_tab=True)` | Open URL in new tab |
| `await browser.new_tab(url)` | Open new tab |
| `await browser.screenshot(path)` | Save screenshot |
| `await browser.wait(seconds)` | Async sleep helper |
| `await browser.stop()` | Graceful shutdown (auto on context exit) |

### SessionManager

```python
from antidetect import SessionManager

manager = SessionManager()
sessions = manager.list()                          # List all sessions
manager.clone("session1", "session1_backup")       # Clone session
manager.delete("old_session")                      # Delete session
meta = manager.get_metadata("my_session")          # Get metadata
```

## Environment Variables

| Variable | Default | Description |
|:---------|:--------|:-----------|
| `AD_PROFILE_PATH` | `profiles/mazamaka_local.json` | Path to JSON profile |
| `AD_TIMEZONE` | `Europe/Budapest` | IANA timezone |
| `AD_LOCALE` | `ru` | Browser locale |
| `AD_SCREEN_WIDTH` | `1920` | Screen width |
| `AD_SCREEN_HEIGHT` | `1080` | Screen height |
| `AD_WEBGL_VENDOR` | Google Inc. (NVIDIA) | WebGL vendor string |
| `AD_WEBGL_RENDERER` | ANGLE (NVIDIA...) | WebGL renderer string |
| `AD_USER_AGENT` | *(auto-detected)* | Override User-Agent |
| `AD_HEADLESS` | `false` | Headless mode |
| `PROXY_URL` | - | Proxy URL |

## Project Structure

```
nodriver-antidetect/
├── antidetect/                # Core library
│   ├── __init__.py            # Public API exports
│   ├── browser.py             # AntidetectBrowser (async context manager)
│   ├── cdp_handler.py         # CDP-level overrides (UA, timezone, locale)
│   ├── chrome_args.py         # Stealth Chrome launch arguments
│   ├── config.py              # Pydantic models, Chrome version detection
│   ├── constants.py           # Centralized constants
│   ├── session.py             # Session manager with file locking
│   ├── stealth.py             # JS stealth script builder
│   ├── py.typed               # PEP 561 typing marker
│   ├── js/                    # Modular JavaScript injection scripts
│   │   ├── utils.js           # wrapFn(), defineProperty() helpers
│   │   ├── webdriver.js       # navigator.webdriver = false
│   │   ├── plugins.js         # PluginArray with proper prototype chain
│   │   ├── screen.js          # Screen dimensions override
│   │   ├── webgl.js           # WebGL vendor/renderer spoofing
│   │   ├── canvas.js          # Canvas noise (deterministic per session)
│   │   ├── media.js           # MediaDevices enumeration
│   │   ├── battery.js         # Battery API (desktop values)
│   │   ├── network.js         # Network Information API
│   │   ├── navigator.js       # doNotTrack, globalPrivacyControl
│   │   ├── permissions.js     # Permissions API responses
│   │   └── cleanup.js         # Remove automation markers
│   └── profiles/
│       ├── __init__.py        # Profile utilities, target metrics
│       └── loader.py          # JSON profile load/save
├── profiles/                  # JSON fingerprint profiles
│   ├── mazamaka_local.json    # Linux + RTX 3060
│   ├── windows_chrome.json    # Windows 10 + RTX 3080
│   └── macos_chrome.json      # macOS + Apple GPU
├── examples/                  # Usage examples
│   ├── basic_usage.py         # Simple usage patterns
│   ├── session_example.py     # Session management demo
│   ├── test_fingerprint.py    # CreepJS + BrowserLeaks testing
│   └── test_fingerprint_fast.py  # Optimized test with metric extraction
├── tests/                     # Unit tests
├── Dockerfile                 # Standard Docker (Xvfb)
├── Dockerfile.xorg            # GPU Docker (Xorg + NVIDIA)
├── Dockerfile.novnc           # GPU Docker with web VNC access
├── docker-compose.yml         # All Docker configurations
├── pyproject.toml             # Build config, ruff, mypy
├── requirements.txt           # Python dependencies
├── .env.example               # Environment variable template
└── LICENSE                    # MIT License
```

## Verification

Run the fingerprint test suite against detection services:

```bash
# Quick test (CreepJS only)
python examples/test_fingerprint_fast.py --tests creepjs --output ./output

# Full test suite
python examples/test_fingerprint_fast.py --tests all --output ./output

# Docker
docker compose up antidetect
```

## Known Limitations

| Limitation | Details | Mitigation |
|:-----------|:--------|:-----------|
| **TLS/JA3 fingerprint** | Inherited from Chrome binary, not spoofable | Use matching Chrome version |
| **WebRTC IP leak** | STUN servers may reveal real IP | Use proxy with TURN relay |
| **GPU in Docker** | Software renderer without NVIDIA setup | Use `antidetect-xorg` mode |
| **Canvas noise** | Same seed per session (deterministic) | Different seed per profile |

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Lint
ruff check antidetect/

# Type check
mypy antidetect/ --strict

# Format
ruff format antidetect/
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes with tests
4. Ensure `ruff check` and `mypy --strict` pass
5. Commit (`git commit -m 'feat: add amazing feature'`)
6. Push and open a Pull Request

## License

[MIT](LICENSE)

## Author

**Maksym Babenko**
- GitHub: [@mazamaka](https://github.com/mazamaka)
- Telegram: [@Mazamaka](https://t.me/Mazamaka)

## Acknowledgments

- [nodriver](https://github.com/ultrafunkamsterdam/nodriver) -- async Chrome automation without detection
- [CreepJS](https://github.com/AbrahamJuliot/creepjs) -- the gold standard for fingerprint analysis
