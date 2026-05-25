from __future__ import annotations

from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from pathlib import Path

import pytest

from swedish_parcels.parsers.airmee import AirmeeParser

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "airmee"

REMINDER = "Missa inte din Airmee-leverans från Amazon.eml"
DELIVERED = "Levererat_ Din beställning från Amazon.eml"


def _load(name: str) -> EmailMessage:
    path = FIXTURE_DIR / name
    if not path.exists():
        pytest.skip(f"fixture not present: {path}")
    with path.open("rb") as f:
        return BytesParser(policy=policy.default).parse(f)


@pytest.fixture
def parser() -> AirmeeParser:
    return AirmeeParser()


def test_matches_airmee_sender(parser: AirmeeParser) -> None:
    assert parser.matches(_load(REMINDER)) is True


def test_does_not_match_other_sender(parser: AirmeeParser) -> None:
    msg = EmailMessage()
    msg["From"] = "support@example.com"
    assert parser.matches(msg) is False


def test_extracts_token_from_reminder(parser: AirmeeParser) -> None:
    s = parser.parse(_load(REMINDER))
    assert s.tracking_number == "SjyVJc_U"
    assert s.tracking_url == "http://airm.ee/SjyVJc_U"


def test_delivered_has_no_tracking_link(parser: AirmeeParser) -> None:
    s = parser.parse(_load(DELIVERED))
    assert s.tracking_number is None
    assert s.tracking_url is None


def test_sendgrid_redirect_urls_are_ignored(parser: AirmeeParser) -> None:
    msg = EmailMessage()
    msg["From"] = "Airmee <no-reply@airmee.com>"
    msg["Subject"] = "Missa inte din Airmee-leverans"
    msg.set_content("Spåra: http://url2381.airmee.com/ls/click?upn=abc123")
    s = parser.parse(msg)
    assert s.tracking_number is None
    assert s.tracking_url is None


def test_status_out_for_delivery_for_reminder(parser: AirmeeParser) -> None:
    assert parser.parse(_load(REMINDER)).status == "out_for_delivery"


def test_status_delivered_for_levererat(parser: AirmeeParser) -> None:
    assert parser.parse(_load(DELIVERED)).status == "delivered"


def test_sender_name_is_amazon_for_both(parser: AirmeeParser) -> None:
    for fixture in (REMINDER, DELIVERED):
        s = parser.parse(_load(fixture))
        assert s.sender_name == "Amazon", f"{fixture} produced {s.sender_name!r}"


def test_received_at_populated(parser: AirmeeParser) -> None:
    assert parser.parse(_load(REMINDER)).received_at is not None


def test_carrier_field_is_airmee(parser: AirmeeParser) -> None:
    assert parser.parse(_load(REMINDER)).carrier == "airmee"
