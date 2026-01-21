# nodriver-antidetect

Antidetect browser на базе [nodriver](https://github.com/ultrafunkamsterdam/nodriver) с CDP-уровневым спуфингом fingerprint.

**Версия: 2.4.0**

## Результаты CreepJS

| Метрика | Результат | Цель |
|---------|-----------|------|
| like_headless | 31% | ≤31% ✅ |
| headless | 0% | 0% ✅ |
| stealth | 0% | 0% ✅ |
| plugins | 5 | 5 ✅ |
| mimeTypes | 2 | 2 ✅ |

## Архитектура спуфинга

**Принцип:** CDP-уровень где возможно, JS только для непокрываемого CDP.

| Уровень | Что спуфим | Метод |
|---------|-----------|-------|
| HTTP | User-Agent, Client Hints | `Network.setUserAgentOverride` |
| Browser | Timezone, Locale | `Emulation.setTimezone/LocaleOverride` |
| Chrome flags | Window size, Language | `--window-size`, `--lang` |
| JS | Plugins, WebGL, Canvas | Stealth script |

## Quick Start

### Локально (без Docker)

```python
import asyncio
from antidetect import AntidetectBrowser

async def main():
    # По умолчанию sandbox=True — нет жёлтой полосы
    async with AntidetectBrowser() as browser:
        page = await browser.get("https://example.com")
        await browser.screenshot("screenshot.png")

asyncio.run(main())
```

### Docker

```python
# В Docker нужен sandbox=False
async with AntidetectBrowser(sandbox=False) as browser:
    page = await browser.get("https://example.com")
```

```bash
# Build
docker build -t nodriver-antidetect .

# Run
docker run --rm -v $(pwd)/output:/output nodriver-antidetect
```

### С JSON профилем

```python
# Загрузка профиля по имени
async with AntidetectBrowser(profile="windows_chrome") as browser:
    ...

# Загрузка из файла
async with AntidetectBrowser(profile="profiles/custom.json") as browser:
    ...
```

### С сессией (persistent cookies/localStorage)

```python
# Сессия сохраняет cookies, localStorage, cache между запусками
async with AntidetectBrowser(session="my_session") as browser:
    page = await browser.get("https://example.com/login")
    # ... login ...
    # Cookies автоматически сохранятся в ./sessions/my_session/

# При следующем запуске — уже залогинены!
async with AntidetectBrowser(session="my_session") as browser:
    page = await browser.get("https://example.com")
```

### SessionManager (продвинутое управление)

```python
from antidetect import SessionManager

manager = SessionManager()

# Список сессий
sessions = manager.list()

# Клонировать сессию
manager.clone("session1", "session1_backup")

# Удалить сессию
manager.delete("old_session")
```

## Профили

Профили хранятся в `profiles/*.json`:

- `mazamaka_local.json` — профиль по умолчанию (Linux, Chrome 144)
- `windows_chrome.json` — Windows 10 + Chrome
- `macos_chrome.json` — macOS + Chrome

### Структура профиля

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
    profile: str | FingerprintProfile | None = None,  # Fingerprint профиль
    proxy: str | None = None,                          # Proxy URL
    headless: bool = False,                            # Headless режим
    sandbox: bool = True,                              # False для Docker
    session: str | None = None,                        # Имя сессии для persistence
    sessions_dir: str | Path | None = None,            # Директория сессий (default: ./sessions)
    browser_args: list[str] | None = None,             # Доп. аргументы Chrome
)
```

### Методы

```python
async with AntidetectBrowser() as browser:
    # Навигация
    page = await browser.get("https://example.com")

    # Новая вкладка
    page2 = await browser.get("https://other.com", new_tab=True)

    # Скриншот
    await browser.screenshot("/path/to/screenshot.png")

    # Ожидание
    await browser.wait(5)
```

## Конфигурация через ENV

| Переменная | Default | Описание |
|------------|---------|----------|
| `AD_PROFILE_PATH` | `profiles/mazamaka_local.json` | Путь к JSON профилю |
| `AD_TIMEZONE` | `Europe/Budapest` | Timezone |
| `AD_LOCALE` | `ru` | Locale |
| `AD_SCREEN_WIDTH` | `1920` | Ширина экрана |
| `AD_SCREEN_HEIGHT` | `1080` | Высота экрана |
| `AD_HEADLESS` | `false` | Headless режим |
| `PROXY_URL` | - | Proxy URL |

## Что спуфится

### Через CDP (надёжно, на уровне браузера)
- User-Agent + Client Hints (Sec-CH-UA-*)
- Timezone
- Locale

### Через JS (для того что CDP не поддерживает)
- `navigator.plugins` / `mimeTypes`
- `navigator.webdriver` → удаляется
- `window.screen.*`
- WebGL vendor/renderer
- Canvas noise
- MediaDevices
- Battery API
- Network Information API
- Permissions API

### Через Chrome flags
- `--disable-blink-features=AutomationControlled`
- `--window-size`
- `--lang`

## Тестирование fingerprint

- [CreepJS](https://abrahamjuliot.github.io/creepjs/) — основной тест
- [BrowserLeaks](https://browserleaks.com/)
- [Bot Detector](https://bot.sannysoft.com/)
- [Pixelscan](https://pixelscan.net/)

## Известные ограничения

1. **WebRTC** — локальные IP скрыты, но STUN/TURN могут раскрыть реальный IP. Используйте proxy.

2. **Canvas/Audio noise** — минимальный шум для уникальности fingerprint, не влияет на детект.

3. **GPU в Docker** — WebGL работает через software renderer, может отличаться от реального GPU.

4. **`sandbox=False`** — показывает жёлтую полосу "неподдерживаемый флаг". Используйте только в Docker.

## Структура проекта

```
nodriver-antidetect/
├── antidetect/
│   ├── __init__.py      # Публичный API
│   ├── browser.py       # AntidetectBrowser + CDP overrides
│   ├── config.py        # Pydantic модели
│   ├── session.py       # SessionManager для persistence
│   ├── stealth.py       # JS stealth script
│   └── profiles/
│       └── loader.py    # Загрузка JSON профилей
├── profiles/            # JSON профили fingerprint
├── sessions/            # Данные сессий (cookies, localStorage)
├── examples/
│   ├── basic_usage.py
│   ├── session_example.py
│   └── test_fingerprint.py
├── CLAUDE.md            # Контекст для AI-агентов
└── README.md
```

## License

MIT

## Credits

- [nodriver](https://github.com/ultrafunkamsterdam/nodriver) — async Chrome automation
- [CreepJS](https://github.com/AbrahamJuliot/creepjs) — fingerprint testing
