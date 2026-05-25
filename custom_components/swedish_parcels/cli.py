from __future__ import annotations

import argparse
import os
import sys
from email import policy
from email.parser import BytesParser
from pathlib import Path

from dotenv import load_dotenv

from swedish_parcels.models import Shipment
from swedish_parcels.parsers import REGISTRY


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    ap = argparse.ArgumentParser(description="Parse a single .eml file.")
    ap.add_argument("path", type=Path)
    ap.add_argument(
        "--live",
        action="store_true",
        help="If the parser yields a tracking_number and a tracker exists, fetch live status.",
    )
    args = ap.parse_args(argv)

    if not args.path.exists():
        print(f"error: file not found: {args.path}", file=sys.stderr)
        return 2

    with args.path.open("rb") as f:
        msg = BytesParser(policy=policy.default).parse(f)

    print(f"From:    {msg.get('From')}")
    print(f"Subject: {msg.get('Subject')}")
    print(f"Date:    {msg.get('Date')}")
    print()

    shipment: Shipment | None = None
    for parser in REGISTRY:
        if parser.matches(msg):
            shipment = parser.parse(msg)
            print(f"matched: {parser.name}")
            print(shipment)
            break

    if shipment is None:
        print("no parser matched")
        print(Shipment(carrier="unknown", raw_message_id=msg.get("Message-ID")))
        return 0

    if args.live and shipment.tracking_number:
        print()
        live, reason = _try_live_lookup(shipment)
        if live is not None:
            print("live lookup:")
            print(live)
        else:
            print(f"live lookup: {reason}")
    return 0


def _try_live_lookup(shipment: Shipment) -> tuple[object, str]:
    if shipment.carrier != "airmee":
        return None, f"no tracker for carrier {shipment.carrier!r}"
    if not os.environ.get("AIRMEE_PHONE_HASH"):
        return None, "AIRMEE_PHONE_HASH not set in env"
    from swedish_parcels.trackers.airmee import AirmeeTracker

    try:
        ls = AirmeeTracker().fetch(shipment.tracking_number)
    except Exception as e:
        return None, f"fetch failed: {type(e).__name__}: {e}"
    if ls is None:
        return None, "API returned no order_details (parcel may be too old)"
    return ls, ""


if __name__ == "__main__":
    raise SystemExit(main())
