from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Iterator

from .models import Shipment
from .trackers import LiveStatus

# Carriers that may deliver Amazon parcels in Sweden. When an Airmee record
# names "Amazon" as sender, we try to link it to a recent Amazon order.
_AMAZON_RETAILERS = {"amazon"}
_LINK_WINDOW_BEFORE = timedelta(days=14)
_LINK_WINDOW_AFTER = timedelta(days=1)
_TERMINAL_STATES = {"delivered", "failed", "returned"}


@dataclass
class Parcel:
    """A single tracked parcel built from one or more email records."""

    key: str
    records: list[Shipment] = field(default_factory=list)
    linked_retailer: Shipment | None = None
    live: LiveStatus | None = None

    @property
    def carrier(self) -> str:
        return self.records[0].carrier if self.records else "unknown"

    @property
    def tracking_number(self) -> str | None:
        for r in self.records:
            if r.tracking_number:
                return r.tracking_number
        return None

    @property
    def tracking_url(self) -> str | None:
        for r in reversed(self.records):
            if r.tracking_url:
                return r.tracking_url
        return None

    @property
    def status(self) -> str | None:
        if self.live and self.live.status:
            return self.live.status
        for r in self._records_newest_first():
            if r.status:
                return r.status
        return None

    @property
    def eta(self) -> datetime | None:
        if self.live and (self.live.eta_latest or self.live.eta_earliest):
            return self.live.eta_latest or self.live.eta_earliest
        if self.linked_retailer and self.linked_retailer.eta:
            return self.linked_retailer.eta
        for r in self._records_newest_first():
            if r.eta:
                return r.eta
        return None

    def _records_newest_first(self) -> list[Shipment]:
        # Sort by received_at desc, records without a date go last.
        with_date = [r for r in self.records if r.received_at is not None]
        without = [r for r in self.records if r.received_at is None]
        with_date.sort(key=lambda r: r.received_at, reverse=True)  # type: ignore[arg-type, return-value]
        return with_date + without

    @property
    def sender_name(self) -> str | None:
        if self.linked_retailer and self.linked_retailer.sender_name:
            return self.linked_retailer.sender_name
        for r in self.records:
            if r.sender_name:
                return r.sender_name
        return None

    @property
    def products(self) -> tuple[str, ...]:
        if self.linked_retailer and self.linked_retailer.products:
            return self.linked_retailer.products
        for r in self.records:
            if r.products:
                return r.products
        return ()

    def _latest_record(self) -> Shipment | None:
        dated = [r for r in self.records if r.received_at is not None]
        if dated:
            return max(dated, key=lambda r: r.received_at)  # type: ignore[arg-type, return-value]
        return self.records[-1] if self.records else None


class ShipmentStore:
    """Dedupe Shipments into Parcels and link carrier records to retailer orders.

    Keying:
    - records with (carrier, tracking_number) merge into the same Parcel
    - records without tracking_number get their own Parcel keyed by message id

    Linking:
    - Airmee parcels with sender_name="Amazon" search for an open Amazon
      retailer parcel whose received_at falls within a window before the
      Airmee record. The closest match wins.
    """

    def __init__(self) -> None:
        self._parcels: dict[str, Parcel] = {}

    def add(self, shipment: Shipment) -> Parcel:
        key = self._key_for(shipment)
        parcel = self._parcels.get(key)
        if parcel is None:
            parcel = Parcel(key=key)
            self._parcels[key] = parcel
        parcel.records.append(shipment)
        self._maybe_link(parcel)
        return parcel

    def attach_live(self, parcel: Parcel, live: LiveStatus) -> None:
        parcel.live = live

    def all(self) -> list[Parcel]:
        return list(self._parcels.values())

    def open_parcels(self) -> Iterator[Parcel]:
        for p in self._parcels.values():
            if p.status not in _TERMINAL_STATES:
                yield p

    def find_by_tracking(self, carrier: str, tracking_number: str) -> Parcel | None:
        return self._parcels.get(_tracking_key(carrier, tracking_number))

    def prune_delivered_older_than(self, now: datetime, max_age: timedelta) -> int:
        """Drop parcels in a terminal state whose newest record is older than max_age.

        Returns the number of parcels removed. Pass max_age=timedelta(0) to disable.
        """
        if max_age <= timedelta(0):
            return 0
        cutoff = now - max_age
        to_drop = []
        for key, parcel in self._parcels.items():
            if parcel.status not in _TERMINAL_STATES:
                continue
            latest = parcel._latest_record()
            if latest is None or latest.received_at is None:
                continue
            if latest.received_at < cutoff:
                to_drop.append(key)
        for key in to_drop:
            del self._parcels[key]
        return len(to_drop)

    def _key_for(self, s: Shipment) -> str:
        if s.tracking_number:
            return _tracking_key(s.carrier, s.tracking_number)
        if s.order_ref and s.carrier in _AMAZON_RETAILERS:
            # Amazon orders share a tracking-less key by order ref.
            return f"order:{s.carrier}:{s.order_ref}"
        return f"msg:{s.raw_message_id or id(s)}"

    def _maybe_link(self, parcel: Parcel) -> None:
        if parcel.carrier != "airmee" or parcel.linked_retailer is not None:
            return
        # Need a sender_name to link against; Airmee almost always says "Amazon".
        sender = (parcel.sender_name or "").lower()
        if sender not in _AMAZON_RETAILERS:
            return

        latest = parcel._latest_record()
        anchor = latest.received_at if latest else None
        if anchor is None:
            return

        candidates = [
            p
            for p in self._parcels.values()
            if p.carrier == "amazon"
            and p is not parcel
            and p._latest_record() is not None
        ]
        best: tuple[timedelta, Parcel] | None = None
        for cand in candidates:
            order_dt = cand._latest_record().received_at  # type: ignore[union-attr]
            if order_dt is None:
                continue
            delta = anchor - order_dt
            if -_LINK_WINDOW_AFTER <= delta <= _LINK_WINDOW_BEFORE:
                if best is None or abs(delta) < abs(best[0]):
                    best = (delta, cand)
        if best is not None:
            parcel.linked_retailer = best[1].records[0]


def _tracking_key(carrier: str, tracking_number: str) -> str:
    return f"track:{carrier}:{tracking_number}"
