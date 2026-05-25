from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import parsedate_to_datetime

from ..models import Shipment
from . import REGISTRY
from .bring import _extract_body_text

_ORDER_URL_RE = re.compile(
    r"https?://www\.zalando\.se/myaccount/order-detail/(\d+)/?[^\s>)\"']*",
    re.IGNORECASE,
)

_POSTNORD_TRACKING_URL_RE = re.compile(
    r"https?://tracking\.postnord\.com/[^\s>)\"']+",
    re.IGNORECASE,
)
_POSTNORD_TRACKING_ID_RE = re.compile(r"\b([A-Z0-9]{10,16}SE)\b")

_SWEDISH_MONTHS = {
    "jan": 1, "januari": 1,
    "feb": 2, "februari": 2,
    "mar": 3, "mars": 3,
    "apr": 4, "april": 4,
    "maj": 5,
    "jun": 6, "juni": 6,
    "jul": 7, "juli": 7,
    "aug": 8, "augusti": 8,
    "sep": 9, "september": 9,
    "okt": 10, "oktober": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}
_DATE_RE = re.compile(
    r"\b(\d{1,2})\s+(" + "|".join(_SWEDISH_MONTHS) + r")\s+(\d{4})\b",
    re.IGNORECASE,
)
_ETA_RANGE_RE = re.compile(r"(\d+)\s*[-–]\s*(\d+)\s*arbetsdagar", re.IGNORECASE)

_STATUS_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"levererat|levererad", re.IGNORECASE), "delivered"),
    (re.compile(r"har (?:nu )?skickats|kommer om \d+", re.IGNORECASE), "shipped"),
    (re.compile(r"best[äa]llningsbekr[äa]ft|tack f[öo]r din best[äa]llning", re.IGNORECASE), "ordered"),
]


class ZalandoParser:
    name = "zalando"

    def matches(self, msg: EmailMessage) -> bool:
        sender = (msg.get("From") or "").lower()
        return "zalando" in sender

    def parse(self, msg: EmailMessage) -> Shipment:
        subject = (msg.get("Subject") or "").strip()
        body = _extract_body_text(msg)
        received_at = _parse_date_header(msg.get("Date"))

        order_url_match = _ORDER_URL_RE.search(body) if body else None
        order_ref = order_url_match.group(1) if order_url_match else None
        order_url = order_url_match.group(0) if order_url_match else None

        tracking_url = _first_full_match(_POSTNORD_TRACKING_URL_RE, body)
        tracking_number = _first_match(_POSTNORD_TRACKING_ID_RE, body)

        eta, eta_precision = _extract_eta(body, subject, anchor=received_at)
        status = _classify_status(subject) or _classify_status(body)

        return Shipment(
            carrier="zalando",
            tracking_number=tracking_number,
            tracking_url=tracking_url,
            status=status,
            eta=eta,
            eta_precision=eta_precision,
            order_ref=order_ref,
            order_url=order_url,
            sender_name="Zalando",
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


def _extract_eta(
    body: str, subject: str, *, anchor: datetime | None
) -> tuple[datetime | None, str | None]:
    if not body and not subject:
        return None, None

    for text in (body, subject):
        if not text:
            continue
        m = _DATE_RE.search(text)
        if m:
            day = int(m.group(1))
            month = _SWEDISH_MONTHS[m.group(2).lower()]
            year = int(m.group(3))
            tz = anchor.tzinfo if anchor else timezone.utc
            try:
                return datetime(year, month, day, tzinfo=tz), "day"
            except ValueError:
                pass

    if anchor is not None:
        for text in (body, subject):
            if not text:
                continue
            m = _ETA_RANGE_RE.search(text)
            if m:
                # Use the upper bound — pessimistic ETA is more useful than optimistic.
                upper = int(m.group(2))
                return _midnight(anchor + timedelta(days=upper)), "range"

    return None, None


def _midnight(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


REGISTRY.append(ZalandoParser())
