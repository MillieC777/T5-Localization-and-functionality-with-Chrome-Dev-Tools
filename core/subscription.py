import base64
import time
import logging
from urllib.parse import urlparse
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

from config.settings import PAGE_LOAD_TIMEOUT, STEP_PAUSE, MAX_WAIT_SECONDS, APK_DOWNLOAD_HOST
from core.checks import dismiss_a2hs

log = logging.getLogger(__name__)


def _capture_frame(driver, frames):
    try:
        result = driver.execute_cdp_cmd("Page.captureScreenshot", {"format": "jpeg", "quality": 70})
        frames.append(base64.b64decode(result["data"]))
    except Exception as exc:
        log.debug("Frame capture skipped: %s", exc)


_THANKYOU_FRAGMENT   = "thankyou.php"
_PRODUCT_FRAGMENT    = "product.php"
_SUCCESS_SRC_MARKERS = [APK_DOWNLOAD_HOST, ".apk\"", "thankyou.php", "thank you", "download now"]


def _is_success_url(url):
    return (
        _THANKYOU_FRAGMENT in url
        or _PRODUCT_FRAGMENT in url
        or APK_DOWNLOAD_HOST in url
    )


def _source_has_success(driver):
    try:
        return any(m in driver.page_source.lower() for m in _SUCCESS_SRC_MARKERS)
    except Exception:
        return False


def subscribe(driver, landing_url, frames=None):
    """
    Navigate to landing_url and complete the subscription flow.
    If frames is provided, JPEG screenshots are appended at key steps
    for stitching into the per-device subscription recording.

    Returns one of:
        ("success",            success_url)  — subscription confirmed
        ("already_subscribed", "")           — landing redirected to index.php
        ("failed",             "")           — CTA not found or poll timed out
    """
    result = ("failed", "")
    try:
        log.info("Navigating to landing page")
        driver.get(landing_url)
        if frames is not None:
            _capture_frame(driver, frames)

        dismiss_a2hs(driver)

        if "index.php" in driver.current_url:
            log.info("Landing redirected to index.php — subscription already active")
            return ("already_subscribed", "")

        if _is_success_url(driver.current_url):
            log.info("Landed directly on success page")
            time.sleep(STEP_PAUSE)
            if frames is not None:
                _capture_frame(driver, frames)
            return ("success", driver.current_url)

        # STEP 1 — Landing CTA click
        try:
            btn = WebDriverWait(driver, PAGE_LOAD_TIMEOUT).until(
                EC.element_to_be_clickable((By.TAG_NAME, "button"))
            )
            cta_text = btn.text.strip().upper()
            log.info("Landing CTA found (%r) — waiting %ds before click", btn.text, STEP_PAUSE)
            time.sleep(STEP_PAUSE)
            driver.execute_script("arguments[0].click()", btn)
        except Exception as exc:
            log.warning("Landing CTA not clickable: %s", exc)
            return result

        time.sleep(3)
        if frames is not None:
            _capture_frame(driver, frames)
        try:
            all_btns  = driver.find_elements(By.TAG_NAME, "button")
            btn_texts = [b.text.strip() for b in all_btns if b.is_displayed() and b.text.strip()]
            log.info("Buttons visible 3s after CTA click: %s | page_title=%r", btn_texts, driver.title)
        except Exception:
            pass

        # STEP 2 — Look for a visible confirmation button with different text
        if _is_success_url(driver.current_url):
            log.info("Already on success page after step 1")
            time.sleep(STEP_PAUSE)
            if frames is not None:
                _capture_frame(driver, frames)
            return ("success", driver.current_url)

        confirm_btn    = None
        step2_deadline = time.time() + 10
        while time.time() < step2_deadline:
            try:
                for b in driver.find_elements(By.TAG_NAME, "button"):
                    txt = b.text.strip().upper()
                    if txt and txt != cta_text and b.is_displayed():
                        confirm_btn = b
                        break
            except Exception:
                pass
            if confirm_btn or "wap_confirm" in driver.current_url:
                break
            time.sleep(1)

        if confirm_btn or "wap_confirm" in driver.current_url:
            if confirm_btn is None:
                try:
                    confirm_btn = driver.find_element(By.TAG_NAME, "button")
                except Exception:
                    pass
            if confirm_btn is not None:
                log.info("Confirmation button found (%r) — clicking", confirm_btn.text)
                time.sleep(STEP_PAUSE)
                driver.execute_script("arguments[0].click()", confirm_btn)
                if frames is not None:
                    _capture_frame(driver, frames)
        else:
            log.info("No confirmation button found — proceeding to poll")

        # STEP 3 — Poll for final success URL or page content
        deadline          = time.time() + MAX_WAIT_SECONDS
        _last_logged_page = ""
        while time.time() < deadline:
            url = driver.current_url
            if _is_success_url(url):
                log.info("Subscription confirmed via URL")
                time.sleep(STEP_PAUSE)
                if frames is not None:
                    _capture_frame(driver, frames)
                return ("success", url)
            if _source_has_success(driver):
                log.info("Subscription confirmed via page content")
                time.sleep(STEP_PAUSE)
                if frames is not None:
                    _capture_frame(driver, frames)
                return ("success", url)
            page = urlparse(url).path.rsplit("/", 1)[-1]
            if page != _last_logged_page:
                log.info("Subscription poll: browser on %r", page)
                _last_logged_page = page
            time.sleep(2)

        log.warning("Subscription timed out after %ds — last page: %r", MAX_WAIT_SECONDS, _last_logged_page)
        return result

    except Exception as exc:
        log.warning("Subscription error: %s", exc)
        return result


def unsubscribe(driver, profile_url):
    """
    Navigate to profile_url, click Manage Subscription then Cancel Subscription.
    Returns True when redirect away from profile.php is confirmed.
    """
    log.info("Navigating to profile page for unsubscription")
    driver.get(profile_url)
    time.sleep(2)

    try:
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        time.sleep(1)
    except Exception:
        pass

    try:
        manage_btn = WebDriverWait(driver, PAGE_LOAD_TIMEOUT).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//*[normalize-space(.)='MANAGE SUBSCRIPTION']")
            )
        )
        manage_btn.click()
        log.info("Clicked Manage Subscription")
    except Exception as exc:
        log.warning("Manage Subscription button not found: %s", exc)
        return False

    try:
        cancel_btn = WebDriverWait(driver, PAGE_LOAD_TIMEOUT).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//*[normalize-space(.)='CANCEL SUBSCRIPTION']")
            )
        )
        cancel_btn.click()
        log.info("Clicked Cancel Subscription")
    except Exception as exc:
        log.warning("Cancel Subscription button not found: %s", exc)
        return False

    try:
        WebDriverWait(driver, PAGE_LOAD_TIMEOUT).until(
            lambda d: "profile.php" not in d.current_url
        )
        log.info("Unsubscription confirmed")
        return True
    except Exception:
        log.warning("No redirect after cancel — unsubscription may have failed")
        return False
