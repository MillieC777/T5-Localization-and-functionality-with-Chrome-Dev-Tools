import logging
import os
import time
from urllib.parse import urlparse, parse_qsl, urlencode

from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException

from config.settings import MAX_APK_GAMES, MAX_HTML5_GAMES, MAX_VIDEOS

log = logging.getLogger(__name__)

_STRIP_PARAMS = {
    "lan", "access_token", "agent_uid", "adid", "opref",
    "sv", "phoneId", "c", "from",
}

_AUTH_PARAMS = {"lan", "access_token", "agent_uid", "adid", "opref"}

_SKIP_PAGES = {
    "index.php", "profile.php", "landing5.php", "landing6.php", "thankyou.php",
}

_LISTING_PAGES = {"games.php", "videos.php", "conditions.php", "help.php", "search.php"}

_VIDEO_PAGES = {"video.php", "videos.php"}

_LIMITS = {
    "apk_game":   MAX_APK_GAMES,
    "html5_game": MAX_HTML5_GAMES,
    "video":      MAX_VIDEOS,
    "other":      5,
}


def _detect_content_type(driver, filename):
    if filename in _VIDEO_PAGES:
        return "video"
    if filename in _LISTING_PAGES:
        return "other"

    try:
        if driver.find_elements(By.TAG_NAME, "video"):
            return "video"
        if ".apk" in driver.page_source.lower():
            return "apk_game"
        if filename == "product.php":
            play_els = driver.find_elements(
                By.XPATH,
                "//*[contains(translate(normalize-space(.), 'PLAY', 'play'), 'play')]",
            )
            if any(el.is_displayed() for el in play_els):
                return "html5_game"
    except Exception as exc:
        log.warning("Content type detection error for %s: %s", filename, exc)
    return "other"


def discover_pages(driver, index_url):
    parsed_index = urlparse(index_url)
    shop_dir     = (
        parsed_index.scheme + "://" + parsed_index.netloc
        + parsed_index.path.rsplit("/", 1)[0]
    )
    index_auth = {k: v for k, v in parse_qsl(parsed_index.query) if k in _AUTH_PARAMS}

    log.info("Crawling index page")
    for attempt in range(3):
        try:
            driver.get(index_url)
            break
        except TimeoutException:
            if attempt == 2:
                raise
            log.warning("Index page load timed out (attempt %d/3) — retrying", attempt + 1)
            time.sleep(5)

    link_elements = driver.find_elements(By.TAG_NAME, "a")
    seen_keys     = set()
    candidates    = []

    for el in link_elements:
        href = (el.get_attribute("href") or "").split("#")[0].strip()
        if not href.startswith(shop_dir):
            continue
        parsed   = urlparse(href)
        filename = os.path.basename(parsed.path)
        if filename in _SKIP_PAGES:
            continue
        extra = {k: v for k, v in parse_qsl(parsed.query) if k not in _STRIP_PARAMS}
        key   = filename + ("?" + urlencode(sorted(extra.items())) if extra else "")
        if key in seen_keys:
            continue
        seen_keys.add(key)

        href_param_keys = {k for k, _ in parse_qsl(parsed.query)}
        if "access_token" not in href_param_keys:
            sep  = "&" if "?" in href else "?"
            href = href + sep + urlencode(index_auth)
        candidates.append((filename, extra, href))

    log.info("Found %d unique candidate pages on index", len(candidates))

    counts   = {t: 0 for t in _LIMITS}
    selected = [
        {"page": "index.php",   "extra_params": {}, "content_type": "index"},
        {"page": "profile.php", "extra_params": {}, "content_type": "other"},
    ]

    for filename, extra, visit_url in candidates:
        try:
            driver.get(visit_url)
            ctype = _detect_content_type(driver, filename)
        except Exception as exc:
            log.warning("Could not visit %s: %s", filename, exc)
            continue

        if counts.get(ctype, 0) < _LIMITS.get(ctype, 0):
            selected.append({"page": filename, "extra_params": extra, "content_type": ctype})
            counts[ctype] = counts.get(ctype, 0) + 1
            label = filename + ("?" + urlencode(extra) if extra else "")
            log.info("Selected [%s] %s", ctype, label)
        else:
            log.info("Limit reached for [%s] — skipping %s", ctype, filename)

    log.info("Crawl complete | selected=%d | breakdown=%s", len(selected), counts)
    return selected
