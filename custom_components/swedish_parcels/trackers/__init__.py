from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class LiveStatus:
    carrier: str
    tracking_number: str
    status: str | None = None
    eta_earliest: datetime | None = None
    eta_latest: datetime | None = None
    eta_estimate: datetime | None = None
    courier_name: str | None = None
    dropoff_address: str | None = None
    courier_lat: float | None = None
    courier_lon: float | None = None
    fetched_at: datetime | None = None
    raw: dict[str, object] = field(default_factory=dict)


@runtime_checkable
class Tracker(Protocol):
    name: str

    def fetch(self, tracking_number: str) -> LiveStatus | None: ...
