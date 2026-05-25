from __future__ import annotations

import os
from datetime import datetime, timezone

import httpx

from swedish_parcels.trackers import LiveStatus

API_URL = "https://api.airmee.com/track/track_by_url"

# Canonical status mapping. Keys are the lowercased courier_status_formatted
# strings Airmee returns; extend as new ones surface.
_STATUS_MAP = {
    "delivered": "delivered",
    "out for delivery": "out_for_delivery",
    "picked up": "in_transit",
    "scheduled": "scheduled",
    "unassigned": "label_created",
    "scanned": "in_transit",
    "failed": "failed",
    "returned": "returned",
}


class AirmeeTracker:
    name = "airmee"

    def __init__(self, phone_number_hash: str | None = None, *, timeout: float = 10.0) -> None:
        self._hash = phone_number_hash or os.environ.get("AIRMEE_PHONE_HASH")
        if not self._hash:
            raise ValueError(
                "AirmeeTracker needs phone_number_hash (or set AIRMEE_PHONE_HASH). "
                "Capture it from the tracking.airmee.com network tab — query param "
                "on the track_by_url request."
            )
        self._timeout = timeout

    def fetch(self, tracking_number: str) -> LiveStatus | None:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "Origin": "https://tracking.airmee.com",
            "Referer": "https://tracking.airmee.com/",
        }
        params = {"tracking_url": tracking_number, "phone_number_hash": self._hash}
        try:
            r = httpx.get(API_URL, params=params, headers=headers, timeout=self._timeout)
        except httpx.HTTPError:
            return None

        if r.status_code != 200:
            return None
        try:
            data = r.json()
        except ValueError:
            return None
        return _from_payload(data, tracking_number)


def _from_payload(data: dict, tracking_number: str) -> LiveStatus | None:
    orders = data.get("order_details") or []
    if not orders:
        return None
    o = orders[0]

    formatted = (o.get("courier_status_formatted") or "").strip()
    canonical = _STATUS_MAP.get(formatted.lower()) or (
        formatted.lower().replace(" ", "_") if formatted else None
    )

    return LiveStatus(
        carrier="airmee",
        tracking_number=tracking_number,
        status=canonical,
        eta_earliest=_unix(o.get("dropoff_earliest_time")),
        eta_latest=_unix(o.get("dropoff_latest_time")),
        eta_estimate=_unix(o.get("dropoff_eta")),
        courier_name=o.get("courier_full_name") or None,
        dropoff_address=o.get("dropoff_place_address") or None,
        courier_lat=_as_float(o.get("latitude_of_courier")),
        courier_lon=_as_float(o.get("longitude_of_courier")),
        fetched_at=datetime.now(timezone.utc),
        raw=data,
    )


def _unix(value: object) -> datetime | None:
    if value in (None, "", 0, "0"):
        return None
    try:
        ts = int(value) if isinstance(value, (str, int, float)) else None
    except (TypeError, ValueError):
        return None
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
