from __future__ import annotations

from datetime import datetime, timezone

import pytest

from swedish_parcels.trackers.airmee import AirmeeTracker, _from_payload

SAMPLE_PAYLOAD = {
    "order_details": [
        {
            "sender_name": "Amazon",
            "courier_status_formatted": "Delivered",
            "courier_full_name": "Talha",
            "dropoff_place_address": "Svärmgatan 7, UPPSALA 75255, Sweden",
            "pickup_earliest_time": "1779544800",
            "pickup_latest_time": "1779546600",
            "dropoff_earliest_time": "1779548400",
            "dropoff_latest_time": "1779566400",
            "dropoff_eta": "1779560450",
            "latitude_of_courier": None,
            "longitude_of_courier": None,
        }
    ]
}


class _StubResponse:
    def __init__(self, status_code: int, body: dict | None = None) -> None:
        self.status_code = status_code
        self._body = body

    def json(self) -> dict:
        if self._body is None:
            raise ValueError("no body")
        return self._body


def test_constructor_requires_phone_hash(monkeypatch) -> None:
    monkeypatch.delenv("AIRMEE_PHONE_HASH", raising=False)
    with pytest.raises(ValueError):
        AirmeeTracker()


def test_constructor_picks_up_env(monkeypatch) -> None:
    monkeypatch.setenv("AIRMEE_PHONE_HASH", "abc123")
    t = AirmeeTracker()
    assert t._hash == "abc123"


def test_payload_maps_delivered() -> None:
    ls = _from_payload(SAMPLE_PAYLOAD, "7A242B")
    assert ls is not None
    assert ls.carrier == "airmee"
    assert ls.tracking_number == "7A242B"
    assert ls.status == "delivered"
    assert ls.courier_name == "Talha"
    assert "UPPSALA" in (ls.dropoff_address or "")


def test_payload_timestamps_converted() -> None:
    ls = _from_payload(SAMPLE_PAYLOAD, "7A242B")
    assert ls is not None
    assert ls.eta_earliest == datetime.fromtimestamp(1779548400, tz=timezone.utc)
    assert ls.eta_latest == datetime.fromtimestamp(1779566400, tz=timezone.utc)
    assert ls.eta_estimate == datetime.fromtimestamp(1779560450, tz=timezone.utc)


def test_payload_unknown_status_normalised() -> None:
    payload = {"order_details": [{"courier_status_formatted": "Some New State"}]}
    ls = _from_payload(payload, "X")
    assert ls is not None
    assert ls.status == "some_new_state"


def test_payload_empty_orders_returns_none() -> None:
    assert _from_payload({"order_details": []}, "X") is None


def test_fetch_404_returns_none(monkeypatch) -> None:
    import swedish_parcels.trackers.airmee as mod

    monkeypatch.setenv("AIRMEE_PHONE_HASH", "x")
    monkeypatch.setattr(mod.httpx, "get", lambda *a, **kw: _StubResponse(404))
    assert AirmeeTracker().fetch("X") is None


def test_fetch_200_returns_livestatus(monkeypatch) -> None:
    import swedish_parcels.trackers.airmee as mod

    monkeypatch.setenv("AIRMEE_PHONE_HASH", "x")
    monkeypatch.setattr(mod.httpx, "get", lambda *a, **kw: _StubResponse(200, SAMPLE_PAYLOAD))
    ls = AirmeeTracker().fetch("7A242B")
    assert ls is not None
    assert ls.status == "delivered"
