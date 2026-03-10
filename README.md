# nodriver-antidetect

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Antidetect browser based on [nodriver](https://github.com/ultrafunkamsterdam/nodriver) with CDP-level fingerprint spoofing.

**Version: 2.6.0**

## CreepJS Results

| Metric | Result | Target |
|--------|--------|--------|
| like_headless | 31% | ≤31% ✅ |
| headless | 0% | 0% ✅ |
| stealth | 0% | 0% ✅ |
| plugins | 5 | 5 ✅ |
| mimeTypes | 2 | 2 ✅ |

## Spoofing Architecture

**Principle:** CDP-level where possible, JS only for what CDP doesn't support.

| Layer | Spoofed | Method |
|-------|---------|--------|
| HTTP | User-Agent, Client Hints | `Network.setUserAgentOverride` |
| Browser | Timezone, Locale | `Emulation.setTimezone/LocaleOverride` |
| Chrome flags | Window size, Language | `--window-size`, `--lang` |
| JS | Plugins, WebGL, Canvas | Stealth script |

### Dynamic User-Agent

User-Agent is generated **automatically** based on the installed Chrome version:

```
Real Chrome: 144.0.7559.59
       ↓
User-Agent: Mozilla/5.0 ... Chrome/144.0.7559.59 Safari/537.36
Client Hints: brands=[Chrome/144, ...]
```

This ensures consistency between UA and the real browser even after Chrome updates.

## Quick Start

### Locally (without Docker)

```python
import asyncio
from antidetect import AntidetectBrowser

async def main():
    # By default sandbox=True (no yellow banner)
    async with AntidetectBrowser() as browser:
        page = await browser.get("https://example.com")
        await browser.screenshot("screenshot.png")

asyncio.run(main())
```

### Docker

```python
# In Docker use sandbox=False
async with AntidetectBrowser(sandbox=False) as browser:
    page = await browser.get("https://example.com")
```

```bash
# Build
docker build -t nodriver-antidetect .

# Run
docker run --rm -v $(pwd)/output:/output nodriver-antidetect
```

### With JSON Profile

```python
# Load profile by name
async with AntidetectBrowser(profile="windows_chrome") as browser:
    ...

# Load from file
async with AntidetectBrowser(profile="profiles/custom.json") as browser:
    ...
```

### With Session (persistent cookies/localStorage)

```python
# Session persists cookies, localStorage, cache between runs
async with AntidetectBrowser(session="my_session") as browser:
    page = await browser.get("https://example.com/login")
    # ... login ...
    # Cookies are automatically saved to ./sessions/my_session/

# Next run will already be logged in!
async with AntidetectBrowser(session="my_session") as browser:
    page = await browser.get("https://example.com")
```

### With Chrome Extensions

```python
# Load unpacked extension
async with AntidetectBrowser(extensions=["./extensions/ublock"]) as browser:
    page = await browser.get("https://example.com")

# Multiple extensions
async with AntidetectBrowser(
    extensions=[
        "./extensions/ublock",
        "./extensions/metamask",
    ]
) as browser:
    ...
```

**Extension requirements:**
- Extension must be unpacked (folder with `manifest.json`)
- Supports Manifest V2 and V3

### SessionManager (advanced management)

```python
from antidetect import SessionManager

manager = SessionManager()

# List sessions
sessions = manager.list()

# Clone session
manager.clone("session1", "session1_backup")

# Delete session
manager.delete("old_session")
```

## Profiles

Profiles are stored in `profiles/*.json`:

- `mazamaka_local.json` — default profile (Linux, Chrome 144)
- `windows_chrome.json` — Windows 10 + Chrome
- `macos_chrome.json` — macOS + Chrome

### Profile Structure

```json
{
  "name": "my_profile",
  "navigator": {
    "platform": "Linux x86_64",
    "user_agent": "Mozilla/5.0 ...",
    "languages": ["ru", "en-US", "en"],
    "hardware_concurrency": 12,
    "device_memory": 8
  },
  "screen": {
    "width": 3440,
    "height": 1440,
    "avail_width": 3374,
    "avail_height": 1408
  },
  "webgl": {
    "vendor": "Google Inc. (NVIDIA Corporation)",
    "renderer": "ANGLE (NVIDIA GeForce RTX 3060...)"
  },
  "timezone": {
    "timezone": "Europe/Budapest",
    "locale": "ru",
    "offset": -60
  }
}
```

## API Reference

### AntidetectBrowser

```python
AntidetectBrowser(
    profile: str | FingerprintProfile | None = None,  # Fingerprint profile
    proxy: str | None = None,                          # Proxy URL
    headless: bool = False,                            # Headless mode
    sandbox: bool = True,                              # False for Docker
    session: str | None = None,                        # Session name for persistence
    sessions_dir: str | Path | None = None,            # Sessions directory (default: ./sessions)
    browser_args: list[str] | None = None,             # Additional Chrome arguments
    extensions: list[str | Path] | None = None,        # Chrome extension paths
)
```

### Methods

```python
async with AntidetectBrowser() as browser:
    # Navigation
    page = await browser.get("https://example.com")

    # New tab
    page2 = await browser.get("https://other.com", new_tab=True)

    # Screenshot
    await browser.screenshot("/path/to/screenshot.png")

    # Wait
    await browser.wait(5)
```

## Environment Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `AD_PROFILE_PATH` | `profiles/mazamaka_local.json` | Path to JSON profile |
| `AD_TIMEZONE` | `Europe/Budapest` | Timezone |
| `AD_LOCALE` | `ru` | Locale |
| `AD_SCREEN_WIDTH` | `1920` | Screen width |
| `AD_SCREEN_HEIGHT` | `1080` | Screen height |
| `AD_HEADLESS` | `false` | Headless mode |
| `PROXY_URL` | - | Proxy URL |

## What Gets Spoofed

### Via CDP (reliable, browser-level)
- User-Agent + Client Hints (Sec-CH-UA-*)
- Timezone
- Locale

### Via JS (for what CDP doesn't support)
- `navigator.plugins` / `mimeTypes`
- `navigator.webdriver` → removed
- `window.screen.*`
- WebGL vendor/renderer
- Canvas noise
- MediaDevices
- Battery API
- Network Information API
- Permissions API

### Via Chrome flags
- `--disable-blink-features=AutomationControlled`
- `--window-size`
- `--lang`

## Fingerprint Testing

- [CreepJS](https://abrahamjuliot.github.io/creepjs/) — основной тест
- [BrowserLeaks](https://browserleaks.com/)
- [Bot Detector](https://bot.sannysoft.com/)
- [Pixelscan](https://pixelscan.net/)

## Known Limitations

1. **WebRTC** — Local IPs are hidden, but STUN/TURN may leak the real IP. Use proxy.

2. **Canvas/Audio noise** — Minimal noise for fingerprint uniqueness, doesn't affect detection.

3. **GPU in Docker** — WebGL works through software renderer, may differ from real GPU.

4. **`sandbox=False`** — Shows yellow banner "unsupported flag". Use only in Docker.

## Project Structure

```
nodriver-antidetect/
├── antidetect/
│   ├── __init__.py      # Public API
│   ├── browser.py       # AntidetectBrowser + CDP overrides
│   ├── config.py        # Pydantic models
│   ├── session.py       # SessionManager for persistence
│   ├── stealth.py       # JS stealth script
│   └── profiles/
│       └── loader.py    # Load JSON profiles
├── profiles/            # JSON fingerprint profiles
├── sessions/            # Session data (cookies, localStorage)
├── examples/
│   ├── basic_usage.py
│   ├── session_example.py
│   └── test_fingerprint.py
├── CLAUDE.md            # AI agent context
└── README.md
```

## License

MIT

## Credits

- [nodriver](https://github.com/ultrafunkamsterdam/nodriver) — async Chrome automation
- [CreepJS](https://github.com/AbrahamJuliot/creepjs) — fingerprint testing

## Links

- **GitHub**: [mazamaka/nodriver-antidetect](https://github.com/mazamaka/nodriver-antidetect)
- **Documentation**: See [CLAUDE.md](./CLAUDE.md) for development details
