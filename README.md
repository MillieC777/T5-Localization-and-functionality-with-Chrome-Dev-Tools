# T5 Localization

The primary purpose of this framework is to perform a full template localization test across all 17 supported languages on the T5 wapshop pages. It also features a ticket template script that testers can copy and use for specific localization-related projects without touching the main test.

For each language × page combination it:
- Scans visible page text for raw/untranslated key patterns (`{placeholder}`, `dot.notation.keys`)
- Scans visible page text against a known list of translation keys (`config/keys.py`)
- Takes a full-page screenshot
- Logs everything to a plain-text summary

Results land in a timestamped folder under `results/` so runs never overwrite each other.

## Pages tested

| Key | Page |
|-----|------|
| LANDING5 | Landing page variant 5 |
| LANDING6 | Landing page variant 6 |
| PROFILE_SUB | Profile — subscription user |
| PROFILE_1TIME | Profile — one-time pass user |

## Languages

EN, AR, BR, PT, DE, ES, LE, FR, IT, MY, TH, RO, SK, NL, UA, RU, ID

## Setup

**Requirements:** Python 3.8+, Google Chrome

```powershell
# 1. Clone the repo
git clone https://github.com/your-username/T5-Localization.git
cd T5-Localization

# 2. Create and activate virtual environment
py -m venv venv
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set access token (required each session, or set permanently — see SETUP.txt)
$env:WAPSHOP_ACCESS_TOKEN = "your-token-here"
```

## Usage

```powershell
# Run all tickets (template is automatically skipped)
python run.py

# Run a specific ticket
python run.py tickets\TICKET_123_translation_keys.py
```

## Creating a ticket for a specific localization project

Copy the template and rename it to your ticket:

```powershell
copy tickets\TICKET_TEMPLATE_DO_NOT_UPDATE.py tickets\TICKET_456_your_check.py
```

Open the new file and fill in the two `TODO` placeholders: the pages to test and the ticket ID.

## Results

Each run creates a timestamped folder under `results/`:

```
results/TICKET-123_YYYYMMDD_HHMMSS/
  summary.txt                ← plain-text summary of flagged issues
  screenshots/
    landing5/                EN.png  AR.png  DE.png ...
    landing6/
    profile_subscription/
    profile_one_time_pass/
```

## Project structure

```
.
├── run.py                              # entry point; skips template files automatically
├── requirements.txt
├── config/
│   ├── languages.py                    # language codes and IDs
│   ├── pages.py                        # page URL templates
│   └── keys.py                         # known translation key names
├── core/
│   ├── language_checker.py             # Selenium engine + check logic
│   └── reporter.py                     # summary output
└── tickets/
    ├── TICKET_TEMPLATE_DO_NOT_UPDATE.py  ← copy this for new tickets
    └── TICKET_123_translation_keys.py
```

## Manual review checklist

Some things can't be caught automatically. After each run, verify screenshots for:

| Language | What to check |
|----------|---------------|
| LP5 / LP6 | Offer labels bold; no double colons; correct spacing before price |
| AR (84) | RTL layout — colons appear on the LEFT side of labels |
| MY (19) | Burmese uses "-" instead of ":" — confirm intentional; no glyph boxes |
| TH (72) | No missing glyphs or placeholder squares |
| BR (12) | "Ativa até:" and "Assinatura" — NOT "Ativo até:" / "Subscrição" |
| PT (9) | "Ativo até:" and "Subscrição" — NOT "Ativa até:" / "Assinatura" |
| ES (4) | "Tipo de acceso:" — NOT "Acceso de tipo:" |
| LE (49) | "Acceso de tipo:" — NOT "Tipo de acceso:" |
| Profile (sub) | Access type reads "Subscription (recurring)" — translated |
| Profile (1-time) | Access type reads "One-time pass" — NOT the recurring variant |

## License

MIT — see [LICENSE](LICENSE)
