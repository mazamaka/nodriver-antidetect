# nodriver-antidetect

Антидетект браузер на базе nodriver для автоматизации и мульти-аккаунтинга.
Версия: 2.6.0

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

## Chrome Extensions

Программная загрузка расширений **не поддерживается** — Google Chrome игнорирует `--load-extension` флаг.

**Решение**: установите расширение вручную в профиль сессии, оно сохранится автоматически.

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

## Идеи на будущее

### IP-based fingerprint (как в Octo Browser)

Автоматическое определение параметров из IP прокси:

```python
# При proxy != None автоматически подтягивать:
'languages': {'type': 'ip'},   # Определить язык по GeoIP
'timezone': {'type': 'ip'},    # Определить timezone по GeoIP
'geolocation': {'type': 'ip'}, # Координаты по GeoIP
'webrtc': {'type': 'ip'},      # WebRTC leak = proxy IP
```

**Реализация:**
1. Сделать запрос через прокси к GeoIP сервису (ipapi.co, ip-api.com)
2. Получить: country, timezone, languages, lat/lon
3. Автоматически применить к профилю

**Польза:** Консистентный fingerprint — если прокси US, то и timezone/language будут US.

---

## Changelog v2.6.0 (2026-01-22)

### Docker GPU Support (NVIDIA)

**Проблема**: Chrome с `--no-sandbox` отключает GPU для безопасности.

**Решение**: Флаг `--disable-gpu-sandbox` разрешает GPU при отключенном основном sandbox.

#### Запуск с GPU в Docker

```bash
# Требования:
# 1. Native Docker Engine (не Docker Desktop на Linux!)
# 2. nvidia-container-toolkit установлен
# 3. xhost +local: выполнен на хосте

xhost +local:
docker compose up antidetect-gpu
```

#### Конфигурация docker-compose.yml

```yaml
antidetect-gpu:
  runtime: nvidia
  devices:
    - /dev/dri:/dev/dri
    - /dev/nvidia0:/dev/nvidia0
    - /dev/nvidiactl:/dev/nvidiactl
    - /dev/nvidia-modeset:/dev/nvidia-modeset
  environment:
    - DISPLAY=${DISPLAY:-:1}
    - AD_SHOW_GUI=true
    - NVIDIA_VISIBLE_DEVICES=all
    - NVIDIA_DRIVER_CAPABILITIES=all,graphics,display
  volumes:
    - /tmp/.X11-unix:/tmp/.X11-unix:rw
```

#### Результаты

| Режим | GPU | WebGL confidence | like_headless | Окно на хосте |
|-------|-----|------------------|---------------|---------------|
| `antidetect` (Xvfb) | llvmpipe (software) | LOW | ~44% | Нет |
| `antidetect-gpu` (X11) | NVIDIA RTX 3060 | HIGH | ~31% | Да |
| `antidetect-vgl` (VirtualGL) | llvmpipe (software) | LOW | ~44% | Нет |
| Локально | NVIDIA RTX 3060 | HIGH | 31% | Да |

#### VirtualGL НЕ работает с Chrome

**Исследование (2026-01-22)**: VirtualGL не может предоставить GPU для Chrome:
- VirtualGL перехватывает GLX вызовы через LD_PRELOAD
- Chrome использует ANGLE/EGL для WebGL (не GLX)
- Флаги `--use-angle=gl`, `--use-gl=egl` не помогают
- Даже с vglrun Chrome видит только llvmpipe на Xvfb

**Вывод**: Для headless GPU с Chrome нужен либо:
1. X11 forwarding к реальному X-серверу с GPU (antidetect-gpu)
2. Xorg с NVIDIA driver внутри Docker (требует privileged mode)
3. Xpra/TurboVNC с VirtualGL backend

**⚠️ Важно**: Docker Desktop на Linux НЕ поддерживает GPU — работает только Native Docker Engine.

---

## Changelog v2.5.1 (2026-01-21)

### Dynamic User-Agent

- User-Agent теперь генерируется динамически из реальной версии Chrome
- При обновлении Chrome UA автоматически обновляется
- Версия Chrome определяется через `get_chrome_version()`

## Changelog v2.5.0 (2026-01-21)

### Рефакторинг (SRP)

- Выделен `CDPOverridesHandler` из browser.py
- Выделен `ChromeArgsBuilder` из browser.py
- JS код вынесен в отдельные файлы (antidetect/js/)

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
