import os
import re
import shutil
from datetime import datetime

from langdetect import detect, DetectorFactory
from langdetect.lang_detect_exception import LangDetectException
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

from config.keys import TRANSLATION_KEYS
from config.languages import LANG_DETECT_MAP
from core.reporter import write_summary

DetectorFactory.seed = 0  # ensures consistent detection results across runs

_RAW_KEY_PATTERN = re.compile(r'\{[a-z][a-z_]*\}|\b[a-z][a-z_]*(?:\.[a-z][a-z_]*){2,}\b')

PAGE_LOAD_TIMEOUT    = 30
MOBILE_WIDTH         = 393
MOBILE_HEIGHT        = 851
MOBILE_PIXEL_RATIO   = 2.75
MOBILE_USER_AGENT    = (
    "Mozilla/5.0 (Linux; Android 11; Pixel 5) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Mobile Safari/537.36"
)

FAIL_REASONS = {
    "raw_keys":              "Raw key patterns visible in page text",
    "raw_translation_keys":  "Known translation keys visible as raw text",
    "wrong_language":        "Page text detected in wrong language",
}


def navigate_to_page(driver, url, lang_id):
    driver.get(url.format(lang_id=lang_id))


def check_no_raw_keys(body_text):
    return sorted(set(_RAW_KEY_PATTERN.findall(body_text)))


def check_translation_keys(body_text):
    return [k for k in TRANSLATION_KEYS if re.search(r'\b' + re.escape(k) + r'\b', body_text)]


def check_language(body_text, lang_name):
    expected = LANG_DETECT_MAP.get(lang_name)
    if not expected:
        return None
    try:
        detected = detect(body_text)
        return detected if detected != expected else None
    except LangDetectException:
        return None


def capture_screenshot(driver, lang_name, page_name, run_folder):
    directory = os.path.join("results", run_folder, "screenshots", page_name)
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"{lang_name}.png")
    driver.save_screenshot(path)
    return path


def run_checks(ticket_id, languages, pages):
    run_folder = f"{ticket_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(os.path.join("results", run_folder), exist_ok=True)

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_experimental_option("mobileEmulation", {
        "deviceMetrics": {
            "width":       MOBILE_WIDTH,
            "height":      MOBILE_HEIGHT,
            "pixelRatio":  MOBILE_PIXEL_RATIO,
        },
        "userAgent": MOBILE_USER_AGENT,
    })
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options,
    )
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)

    total   = len(languages) * len(pages)
    count   = 0
    results = []
    try:
        for lang_name, lang_id in languages:
            for url_template, page_name in pages:
                count += 1
                navigate_to_page(driver, url_template, lang_id)
                body_text            = driver.find_element(By.TAG_NAME, "body").text
                raw_keys             = check_no_raw_keys(body_text)
                raw_translation_keys = check_translation_keys(body_text)
                detected_language    = check_language(body_text, lang_name)
                screenshot_path      = capture_screenshot(driver, lang_name, page_name, run_folder)
                failed_criteria = []
                if raw_keys:
                    failed_criteria.append(FAIL_REASONS["raw_keys"])
                if raw_translation_keys:
                    failed_criteria.append(FAIL_REASONS["raw_translation_keys"])
                if detected_language:
                    failed_criteria.append(FAIL_REASONS["wrong_language"])
                status = "FAIL" if failed_criteria else "PASS"
                if status == "FAIL":
                    flagged_dir = os.path.join("results", run_folder, "flagged")
                    os.makedirs(flagged_dir, exist_ok=True)
                    shutil.copy(screenshot_path, os.path.join(flagged_dir, f"{lang_name}_{page_name}.png"))
                results.append({
                    "language":             lang_name,
                    "page":                 page_name,
                    "url":                  driver.current_url,
                    "raw_keys":             raw_keys,
                    "raw_translation_keys": raw_translation_keys,
                    "detected_language":    detected_language,
                    "failed_criteria":      failed_criteria,
                    "screenshot":           screenshot_path,
                    "status":               status,
                })
                print(f"  [{lang_name} / {page_name}] {count}/{total}")
    finally:
        driver.quit()

    write_summary(ticket_id, results, run_folder)
