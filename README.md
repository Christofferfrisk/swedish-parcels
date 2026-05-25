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

Early scaffolding. No parsers implemented yet.

## Out of scope (for v0.1)

- Live carrier API polling
- OAuth (IMAP password auth only)
- Custom Lovelace card
