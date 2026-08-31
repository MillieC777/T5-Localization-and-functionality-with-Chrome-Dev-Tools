import argparse
import io
import logging
import os
import time
import urllib.parse

import imageio.v2 as imageio
import numpy as np

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from config.settings import (
    SHOP_BASE_URL, LANDING_BASE_URL,
    ACCESS_TOKEN, AGENT_UID, ADID, OPREF,
    PAGE_LOAD_TIMEOUT, STEP_PAUSE, APK_DOWNLOAD_HOST,
)
from config.languages import LANGUAGES
from config.devices import EMULATED_DEVICES
from core.crawler import discover_pages
from core.checks import run_page_checks, dismiss_a2hs
from core.subscription import subscribe, unsubscribe
from core.reporter import create_run_folder, create_device_folder, save_screenshot, flag_screenshot, write_summary

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

_SHOP_DIR    = SHOP_BASE_URL.rsplit("/", 1)[0]
_EN_LAN_ID   = 2
_HARD_CHECKS = {"raw_keys", "untranslated_keys", "wrong_language", "overflow_elements"}


def append_params(base_url, lang_id, extra=None):
    params = {
        "lan":          lang_id,
        "adid":         ADID,
        "opref":        OPREF,
        "access_token": ACCESS_TOKEN,
        "agent_uid":    AGENT_UID,
        **(extra or {}),
    }
    return base_url + "?" + urllib.parse.urlencode(params)


def _create_driver(device):
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_experimental_option("mobileEmulation", {
        "deviceMetrics": {
            "width":      device["width"],
            "height":     device["height"],
            "pixelRatio": device["pixel_ratio"],
        },
        "userAgent": device["user_agent"],
    })
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options,
    )
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
    return driver


def _record_check(driver, device_folder, lang_name, label, results):
    dismiss_a2hs(driver)
    try:
        # Headless Chrome does not fire IntersectionObserver for off-screen elements,
        # so lazy-loaded images never start loading unless scrolled into view.
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(0.5)
        driver.execute_script("window.scrollTo(0, 0)")
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script(
                "return Array.from(document.querySelectorAll('img')).every(function(i){"
                "  if (!i.src || i.src.startsWith('data:')) return true;"
                "  return i.complete && i.naturalWidth > 0;"
                "})"
            )
        )
    except Exception:
        time.sleep(3)
    screenshot = save_screenshot(driver, device_folder, lang_name, label)
    checks     = run_page_checks(driver, lang_name)
    hard_fails = [k for k in _HARD_CHECKS if checks.get(k)]
    status     = "FAIL" if hard_fails else "PASS"
    if status == "FAIL":
        flag_screenshot(screenshot, device_folder, lang_name, label)
    results.append({"lang": lang_name, "page_label": label, "checks": checks, "status": status})
    log.info("[%s] %s / %s", status, lang_name, label)


def _try_click_text(driver, text, timeout=10):
    try:
        WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable(
                (By.XPATH, f"//*[contains(translate(normalize-space(.), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), '{text.upper()}')]")
            )
        ).click()
        time.sleep(STEP_PAUSE)
        return True
    except Exception as exc:
        log.warning("Tab %r not found (%s) — listing visible page labels for diagnosis", text, exc)
        try:
            visible = [
                e.text.strip() for e in driver.find_elements(By.XPATH, "//*[normalize-space(.) and not(*)]")
                if e.is_displayed() and 0 < len(e.text.strip()) < 60
            ]
            log.info("Visible text elements: %s", list(dict.fromkeys(visible))[:30])
        except Exception:
            pass
        return False


def _run_device(device, active_languages, run_folder):
    driver               = None
    results              = []
    device_frames        = []
    sub_skipped          = False
    sub_already_active   = False
    unsub_failed         = False
    confirm_unavailable  = False
    still_subscribed_seen = False
    profile_base         = None
    ty_params            = None
    device_folder = create_device_folder(run_folder, device["name"])

    try:
        device_label = device.get("device_name") or f"{device['width']}x{device['height']} dpr{device['pixel_ratio']}"
        log.info("=== Device: %s (%s) ===", device["name"], device_label)
        driver = _create_driver(device)

        # ── PHASE 1: Crawl (EN only) ─────────────────────────────────────────
        pages = discover_pages(driver, append_params(SHOP_BASE_URL, _EN_LAN_ID))
        log.info("Pages selected for testing: %d", len(pages))

        # ── PHASE 2: Unsubscribed checks — all languages ──────────────────────
        for lang_name, lang_id in active_languages:
            log.info("--- [unsubscribed] %s (lan=%d) ---", lang_name, lang_id)
            try:
                driver.delete_all_cookies()
                driver.execute_script("window.localStorage.clear(); window.sessionStorage.clear();")
            except Exception as exc:
                log.warning("Session clear failed: %s", exc)

            for page_info in pages:
                label = page_info["page"].replace(".php", "")
                if page_info["extra_params"]:
                    label += "_" + "_".join(str(v) for v in page_info["extra_params"].values())
                test_url = append_params(
                    _SHOP_DIR + "/" + page_info["page"],
                    lang_id,
                    page_info["extra_params"],
                )
                try:
                    driver.get(test_url)
                    _record_check(driver, device_folder, lang_name, label, results)
                except Exception as exc:
                    log.warning("Check error for %s/%s: %s", lang_name, label, exc)
                    results.append({
                        "lang":       lang_name,
                        "page_label": label,
                        "checks":     {"error": str(exc)},
                        "status":     "ERROR",
                    })

        # ── PHASE 3: Subscribe once (EN) ─────────────────────────────────────
        log.info("--- Subscribe (EN) ---")
        sub_status, success_url = subscribe(
            driver,
            append_params(LANDING_BASE_URL, _EN_LAN_ID),
            device_frames,
        )
        sub_already_active = (sub_status == "already_subscribed")

        if sub_status == "failed":
            log.warning("Subscription failed — skipping subscribed profile/library checks")
            sub_skipped = True
        else:
            if sub_already_active:
                # Landing redirected to index.php: already subscribed (e.g. leftover
                # from an aborted run). JOIN/CONFIRM cannot be exercised, but the
                # subscribed state IS active — still run every language's subscribed
                # checks (Phase 4) and still cancel once at the end (Phase 5).
                log.warning("Already subscribed — JOIN/CONFIRM skipped; running subscribed checks + unsubscribe")
                profile_base = _SHOP_DIR + "/profile.php"
                ty_params    = {"access_token": ACCESS_TOKEN, "agent_uid": AGENT_UID}
            else:
                # Derive profile base from success URL
                ty_parsed = urllib.parse.urlparse(success_url)
                if ty_parsed.netloc == APK_DOWNLOAD_HOST:
                    profile_base = _SHOP_DIR + "/profile.php"
                    ty_params    = {"access_token": ACCESS_TOKEN, "agent_uid": AGENT_UID}
                else:
                    profile_base = urllib.parse.urlunparse(
                        ty_parsed._replace(
                            path=ty_parsed.path.rsplit("/", 1)[0] + "/profile.php"
                        )
                    )
                    ty_params = dict(urllib.parse.parse_qsl(ty_parsed.query))

            # Discover library base URL once from EN profile (href pattern, language-agnostic)
            lib_base = None
            try:
                driver.get(profile_base + "?" + urllib.parse.urlencode({**ty_params, "lan": _EN_LAN_ID}))
                lib_base = driver.execute_script("""
                    var links = document.querySelectorAll('a');
                    for (var i = 0; i < links.length; i++) {
                        if (links[i].href && links[i].href.indexOf('library.php') !== -1) {
                            return links[i].href.split('?')[0];
                        }
                    }
                    return null;
                """)
                if lib_base:
                    log.info("Library base URL: %s", lib_base)
                else:
                    log.warning("Library base URL not found on EN profile page")
            except Exception as exc:
                log.warning("Could not discover library base URL: %s", exc)

            # ── PHASE 4: Subscribed checks — all languages ────────────────────
            for lang_name, lang_id in active_languages:
                log.info("--- [subscribed] %s (lan=%d) ---", lang_name, lang_id)
                profile_url = profile_base + "?" + urllib.parse.urlencode({**ty_params, "lan": lang_id})
                try:
                    driver.get(profile_url)
                    _record_check(driver, device_folder, lang_name, "profile_settings", results)

                    # Thank-you / success page — only reachable while subscribed,
                    # so captured here (not in Phase 6). Reuse the success URL from
                    # the one-time subscribe, swapping lan=. Skipped when already
                    # subscribed (no success URL) or when the success is an APK.
                    if success_url and APK_DOWNLOAD_HOST not in success_url:
                        ty_parts = urllib.parse.urlparse(success_url)
                        ty_query = dict(urllib.parse.parse_qsl(ty_parts.query))
                        ty_query["lan"] = lang_id
                        driver.get(urllib.parse.urlunparse(
                            ty_parts._replace(query=urllib.parse.urlencode(ty_query))
                        ))
                        _record_check(driver, device_folder, lang_name, "thankyou", results)

                    if lib_base:
                        lib_href = lib_base + "?" + urllib.parse.urlencode({**ty_params, "lan": lang_id})

                        driver.get(lib_href)
                        _record_check(driver, device_folder, lang_name, "library_all_games", results)

                        driver.get(lib_href)
                        if _try_click_text(driver, "FAVORITE GAMES"):
                            _record_check(driver, device_folder, lang_name, "library_favorite_games", results)

                        driver.get(lib_href)
                        if _try_click_text(driver, "MY DOWNLOADS"):
                            _record_check(driver, device_folder, lang_name, "library_my_downloads", results)

                        driver.get(lib_href)
                        if _try_click_text(driver, "ALL VIDEOS"):
                            _record_check(driver, device_folder, lang_name, "library_all_videos", results)

                            if _try_click_text(driver, "FAVORITE VIDEOS"):
                                _record_check(driver, device_folder, lang_name, "library_favorite_videos", results)

                            driver.get(lib_href)
                            if _try_click_text(driver, "ALL VIDEOS"):
                                if _try_click_text(driver, "RECENTLY PLAYED"):
                                    _record_check(driver, device_folder, lang_name, "library_recently_played", results)
                    else:
                        log.warning("Library base URL unknown — skipping library sections for %s", lang_name)

                except Exception as exc:
                    log.warning("Profile/library check error for %s: %s", lang_name, exc)

            # ── PHASE 5: Unsubscribe once ─────────────────────────────────────
            log.info("--- Unsubscribe ---")
            unsub_url = profile_base + "?" + urllib.parse.urlencode({**ty_params, "lan": _EN_LAN_ID})
            if not unsubscribe(driver, unsub_url):
                log.warning("Unsubscription failed — manual cleanup may be required")
                unsub_failed = True

        # ── PHASE 6: Subscription-flow pages (unsubscribed state) ───────────
        # Landing page and confirmation page (wap_confirm=1) are only meaningful
        # while unsubscribed, so they are captured here — after Phase 5 — for
        # every language, by URL only (no JOIN/CONFIRM clicks, so no re-subscribe).
        log.info("--- Subscription-flow page checks (every language) ---")
        confirm_caught = 0
        for lang_name, lang_id in active_languages:
            try:
                driver.delete_all_cookies()
                driver.execute_script("window.localStorage.clear(); window.sessionStorage.clear();")
            except Exception as exc:
                log.warning("Session clear failed: %s", exc)

            try:
                driver.get(append_params(LANDING_BASE_URL, lang_id))
                if "index.php" in driver.current_url:
                    still_subscribed_seen = True
                    log.warning("[%s] landing redirected to index.php — still subscribed, landing skipped", lang_name)
                else:
                    _record_check(driver, device_folder, lang_name, "landing", results)
            except Exception as exc:
                log.warning("Landing capture error for %s: %s", lang_name, exc)

            try:
                driver.get(append_params(LANDING_BASE_URL, lang_id, {"wap_confirm": 1}))
                if "wap_confirm" in driver.current_url:
                    _record_check(driver, device_folder, lang_name, "landing_confirm", results)
                    confirm_caught += 1
                else:
                    log.info("[%s] confirmation page (wap_confirm=1) not directly loadable — skipped", lang_name)
            except Exception as exc:
                log.warning("Confirmation capture error for %s: %s", lang_name, exc)

        confirm_unavailable = (confirm_caught == 0)

        # Safety net: guarantee the subscription is cancelled before exit.
        if profile_base is not None and (unsub_failed or still_subscribed_seen):
            log.info("--- Final unsubscribe safety check ---")
            try:
                driver.delete_all_cookies()
                driver.get(append_params(LANDING_BASE_URL, _EN_LAN_ID))
                if "index.php" in driver.current_url:
                    log.warning("Still subscribed — cancelling again")
                    unsub_url = profile_base + "?" + urllib.parse.urlencode({**ty_params, "lan": _EN_LAN_ID})
                    unsub_failed = not unsubscribe(driver, unsub_url)
                else:
                    unsub_failed = False
            except Exception as exc:
                log.warning("Final unsubscribe safety check error: %s", exc)

        if device_frames:
            video_path = os.path.join(device_folder, "subscription_recording.mp4")
            try:
                writer = imageio.get_writer(video_path, fps=1, macro_block_size=1)
                for frame_bytes in device_frames:
                    img = imageio.imread(io.BytesIO(frame_bytes))
                    # libx264 requires even width and height
                    h, w = img.shape[:2]
                    ph, pw = h + h % 2, w + w % 2
                    if ph != h or pw != w:
                        padded = np.zeros((ph, pw, img.shape[2]), dtype=img.dtype)
                        padded[:h, :w] = img
                        img = padded
                    for _ in range(5):
                        writer.append_data(img)
                writer.close()
                log.info("Subscription recording saved → %s", video_path)
            except Exception as exc:
                log.warning("Failed to save subscription recording: %s", exc)

        write_summary(
            results, device_folder, device["name"],
            sub_skipped=sub_skipped,
            sub_already_active=sub_already_active,
            unsub_failed=unsub_failed,
            confirm_unavailable=confirm_unavailable,
        )

    finally:
        if driver is not None:
            try:
                driver.delete_all_cookies()
            except Exception as exc:
                log.warning("Cookie clear failed: %s", exc)
            driver.quit()
            log.info("Driver quit for device %s", device["name"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang",   nargs="+", metavar="LANG",
                        help="Run only these language codes, e.g. --lang EN AR")
    parser.add_argument("--device", nargs="+", metavar="DEVICE",
                        help="Run only these device names, e.g. --device device_placeholder_1")
    args = parser.parse_args()

    lang_filter   = set(args.lang)   if args.lang   else None
    device_filter = set(args.device) if args.device else None

    active_languages = [
        (name, lid) for name, lid in LANGUAGES
        if lang_filter is None or name in lang_filter
    ]
    active_devices = [
        d for d in EMULATED_DEVICES
        if device_filter is None or d["name"] in device_filter
    ]

    if not active_languages:
        raise SystemExit(f"No languages matched filter: {args.lang}")
    if not active_devices:
        raise SystemExit(f"No devices matched filter: {args.device}")

    run_folder = create_run_folder()
    for device in active_devices:
        _run_device(device, active_languages, run_folder)


if __name__ == "__main__":
    main()
