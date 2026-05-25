from swedish_parcels import __version__
from swedish_parcels.models import Shipment
from swedish_parcels.parsers import REGISTRY


def test_version() -> None:
    assert __version__ == "0.1.0"


def test_registry_has_parsers() -> None:
    names = {p.name for p in REGISTRY}
    assert {"bring", "amazon", "airmee"}.issubset(names)


def test_shipment_minimal() -> None:
    s = Shipment(carrier="postnord")
    assert s.carrier == "postnord"
    assert s.tracking_number is None
    assert s.extra == {}
