"""Number platform — setpoint offset, scale factor, boost defaults."""
from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_HUB, DATA_STORE, DEFAULT_BOOST_MINUTES, DEFAULT_BOOST_TEMP, DOMAIN
from .coordinator import HiveTRVCoordinator, HiveTRVHub
from .entity import HiveTRVEntity
from .storage import HiveTRVStore


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    hub: HiveTRVHub    = hass.data[DOMAIN][entry.entry_id][DATA_HUB]
    store: HiveTRVStore = hass.data[DOMAIN][entry.entry_id][DATA_STORE]
    _entities: dict[str, list] = {}

    def _add(coord: HiveTRVCoordinator) -> None:
        if coord.friendly_name not in _entities:
            es = [
                HiveOffsetNumber(coord),
                HiveAlgorithmScaleNumber(coord),
                HiveBoostTempNumber(coord, store),
                HiveBoostDurationNumber(coord, store),
            ]
            _entities[coord.friendly_name] = es
            async_add_entities(es)

    def _remove(name: str) -> None:
        for e in _entities.pop(name, []):
            hass.async_create_task(e.async_remove())

    hub.register_add_entities("number", _add, _remove)

    # ── Room group number entities ──────────────────────────────────────
    from homeassistant.core import callback
    _room: dict[str, list] = {}

    @callback
    def _on_room_added(event):
        if event.data.get("entry_id") != entry.entry_id: return
        room_id    = event.data.get("room_id")
        room_coord = event.data.get("coordinator")
        if room_coord and room_id not in _room:
            es = [
                HiveRoomBoostTempNumber(room_coord, store),
                HiveRoomBoostDurationNumber(room_coord, store),
            ]
            _room[room_id] = es
            async_add_entities(es)

    @callback
    def _on_room_removed(event):
        for e in _room.pop(event.data.get("room_id"), []):
            hass.async_create_task(e.async_remove())

    entry.async_on_unload(hass.bus.async_listen(f"{DOMAIN}_room_added",   _on_room_added))
    entry.async_on_unload(hass.bus.async_listen(f"{DOMAIN}_room_removed", _on_room_removed))


class HiveOffsetNumber(HiveTRVEntity, NumberEntity):
    _attr_name = "Setpoint Offset"
    _attr_icon = "mdi:thermometer-plus"
    _attr_native_min_value = -2.5
    _attr_native_max_value =  2.5
    _attr_native_step      =  0.1
    _attr_native_unit_of_measurement = "°C"
    _attr_mode = NumberMode.BOX

    def __init__(self, coord: HiveTRVCoordinator) -> None:
        super().__init__(coord, "regulation_offset")

    @property
    def native_value(self) -> float | None:
        v = self.coordinator.get("regulation_setpoint_offset")
        return float(v) if v is not None else None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_regulation_offset(value)


class HiveAlgorithmScaleNumber(HiveTRVEntity, NumberEntity):
    _attr_name = "Algorithm Scale Factor"
    _attr_icon = "mdi:sine-wave"
    _attr_native_min_value = 1
    _attr_native_max_value = 10
    _attr_native_step      = 1
    _attr_mode = NumberMode.SLIDER
    _attr_entity_registry_enabled_default = False

    def __init__(self, coord: HiveTRVCoordinator) -> None:
        super().__init__(coord, "algorithm_scale")

    @property
    def native_value(self) -> int | None:
        v = self.coordinator.get("algorithm_scale_factor")
        return int(v) if v is not None else None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_publish({"algorithm_scale_factor": int(value)})


class HiveBoostTempNumber(HiveTRVEntity, NumberEntity):
    """Default temperature used when boosting this TRV."""

    _attr_name = "Boost Temperature"
    _attr_icon = "mdi:fire"
    _attr_native_min_value = 10.0
    _attr_native_max_value = 32.0
    _attr_native_step      = 0.5
    _attr_native_unit_of_measurement = "°C"
    _attr_mode = NumberMode.BOX

    def __init__(self, coord: HiveTRVCoordinator, store: HiveTRVStore) -> None:
        super().__init__(coord, "boost_temperature")
        self._store = store

    @property
    def native_value(self) -> float:
        return self._store.get_trv_boost_temperature(self.coordinator.friendly_name)

    async def async_set_native_value(self, value: float) -> None:
        duration = self._store.get_trv_boost_duration(self.coordinator.friendly_name)
        await self._store.async_set_trv_boost_defaults(
            self.coordinator.friendly_name, value, duration
        )
        self.async_write_ha_state()


class HiveBoostDurationNumber(HiveTRVEntity, NumberEntity):
    """Default boost duration in minutes for this TRV."""

    _attr_name = "Boost Duration"
    _attr_icon = "mdi:timer"
    _attr_native_min_value = 5
    _attr_native_max_value = 1440
    _attr_native_step      = 5
    _attr_native_unit_of_measurement = "min"
    _attr_mode = NumberMode.BOX

    def __init__(self, coord: HiveTRVCoordinator, store: HiveTRVStore) -> None:
        super().__init__(coord, "boost_duration")
        self._store = store

    @property
    def native_value(self) -> int:
        return self._store.get_trv_boost_duration(self.coordinator.friendly_name)

    async def async_set_native_value(self, value: float) -> None:
        temp = self._store.get_trv_boost_temperature(self.coordinator.friendly_name)
        await self._store.async_set_trv_boost_defaults(
            self.coordinator.friendly_name, temp, int(value)
        )
        self.async_write_ha_state()


# ── Room group number entities ─────────────────────────────────────────────────

class HiveRoomBoostTempNumber(CoordinatorEntity[HiveRoomCoordinator], NumberEntity):
    """Default boost temperature for a room group."""
    _attr_icon = "mdi:thermometer-high"
    _attr_native_min_value = 5.0; _attr_native_max_value = 32.0
    _attr_native_step = 0.5; _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_mode = NumberMode.BOX; _attr_has_entity_name = True

    def __init__(self, coordinator, store):
        super().__init__(coordinator)
        self._store = store
        self._attr_unique_id = f"room_{coordinator.room_id}_boost_temperature"
        self._attr_name      = f"{coordinator.room_name} Boost Temperature"

    @property
    def device_info(self): return {"identifiers": {(DOMAIN, f"room_{self.coordinator.room_id}")}}

    @property
    def native_value(self): return self._store.get_room_boost_temperature(self.coordinator.room_id)

    async def async_set_native_value(self, value: float) -> None:
        await self._store.async_set_room_boost_defaults(
            self.coordinator.room_id, value,
            self._store.get_room_boost_duration(self.coordinator.room_id))


class HiveRoomBoostDurationNumber(CoordinatorEntity[HiveRoomCoordinator], NumberEntity):
    """Default boost duration for a room group."""
    _attr_icon = "mdi:timer-outline"
    _attr_native_min_value = 1; _attr_native_max_value = 240
    _attr_native_step = 1; _attr_native_unit_of_measurement = "min"
    _attr_mode = NumberMode.BOX; _attr_has_entity_name = True

    def __init__(self, coordinator, store):
        super().__init__(coordinator)
        self._store = store
        self._attr_unique_id = f"room_{coordinator.room_id}_boost_duration"
        self._attr_name      = f"{coordinator.room_name} Boost Duration"

    @property
    def device_info(self): return {"identifiers": {(DOMAIN, f"room_{self.coordinator.room_id}")}}

    @property
    def native_value(self): return self._store.get_room_boost_duration(self.coordinator.room_id)

    async def async_set_native_value(self, value: float) -> None:
        await self._store.async_set_room_boost_defaults(
            self.coordinator.room_id,
            self._store.get_room_boost_temperature(self.coordinator.room_id),
            int(value))
