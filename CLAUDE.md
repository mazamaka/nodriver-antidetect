# nodriver-antidetect

Антидетект браузер на базе nodriver для автоматизации и мульти-аккаунтинга.
Версия: 2.3.0

## Архитектура

```
antidetect/
├── __init__.py     # Публичный API модуля
├── browser.py      # AntidetectBrowser - wrapper над nodriver
├── config.py       # Pydantic-модели + автоопределение Chrome
├── stealth.py      # JS-скрипт инжекции fingerprint
└── profiles/
    ├── __init__.py # Утилиты для работы с профилями
    └── loader.py   # Загрузка/сохранение JSON профилей

profiles/           # JSON профили fingerprint (единственный источник!)
├── mazamaka_local.json  # Профиль по умолчанию
├── windows_chrome.json
└── macos_chrome.json
```

### Поток данных

```
JSON профиль → FingerprintProfile (Pydantic) → build_stealth_script() → CDP injection
```

### Приоритет загрузки профилей

1. `AD_PROFILE_PATH` (путь к JSON файлу) - **рекомендуется**
2. Переменные окружения `AD_*`
3. Автоопределённые значения (Chrome версия, timezone offset)

## Ключевые паттерны

### Stealth-инжекция (stealth.py)

```javascript
// wrapFn() - КРИТИЧЕСКИ ВАЖНО для обхода детекта
// Сохраняет оригинальный toString()
const wrapFn = (original, replacement) => {
    replacement.toString = () => original.toString();
    Object.defineProperty(replacement, 'name', { value: original.name, configurable: true });
    return replacement;
};

// Все свойства ДОЛЖНЫ быть configurable: true
Object.defineProperty(obj, prop, { ...desc, configurable: true });
```

### Автоопределение Chrome (config.py)

```python
from antidetect import get_chrome_version

version = get_chrome_version()  # "132.0.6834.83" или из установленного Chrome
```

## Что подменяется

| Категория | Детали |
|-----------|--------|
| **Navigator** | platform, userAgent, vendor, languages, hardwareConcurrency, deviceMemory, plugins, mimeTypes |
| **Screen** | width, height, availWidth, availHeight, colorDepth, pixelDepth |
| **Window** | devicePixelRatio, innerWidth, outerWidth, chrome object |
| **WebGL** | vendor, renderer (UNMASKED_VENDOR/RENDERER_WEBGL) |
| **Timezone** | getTimezoneOffset(), Intl.DateTimeFormat |
| **Canvas** | toDataURL(), getImageData() с noise |
| **Audio** | AudioContext с noise |
| **Media** | enumerateDevices() |
| **WebRTC** | iceTransportPolicy: 'relay' |
| **Battery** | getBattery() |
| **Network** | navigator.connection |
| **Permissions** | permissions.query() |

## Критические требования антидетекта

### ОБЯЗАТЕЛЬНО

- Сохранять toString() оригинальных функций через `wrapFn()`
- Использовать `configurable: true` для всех свойств
- Удалять маркеры автоматизации (`cdc_*`, `__webdriver_*`, etc.)
- Консистентность fingerprint в рамках сессии
- Профили ТОЛЬКО из JSON (не дублировать в Python)

### ЗАПРЕЩЕНО

- Добавлять debug-маркеры (`__stealth_applied`, `__stealth_profile` - УДАЛЕНЫ)
- Использовать `except Exception: pass` без логирования
- Хардкодить версию Chrome (использовать `get_chrome_version()`)
- Несовпадение GPU vendor/renderer с реальным rendering

## Тестирование

### Визуальные тесты

- **CreepJS**: https://abrahamjuliot.github.io/creepjs/
- **BrowserLeaks**: https://browserleaks.com/
- **bot.sannysoft.com**: https://bot.sannysoft.com/
- **pixelscan**: https://pixelscan.net/

### Целевые метрики (CreepJS)

- `like_headless` <= 31%
- `headless` = 0%
- `stealth` = 0%

## Запуск

```bash
# Docker
docker-compose up antidetect

# Локально с профилем по умолчанию
python examples/test_fingerprint.py --output ./output

# С кастомным профилем
AD_PROFILE_PATH=profiles/windows_chrome.json python examples/basic_usage.py

# Программно
from antidetect import AntidetectBrowser, get_profile

async with AntidetectBrowser(profile="mazamaka_local") as browser:
    page = await browser.get("https://example.com")
```

## Переменные окружения

| Переменная | Описание | Default |
|------------|----------|---------|
| AD_PROFILE_PATH | Путь к JSON профилю | profiles/mazamaka_local.json |
| AD_TIMEZONE | Timezone | Europe/Budapest |
| AD_LOCALE | Locale | ru |
| AD_SCREEN_WIDTH | Ширина экрана | 1920 |
| AD_SCREEN_HEIGHT | Высота экрана | 1080 |
| AD_WEBGL_VENDOR | WebGL vendor | Google Inc. (NVIDIA) |
| AD_WEBGL_RENDERER | WebGL renderer | ANGLE (NVIDIA...) |
| AD_USER_AGENT | User Agent | (автоопределение) |
| AD_HEADLESS | Headless режим | false |
| PROXY_URL | Proxy URL | - |

## Известные ограничения

- **WebRTC**: работает только с `iceTransportPolicy: 'relay'` (нужны TURN серверы)
- **TLS/JA3**: не меняется (наследуется от Chrome)
- **Canvas noise**: одинаковый seed на сессию

## Зависимости

- **nodriver** >= 0.38 - async Chrome automation
- **pydantic** >= 2.0 - валидация конфигов
- **pydantic-settings** >= 2.0 - env variables
- **loguru** - логирование

## Changelog v2.3.0 (2026-01-21)

### CDP-уровень подмена (вместо только JS injection)

**Принцип**: Используем CDP где возможно, JS только для того что CDP не умеет.
CDP надёжнее потому что работает на уровне браузера ДО выполнения любого кода страницы.

**Что делается через CDP:**
- `Network.setUserAgentOverride` — User-Agent + Client Hints на уровне HTTP заголовков
- `Emulation.setTimezoneOverride` — timezone на уровне браузера
- `Emulation.setLocaleOverride` — locale на уровне браузера

**Что делается через JS (CDP не поддерживает):**
- WebGL vendor/renderer
- navigator.plugins / mimeTypes
- window.chrome object
- Canvas/audio noise
- MediaDevices, WebRTC, Battery, Network API

**⚠️ НЕ ИСПОЛЬЗОВАТЬ:** `Emulation.setDeviceMetricsOverride` — включает режим эмуляции, который детектируется! Вместо этого используем `--window-size` flag + JS spoofing.

### Результаты (CreepJS)

| Метрика | Antidetect | Реальный браузер |
|---------|------------|------------------|
| like_headless | **31%** | 31% ✅ |
| headless | **0%** | 0% ✅ |
| stealth | **0%** | 0% ✅ |
| plugins | **5** | 5 ✅ |
| mimeTypes | **2** | 2 ✅ |
| Client Hints | **работают** | работают ✅ |

### Новый метод `_apply_cdp_overrides()`
```python
async def _apply_cdp_overrides(self, page):
    # 1. User-Agent + Client Hints на уровне HTTP
    await page.send(cdp.network.set_user_agent_override(...))

    # 2. Timezone на уровне браузера
    await page.send(cdp.emulation.set_timezone_override(...))

    # 3. Locale на уровне браузера
    await page.send(cdp.emulation.set_locale_override(...))

    # 4. JS stealth для остального
    await page.send(cdp.page.add_script_to_evaluate_on_new_document(...))
```

## Changelog v2.2.0

### КРИТИЧЕСКИЙ ФИХ: Тайминг инъекции stealth

**Проблема**: Stealth скрипт инъектировался ПОСЛЕ загрузки страницы.

**Решение**: Stealth регистрируется ПЕРЕД навигацией.

### Добавлено
- `navigator.pdfViewerEnabled` = true
- `navigator.cookieEnabled` = true

## Changelog v2.1.0

- Удалены debug-маркеры `__stealth_applied` (критично для антидетекта!)
- Добавлена подмена `navigator.plugins` и `mimeTypes`
- Добавлен объект `window.chrome` (runtime, csi, loadTimes)
- Добавлена подмена `navigator.getBattery()` и `navigator.connection`
- Добавлена подмена `permissions.query()`
- Автоопределение версии Chrome (`get_chrome_version()`)
- Убрано дублирование профилей - только JSON
- Timezone offset через zoneinfo (правильный расчёт DST)
- Улучшена обработка ошибок (без `except Exception: pass`)
