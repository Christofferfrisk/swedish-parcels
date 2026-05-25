from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from swedish_parcels.store import Parcel

from .const import DOMAIN
from .coordinator import SwedishParcelsCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SwedishParcelsCoordinator = hass.data[DOMAIN][entry.entry_id]
    known: set[str] = set()

    @callback
    def _add_new() -> None:
        data = coordinator.data or {}
        new_keys = set(data.keys()) - known
        if new_keys:
            async_add_entities([ParcelSensor(coordinator, k) for k in sorted(new_keys)])
            known.update(new_keys)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


class ParcelSensor(CoordinatorEntity[SwedishParcelsCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:package-variant"

    def __init__(self, coordinator: SwedishParcelsCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{DOMAIN}_{key}"

    @property
    def _parcel(self) -> Parcel | None:
        data = self.coordinator.data or {}
        return data.get(self._key)

    @property
    def available(self) -> bool:
        return self._parcel is not None

    @property
    def name(self) -> str:
        p = self._parcel
        if p is None:
            return self._key
        if p.sender_name and p.tracking_number:
            return f"{p.sender_name} {p.tracking_number}"
        if p.tracking_number:
            return f"{p.carrier} {p.tracking_number}"
        if p.sender_name:
            return f"{p.sender_name} parcel"
        return p.key

    @property
    def native_value(self) -> str | None:
        p = self._parcel
        return p.status if p else None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        p = self._parcel
        if p is None:
            return {}
        attrs: dict[str, object] = {
            "carrier": p.carrier,
            "tracking_number": p.tracking_number,
            "tracking_url": p.tracking_url,
            "sender_name": p.sender_name,
            "products": list(p.products),
            "email_count": len(p.records),
        }
        if p.eta:
            attrs["eta"] = p.eta.isoformat()
        if p.linked_retailer:
            attrs["linked_order_ref"] = p.linked_retailer.order_ref
        if p.live:
            attrs["courier_name"] = p.live.courier_name
            attrs["dropoff_address"] = p.live.dropoff_address
            if p.live.eta_estimate:
                attrs["live_eta_estimate"] = p.live.eta_estimate.isoformat()
        return {k: v for k, v in attrs.items() if v not in (None, [], "")}
