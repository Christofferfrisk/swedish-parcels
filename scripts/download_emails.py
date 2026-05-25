from __future__ import annotations

import argparse
import hashlib
import imaplib
import os
import re
import sys
from datetime import date
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_ROOT = REPO_ROOT / "fixtures"

CARRIER_HINTS: list[tuple[str, str]] = [
    ("postnord", "postnord"),
    ("budbee", "budbee"),
    ("instabox", "instabox"),
    ("dhl", "dhl"),
    ("schenker", "schenker"),
    ("bring", "bring"),
    ("airmee", "airmee"),
    ("early", "early"),
    ("amazon", "amazon"),
    ("zalando", "zalando"),
]


def carrier_for(msg: EmailMessage) -> str:
    sender = (msg.get("From") or "").lower()
    for needle, folder in CARRIER_HINTS:
        if needle in sender:
            return folder
    return "unknown"


_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def slug(text: str, max_len: int = 60) -> str:
    cleaned = _SAFE.sub("-", text).strip("-")
    return cleaned[:max_len] or "untitled"


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", type=date.fromisoformat)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--mailbox", default=None)
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = parse_args(argv)

    host = os.environ.get("IMAP_HOST")
    user = os.environ.get("IMAP_USER")
    password = os.environ.get("IMAP_PASSWORD")
    port = int(os.environ.get("IMAP_PORT", "993"))
    mailbox = args.mailbox or os.environ.get("IMAP_MAILBOX", "INBOX")
    senders_raw = os.environ.get("PARCEL_SENDERS", "").strip()

    if not (host and user and password):
        print("error: set IMAP_HOST, IMAP_USER, IMAP_PASSWORD in .env", file=sys.stderr)
        return 2
    if not senders_raw:
        print("error: set PARCEL_SENDERS in .env (comma-separated)", file=sys.stderr)
        return 2

    senders = [s.strip() for s in senders_raw.split(",") if s.strip()]
    FIXTURE_ROOT.mkdir(exist_ok=True)

    print(f"connecting to {host}:{port} as {user} ...")
    conn = imaplib.IMAP4_SSL(host, port)
    conn.login(user, password)
    conn.select(mailbox, readonly=True)

    date_clause = f'SINCE {args.since.strftime("%d-%b-%Y")}' if args.since else "ALL"

    seen_uids: set[bytes] = set()
    saved = 0
    skipped = 0

    try:
        for sender in senders:
            criteria = f'({date_clause} FROM "{sender}")' if args.since else f'(FROM "{sender}")'
            typ, data = conn.uid("SEARCH", None, criteria)
            if typ != "OK" or not data or not data[0]:
                print(f"  {sender}: no matches")
                continue

            uids = data[0].split()
            print(f"  {sender}: {len(uids)} matches")

            for uid in uids:
                if uid in seen_uids:
                    continue
                seen_uids.add(uid)

                typ, msg_data = conn.uid("FETCH", uid, "(RFC822)")
                if typ != "OK" or not msg_data or not msg_data[0]:
                    continue

                raw = msg_data[0][1]
                if not isinstance(raw, (bytes, bytearray)):
                    continue

                msg = BytesParser(policy=policy.default).parsebytes(bytes(raw))
                carrier = carrier_for(msg)
                subject = msg.get("Subject") or "no-subject"
                digest = hashlib.sha1(raw).hexdigest()[:12]
                filename = f"{digest}_{slug(subject)}.eml"

                out_dir = FIXTURE_ROOT / carrier
                out_dir.mkdir(parents=True, exist_ok=True)
                out_path = out_dir / filename

                if out_path.exists():
                    skipped += 1
                    continue

                out_path.write_bytes(bytes(raw))
                saved += 1
                print(f"    + {out_path.relative_to(REPO_ROOT)}")

                if args.limit is not None and saved >= args.limit:
                    print(f"hit --limit {args.limit}; stopping.")
                    return 0
    finally:
        conn.logout()

    print(f"\ndone. saved {saved} new, skipped {skipped} existing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
