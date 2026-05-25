from __future__ import annotations

from datetime import datetime, timezone

import pytest

from swedish_parcels.trackers.airmee import (
    AirmeeTracker,
    AirmeeTrackerAuthError,
    _from_airmee_payload,
)


def test_payload_mapping_minimal() -> None:
    payload = {
        "trackStatus": "ON_ROUTE",
        "dropoff": {
            "eta": {
                "earliest": "2026-05-25T14:00:00Z",
                "latest": "2026-05-25T16:00:00Z",
            }
        },
    }
    ls = _from_airmee_payload(payload, "7A242B")
    assert ls.carrier == "airmee"
    assert ls.tracking_number == "7A242B"
    assert ls.status == "out_for_delivery"
    assert ls.eta_earliest == datetime(2026, 5, 25, 14, 0, tzinfo=timezone.utc)
    assert ls.eta_latest == datetime(2026, 5, 25, 16, 0, tzinfo=timezone.utc)


def test_payload_mapping_unknown_status_falls_back_to_lowercased() -> None:
    ls = _from_airmee_payload({"trackStatus": "WONKY"}, "X")
    assert ls.status == "wonky"


def test_payload_mapping_missing_eta_is_none() -> None:
    ls = _from_airmee_payload({"trackStatus": "DELIVERED"}, "X")
    assert ls.status == "delivered"
    assert ls.eta_earliest is None
    assert ls.eta_latest is None


class _StubResponse:
    def __init__(self, status_code: int, body: dict | None = None) -> None:
        self.status_code = status_code
        self._body = body

    def json(self) -> dict:
        if self._body is None:
            raise ValueError("no body")
        return self._body


def test_fetch_without_auth_raises_descriptive_error(monkeypatch) -> None:
    import swedish_parcels.trackers.airmee as mod

    monkeypatch.setattr(mod.httpx, "get", lambda *a, **kw: _StubResponse(403))
    with pytest.raises(AirmeeTrackerAuthError):
        AirmeeTracker().fetch("7A242B")


def test_fetch_with_auth_returns_livestatus(monkeypatch) -> None:
    import swedish_parcels.trackers.airmee as mod

    payload = {
        "trackStatus": "DELIVERED",
        "dropoff": {"eta": {"earliest": "2026-05-25T10:00:00Z"}},
    }
    monkeypatch.setattr(mod.httpx, "get", lambda *a, **kw: _StubResponse(200, payload))

    tracker = AirmeeTracker(extra_headers={"x-api-key": "fake"})
    ls = tracker.fetch("7A242B")
    assert ls is not None
    assert ls.status == "delivered"
    assert ls.eta_earliest == datetime(2026, 5, 25, 10, 0, tzinfo=timezone.utc)
