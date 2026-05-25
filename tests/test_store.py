from __future__ import annotations

from datetime import datetime, timezone

from swedish_parcels.models import Shipment
from swedish_parcels.store import ShipmentStore
from swedish_parcels.trackers import LiveStatus


def _at(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, 12, 0, tzinfo=timezone.utc)


def test_dedupes_records_with_same_tracking_number() -> None:
    store = ShipmentStore()
    a = Shipment(carrier="bring", tracking_number="111", status="label_created", received_at=_at(2026, 5, 1))
    b = Shipment(carrier="bring", tracking_number="111", status="in_transit", received_at=_at(2026, 5, 3))
    store.add(a)
    parcel = store.add(b)
    assert len(parcel.records) == 2
    assert parcel.tracking_number == "111"
    assert parcel.status == "in_transit"


def test_records_with_different_tracking_numbers_are_separate() -> None:
    store = ShipmentStore()
    store.add(Shipment(carrier="bring", tracking_number="111", received_at=_at(2026, 5, 1)))
    store.add(Shipment(carrier="bring", tracking_number="222", received_at=_at(2026, 5, 2)))
    assert len(store.all()) == 2


def test_records_without_tracking_get_their_own_parcel() -> None:
    store = ShipmentStore()
    store.add(Shipment(carrier="airmee", raw_message_id="<a>", received_at=_at(2026, 5, 1)))
    store.add(Shipment(carrier="airmee", raw_message_id="<b>", received_at=_at(2026, 5, 2)))
    assert len(store.all()) == 2


def test_amazon_order_keyed_by_order_ref() -> None:
    store = ShipmentStore()
    a = Shipment(carrier="amazon", order_ref="405-XYZ", raw_message_id="<1>", received_at=_at(2026, 5, 1))
    b = Shipment(carrier="amazon", order_ref="405-XYZ", raw_message_id="<2>", received_at=_at(2026, 5, 2))
    store.add(a)
    parcel = store.add(b)
    assert len(parcel.records) == 2


def test_airmee_links_to_recent_amazon_order() -> None:
    store = ShipmentStore()
    amazon = Shipment(
        carrier="amazon",
        order_ref="405-XYZ",
        sender_name="Amazon",
        eta=_at(2026, 5, 5),
        eta_precision="weekday",
        received_at=_at(2026, 5, 1),
    )
    airmee = Shipment(
        carrier="airmee",
        tracking_number="7A242B",
        sender_name="Amazon",
        status="out_for_delivery",
        received_at=_at(2026, 5, 5),
    )
    store.add(amazon)
    parcel = store.add(airmee)
    assert parcel.carrier == "airmee"
    assert parcel.linked_retailer is not None
    assert parcel.linked_retailer.order_ref == "405-XYZ"
    # ETA inherited from Amazon since Airmee email had none
    assert parcel.eta == _at(2026, 5, 5)


def test_airmee_does_not_link_outside_window() -> None:
    store = ShipmentStore()
    store.add(Shipment(
        carrier="amazon",
        order_ref="405-OLD",
        sender_name="Amazon",
        received_at=_at(2026, 4, 1),  # > 14 days before airmee
    ))
    parcel = store.add(Shipment(
        carrier="airmee",
        tracking_number="X",
        sender_name="Amazon",
        received_at=_at(2026, 5, 1),
    ))
    assert parcel.linked_retailer is None


def test_airmee_with_non_amazon_sender_does_not_link() -> None:
    store = ShipmentStore()
    store.add(Shipment(
        carrier="amazon",
        order_ref="405-X",
        sender_name="Amazon",
        received_at=_at(2026, 5, 1),
    ))
    parcel = store.add(Shipment(
        carrier="airmee",
        tracking_number="X",
        sender_name="ZooStore",
        received_at=_at(2026, 5, 5),
    ))
    assert parcel.linked_retailer is None


def test_airmee_links_to_closest_amazon_order_when_multiple() -> None:
    store = ShipmentStore()
    store.add(Shipment(
        carrier="amazon",
        order_ref="405-A",
        sender_name="Amazon",
        received_at=_at(2026, 4, 28),
    ))
    store.add(Shipment(
        carrier="amazon",
        order_ref="405-B",
        sender_name="Amazon",
        received_at=_at(2026, 5, 4),  # closer to Airmee on May 5
    ))
    parcel = store.add(Shipment(
        carrier="airmee",
        tracking_number="X",
        sender_name="Amazon",
        received_at=_at(2026, 5, 5),
    ))
    assert parcel.linked_retailer is not None
    assert parcel.linked_retailer.order_ref == "405-B"


def test_live_status_overrides_email_status() -> None:
    store = ShipmentStore()
    parcel = store.add(Shipment(
        carrier="airmee",
        tracking_number="7A242B",
        status="out_for_delivery",
        received_at=_at(2026, 5, 5),
    ))
    store.attach_live(parcel, LiveStatus(carrier="airmee", tracking_number="7A242B", status="delivered"))
    assert parcel.status == "delivered"


def test_live_eta_overrides_linked_amazon_eta() -> None:
    store = ShipmentStore()
    store.add(Shipment(
        carrier="amazon",
        order_ref="405-X",
        sender_name="Amazon",
        eta=_at(2026, 5, 7),  # Amazon's "Kommer torsdag"
        received_at=_at(2026, 5, 4),
    ))
    parcel = store.add(Shipment(
        carrier="airmee",
        tracking_number="X",
        sender_name="Amazon",
        received_at=_at(2026, 5, 6),
    ))
    assert parcel.eta == _at(2026, 5, 7)  # from linked Amazon
    store.attach_live(parcel, LiveStatus(
        carrier="airmee",
        tracking_number="X",
        eta_latest=_at(2026, 5, 6),  # live says today
    ))
    assert parcel.eta == _at(2026, 5, 6)


def test_open_parcels_excludes_delivered() -> None:
    store = ShipmentStore()
    store.add(Shipment(carrier="bring", tracking_number="A", status="in_transit", received_at=_at(2026, 5, 1)))
    store.add(Shipment(carrier="bring", tracking_number="B", status="delivered", received_at=_at(2026, 5, 2)))
    open_keys = {p.tracking_number for p in store.open_parcels()}
    assert open_keys == {"A"}


def test_find_by_tracking() -> None:
    store = ShipmentStore()
    store.add(Shipment(carrier="bring", tracking_number="ABC", received_at=_at(2026, 5, 1)))
    assert store.find_by_tracking("bring", "ABC") is not None
    assert store.find_by_tracking("bring", "ZZZ") is None
