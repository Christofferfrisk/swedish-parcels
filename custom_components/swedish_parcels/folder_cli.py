from __future__ import annotations

import argparse
import sys
from email import policy
from email.parser import BytesParser
from pathlib import Path

from .parsers import REGISTRY
from .store import Parcel, ShipmentStore


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Walk a folder of .eml files, parse them, and print deduped Parcels."
    )
    ap.add_argument("path", type=Path)
    ap.add_argument("--open-only", action="store_true", help="Hide delivered/terminal parcels.")
    args = ap.parse_args(argv)

    if not args.path.exists():
        print(f"error: not found: {args.path}", file=sys.stderr)
        return 2

    store = ShipmentStore()
    total = 0
    unmatched = 0
    for eml in _walk(args.path):
        with eml.open("rb") as f:
            msg = BytesParser(policy=policy.default).parse(f)
        total += 1
        for parser in REGISTRY:
            if parser.matches(msg):
                store.add(parser.parse(msg))
                break
        else:
            unmatched += 1

    all_parcels = store.all()
    if args.open_only:
        parcels = [p for p in store.open_parcels() if _has_signal(p)]
    else:
        parcels = all_parcels
    parcels.sort(key=_sort_key, reverse=True)

    print(
        f"scanned {total} emails ({unmatched} unmatched) "
        f"→ {len(all_parcels)} parcels, showing {len(parcels)}\n"
    )
    for p in parcels:
        _print_parcel(p)
    return 0


def _has_signal(p: Parcel) -> bool:
    return any((p.tracking_number, p.status, p.records[0].order_ref if p.records else None))


def _walk(root: Path):
    if root.is_file():
        yield root
        return
    yield from sorted(root.rglob("*.eml"))


def _sort_key(p: Parcel):
    latest = p._latest_record()
    return (latest.received_at if latest and latest.received_at else _epoch())


def _epoch():
    from datetime import datetime, timezone
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def _print_parcel(p: Parcel) -> None:
    bits = [f"[{p.carrier}]"]
    if p.tracking_number:
        bits.append(p.tracking_number)
    if p.status:
        bits.append(f"status={p.status}")
    if p.eta:
        bits.append(f"eta={p.eta.date().isoformat()}")
    if p.sender_name:
        bits.append(f"from={p.sender_name}")
    print(" ".join(bits))
    if p.products:
        print(f"    {p.products[0][:90]}")
    if p.linked_retailer:
        print(f"    linked to {p.linked_retailer.carrier} order {p.linked_retailer.order_ref}")
    if p.tracking_url:
        print(f"    {p.tracking_url}")
    print(f"    ({len(p.records)} email(s))")
    print()


if __name__ == "__main__":
    raise SystemExit(main())
