import re
import logging
from selenium.webdriver.common.by import By
from langdetect import detect, DetectorFactory
from langdetect.lang_detect_exception import LangDetectException

from config.keys import TRANSLATION_KEYS, OVERFLOW_IGNORE_TEXTS
from config.languages import LANG_DETECT_MAP
from config.settings import MIN_FONT_SIZE_PX, MIN_CONTRAST_RATIO

DetectorFactory.seed = 0

log = logging.getLogger(__name__)

_RAW_KEY_PATTERN = re.compile(r'\{[a-z][a-z_]*\}|\b[a-z][a-z_]*(?:\.[a-z][a-z_]*){2,}\b')

_TEXT_SELECTORS = "p, span, h1, h2, h3, h4, li, a, button, label"

_OVERFLOW_JS = """
var results = [];
var els = document.querySelectorAll('SELECTORS');
for (var i = 0; i < els.length; i++) {
    var el = els[i];
    if (!el.offsetParent && el.tagName !== 'BODY') continue;
    var fs = parseFloat(window.getComputedStyle(el).fontSize);
    if (fs <= 0) continue;
    if (el.clientWidth < 5) continue;
    if (el.scrollWidth > el.clientWidth + 2 || el.scrollHeight > el.clientHeight + 2) {
        var t = (el.innerText || '').trim().slice(0, 80);
        if (!t || t.length < 3) continue;
        results.push(t);
    }
}
return results.slice(0, 20);
""".replace("SELECTORS", _TEXT_SELECTORS)

_CONTRAST_JS = """
function luminance(r, g, b) {
    return [r, g, b].map(function(v) {
        v /= 255;
        return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    }).reduce(function(acc, v, i) {
        return acc + v * [0.2126, 0.7152, 0.0722][i];
    }, 0);
}
function parseRgba(str) {
    var m = str.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)(?:,\\s*([\\d.]+))?/);
    return m ? {r: +m[1], g: +m[2], b: +m[3], a: m[4] !== undefined ? +m[4] : 1} : null;
}
function effectiveBg(el) {
    var node = el;
    while (node && node !== document.documentElement) {
        var style = window.getComputedStyle(node);
        if (style.backgroundImage && style.backgroundImage !== 'none') return null;
        var bg = parseRgba(style.backgroundColor);
        if (bg && bg.a >= 1) return bg;
        node = node.parentElement;
    }
    return {r: 255, g: 255, b: 255, a: 1};
}
var failures = [];
var els = document.querySelectorAll('SELECTORS');
for (var i = 0; i < els.length; i++) {
    var el = els[i];
    var text = (el.innerText || '').trim();
    if (!text || !el.offsetParent) continue;
    var fs = parseFloat(window.getComputedStyle(el).fontSize);
    if (fs <= 0) continue;
    var fg = parseRgba(window.getComputedStyle(el).color);
    if (!fg || fg.a < 1) continue;
    var bg = effectiveBg(el);
    if (!bg) continue;
    var l1 = luminance(fg.r, fg.g, fg.b) + 0.05;
    var l2 = luminance(bg.r, bg.g, bg.b) + 0.05;
    var ratio = l1 > l2 ? l1 / l2 : l2 / l1;
    if (ratio < CONTRAST_THRESHOLD) {
        failures.push(text.slice(0, 80) + ' [ratio=' + ratio.toFixed(2) + ']');
    }
}
return failures.slice(0, 20);
""".replace("SELECTORS", _TEXT_SELECTORS).replace("CONTRAST_THRESHOLD", str(MIN_CONTRAST_RATIO))

_FONT_SIZE_JS = """
var results = [];
var els = document.querySelectorAll('SELECTORS');
for (var i = 0; i < els.length; i++) {
    var el = els[i];
    var text = (el.innerText || '').trim();
    if (!text || !el.offsetParent) continue;
    var fs = parseFloat(window.getComputedStyle(el).fontSize);
    if (fs <= 0) continue;
    if (fs < MIN_SIZE) {
        results.push(text.slice(0, 80) + ' [' + fs + 'px]');
    }
}
return results.slice(0, 20);
""".replace("SELECTORS", _TEXT_SELECTORS).replace("MIN_SIZE", str(MIN_FONT_SIZE_PX))


def find_raw_keys(body_text):
    return sorted(set(_RAW_KEY_PATTERN.findall(body_text)))


def find_untranslated_keys(body_text, lang_name):
    if lang_name == "EN":
        return []
    return [k for k in TRANSLATION_KEYS if re.search(r'\b' + re.escape(k) + r'\b', body_text)]


def detect_wrong_language(body_text, lang_name):
    expected = LANG_DETECT_MAP.get(lang_name)
    if not expected:
        return None
    try:
        detected = detect(body_text)
        return detected if detected != expected else None
    except LangDetectException:
        return None


def find_overflow_elements(driver):
    try:
        results = driver.execute_script(_OVERFLOW_JS) or []
        return [r for r in results if not any(t in r for t in OVERFLOW_IGNORE_TEXTS)]
    except Exception as exc:
        log.warning("Overflow check failed: %s", exc)
        return []


def find_contrast_failures(driver):
    try:
        return driver.execute_script(_CONTRAST_JS) or []
    except Exception as exc:
        log.warning("Contrast check failed: %s", exc)
        return []


def find_small_font_elements(driver):
    try:
        return driver.execute_script(_FONT_SIZE_JS) or []
    except Exception as exc:
        log.warning("Font size check failed: %s", exc)
        return []


def dismiss_a2hs(driver):
    """Click the close/× button of the Add to Home Screen banner if present."""
    try:
        dismissed = driver.execute_script("""
            var tags = ['button','span','div','a','i'];
            for (var t = 0; t < tags.length; t++) {
                var els = document.querySelectorAll(tags[t]);
                for (var i = 0; i < els.length; i++) {
                    var el = els[i];
                    if (!el.offsetParent) continue;
                    var txt = (el.innerText || el.textContent || '').trim();
                    var lbl = (el.getAttribute('aria-label') || '').toLowerCase();
                    if (txt === '\xd7' || txt === '✕' || txt === '✖'
                            || lbl === 'close' || lbl === 'dismiss') {
                        el.click();
                        return true;
                    }
                }
            }
            return false;
        """)
        if dismissed:
            log.debug("A2HS popup dismissed")
        return bool(dismissed)
    except Exception as exc:
        log.debug("dismiss_a2hs: %s", exc)
        return False


def run_page_checks(driver, lang_name):
    body_text = ""
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text
    except Exception as exc:
        log.warning("Could not read body text: %s", exc)

    return {
        "raw_keys":            find_raw_keys(body_text),
        "untranslated_keys":   find_untranslated_keys(body_text, lang_name),
        "wrong_language":      detect_wrong_language(body_text, lang_name),
        "overflow_elements":   find_overflow_elements(driver),
        "contrast_failures":   find_contrast_failures(driver),
        "small_font_elements": find_small_font_elements(driver),
    }
