from __future__ import annotations

from datetime import datetime, timezone

import httpx

from swedish_parcels.trackers import LiveStatus

API_BASE = "https://api.airmee.com"
ENDPOINT = "/shipment-track/{token}"

# Status codes seen in the SPA bundle. Extend as we encounter more.
_STATUS_MAP = {
    "DELIVERED": "delivered",
    "PICKED_UP": "in_transit",
    "ON_ROUTE": "out_for_delivery",
    "RETURN_LIVE": "returning",
    "FAILED": "failed",
    "SCHEDULED": "scheduled",
}


class AirmeeTrackerAuthError(RuntimeError):
    pass


class AirmeeTracker:
    name = "airmee"

    def __init__(self, *, extra_headers: dict[str, str] | None = None, timeout: float = 10.0) -> None:
        # extra_headers lets the caller inject an x-api-key / Authorization
        # captured from browser DevTools. See docstring of fetch().
        self._extra_headers = extra_headers or {}
        self._timeout = timeout

    def fetch(self, tracking_number: str) -> LiveStatus | None:
        """Hit the Airmee tracking endpoint.

        Without browser-captured auth headers this will return None — the
        endpoint requires headers that the SPA injects at runtime.
        Reproduce: open tracking.airmee.com/sv/#/track/<id> in Chrome,
        open DevTools → Network, reload, find the GET to
        api.airmee.com/shipment-track/<id>, and copy any request headers
        starting with `x-api-key`, `authorization`, or `cookie`.
        """
        url = API_BASE + ENDPOINT.format(token=tracking_number)
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "Origin": "https://tracking.airmee.com",
            "Referer": "https://tracking.airmee.com/sv/",
            **self._extra_headers,
        }
        try:
            r = httpx.get(url, headers=headers, timeout=self._timeout)
        except httpx.HTTPError:
            return None

        if r.status_code == 403:
            if not self._extra_headers:
                raise AirmeeTrackerAuthError(
                    "Airmee API returned 403. Provide browser-captured auth headers "
                    "via AirmeeTracker(extra_headers={...})."
                )
            return None
        if r.status_code != 200:
            return None

        try:
            data = r.json()
        except ValueError:
            return None

        return _from_airmee_payload(data, tracking_number)


def _from_airmee_payload(data: dict, tracking_number: str) -> LiveStatus:
    track_status = data.get("trackStatus")
    status = _STATUS_MAP.get(track_status, track_status.lower() if track_status else None)

    dropoff = data.get("dropoff") or {}
    eta = dropoff.get("eta") or {}
    earliest = _parse_iso(eta.get("earliest"))
    latest = _parse_iso(eta.get("latest"))

    return LiveStatus(
        carrier="airmee",
        tracking_number=tracking_number,
        status=status,
        eta_earliest=earliest,
        eta_latest=latest,
        fetched_at=datetime.now(timezone.utc),
        raw=data,
    )


def _parse_iso(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
