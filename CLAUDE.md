# T5 Localization — Emulated Device (Selenium/Chrome DevTools)

## Purpose
Same 6-phase localization and UI-quality crawl test as the real-device project (`T5\Localization with functionality real device`), but driven by Selenium with Chrome DevTools mobile emulation instead of Appium + a physical Android device. Runs across multiple configurable device/resolution presets.

## Scripting Standards
Follow `C:\Users\miliana.chipaila\Desktop\Automation projects\T5\scripting_norms.md` in full. Flat structure, no single-use helpers, no classes, no magic strings, no credential logging.

## Project Layout
```
run.py                  # 6-phase orchestrator + argparse --lang / --device filters
config/
  settings.py           # all env vars + timing constants
  languages.py          # LANGUAGE_IDS, LANGUAGES list, LANG_DETECT_MAP
  devices.py            # EMULATED_DEVICES list (Pixel 5, Samsung Galaxy S20 Ultra)
  keys.py               # TRANSLATION_KEYS list (known untranslated keys)
  pages.py              # page URL templates (used by ticket system only)
core/
  crawler.py            # crawls index.php, classifies and caps content types
  checks.py             # 6 per-page checks (JS + langdetect) + dismiss_a2hs()
  subscription.py       # subscribe + unsubscribe; dismiss_a2hs() called on landing
  reporter.py           # run folder, screenshots, flagged copies, summary.txt
tickets/                # optional targeted checks; not the main entry point
  TICKET_TEMPLATE_DO_NOT_UPDATE.py
  TICKET_123_translation_keys.py
results/                # gitignored — one folder per run, device subfolders inside
.env                    # gitignored — all secrets
```

## Device Configuration
Devices live in `config/devices.py` as `EMULATED_DEVICES` — a list of dicts with keys:
- `name` — used in the run folder name and summary header
- `width`, `height` — viewport dimensions in CSS pixels
- `pixel_ratio` — device pixel ratio
- `user_agent` — mobile UA string sent to the server

Current confirmed devices:
| name | width | height | pixel_ratio |
|---|---|---|---|
| pixel_5 | 393 | 851 | 2.75 |
| samsung_galaxy_s20_ultra | 412 | 915 | 3.5 |

Note: `deviceName` presets are NOT used — ChromeDriver 148+ rejects them. Always use manual metrics.

## Driver
Pure Selenium — no Appium, no ADB, no physical device. Each device entry creates one Chrome instance with `mobileEmulation` set via ChromeOptions experimental option. `webdriver_manager` downloads the matching ChromeDriver automatically.

## URL Pattern
Both SHOP and LANDING URLs must include all five params:
```
?lan={id}&adid={ADID}&opref={OPREF}&access_token={ACCESS_TOKEN}&agent_uid={AGENT_UID}
```

## Languages
```
EN=2  AR=84 BR=12 PT=9  DE=3  ES=4  LE=49 FR=1
IT=5  MY=19 TH=72 RO=8  SK=70 NL=7  UA=95 RU=10 ID=82
```
Single-language runs: `venv\Scripts\python.exe run.py --lang EN`
Single-device runs:   `venv\Scripts\python.exe run.py --device pixel_5`
Full run (all devices × all languages): `venv\Scripts\python.exe run.py`

## Credentials (never log, never hardcode)
All in `.env`:
- `ACCESS_TOKEN`, `AGENT_UID`, `ADID`, `OPREF`
- `SHOP_BASE_URL`, `LANDING_BASE_URL`
- `MSISDN_1` — present in .env but not used in any URL

## Phases
1. **Crawl (EN only)** — loads `index.php`, follows links, classifies pages; selects up to 3 APK games, 3 HTML5 games, 3 videos, 5 other pages
2. **Unsubscribed checks** — all languages × all crawled pages: raw keys, untranslated keys, wrong language, text overflow (hard failures); contrast and font size (advisory)
3. **Subscribe once (EN)** — 2-step: JOIN NOW → CONFIRM → polls for success URL; captures subscription recording frames
4. **Subscribed checks** — all languages × profile_settings + thank-you page + 6 My Library sub-views
5. **Unsubscribe once** — MANAGE SUBSCRIPTION → CANCEL SUBSCRIPTION; flags failure in summary
6. **Subscription-flow pages** — all languages × landing + confirmation (`wap_confirm=1`), loaded by URL only (no click-through), after unsubscribe

Each device runs all 6 phases independently. Results land in `results/crawl_{timestamp}/{device_name}/`.

**The subscribe and unsubscribe transactions each run exactly once per device (EN),
not per language**, to minimise run time. Localization coverage as an unsubscribed
user (Phases 2 & 6) and as a subscribed user (Phase 4) is **mandatory for every
language and every device**. The library base URL is discovered once from the EN
profile page and reused for all languages with the `lan=` param swapped; the
thank-you page reuses the Phase 3 success URL the same way.

- **Already subscribed** (landing redirects to `index.php` in Phase 3): JOIN/CONFIRM
  is skipped, but Phases 4 and 5 still run for every language (Phase 5 doubles as
  cleanup); the thank-you page is not captured (no success URL).
- **Subscription failed** in Phase 3: Phases 4 and 5 are skipped; Phase 6 still runs.
- After Phase 6 a safety check re-loads the EN landing page and cancels again if it
  still redirects to `index.php`.

## Known Suppressed Overflows (config/keys.py → OVERFLOW_IGNORE_TEXTS)
These overflow text substrings are filtered out globally in `find_overflow_elements` and will never cause a FAIL. Add new entries to `OVERFLOW_IGNORE_TEXTS` in `config/keys.py` when confirmed as design/content issues.

- `"Tom & Jerry - Advance and Be Mechanized"` — video title overflows its container at mobile viewport widths on `video_trending_videos_*` pages. Design/content issue, not a localization bug. Suppressed across all languages and devices.

**Advisory items (design intent, do not flag):**
- Nav items (Home, Games, Videos, Account): contrast ~3.01 — design intent
- Footer links (Terms of Use, Privacy Policy, EULA, Legal Notices): contrast ~1.96 — design intent
- Active category tab label (e.g. "Action & Arcade"): contrast ~1.00 — selected state uses background-image, not color
- Section headers (TRENDING VIDEOS, TRENDING NOW, NEW RELEASES): contrast ~2.33 — design intent
- Game ratings ("4.6", "4.9", etc.): contrast ~2.33 — design intent
- Carousel pagination dots ("2","3","4","5"): not overflow — design intent (text < 3 chars filter)
- Close button "×": contrast ~1.84 — design intent

## Screenshots / Image Loading
Before each screenshot, the runner scrolls to the bottom of the page to trigger IntersectionObserver-based lazy loading (headless Chrome does not fire these automatically), then waits up to 10s for all `<img>` elements to have `complete && naturalWidth > 0`. Falls back to a 3s sleep on timeout.

## Subscription Recording
`subscribe()` runs once per device (EN) and captures JPEG screenshots via CDP `Page.captureScreenshot` at four key moments: landing loaded → after CTA click → after CONFIRM click → success page. Those frames are written to one MP4: `device_folder/subscription_recording.mp4`.

- Each frame is written 5× at fps=1 so each key moment is visible for 5 seconds
- `macro_block_size=1` — avoids ffmpeg dimension-rounding resize (CDP frame dims are rarely divisible by 16)
- Uses `imageio.v2` API to avoid the v3 deprecation warning
- Requires `imageio` + `imageio-ffmpeg`

## A2HS Popup Dismissal
The site detects mobile UA and shows an "Add to Home Screen" custom web banner. It appears as an overlay with an × close button and causes false-positive overflow/contrast detections if not dismissed first.

`dismiss_a2hs(driver)` in `core/checks.py` scans visible DOM elements (`button`, `span`, `div`, `a`, `i`) for text matching `×`/`✕`/`✖` or `aria-label` of `close`/`dismiss`, and clicks the first match. Returns `True` if dismissed, `False` if not found.

Called in two places:
1. `_record_check()` in `run.py` — at the very top, before scroll/image-wait and screenshot
2. `subscribe()` in `core/subscription.py` — right after the landing page loads, before CTA click

## Key Difference vs. Real Device Project
- No Appium, no ADB, no screen recording, no physical device
- Outer loop is over `EMULATED_DEVICES`; both projects share the same 6-phase, once-per-run subscribe/unsubscribe structure with per-language checks inside
- `subscribe()` uses CDP frame capture instead of Appium screen recording

## Per-Page Checks (Phases 2, 4, 6)
Every screenshotted page — unsubscribed pages, subscribed pages, and the
subscription-flow pages (landing, confirmation, thank-you) — runs the same six
checks. Checks 1–4 are **hard** (cause FAIL + screenshot flagging). Checks 5–6 are **advisory**.

1. **Raw keys** — regex `{placeholder}` or `dot.notation.keys` in body text
2. **Untranslated keys** — word-boundary match against `config/keys.py`; skipped for EN
3. **Wrong language** — langdetect vs `LANG_DETECT_MAP`; seed=0 for consistency
4. **Text overflow** — JS `scrollWidth > clientWidth + 2`; skips `fs<=0`, `clientWidth<5`, text < 3 chars
5. **Contrast** — WCAG luminance ratio < 4.5; advisory only
6. **Font size** — computed `fontSize < 10px`; advisory only

## Session Reset
Before each language: `delete_all_cookies()` + `localStorage.clear()` + `sessionStorage.clear()`

## Key Constants (config/settings.py)
| Constant | Value |
|---|---|
| PAGE_LOAD_TIMEOUT | 60s |
| STEP_PAUSE | 3s |
| MAX_WAIT_SECONDS | 60s |
| MIN_FONT_SIZE_PX | 10 |
| MIN_CONTRAST_RATIO | 4.5 |
