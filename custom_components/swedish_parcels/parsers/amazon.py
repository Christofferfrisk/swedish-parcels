from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import parsedate_to_datetime

from swedish_parcels.models import Shipment
from swedish_parcels.parsers import REGISTRY
from swedish_parcels.parsers.bring import _extract_body_text

_ORDER_RE = re.compile(r"\b(\d{3}-\d{7}-\d{7})\b")
_ORDER_URL_RES = [
    re.compile(
        r"https?://www\.amazon\.[a-z.]+/your-orders/order-details\?[^\s)\"']+",
        re.IGNORECASE,
    ),
    re.compile(
        r"https?://www\.amazon\.[a-z.]+/progress-tracker/package\?[^\s)\"']+",
        re.IGNORECASE,
    ),
]

_WEEKDAYS = {
    "måndag": 0, "mandag": 0,
    "tisdag": 1,
    "onsdag": 2,
    "torsdag": 3,
    "fredag": 4,
    "lördag": 5, "lordag": 5,
    "söndag": 6, "sondag": 6,
}

_ETA_WEEKDAY_RE = re.compile(
    r"Kommer\s+(?:p[åa]\s+)?(" + "|".join(_WEEKDAYS) + r")\b",
    re.IGNORECASE,
)
_ETA_TODAY_RE = re.compile(r"Kommer\s+idag\b", re.IGNORECASE)
_ETA_TOMORROW_RE = re.compile(r"Kommer\s+imorgon\b", re.IGNORECASE)

_PRODUCT_RE = re.compile(r"^\*\s+(.+?)$", re.MULTILINE)

# Order matters: more specific rules first. Word boundaries prevent
# "leverans" from accidentally matching the "leverera" family.
_STATUS_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"n[äa]rmaste ombud|uth[äa]mtnings|redo att h[äa]mta", re.IGNORECASE), "ready_for_pickup"),
    (re.compile(r"leverans p[åa] v[äa]g|ute f[öo]r leverans|levereras\b", re.IGNORECASE), "out_for_delivery"),
    (re.compile(r"\blevererat\b|\blevererad\b", re.IGNORECASE), "delivered"),
    (re.compile(r"har skickats|\bskickat\b|\bskickad\b|\bskickade\b", re.IGNORECASE), "shipped"),
    (re.compile(r"best[äa]ll[dt]|best[äa]llningsbekr[äa]ft", re.IGNORECASE), "ordered"),
]


class AmazonParser:
    name = "amazon"

    def matches(self, msg: EmailMessage) -> bool:
        sender = (msg.get("From") or "").lower()
        return "@amazon.se" in sender or "@amazon.com" in sender

    def parse(self, msg: EmailMessage) -> Shipment:
        subject = (msg.get("Subject") or "").strip()
        body = _extract_body_text(msg)
        received_at = _parse_date_header(msg.get("Date"))

        order_ref = _first_match(_ORDER_RE, body) or _first_match(_ORDER_RE, subject)
        order_url = next(
            (m.group(0) for pat in _ORDER_URL_RES for m in [pat.search(body or "")] if m),
            None,
        )
        eta, eta_precision = _extract_eta(body, anchor=received_at)
        products = tuple(_PRODUCT_RE.findall(body))
        status = _classify_status(subject) or _classify_status(body)

        return Shipment(
            carrier="amazon",
            status=status,
            eta=eta,
            eta_precision=eta_precision,
            order_ref=order_ref,
            order_url=order_url,
            sender_name="Amazon",
            products=products,
            received_at=received_at,
            raw_message_id=msg.get("Message-ID"),
        )


def _first_match(pat: re.Pattern[str], text: str) -> str | None:
    if not text:
        return None
    m = pat.search(text)
    return m.group(1) if m else None


def _first_full_match(pat: re.Pattern[str], text: str) -> str | None:
    if not text:
        return None
    m = pat.search(text)
    return m.group(0) if m else None


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
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _extract_eta(body: str, *, anchor: datetime | None) -> tuple[datetime | None, str | None]:
    if not body or anchor is None:
        return None, None

    if _ETA_TODAY_RE.search(body):
        return _midnight(anchor), "day"

    if _ETA_TOMORROW_RE.search(body):
        return _midnight(anchor + timedelta(days=1)), "day"

    m = _ETA_WEEKDAY_RE.search(body)
    if m:
        target = _WEEKDAYS[m.group(1).lower()]
        days_ahead = (target - anchor.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        return _midnight(anchor + timedelta(days=days_ahead)), "weekday"

    return None, None


def _midnight(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


REGISTRY.append(AmazonParser())
