from __future__ import annotations

from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from pathlib import Path

import pytest

from swedish_parcels.parsers.zalando import ZalandoParser

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "zalando"

ORDER = "Beställningsbekräftelse och betalningsinformation.eml"
SHIPPED = "Ditt paket kommer om 1-3 arbetsdagar.eml"


def _load(name: str) -> EmailMessage:
    path = FIXTURE_DIR / name
    if not path.exists():
        pytest.skip(f"fixture not present: {path}")
    with path.open("rb") as f:
        return BytesParser(policy=policy.default).parse(f)


@pytest.fixture
def parser() -> ZalandoParser:
    return ZalandoParser()


def test_matches_zalando_sender(parser: ZalandoParser) -> None:
    assert parser.matches(_load(ORDER)) is True


def test_does_not_match_other_sender(parser: ZalandoParser) -> None:
    msg = EmailMessage()
    msg["From"] = "noreply@example.com"
    assert parser.matches(msg) is False


def test_order_number_extracted_from_both_emails(parser: ZalandoParser) -> None:
    for fixture in (ORDER, SHIPPED):
        s = parser.parse(_load(fixture))
        assert s.order_ref == "11106065541730", f"{fixture} gave {s.order_ref!r}"


def test_order_url_extracted(parser: ZalandoParser) -> None:
    s = parser.parse(_load(ORDER))
    assert s.order_url is not None
    assert "myaccount/order-detail/11106065541730" in s.order_url


def test_shipped_email_has_postnord_tracking(parser: ZalandoParser) -> None:
    s = parser.parse(_load(SHIPPED))
    assert s.tracking_number == "98410008107SE"
    assert s.tracking_url is not None
    assert "tracking.postnord.com" in s.tracking_url


def test_order_email_has_no_tracking(parser: ZalandoParser) -> None:
    s = parser.parse(_load(ORDER))
    assert s.tracking_number is None
    assert s.tracking_url is None


def test_status_ordered_for_order_confirmation(parser: ZalandoParser) -> None:
    assert parser.parse(_load(ORDER)).status == "ordered"


def test_status_shipped_for_shipping_email(parser: ZalandoParser) -> None:
    assert parser.parse(_load(SHIPPED)).status == "shipped"


def test_eta_exact_date_from_order_email(parser: ZalandoParser) -> None:
    s = parser.parse(_load(ORDER))
    assert s.eta is not None
    assert s.eta.date().isoformat() == "2026-03-05"
    assert s.eta_precision == "day"


def test_eta_range_from_shipping_email(parser: ZalandoParser) -> None:
    s = parser.parse(_load(SHIPPED))
    assert s.eta is not None
    # Email Date: Thu, 05 Mar 2026 → upper bound 3 days = Sun 8 Mar
    assert s.eta.date().isoformat() == "2026-03-08"
    assert s.eta_precision == "range"


def test_sender_name_is_zalando(parser: ZalandoParser) -> None:
    assert parser.parse(_load(ORDER)).sender_name == "Zalando"


def test_received_at_populated(parser: ZalandoParser) -> None:
    s = parser.parse(_load(ORDER))
    assert s.received_at is not None
