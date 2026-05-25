from __future__ import annotations

import argparse
import sys
from email import policy
from email.parser import BytesParser
from pathlib import Path

from swedish_parcels.models import Shipment
from swedish_parcels.parsers import REGISTRY


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Parse a single .eml file.")
    ap.add_argument("path", type=Path)
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

    for parser in REGISTRY:
        if parser.matches(msg):
            shipment = parser.parse(msg)
            print(f"matched: {parser.name}")
            print(shipment)
            return 0

    print("no parser matched")
    print(Shipment(carrier="unknown", raw_message_id=msg.get("Message-ID")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
