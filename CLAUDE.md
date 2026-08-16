# nodriver-antidetect

Антидетект-браузер на базе nodriver для автоматизации и мульти-аккаунтинга.
Версия: 2.7.0 · актуализировано 16.08.2026 (Chrome 151, nodriver 0.50.3)

## Архитектура

```
antidetect/
├── __init__.py      # Публичный API
├── browser.py       # AntidetectBrowser: старт, прокси, расширения, сессии
├── cdp_handler.py   # CDP-оверрайды: UA, Client Hints, timezone, locale + регистрация stealth
├── chrome_args.py   # Флаги Chrome
├── config.py        # Pydantic-модели, ENV-конфиг, автоопределение версии Chrome
├── session.py       # SessionManager (persistent cookies/localStorage)
├── stealth.py       # Сборка stealth-скрипта из JS-модулей
├── js/*.js          # JS-модули стелса
└── profiles/loader.py

profiles/            # JSON-профили fingerprint (единственный источник!)
tools/benchmark.py   # Замеры: baseline vs antidetect + скриншоты
docs/                # Отчёт последнего прогона (benchmark.md/json) и скриншоты
```

### Поток данных

```
JSON профиль → FingerprintProfile (Pydantic) → CDP overrides + build_stealth_script() → Page.addScriptToEvaluateOnNewDocument
```

### Приоритет загрузки профилей

1. `AD_PROFILE_PATH` (путь к JSON) — **рекомендуется**
2. Переменные окружения `AD_*`
3. Автоопределённые значения (версия Chrome, timezone offset)

## Ключевые инварианты

### Page.enable обязателен

`Page.addScriptToEvaluateOnNewDocument` возвращает идентификатор, но **не инжектит скрипт**, если домен Page не включён. Без `await page.send(cdp.page.enable())` весь JS-слой молча не работает (так было до 2.7.0 — screen/WebGL/hardware не применялись вовсе).

### Скрипт регистрируется один раз на вкладку

Повторная регистрация означает, что скрипт выполнится N раз при каждой загрузке. За этим следит `CDPOverridesHandler._registered`.

### CDP — канон, JS — крайний случай

Подмена через CDP выполняется самим браузером: прототипы остаются нетронутыми, геттеры возвращают `[native code]`, own-properties не появляются. JS-патч виден любому чекеру, который сравнивает дескрипторы (pixelscan помечает такое как `Navigator: Detected`).

Через CDP делаем: UA + Client Hints + Accept-Language (`Network.setUserAgentOverride`), timezone/locale (`Emulation.setTimezone/LocaleOverride`), `screen.*` (`Emulation.setDeviceMetricsOverride` с width/height/deviceScaleFactor = 0 — viewport не трогаем), `hardwareConcurrency` (`Emulation.setHardwareConcurrencyOverride`), `maxTouchPoints` (`Emulation.setTouchEmulationEnabled`).

JS остаётся только там, где у CDP нет API: WebGL vendor/renderer, plugins, canvas noise, mediaDevices, battery, connection, permissions, deviceMemory.

Прежде чем добавлять JS-патч — искать метод в домене `Emulation`.

### Не подменять то, что и так правдоподобно

Каждый патч детектируем. Правило: сначала прочитать реальное значение, вмешиваться только при аномалии. Замеренный пример: безусловная подмена `WebGLRenderingContext.getParameter` на машине с реальным GPU поднимала CreepJS stealth с 0% до 20%, ничего не скрывая.

Условными сделаны: `webgl` (`mode: auto`), `plugins`, `media`, `battery`, `network`, `permissions`, `webdriver`.

### wrapFn / wrapGetter

Подмена обязана сохранять `toString()`, `name`, `length` оригинала и ставить `configurable: true`. Утилиты — в `js/utils.js`.

## Что подменяется

| Слой | Что | Как |
|------|-----|-----|
| CDP | User-Agent, Client Hints, Accept-Language | `Network.setUserAgentOverride` |
| CDP | Timezone, locale (включая воркеры) | `Emulation.setTimezone/LocaleOverride` |
| CDP | `screen.*` | `Emulation.setDeviceMetricsOverride` (width/height/scale = 0) |
| CDP | `hardwareConcurrency`, `maxTouchPoints` | `Emulation.setHardwareConcurrencyOverride`, `setTouchEmulationEnabled` |
| Chrome flags | `--window-size`, `--lang`, `--disable-blink-features=AutomationControlled` | аргументы запуска |
| JS (нет CDP API) | canvas noise, `deviceMemory` | stealth-скрипт |
| JS (условно) | WebGL, plugins, mediaDevices, battery, connection, permissions | только при аномалии |

**Не подменяется намеренно:** `window.innerWidth/outerWidth/devicePixelRatio` (сверяются с CSS-медиазапросами — bot.sannysoft MQ_SCREEN), WebGL в Worker-контексте (скрипт туда не доходит), `doNotTrack` при совпадении с реальным (`null`).

## Запрещено

- Debug-маркеры (`__stealth_applied` и подобные)
- `except Exception: pass` без логирования
- Хардкод версии Chrome (использовать `get_chrome_version()`)
- Хардкод GREASE-бренда Client Hints (читать из `navigator.userAgentData.brands`)
- Подмена ради подмены — см. инвариант выше

## Тестирование

```bash
python tools/benchmark.py                                    # baseline + antidetect, все пробы
python tools/benchmark.py --setups antidetect --probes creepjs
python tools/benchmark.py --profile windows_chrome --output docs
```

Пробы: `headers` (локальный HTTP-сервер ловит реальные заголовки), `js` (страница + Worker), `sannysoft`, `creepjs`, `pixelscan`.

Стенды: [CreepJS](https://abrahamjuliot.github.io/creepjs/), [bot.sannysoft.com](https://bot.sannysoft.com/), [BrowserLeaks](https://browserleaks.com/), [pixelscan](https://pixelscan.net/).

### Ориентиры (macOS, Chrome 151, профиль macos_chrome)

`pixelscan.net/bot-check`: вердикт `You're Definitely a Human`, все сигналы (Navigator, Webdriver, CDP, User Agent, Plugins, Languages, DoNotTrack, VendorSub, ProductSub) — `Clear`. Любой `Detected` = регрессия JS-слоя.

Замер antidetect не должен быть **хуже baseline** (чистого nodriver) на той же машине:

| Метрика | baseline | antidetect |
|---|---|---|
| CreepJS headless / stealth / lies | 0% / 0% / 0 | 0% / 0% / 0 |
| CreepJS like headless | 25% | 25% |
| bot.sannysoft | 31 passed / 0 failed | 31 passed / 0 failed |

Рост `stealth` или падение sannysoft после правок JS-слоя = регрессия.

## Запуск

```bash
docker compose up antidetect
AD_PROFILE_PATH=profiles/windows_chrome.json python examples/basic_usage.py
```

```python
async with AntidetectBrowser(profile="macos_chrome") as browser:
    page = await browser.get("https://example.com")
```

Профиль берём под ОС хоста: Linux-профиль на macOS — несогласованность, видимая детекторам.

## Chrome Extensions

Загружаются через CDP-домен `Extensions.loadUnpacked` (Chrome 138+), а не через `--load-extension`: флаг работает нестабильно и конфликтует с `--test-type`.

```python
async with AntidetectBrowser(extensions=["./extensions/ublock"]) as browser:
    ...
```

## Прокси

`--proxy-server` для прокси без авторизации; для прокси с логином/паролем поднимается локальный форвардер `nodriver.core.util.ProxyForwarder` (креды не попадают в командную строку Chrome).

## Переменные окружения

| Переменная | Описание | Default |
|------------|----------|---------|
| AD_PROFILE_PATH | Путь к JSON профилю | profiles/mazamaka_local.json |
| AD_TIMEZONE / AD_LOCALE | Timezone / locale | Europe/Budapest / ru |
| AD_SCREEN_WIDTH / AD_SCREEN_HEIGHT | Экран | 1920 / 1080 |
| AD_HARDWARE_CONCURRENCY / AD_DEVICE_MEMORY | Железо | 8 / 8 |
| AD_PLATFORM | Платформа | Linux x86_64 |
| AD_WEBGL_VENDOR / AD_WEBGL_RENDERER | WebGL | NVIDIA-строки |
| AD_HEADLESS | Headless-режим | false |
| PROXY_URL | Proxy URL | - |

## Известные ограничения

- **Worker-контексты**: JS-стелс туда не доходит (`addScriptToEvaluateOnNewDocument` не покрывает воркеры). CDP-оверрайды (timezone/locale/UA) — доходят. Каноничное решение: `Target.setAutoAttach` + инъекция в worker-таргеты.
- **WebRTC**: работает только с `iceTransportPolicy: 'relay'` (нужны TURN-серверы)
- **TLS/JA3**: не меняется (наследуется от Chrome)
- **Canvas noise**: одинаковый seed на сессию
- **WebGPU-флаги** применяются только на Linux: на macOS/Windows реальный Chrome отдаёт WebGPU, и его отключение само по себе аномалия

## Зависимости

nodriver >= 0.50.3, pydantic >= 2.13, pydantic-settings >= 2.12, loguru, httpx[socks]

## Идеи на будущее

- **Инъекция в Worker-таргеты** через `Target.setAutoAttach(wait_for_debugger_on_start=True)` — закроет расхождение GPU между главным потоком и воркером.
- **IP-based fingerprint**: при заданном прокси подтягивать timezone/languages/geolocation по GeoIP (ipapi.co, ip-api.com), чтобы профиль соответствовал стране выхода.

## Changelog v2.7.0 (2026-08-16)

Актуализация под Chrome 151 / nodriver 0.50.3 и починка того, что молча не работало:

- **`Page.enable` перед регистрацией stealth-скрипта.** До этого весь JS-слой не применялся: screen, WebGL, canvas noise, media devices — ничего.
- **`hardwareConcurrency` / `deviceMemory` / `maxTouchPoints`** из профиля не доезжали до JS-конфига — исправлено.
- **`proxy=` игнорировался** (браузер ходил напрямую) — теперь `--proxy-server` + `ProxyForwarder` для прокси с авторизацией.
- **`extensions=`** был описан в README, но код удалён в e2f5d34 — восстановлен и переведён на `Extensions.loadUnpacked`.
- **`navigator.webdriver`** подменялся на `undefined`, хотя реальный Chrome отдаёт `false` — теперь вмешиваемся только если флаг поднят.
- **pixelscan.net добавлен в замеры** (`bot-check` + `fingerprint-check`): вердикт `human`, все сигналы `Clear`.
- **`screen.width/height`, `hardwareConcurrency`, `maxTouchPoints` переехали с JS на CDP** (`Emulation.setDeviceMetricsOverride` / `setHardwareConcurrencyOverride` / `setTouchEmulationEnabled`). pixelscan помечал JS-версию как `Navigator: Detected`; после переноса геттеры снова нативные и все сигналы `Clear`. В JS остался только `avail*` — CDP отдаёт `avail == screen`, а это стоило +6% like-headless в CreepJS.
- **`doNotTrack`** определялся на инстансе `navigator` (own property, которого нет у реального Chrome) → `DoNotTrack: Detected` на pixelscan. Теперь патч на прототипе и только при несовпадении.
- **`window.inner*` больше не подделываются** — это ломало MQ_SCREEN в bot.sannysoft.
- **WebGL-спуф стал условным** (`mode: auto`): CreepJS stealth 20% → 0%.
- **plugins/battery/connection/permissions/media** — подмена только при аномалии; исправлен тип `PluginArray`.
- **GREASE-бренд Client Hints** читается из браузера, а не хардкодится (`Not-A.Brand/24` → реальный `Not=A?Brand/99`).
- **WebGPU-флаги и `--use-angle=gl`** — только на Linux.
- Скрипт регистрируется один раз на вкладку (было — при каждой навигации).
- `COPY scripts/` в Dockerfile ломал сборку (папки нет в репозитории) — убрано.
- `tools/benchmark.py` вместо `examples/test_fingerprint*.py`; пробы `headers`/`js`/`sannysoft`/`creepjs`/`pixelscan`, отчёты и скриншоты в `docs/`.

История версий 2.1.0–2.6.1 — в git log.
