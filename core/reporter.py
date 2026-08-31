import os
import shutil
import logging
from datetime import datetime

log = logging.getLogger(__name__)

_SUMMARY_WIDTH = 72

_HARD_LABELS = {
    "raw_keys":          "Raw key patterns",
    "untranslated_keys": "Known untranslated keys",
    "wrong_language":    "Wrong language detected",
    "overflow_elements": "Text overflow",
}
_ADVISORY_LABELS = {
    "contrast_failures":   "Contrast too low",
    "small_font_elements": "Font size below minimum",
}


def create_run_folder():
    folder = os.path.join("results", f"crawl_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    os.makedirs(folder, exist_ok=True)
    return folder


def create_device_folder(run_folder, device_name):
    folder = os.path.join(run_folder, device_name)
    os.makedirs(os.path.join(folder, "screenshots"), exist_ok=True)
    os.makedirs(os.path.join(folder, "flagged"),     exist_ok=True)
    return folder


def save_screenshot(driver, run_folder, lang_name, page_label):
    path = os.path.join(run_folder, "screenshots", f"{lang_name}_{page_label}.png")
    try:
        driver.save_screenshot(path)
    except Exception as exc:
        log.warning("Screenshot failed for %s/%s: %s", lang_name, page_label, exc)
        return ""
    return path


def flag_screenshot(screenshot_path, run_folder, lang_name, page_label):
    if not screenshot_path:
        return
    dest = os.path.join(run_folder, "flagged", f"{lang_name}_{page_label}.png")
    shutil.copy(screenshot_path, dest)


def write_summary(results, run_folder, device_name, sub_skipped=False,
                  sub_already_active=False, unsub_failed=False, confirm_unavailable=False):
    total    = len(results)
    passed   = sum(1 for r in results if r["status"] == "PASS")
    failures = [r for r in results if r["status"] != "PASS"]

    unique_langs = list(dict.fromkeys(r["lang"]       for r in results))
    unique_pages = list(dict.fromkeys(r["page_label"] for r in results))

    lines = [
        "=" * _SUMMARY_WIDTH,
        "  Localization Crawl Summary",
        f"  Device : {device_name}",
        f"  Run    : {run_folder}",
        "=" * _SUMMARY_WIDTH,
        "",
        "TESTED",
        f"  Languages : {', '.join(unique_langs)}",
        f"  Pages     : {', '.join(unique_pages)}",
        f"  Total     : {total}",
        "",
        "RESULTS",
        f"  PASS : {passed}/{total}",
        f"  FAIL : {len(failures)}/{total}",
    ]

    hard_failures = [r for r in failures if any(r["checks"].get(k) for k in _HARD_LABELS)]
    advisory_hits = [r for r in results if any(r["checks"].get(k) for k in _ADVISORY_LABELS)]

    if hard_failures:
        lines += ["", "FLAGGED (localization issues)"]
        for r in hard_failures:
            lines.append(f"\n  [{r['status']}] {r['lang']} / {r['page_label']}")
            for key, label in _HARD_LABELS.items():
                val = r["checks"].get(key)
                if not val:
                    continue
                if isinstance(val, list):
                    lines.append(f"    {label}:")
                    for item in val:
                        lines.append(f"      - {item}")
                else:
                    lines.append(f"    {label}: {val}")
    else:
        lines += ["", "  No localization issues flagged."]

    if advisory_hits:
        lines += ["", "DESIGN ADVISORY (not counted as failures)"]
        for r in advisory_hits:
            for key, label in _ADVISORY_LABELS.items():
                val = r["checks"].get(key)
                if not val:
                    continue
                lines.append(f"\n  {r['lang']} / {r['page_label']}")
                if isinstance(val, list):
                    lines.append(f"    {label}:")
                    for item in val:
                        lines.append(f"      - {item}")
                else:
                    lines.append(f"    {label}: {val}")
                break

    if sub_already_active:
        lines += [
            "",
            "NOTE: SUBSCRIPTION ALREADY ACTIVE",
            "  The landing page redirected to index.php — already subscribed.",
            "  The JOIN NOW / CONFIRM flow could not be exercised this run and the",
            "  thank-you page was not captured (no success URL), but the",
            "  subscribed-state checks ran for every language and the subscription",
            "  was cancelled once at the end.",
        ]

    if sub_skipped:
        lines += [
            "",
            "WARNING: SUBSCRIPTION FAILED",
            "  The one-time subscription flow did not reach a success page.",
            "  Profile, library and thank-you checks were not performed.",
            "  Manual cleanup may be required before the next run.",
        ]

    if confirm_unavailable:
        lines += [
            "",
            "NOTE: CONFIRMATION PAGE NOT CAPTURED",
            "  The confirmation page (wap_confirm=1) could not be loaded directly",
            "  for any language — it only exists mid click-through. It remains",
            "  covered by the subscription screen recording.",
        ]

    if unsub_failed:
        lines += [
            "",
            "WARNING: UNSUBSCRIPTION FAILED",
            "  Subscription was not cancelled at end of run.",
            "  Manual cleanup required — unsubscribe before the next run.",
        ]

    lines += ["", "=" * _SUMMARY_WIDTH, ""]

    path = os.path.join(run_folder, "summary.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log.info("Summary written → %s", path)
