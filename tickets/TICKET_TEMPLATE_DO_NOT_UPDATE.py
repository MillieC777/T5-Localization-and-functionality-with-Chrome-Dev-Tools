# ==============================================================================
# TICKET TEMPLATE — DO NOT MODIFY THIS FILE
# Copy this file, rename it to your ticket (e.g. TICKET_456_my_check.py),
# then fill in the two placeholders marked with TODO below.
# ==============================================================================

from core.language_checker import run_checks
from config.languages import LANGUAGES
from config.pages import PAGES as PAGE_URLS

# TODO: Add the pages you want to test. Remove any you don't need.
# Available keys: LANDING5, LANDING6, PROFILE_SUB, PROFILE_1TIME
PAGES = [
    (PAGE_URLS["LANDING5"],      "landing5"),
    (PAGE_URLS["LANDING6"],      "landing6"),
    (PAGE_URLS["PROFILE_SUB"],   "profile_subscription"),
    (PAGE_URLS["PROFILE_1TIME"], "profile_one_time_pass"),
]

if __name__ == "__main__":
    run_checks("TICKET-000", LANGUAGES, PAGES)  # TODO: replace TICKET-000
