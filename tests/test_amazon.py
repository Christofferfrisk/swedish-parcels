from __future__ import annotations

from datetime import datetime, timezone
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from pathlib import Path

import pytest

from swedish_parcels.parsers.amazon import AmazonParser, _extract_eta

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "amazon"

ORDER_CONFIRMATION = "Beställt_ ”SONOFF SNZB-02P ZigBee 3.0...”.eml"


def _load(name: str) -> EmailMessage:
    path = FIXTURE_DIR / name
    if not path.exists():
        pytest.skip(f"fixture not present: {path}")
    with path.open("rb") as f:
        return BytesParser(policy=policy.default).parse(f)


@pytest.fixture
def parser() -> AmazonParser:
    return AmazonParser()


def test_matches_amazon_se(parser: AmazonParser) -> None:
    assert parser.matches(_load(ORDER_CONFIRMATION)) is True


def test_does_not_match_other_sender(parser: AmazonParser) -> None:
    msg = EmailMessage()
    msg["From"] = "noreply@example.com"
    assert parser.matches(msg) is False


def test_extracts_order_number(parser: AmazonParser) -> None:
    assert parser.parse(_load(ORDER_CONFIRMATION)).order_ref == "405-0571742-4234709"


def test_extracts_order_url(parser: AmazonParser) -> None:
    s = parser.parse(_load(ORDER_CONFIRMATION))
    assert s.order_url is not None
    assert "your-orders/order-details" in s.order_url
    assert "405-0571742-4234709" in s.order_url


def test_extracts_at_least_one_product(parser: AmazonParser) -> None:
    s = parser.parse(_load(ORDER_CONFIRMATION))
    assert len(s.products) >= 1
    assert "SONOFF" in s.products[0]


def test_status_ordered_for_bestallt(parser: AmazonParser) -> None:
    assert parser.parse(_load(ORDER_CONFIRMATION)).status == "ordered"


def test_eta_resolved_from_kommer_tisdag(parser: AmazonParser) -> None:
    s = parser.parse(_load(ORDER_CONFIRMATION))
    assert s.eta is not None
    assert s.eta.date().isoformat() == "2026-05-26"
    assert s.eta_precision == "weekday"


@pytest.mark.parametrize(
    ("anchor_iso", "body", "expected_date"),
    [
        ("2026-05-25T10:00:00+00:00", "Kommer tisdag", "2026-05-26"),
        ("2026-05-26T10:00:00+00:00", "Kommer tisdag", "2026-06-02"),
        ("2026-05-26T10:00:00+00:00", "Kommer idag", "2026-05-26"),
        ("2026-05-26T10:00:00+00:00", "Kommer imorgon", "2026-05-27"),
        ("2026-05-25T10:00:00+00:00", "Kommer mandag nasta vecka", "2026-06-01"),
    ],
)
def test_extract_eta_unit(anchor_iso: str, body: str, expected_date: str) -> None:
    anchor = datetime.fromisoformat(anchor_iso)
    eta, precision = _extract_eta(body, anchor=anchor)
    assert eta is not None
    assert eta.date().isoformat() == expected_date
    assert precision in {"day", "weekday"}


def test_eta_is_none_without_kommer_phrase() -> None:
    eta, precision = _extract_eta("ingen tidsangivelse alls", anchor=datetime.now(timezone.utc))
    assert eta is None
    assert precision is None


def test_received_at_matches_email_date(parser: AmazonParser) -> None:
    s = parser.parse(_load(ORDER_CONFIRMATION))
    assert s.received_at is not None
    assert s.received_at.date().isoformat() == "2026-05-24"


def test_sender_name_is_amazon(parser: AmazonParser) -> None:
    assert parser.parse(_load(ORDER_CONFIRMATION)).sender_name == "Amazon"
