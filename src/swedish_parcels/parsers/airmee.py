from __future__ import annotations

import re
from datetime import datetime
from email.message import EmailMessage
from email.utils import parsedate_to_datetime

from swedish_parcels.models import Shipment
from swedish_parcels.parsers import REGISTRY
from swedish_parcels.parsers.bring import _extract_body_text

_AIRMEE_SHORTLINK_RE = re.compile(r"https?://airm\.ee/([A-Za-z0-9_\-]+)", re.IGNORECASE)
_SENDER_RE = re.compile(r"fr[åa]n\s+([A-Za-zÅÄÖåäö0-9][A-Za-zÅÄÖåäö0-9_\-]*)")

_STATUS_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"levererat|levererad", re.IGNORECASE), "delivered"),
    (re.compile(r"missa inte|leverans idag|ut(?:e|kommer) för leverans", re.IGNORECASE), "out_for_delivery"),
    (re.compile(r"kommande leverans|f[öo]rbereds", re.IGNORECASE), "scheduled"),
]

_SENDER_STOPWORDS = {"din", "ditt", "dina", "oss", "vår", "vårt", "våra"}

CANONICAL_TRACKING_URL = "http://airm.ee/{token}"


class AirmeeParser:
    name = "airmee"

    def matches(self, msg: EmailMessage) -> bool:
        sender = (msg.get("From") or "").lower()
        return "@airmee.com" in sender or "airmee.com" in sender

    def parse(self, msg: EmailMessage) -> Shipment:
        subject = (msg.get("Subject") or "").strip()
        body = _extract_body_text(msg)

        token = _extract_token(body)
        tracking_url = CANONICAL_TRACKING_URL.format(token=token) if token else None
        status = _classify_status(subject) or _classify_status(body)
        sender_name = _extract_sender_name(subject) or _extract_sender_name(body)
        received_at = _parse_date_header(msg.get("Date"))

        return Shipment(
            carrier="airmee",
            tracking_number=token,
            tracking_url=tracking_url,
            status=status,
            sender_name=sender_name,
            received_at=received_at,
            raw_message_id=msg.get("Message-ID"),
        )


def _extract_token(text: str) -> str | None:
    if not text:
        return None
    m = _AIRMEE_SHORTLINK_RE.search(text)
    return m.group(1) if m else None


def _extract_sender_name(text: str) -> str | None:
    if not text:
        return None
    for m in _SENDER_RE.finditer(text):
        candidate = m.group(1).strip()
        if candidate.lower() not in _SENDER_STOPWORDS and len(candidate) >= 2:
            return candidate
    return None


def _classify_status(text: str) -> str | None:
    if not text:
        return None
    for pat, label in _STATUS_RULES:
        if pat.search(text):
            return label
    return None


def _parse_date_header(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None


REGISTRY.append(AirmeeParser())
