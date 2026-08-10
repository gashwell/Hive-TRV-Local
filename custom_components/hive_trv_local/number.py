"""Number platform — room group boost temperature and duration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_STORE, DOMAIN, EVENT_ROOM_ADDED, EVENT_ROOM_REMOVED
from .room import HiveRoomCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    store = hass.data[DOMAIN][entry.entry_id][DATA_STORE]
    _entities: dict[str, list] = {}

    @callback
    def _on_room_added(event: Any) -> None:
        if event.data.get("entry_id") != entry.entry_id:
            return
        room_id = event.data.get("room_id")
        rc      = event.data.get("coordinator")
        if rc and room_id not in _entities:
            es = [
                HiveRoomBoostTempNumber(rc, store),
                HiveRoomBoostDurationNumber(rc, store),
            ]
            _entities[room_id] = es
            async_add_entities(es)

    @callback
    def _on_room_removed(event: Any) -> None:
        for e in _entities.pop(event.data.get("room_id"), []):
            hass.async_create_task(e.async_remove())

    entry.async_on_unload(hass.bus.async_listen(EVENT_ROOM_ADDED,   _on_room_added))
    entry.async_on_unload(hass.bus.async_listen(EVENT_ROOM_REMOVED, _on_room_removed))


class HiveRoomBoostTempNumber(CoordinatorEntity[HiveRoomCoordinator], NumberEntity):
    """Default boost temperature for a room group."""

    _attr_icon                       = "mdi:thermometer-high"
    _attr_native_min_value           = 5.0
    _attr_native_max_value           = 32.0
    _attr_native_step                = 0.5
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_mode                       = NumberMode.BOX
    _attr_has_entity_name            = True

    def __init__(self, coordinator: HiveRoomCoordinator, store: Any) -> None:
        super().__init__(coordinator)
        self._store          = store
        self._attr_unique_id = f"room_{coordinator.room_id}_boost_temperature"
        self._attr_name      = f"{coordinator.room_name} Boost Temperature"

    @property
    def device_info(self) -> dict:
        return {"identifiers": {(DOMAIN, f"room_{self.coordinator.room_id}")}}

    @property
    def native_value(self) -> float:
        return self._store.get_room_boost_temperature(self.coordinator.room_id)

    async def async_set_native_value(self, value: float) -> None:
        await self._store.async_set_room_boost_defaults(
            self.coordinator.room_id,
            value,
            self._store.get_room_boost_duration(self.coordinator.room_id),
        )


class HiveRoomBoostDurationNumber(CoordinatorEntity[HiveRoomCoordinator], NumberEntity):
    """Default boost duration for a room group."""

    _attr_icon                       = "mdi:timer-outline"
    _attr_native_min_value           = 1
    _attr_native_max_value           = 240
    _attr_native_step                = 1
    _attr_native_unit_of_measurement = "min"
    _attr_mode                       = NumberMode.BOX
    _attr_has_entity_name            = True

    def __init__(self, coordinator: HiveRoomCoordinator, store: Any) -> None:
        super().__init__(coordinator)
        self._store          = store
        self._attr_unique_id = f"room_{coordinator.room_id}_boost_duration"
        self._attr_name      = f"{coordinator.room_name} Boost Duration"

    @property
    def device_info(self) -> dict:
        return {"identifiers": {(DOMAIN, f"room_{self.coordinator.room_id}")}}

    @property
    def native_value(self) -> int:
        return self._store.get_room_boost_duration(self.coordinator.room_id)

    async def async_set_native_value(self, value: float) -> None:
        await self._store.async_set_room_boost_defaults(
            self.coordinator.room_id,
            self._store.get_room_boost_temperature(self.coordinator.room_id),
            int(value),
        )
