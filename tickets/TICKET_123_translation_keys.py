from core.language_checker import run_checks
from config.languages import LANGUAGES
from config.pages import PAGES as PAGE_URLS

PAGES = [
    (PAGE_URLS["LANDING5"],      "landing5"),
    (PAGE_URLS["LANDING6"],      "landing6"),
    (PAGE_URLS["PROFILE_SUB"],   "profile_subscription"),
    (PAGE_URLS["PROFILE_1TIME"], "profile_one_time_pass"),
]

LANGUAGE_SPECIFIC_CHECKS = {
    12: {"active-until": "Ativa até:", "offer-label-subscription": "Assinatura"},
    9:  {"active-until": "Ativo até:", "offer-label-subscription": "Subscrição"},
    4:  {"access-type": "Tipo de acceso:"},
    49: {"access-type": "Acceso de tipo:"},
    84: {"rtl": True},
    19: {"dash_instead_of_colon": True},
}

# ─── Manual screenshot review ──────────────────────────────────────────────────
# LP5 / LP6        offer labels bold; no double colons; correct spacing before price
# AR  (84)         RTL: colons appear on LEFT side of labels
# MY  (19)         Burmese: confirm "-" instead of ":" is intentional; no glyph boxes
# TH  (72)         Thai: no missing glyphs or placeholder squares
# BR  (12)         "Ativa até:" · "Assinatura"   — NOT "Ativo até:" / "Subscrição"
# PT  (9)          "Ativo até:" · "Subscrição"   — NOT "Ativa até:" / "Assinatura"
# ES  (4)          "Tipo de acceso:"             — NOT "Acceso de tipo:"
# LE  (49)         "Acceso de tipo:"             — NOT "Tipo de acceso:"
# profile_subscription    access-type = "Subscription (recurring)" — translated
# profile_one_time_pass   access-type = "One-time pass" — NOT the recurring variant
# ───────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    run_checks("TICKET-123", LANGUAGES, PAGES)
