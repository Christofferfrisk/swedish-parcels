from __future__ import annotations

from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from pathlib import Path

import pytest

from swedish_parcels.parsers.bring import BringParser

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "bring"

UPCOMING = "Kommande leverans från klockmagasinet.eml"
IN_TRANSIT = "Ditt paket från klockmagasinet är på väg..eml"


def _load(name: str) -> EmailMessage:
    path = FIXTURE_DIR / name
    if not path.exists():
        pytest.skip(f"fixture not present: {path}")
    with path.open("rb") as f:
        return BytesParser(policy=policy.default).parse(f)


@pytest.fixture
def parser() -> BringParser:
    return BringParser()


def test_matches_bring_sender(parser: BringParser) -> None:
    assert parser.matches(_load(UPCOMING)) is True


def test_does_not_match_other_sender(parser: BringParser) -> None:
    msg = EmailMessage()
    msg["From"] = "support@example.com"
    msg["Subject"] = "Ditt paket är på väg"
    msg.set_content("spårningsnummer: 1234567890")
    assert parser.matches(msg) is False


def test_extracts_tracking_number_from_url(parser: BringParser) -> None:
    s = parser.parse(_load(UPCOMING))
    assert s.tracking_number == "373325386371062092"


def test_extracts_tracking_number_from_text(parser: BringParser) -> None:
    s = parser.parse(_load(IN_TRANSIT))
    assert s.tracking_number == "373325386371062092"


def test_synthesises_canonical_tracking_url(parser: BringParser) -> None:
    s = parser.parse(_load(IN_TRANSIT))
    assert s.tracking_url == "https://tracking.bring.se/tracking/373325386371062092"


def test_status_label_created_for_upcoming(parser: BringParser) -> None:
    assert parser.parse(_load(UPCOMING)).status == "label_created"


def test_status_in_transit_for_on_its_way(parser: BringParser) -> None:
    assert parser.parse(_load(IN_TRANSIT)).status == "in_transit"


def test_extracts_retailer_sender_name(parser: BringParser) -> None:
    for name in (UPCOMING, IN_TRANSIT):
        s = parser.parse(_load(name))
        assert s.sender_name == "klockmagasinet", f"fixture {name} produced {s.sender_name!r}"


def test_carrier_field_is_bring(parser: BringParser) -> None:
    assert parser.parse(_load(UPCOMING)).carrier == "bring"


def test_message_id_preserved(parser: BringParser) -> None:
    s = parser.parse(_load(IN_TRANSIT))
    assert s.raw_message_id is not None
    assert "@notifications-engine" in s.raw_message_id


def test_received_at_populated(parser: BringParser) -> None:
    s = parser.parse(_load(IN_TRANSIT))
    assert s.received_at is not None
    assert s.received_at.date().isoformat() == "2026-05-25"
