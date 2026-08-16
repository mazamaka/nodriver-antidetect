# Fingerprint benchmark — 2026-08-16

Host: Darwin 24.6.0 (arm64) · Chrome 151.0.7922.138 · nodriver 0.50.3
Profile: `macos_chrome`

## What the page sees

| | baseline | antidetect |
|---|---|---|
| navigator.platform | MacIntel | MacIntel |
| screen | 1470x956 | 2560x1440 |
| hardwareConcurrency | 8 | 10 |
| deviceMemory | 8 | 8 |
| languages | ru-RU,ru,en-US,en | en-US,en |
| timezone | Europe/Prague | America/Los_Angeles |
| WebGL renderer | ANGLE (Apple, ANGLE Metal Renderer: Apple M2, Unspecified Version) | ANGLE (Apple, ANGLE Metal Renderer: Apple M2, Unspecified Version) |
| WebGL renderer (Worker) | ANGLE (Apple, ANGLE Metal Renderer: Apple M2, Unspecified Version) | ANGLE (Apple, ANGLE Metal Renderer: Apple M2, Unspecified Version) |
| navigator.webdriver | false | false |
| plugins | 5 | 5 |

## What Chrome sends (HTTP)

| | baseline | antidetect |
|---|---|---|
| User-Agent | Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 | Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 |
| Accept-Language | ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7 | en-US,en;q=0.9 |
| Sec-CH-UA-Platform | "macOS" | "macOS" |

## CreepJS

| | baseline | antidetect |
|---|---|---|
| like headless | 25% | 25% |
| headless | 0% | 0% |
| stealth | 0% | 0% |
| lies | 0 | 0 |

## pixelscan.net

| | baseline | antidetect |
|---|---|---|
| bot check | human | human |
| flagged signals | none | none |
| reported platform | MacIntel | MacIntel |
| reported cores | 8 | 10 |

## bot.sannysoft.com

| | baseline | antidetect |
|---|---|---|
| passed | 31 | 31 |
| failed | 0 | 0 |

## Timing

| | baseline | antidetect |
|---|---|---|
| browser startup, s | 1.23 | 0.84 |
| first navigation, s | 0.17 | 0.05 |
