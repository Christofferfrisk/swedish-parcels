# swedish-parcels

A Home Assistant custom integration that tracks Swedish parcel deliveries by parsing
shipping notification emails (Postnord, Budbee, Instabox, and retailer order confirmations).

## Why email-first?

Most Swedish carriers don't offer a clean consumer API, but they all send well-structured
notification emails. Parsing those gives us tracking numbers, ETAs, and status updates
without scraping or maintaining brittle API integrations.

## Architecture

Parser-first design:

```
src/swedish_parcels/
    parsers/        # one module per carrier/sender, each independently testable
    models.py       # Shipment dataclass — the canonical extracted record
    cli.py          # `parse-eml path/to/file.eml` for ad-hoc parser debugging
scripts/
    download_emails.py   # IMAP fetcher → writes .eml files into fixtures/<carrier>/
tests/              # pytest, one test module per parser, driven by fixtures
fixtures/           # real .eml files (gitignored — contain personal data)
```

The Home Assistant integration wraps this pure-Python core. The core has no HA
dependency and can run standalone.

## Quick start

```powershell
uv sync --extra dev
copy .env.example .env   # then fill in IMAP credentials
uv run python scripts/download_emails.py
uv run parse-eml fixtures/postnord/<some-file>.eml
uv run pytest
```

## Status

Parsers: Bring, Amazon, Airmee, Zalando (email-driven).
Tracker: Airmee live tracker scaffolded — needs browser-captured auth headers (see below).
Store: dedup + Airmee↔Amazon time-window linker.

## Open user actions

### 1. Harvest more fixtures from your inbox

The parsers are designed against only 7 real emails so far. To stress-test
them and discover the shape of "Skickad" / "Levererad" notifications, pull
a wider sample:

```powershell
copy .env.example .env
# edit .env: fill IMAP_HOST/USER/PASSWORD and PARCEL_SENDERS
uv run python scripts/download_emails.py --since 2026-01-01 --limit 50
```

Then re-run `uv run parse-eml fixtures/<carrier>/<file>.eml` on a few and
check whether anything new shows up unmatched or with missing fields.

### 2. Capture Airmee API auth header

`trackers/airmee.py` knows the endpoint
(`https://api.airmee.com/shipment-track/<token>`) and the response shape,
but the API returns 403 from outside a browser. To finish the live tracker:

1. Open `https://tracking.airmee.com/sv/#/track/<token>` in Chrome with a
   currently-active parcel.
2. Open DevTools → Network. Reload.
3. Find the GET to `api.airmee.com/shipment-track/<token>`.
4. Right-click → Copy → Copy as cURL (bash).
5. Paste here; we'll pull whichever header makes it work (likely
   `x-api-key` or `authorization`) and pass it via `AirmeeTracker(extra_headers={...})`.

## Out of scope (for v0.1)

- Live carrier API polling
- OAuth (IMAP password auth only)
- Custom Lovelace card
