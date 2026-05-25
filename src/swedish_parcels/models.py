from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Shipment:
    carrier: str
    tracking_number: str | None = None
    tracking_url: str | None = None
    status: str | None = None
    eta: datetime | None = None
    eta_precision: str | None = None
    order_ref: str | None = None
    order_url: str | None = None
    sender_name: str | None = None
    products: tuple[str, ...] = ()
    received_at: datetime | None = None
    raw_message_id: str | None = None
    extra: dict[str, str] = field(default_factory=dict)
