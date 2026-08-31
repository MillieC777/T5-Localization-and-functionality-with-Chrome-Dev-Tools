# T5 Localization — Emulated Device

Automated 6-phase localization and UI-quality test for the T5 wapshop, driven by Selenium with Chrome DevTools mobile emulation. Runs across multiple configurable device/resolution presets without a physical device.

## What it tests

For every language × page combination (unsubscribed state):
- Raw/untranslated key patterns in visible text (`{placeholder}`, `dot.notation.keys`)
- Known translation keys from `config/keys.py`
- Wrong language detection (langdetect)
- Text overflow (JS scrollWidth check)
- Contrast ratio and font size (advisory — not counted as failures)

For every language in subscribed state:
- Profile settings page
- Thank-you / success page
- My Library — All Games, Favorite Games, My Downloads, All Videos, Favorite Videos, Recently Played

For every language on the subscription-flow pages:
- Landing page
- Confirmation page (`wap_confirm=1`), when it is loadable by URL

The subscribe and unsubscribe **transactions** each run once per device (in EN).
The localization **checks** — unsubscribed (Phases 2 & 6) and subscribed (Phase 4)
— are mandatory for every language and every device.

## Phases (per device)

| # | Phase | Detail |
|---|-------|--------|
| 1 | Crawl | EN only — discovers up to 3 APK games, 3 HTML5 games, 3 videos, 5 other pages from `index.php` |
| 2 | Unsubscribed checks | **All 17 languages** × all crawled pages |
| 3 | Subscribe once | EN — JOIN NOW → CONFIRM → poll for success URL |
| 4 | Subscribed checks | **All 17 languages** × profile + thank-you + 6 My Library sub-views |
| 5 | Unsubscribe once | MANAGE SUBSCRIPTION → CANCEL SUBSCRIPTION (+ post-Phase-6 safety re-check) |
| 6 | Subscription-flow pages | **All 17 languages** × landing + confirmation, by URL only, after unsubscribe |

## Devices

| Name | Viewport | DPR |
|------|----------|-----|
| `pixel_5` | 393 × 851 | 2.75 |
| `samsung_galaxy_s20_ultra` | 412 × 915 | 3.5 |

Add or modify devices in `config/devices.py`.

## Languages

| Code | ID | Code | ID | Code | ID |
|------|----|------|----|------|----|
| EN | 2 | FR | 1 | RO | 8 |
| AR | 84 | IT | 5 | SK | 70 |
| BR | 12 | MY | 19 | NL | 7 |
| PT | 9 | TH | 72 | UA | 95 |
| DE | 3 | RU | 10 | ID | 82 |
| ES | 4 | LE | 49 | | |

## Setup

**Requirements:** Python 3.8+, Google Chrome

```powershell
# 1. Create and activate virtual environment
py -m venv venv
venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create .env file (see .env.example or ask a teammate)
```

`.env` must define: `ACCESS_TOKEN`, `AGENT_UID`, `ADID`, `OPREF`, `SHOP_BASE_URL`, `LANDING_BASE_URL`

## Usage

```powershell
# Full run — all devices × all languages (~1h 20m)
venv\Scripts\python.exe run.py

# Single language
venv\Scripts\python.exe run.py --lang EN

# Single device
venv\Scripts\python.exe run.py --device pixel_5

# Combined filter
venv\Scripts\python.exe run.py --lang EN AR DE --device pixel_5
```

## Results

Each run creates one timestamped folder with per-device subfolders:

```
results/crawl_YYYYMMDD_HHMMSS/
  pixel_5/
    screenshots/          EN_index.png … plus EN_landing, EN_landing_confirm, EN_thankyou per language
    flagged/              copies of screenshots with hard failures
    summary.txt           pass/fail counts + flagged details + subscription notes
    subscription_recording.mp4   one-time subscription flow (EN)
  samsung_galaxy_s20_ultra/
    ...
```

Hard failures (FAIL + flagged screenshot): raw keys, untranslated keys, wrong language, text overflow  
Advisory only (logged, not flagged): contrast ratio < 4.5, font size < 10px

## Project structure

```
run.py                  # 6-phase orchestrator + argparse --lang / --device
config/
  settings.py           # env vars + timing constants
  languages.py          # LANGUAGE_IDS, LANGUAGES, LANG_DETECT_MAP
  devices.py            # EMULATED_DEVICES list
  keys.py               # TRANSLATION_KEYS + OVERFLOW_IGNORE_TEXTS
  pages.py              # page URL templates (ticket system only)
core/
  crawler.py            # crawls index.php, classifies and caps content types
  checks.py             # 6 per-page checks + dismiss_a2hs()
  subscription.py       # subscribe + unsubscribe + CDP frame capture
  reporter.py           # run folder, screenshots, flagged copies, summary.txt
tickets/                # optional targeted checks; not the main entry point
  TICKET_TEMPLATE_DO_NOT_UPDATE.py
  TICKET_123_translation_keys.py
results/                # gitignored
.env                    # gitignored
```

## Manual review checklist

Some things require human verification of screenshots after the run:

| Language | What to check |
|----------|---------------|
| AR (84) | RTL layout — colons appear on the LEFT side of labels |
| MY (19) | Burmese uses "-" instead of ":" — confirm intentional; no glyph boxes |
| TH (72) | No missing glyphs or placeholder squares |
| BR (12) | "Ativa até:" and "Assinatura" — NOT "Ativo até:" / "Subscrição" |
| PT (9) | "Ativo até:" and "Subscrição" — NOT "Ativa até:" / "Assinatura" |
| ES (4) | "Tipo de acceso:" — NOT "Acceso de tipo:" |
| LE (49) | "Acceso de tipo:" — NOT "Tipo de acceso:" |
