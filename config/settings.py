import os
import sys

from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN     = os.environ.get("ACCESS_TOKEN",     "")
AGENT_UID        = os.environ.get("AGENT_UID",        "")
ADID             = os.environ.get("ADID",             "")
OPREF            = os.environ.get("OPREF",            "")
SHOP_BASE_URL    = os.environ.get("SHOP_BASE_URL",    "")
LANDING_BASE_URL = os.environ.get("LANDING_BASE_URL", "")

_missing = [
    name for name, val in [
        ("ACCESS_TOKEN",     ACCESS_TOKEN),
        ("AGENT_UID",        AGENT_UID),
        ("ADID",             ADID),
        ("OPREF",            OPREF),
        ("SHOP_BASE_URL",    SHOP_BASE_URL),
        ("LANDING_BASE_URL", LANDING_BASE_URL),
    ]
    if not val
]
if _missing:
    sys.exit("Missing required .env variables: " + ", ".join(_missing))

PAGE_LOAD_TIMEOUT = 60
STEP_PAUSE        = 3
MAX_WAIT_SECONDS  = 60

MAX_APK_GAMES   = 3
MAX_HTML5_GAMES = 3
MAX_VIDEOS      = 3

MIN_FONT_SIZE_PX   = 10
MIN_CONTRAST_RATIO = 4.5

APK_DOWNLOAD_HOST = "dl.gameloft.com"
