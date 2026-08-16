<div align="center">

# nodriver-antidetect

**CDP-level fingerprint spoofing for undetectable browser automation**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-D7FF64.svg)](https://github.com/astral-sh/ruff)
[![Typing: mypy](https://img.shields.io/badge/typing-mypy-blue.svg)](https://mypy-lang.org/)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com/)

Antidetect wrapper around [nodriver](https://github.com/ultrafunkamsterdam/nodriver): fingerprint spoofing at the **Chrome DevTools Protocol level**, with JS injection reserved for what CDP cannot reach.

[Benchmark](#benchmark-results) ·
[Architecture](#spoofing-architecture) ·
[Quick Start](#quick-start) ·
[API](#api) ·
[Limitations](#known-limitations)

</div>

---

**Version 2.7.0** · verified 2026-08-16 on Chrome 151.0.7922.138 + nodriver 0.50.3

## Benchmark results

`tools/benchmark.py` runs two setups on the same machine: `baseline` — plain nodriver, `antidetect` — this wrapper with the `macos_chrome` profile. Full report: [docs/benchmark.md](docs/benchmark.md), raw data: [docs/benchmark.json](docs/benchmark.json).

Benchmark host: macOS 15 (Apple M2, 1470×956 display, TZ Europe/Prague, ru-RU locale).

| What the page sees | baseline | antidetect | profile asks for |
|---|---|---|---|
| screen | 1470×956 | **2560×1440** | 2560×1440 |
| hardwareConcurrency | 8 | **10** | 10 |
| languages | ru-RU,ru,en-US,en | **en-US,en** | en-US,en |
| timezone | Europe/Prague | **America/Los_Angeles** | America/Los_Angeles |
| Accept-Language (HTTP) | ru-RU,ru;q=0.9,… | **en-US,en;q=0.9** | en-US,en |
| navigator.webdriver | false | false | — |

| Detector | baseline | antidetect |
|---|---|---|
| CreepJS: headless | 0% | 0% |
| CreepJS: stealth | 0% | 0% |
| CreepJS: like headless | 25% | 25% |
| CreepJS: lies | 0 | 0 |
| bot.sannysoft.com | 31 passed / 0 failed | 31 passed / 0 failed |
| pixelscan.net bot check | human | human |
| pixelscan.net flagged signals | none | none |
| Browser startup | 1.23 s | 0.84 s |

The point of these numbers: swapping the fingerprint costs **nothing** in detector scores. `like headless 25%` is what plain headful Chrome scores on the same host — it is not a defect of the wrapper.

### pixelscan.net — bot check

![pixelscan bot detection test](docs/img/pixelscan-bot-antidetect.png)

`You're Definitely a Human`, and every signal group is `Clear` — Navigator (73 parameters), Webdriver (37), CDP (2), User Agent (5).

This is the check that forced the CDP-first design. With `screen`, `hardwareConcurrency` and `doNotTrack` patched in JS, pixelscan reported `Navigator: Detected` and `DoNotTrack: Detected`; moving them to the Emulation domain — and dropping the `doNotTrack` override that only ever restated the real value — cleared both.

### pixelscan.net — fingerprint report

![pixelscan fingerprint check](docs/img/pixelscan-fingerprint-antidetect.png)

The HTTP and JavaScript User-Agents agree, the platform matches the profile, and `HardwareConcurency` reports the profile's 10 cores on an 8-core host — spoofed by the browser, not by a patched getter.

### The profile reaches Worker contexts

CreepJS queries a Worker separately and compares its answers with the main thread — that is where half-applied spoofing shows up. Locale and timezone come from the profile, not from the host:

![CreepJS Worker section](docs/img/creepjs-worker-antidetect.png)

The GPU string here is the real one — see [Known limitations](#known-limitations).

### CreepJS verdict

![CreepJS headless section](docs/img/creepjs-headless-antidetect.png)

`0% headless`, `0% stealth` — no headless markers, and the API patches are not detected as stealth techniques.

### bot.sannysoft.com

![bot.sannysoft.com](docs/img/sannysoft-antidetect.png)

Every test green. The table also shows the applied UA (Chrome 151), the profile languages, and a correct `PluginArray` type.

### Reproduce it yourself

```bash
python tools/benchmark.py                        # baseline + antidetect, all probes
python tools/benchmark.py --setups antidetect --probes creepjs
python tools/benchmark.py --profile windows_chrome --output docs
```

Probes: `headers` (a local HTTP server captures what Chrome really sends), `js` (properties in the page and inside a Worker), `sannysoft`, `creepjs`, `pixelscan`. The report lands in `<output>/benchmark.md`, screenshots in `<output>/img/`.

Unit tests (config, profiles, stealth assembly, sessions, Chrome args):

```bash
pytest
```

## Spoofing architecture

**Principle:** spoof through CDP wherever an API exists, fall back to JS only where it does not, and skip the override entirely when the real value already looks plausible.

CDP overrides are performed by the browser itself: prototypes stay untouched, getters still report `[native code]`, and no own-properties appear on `navigator`. A JS patch, by contrast, is visible to anything that inspects property descriptors — pixelscan flags exactly that as `Navigator: Detected`.

| Layer | What | How |
|---|---|---|
| CDP | User-Agent, Client Hints, Accept-Language | `Network.setUserAgentOverride` |
| CDP | Timezone, locale (workers included) | `Emulation.setTimezone/LocaleOverride` |
| CDP | `screen.width/height` | `Emulation.setDeviceMetricsOverride` (width/height/scale = 0, so the viewport is left alone) |
| CDP | `hardwareConcurrency`, `maxTouchPoints` | `Emulation.setHardwareConcurrencyOverride`, `setTouchEmulationEnabled` |
| Chrome flags | Window size, language, automation flags | `--window-size`, `--lang`, `--disable-blink-features` |
| JS (no CDP API) | canvas noise, `deviceMemory`, `screen.avail*` | stealth script |
| JS (conditional) | WebGL, plugins, mediaDevices, battery, connection, permissions | patched only when the real value is anomalous |

### Dynamic User-Agent

The UA is built from the version of the Chrome actually installed, so it never goes stale after a browser update:

```
Chrome 151.0.7922.138  →  UA: …Chrome/151.0.0.0 Safari/537.36   (UA reduction)
                          Client Hints: full_version=151.0.7922.138
```

The GREASE brand (`"Not=A?Brand";v="99"`) is read from the browser itself instead of being hardcoded — a stale GREASE entry from an older Chrome gives the override away.

### Conditional patches

| Module | Steps in when |
|---|---|
| `webgl.js` | `mode: auto` — only if the real renderer is software (SwiftShader/llvmpipe/Mesa), i.e. it already screams headless. `always` / `off` to force it |
| `plugins.js` | the real plugin list differs from the target one (old headless reports none) |
| `media.js` | `enumerateDevices()` returns an empty list |
| `battery.js` | `getBattery` is missing |
| `network.js` | `navigator.connection` is missing |
| `permissions.js` | `Notification.permission` and `permissions.query()` disagree |
| `webdriver.js` | the flag is actually raised (normal Chrome already reports `false`) |
| `navigator.js` | `deviceMemory`/`doNotTrack` differ from the profile — and always on `Navigator.prototype`, never as an own property on `navigator` |
| `screen.js` | only `availWidth`/`availHeight`, which `setDeviceMetricsOverride` reports as equal to the screen size while a real desktop loses a strip to the menu bar |

The measurement behind the `webgl` rule: on a machine with a real GPU, unconditionally patching `getParameter` pushed CreepJS stealth from 0% to 20% while hiding nothing — the real GPU still leaks through the Worker context.

## Quick start

### Local

```python
import asyncio
from antidetect import AntidetectBrowser

async def main():
    # sandbox=True by default — no yellow "unsupported flag" bar
    async with AntidetectBrowser(profile="macos_chrome") as browser:
        page = await browser.get("https://example.com")
        await browser.screenshot("screenshot.png")

asyncio.run(main())
```

Pick a profile matching your host OS: a Linux profile on a macOS host is an inconsistency detectors can see.

### Docker

```python
async with AntidetectBrowser(sandbox=False) as browser:  # Docker needs sandbox=False
    page = await browser.get("https://example.com")
```

```bash
docker build -t nodriver-antidetect .
docker run --rm -v $(pwd)/output:/output nodriver-antidetect
docker compose run --rm antidetect        # run the benchmark inside the container
```

### Sessions (persistent cookies/localStorage)

```python
async with AntidetectBrowser(session="my_session") as browser:
    page = await browser.get("https://example.com/login")
    # cookies are stored in ./sessions/my_session/

async with AntidetectBrowser(session="my_session") as browser:
    ...  # already logged in on the next run
```

```python
from antidetect import SessionManager

manager = SessionManager()
manager.list()
manager.clone("session1", "session1_backup")
manager.delete("old_session")
```

### Proxy

```python
# no auth — passed straight to --proxy-server
async with AntidetectBrowser(proxy="http://1.2.3.4:8080") as browser:
    ...

# with auth — nodriver's local forwarder holds the credentials,
# so they never appear in Chrome's command line
async with AntidetectBrowser(proxy="socks5://user:pass@1.2.3.4:1080") as browser:
    ...
```

### Chrome extensions

```python
async with AntidetectBrowser(extensions=["./extensions/ublock"]) as browser:
    ...
```

Extensions must be unpacked (a folder containing `manifest.json`). They are installed through the `Extensions.loadUnpacked` CDP domain rather than the `--load-extension` flag: current Chrome loads that flag unreliably and it conflicts with `--test-type`, whereas the CDP call installs and activates the extension for real (verified on Chrome 151 — a content script from a freshly loaded MV3 extension executes on the next navigation).

## Profiles

`profiles/*.json`:

- `mazamaka_local.json` — Linux, NVIDIA RTX 3060 (default profile, aimed at Docker)
- `windows_chrome.json` — Windows 10
- `macos_chrome.json` — macOS, Apple M1 Pro

```json
{
  "name": "my_profile",
  "navigator": {
    "platform": "MacIntel",
    "languages": ["en-US", "en"],
    "hardware_concurrency": 10,
    "device_memory": 8
  },
  "screen": {"width": 2560, "height": 1440, "avail_width": 2560, "avail_height": 1415},
  "webgl": {
    "mode": "auto",
    "vendor": "Google Inc. (Apple)",
    "renderer": "ANGLE (Apple, ANGLE Metal Renderer: Apple M1 Pro, Version 14.0)"
  },
  "timezone": {"timezone": "America/Los_Angeles", "locale": "en-US"}
}
```

No need to put `user_agent` in a profile: it is always generated from the installed Chrome version.

## API

```python
AntidetectBrowser(
    profile: str | FingerprintProfile | None = None,  # name, path to .json, or an object
    config: AntidetectConfig | None = None,
    proxy: str | None = None,                          # http/socks5, with or without auth
    headless: bool = False,
    browser_args: list[str] | None = None,
    sandbox: bool = True,                              # False for Docker
    session: str | None = None,
    sessions_dir: str | Path | None = None,
    extensions: list[str | Path] | None = None,
)
```

```python
async with AntidetectBrowser() as browser:
    page = await browser.get("https://example.com")
    page2 = await browser.get("https://other.com", new_tab=True)
    await browser.screenshot("shot.png")
    await browser.wait(5)
```

## Environment configuration

| Variable | Default | Description |
|---|---|---|
| `AD_PROFILE_PATH` | `profiles/mazamaka_local.json` | JSON profile path (takes priority over the variables below) |
| `AD_TIMEZONE` | `Europe/Budapest` | Timezone |
| `AD_LOCALE` | `ru` | Locale |
| `AD_SCREEN_WIDTH` / `AD_SCREEN_HEIGHT` | `1920` / `1080` | Screen |
| `AD_HARDWARE_CONCURRENCY` / `AD_DEVICE_MEMORY` | `8` / `8` | Hardware |
| `AD_PLATFORM` | `Linux x86_64` | Platform |
| `AD_HEADLESS` | `false` | Headless mode (detectable — enable deliberately) |
| `PROXY_URL` | — | Proxy URL |

## Known limitations

1. **WebGL is not spoofed inside Worker contexts.** `Page.addScriptToEvaluateOnNewDocument` does not reach workers, so with `webgl.mode: always` the renderer reported by the main thread and by a worker disagree — a louder lie than an honest GPU string. Hence `auto` as the default. The real fix is injecting into worker targets via `Target.setAutoAttach`.

2. **`screen` is spoofed, `window.inner*` is not.** Window dimensions are cross-checked by CSS media queries (bot.sannysoft's MQ_SCREEN compares `innerWidth` against `matchMedia`), so window size is set with `--window-size` rather than faked in JS. A profile whose screen is larger than the host display is fine — the window is simply smaller than the screen.

   `setDeviceMetricsOverride` has no notion of the available area and reports `avail* == screen`, which reads as unusual on a desktop (CreepJS: 25% → 31% like-headless). That one delta is patched in JS.

3. **WebRTC** — local IPs are hidden, but STUN/TURN can still expose the real one. Use a proxy.

4. **GPU in Docker** — WebGL runs on a software renderer; that is exactly the case where `webgl` in `auto` mode kicks in.

5. **`sandbox=False`** shows the yellow "unsupported flag" bar — Docker only.

6. **These numbers were measured on macOS.** Linux/Docker will differ (software rendering, different font set) — re-run `tools/benchmark.py` on your own platform.

## Project layout

```
nodriver-antidetect/
├── antidetect/
│   ├── browser.py       # AntidetectBrowser: startup, proxy, extensions, sessions
│   ├── cdp_handler.py   # CDP overrides: UA, Client Hints, timezone, locale
│   ├── chrome_args.py   # Chrome flags
│   ├── config.py        # pydantic models and env config
│   ├── session.py       # SessionManager
│   ├── stealth.py       # stealth script assembly
│   ├── js/              # stealth JS modules
│   └── profiles/loader.py
├── profiles/            # JSON fingerprint profiles
├── tools/benchmark.py   # baseline vs antidetect measurements + screenshots
├── docs/                # latest report and screenshots
├── examples/
├── tests/               # unit tests (pytest)
├── pyproject.toml       # packaging, ruff, mypy, pytest config
├── CLAUDE.md            # context for AI agents
└── README.md
```

## License

MIT

## Credits

- [nodriver](https://github.com/ultrafunkamsterdam/nodriver) — async Chrome automation
- [CreepJS](https://github.com/AbrahamJuliot/creepjs) and [bot.sannysoft.com](https://bot.sannysoft.com/) — test benches
