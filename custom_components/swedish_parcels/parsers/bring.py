from __future__ import annotations

import re
from email.message import EmailMessage
from email.utils import parsedate_to_datetime

from ..models import Shipment
from . import REGISTRY

_TRACKING_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:bring\.se/t/|tracking\.bring\.se/tracking/)(\d+)",
    re.IGNORECASE,
)
_TRACKING_TEXT_RE = re.compile(r"sp[åa]rningsnummer\s*[:=]?\s*(\d{6,})", re.IGNORECASE)
_SENDER_RE = re.compile(r"fr[åa]n\s+([A-Za-zÅÄÖåäö0-9][A-Za-zÅÄÖåäö0-9_\-]*)")

_STATUS_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"levererat|levererad|utl[äa]mnad", re.IGNORECASE), "delivered"),
    (re.compile(r"redo att h[äa]mtas|klart att h[äa]mta|h[äa]mta ditt paket", re.IGNORECASE), "ready_for_pickup"),
    (re.compile(r"p[åa] v[äa]g|tagit emot|p[åa] v[äa]g till", re.IGNORECASE), "in_transit"),
    (re.compile(r"kommande leverans|f[öo]rbereds|kommer om", re.IGNORECASE), "label_created"),
]

_SENDER_STOPWORDS = {"din", "ditt", "dina", "oss", "vår", "vårt", "våra", "amazon"}

CANONICAL_TRACKING_URL = "https://tracking.bring.se/tracking/{number}"


class BringParser:
    name = "bring"

    def matches(self, msg: EmailMessage) -> bool:
        sender = (msg.get("From") or "").lower()
        return "@bring.com" in sender or "bring.se" in sender

    def parse(self, msg: EmailMessage) -> Shipment:
        subject = (msg.get("Subject") or "").strip()
        body = _extract_body_text(msg)

        tracking_number = _extract_tracking_number(body) or _extract_tracking_number(subject)
        tracking_url = (
            CANONICAL_TRACKING_URL.format(number=tracking_number) if tracking_number else None
        )
        status = _classify_status(subject) or _classify_status(body)
        sender_name = _extract_sender_name(subject) or _extract_sender_name(body)

        received_at = None
        date_header = msg.get("Date")
        if date_header:
            try:
                received_at = parsedate_to_datetime(date_header)
            except (TypeError, ValueError):
                received_at = None

        return Shipment(
            carrier="bring",
            tracking_number=tracking_number,
            tracking_url=tracking_url,
            status=status,
            sender_name=sender_name,
            received_at=received_at,
            raw_message_id=msg.get("Message-ID"),
        )


def _extract_tracking_number(text: str) -> str | None:
    if not text:
        return None
    m = _TRACKING_URL_RE.search(text)
    if m:
        return m.group(1)
    m = _TRACKING_TEXT_RE.search(text)
    return m.group(1) if m else None


def _classify_status(text: str) -> str | None:
    if not text:
        return None
    for pattern, label in _STATUS_RULES:
        if pattern.search(text):
            return label
    return None


def _extract_sender_name(text: str) -> str | None:
    if not text:
        return None
    for match in _SENDER_RE.finditer(text):
        candidate = match.group(1).strip()
        if candidate.lower() not in _SENDER_STOPWORDS and len(candidate) >= 2:
            return candidate
    return None


def _extract_body_text(msg: EmailMessage) -> str:
    # Concatenate both plain and html parts: SendGrid sometimes rewrites URLs
    # in only one alternative, and the canonical URL may live in either.
    if msg.is_multipart():
        chunks: list[str] = []
        for sub in msg.walk():
            if sub.get_content_type() in {"text/plain", "text/html"}:
                chunks.append(_safe_get_content(sub))
        return "\n".join(chunks)
    return _safe_get_content(msg)


def _safe_get_content(part: EmailMessage) -> str:
    try:
        content = part.get_content()
    except (KeyError, LookupError):
        raw = part.get_payload(decode=True) or b""
        return raw.decode("utf-8", errors="replace")
    if isinstance(content, bytes):
        return content.decode("utf-8", errors="replace")
    return str(content)


REGISTRY.append(BringParser())
