"""Number platform — device boost/frost defaults and group boost defaults."""
from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ENTRY_TYPE, DATA_STORE, DOMAIN,
    DEFAULT_BOOST_MINUTES, DEFAULT_BOOST_TEMP, DEFAULT_FROST_TEMP,
    DEFAULT_HEATING_BOOST_MINS, DEFAULT_HEATING_BOOST_TEMP, DEFAULT_WATER_BOOST_MINS,
    ENTRY_TYPE_GROUPS, ENTRY_TYPE_RECEIVER, ENTRY_TYPE_TRV,
    EVENT_ROOM_ADDED, EVENT_ROOM_REMOVED,
    MAXIMUM_BOOST_MINUTES, MODEL_SLR2,
)
from .coordinator import HiveDeviceCoordinator
from .entity import HiveDeviceEntity
from .room import HiveRoomCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entry_type = entry.data.get(CONF_ENTRY_TYPE)

    if entry_type in (ENTRY_TYPE_TRV, ENTRY_TYPE_RECEIVER):
        coordinator: HiveDeviceCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        entities = [
            HiveBoostTemperatureNumber(coordinator),
            HiveBoostDurationNumber(coordinator),
            HiveFrostTemperatureNumber(coordinator),
        ]
        if entry_type == ENTRY_TYPE_RECEIVER and coordinator.model == MODEL_SLR2:
            entities.append(HiveWaterBoostDurationNumber(coordinator))
        async_add_entities(entities)

    elif entry_type == ENTRY_TYPE_GROUPS:
        store = hass.data[DOMAIN][entry.entry_id][DATA_STORE]
        _entities: dict[str, list] = {}

        @callback
        def _on_room_added(event: Any) -> None:
            if event.data.get("entry_id") != entry.entry_id:
                return
            room_id = event.data.get("room_id")
            rc      = event.data.get("coordinator")
            if rc and room_id not in _entities:
                es = [HiveRoomBoostTempNumber(rc, store), HiveRoomBoostDurationNumber(rc, store)]
                _entities[room_id] = es
                async_add_entities(es)

        @callback
        def _on_room_removed(event: Any) -> None:
            if event.data.get("entry_id") != entry.entry_id:
                return
            for e in _entities.pop(event.data.get("room_id"), []):
                hass.async_create_task(e.async_remove())

        entry.async_on_unload(hass.bus.async_listen(EVENT_ROOM_ADDED,   _on_room_added))
        entry.async_on_unload(hass.bus.async_listen(EVENT_ROOM_REMOVED, _on_room_removed))


# ── Device number entities ─────────────────────────────────────────────────────

class _HiveRestoreNumber(HiveDeviceEntity, RestoreNumber):
    """Base RestoreNumber for device entities."""
    _default: float = 20.0

    def __init__(self, coordinator: HiveDeviceCoordinator) -> None:
        super().__init__(coordinator)
        self._state: float | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (ls := await self.async_get_last_state()) and (nd := await self.async_get_last_number_data()):
            if ls.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                self._state = nd.native_value
            else:
                self._state = self._default
        else:
            self._state = self._default
        setattr(self.coordinator, self._coordinator_attr, self._state)

    @property
    def native_value(self) -> float | None:
        return self._state

    async def async_set_native_value(self, value: float) -> None:
        self._state = value
        setattr(self.coordinator, self._coordinator_attr, value)
        self.async_write_ha_state()

    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()


class HiveBoostTemperatureNumber(_HiveRestoreNumber):
    _attr_native_min_value = 12.0
    _attr_native_max_value = 32.0
    _attr_native_step      = 0.5
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_entity_category  = EntityCategory.CONFIG
    _attr_icon             = "mdi:thermometer-high"
    _coordinator_attr      = "heating_boost_temperature"
    _default               = DEFAULT_HEATING_BOOST_TEMP

    def __init__(self, coordinator: HiveDeviceCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry_id}_boost_temperature"
        self._attr_name      = f"{coordinator.device_name} Boost Temperature"


class HiveBoostDurationNumber(_HiveRestoreNumber):
    _attr_native_min_value = 15
    _attr_native_max_value = MAXIMUM_BOOST_MINUTES
    _attr_native_step      = 1
    _attr_native_unit_of_measurement = "min"
    _attr_entity_category  = EntityCategory.CONFIG
    _attr_icon             = "mdi:timer-outline"
    _coordinator_attr      = "heating_boost_duration"
    _default               = DEFAULT_HEATING_BOOST_MINS

    def __init__(self, coordinator: HiveDeviceCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry_id}_boost_duration"
        self._attr_name      = f"{coordinator.device_name} Boost Duration"


class HiveFrostTemperatureNumber(_HiveRestoreNumber):
    _attr_native_min_value = 5.0
    _attr_native_max_value = 16.0
    _attr_native_step      = 0.5
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_entity_category  = EntityCategory.CONFIG
    _attr_icon             = "mdi:snowflake-thermometer"
    _coordinator_attr      = "heating_frost_prevention"
    _default               = DEFAULT_FROST_TEMP

    def __init__(self, coordinator: HiveDeviceCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry_id}_frost_temperature"
        self._attr_name      = f"{coordinator.device_name} Frost Protection Temperature"


class HiveWaterBoostDurationNumber(_HiveRestoreNumber):
    _attr_native_min_value = 15
    _attr_native_max_value = MAXIMUM_BOOST_MINUTES
    _attr_native_step      = 1
    _attr_native_unit_of_measurement = "min"
    _attr_entity_category  = EntityCategory.CONFIG
    _attr_icon             = "mdi:timer-water"
    _coordinator_attr      = "water_boost_duration"
    _default               = DEFAULT_WATER_BOOST_MINS

    def __init__(self, coordinator: HiveDeviceCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry_id}_water_boost_duration"
        self._attr_name      = f"{coordinator.device_name} Water Boost Duration"


# ── Group number entities ──────────────────────────────────────────────────────

class HiveRoomBoostTempNumber(CoordinatorEntity[HiveRoomCoordinator], NumberEntity):
    _attr_native_min_value = 5.0
    _attr_native_max_value = 32.0
    _attr_native_step      = 0.5
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_mode             = NumberMode.BOX
    _attr_icon             = "mdi:thermometer-high"
    _attr_has_entity_name  = True

    def __init__(self, coordinator: HiveRoomCoordinator, store: Any) -> None:
        super().__init__(coordinator)
        self._store          = store
        self._attr_unique_id = f"room_{coordinator.room_id}_boost_temperature"
        self._attr_name      = f"{coordinator.room_name} Boost Temperature"

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, f"room_{self.coordinator.room_id}")}}

    @property
    def native_value(self) -> float:
        return self._store.get_room_boost_temperature(self.coordinator.room_id)

    async def async_set_native_value(self, value: float) -> None:
        await self._store.async_set_room_boost_defaults(
            self.coordinator.room_id, value,
            self._store.get_room_boost_duration(self.coordinator.room_id),
        )


class HiveRoomBoostDurationNumber(CoordinatorEntity[HiveRoomCoordinator], NumberEntity):
    _attr_native_min_value = 1
    _attr_native_max_value = 240
    _attr_native_step      = 1
    _attr_native_unit_of_measurement = "min"
    _attr_mode             = NumberMode.BOX
    _attr_icon             = "mdi:timer-outline"
    _attr_has_entity_name  = True

    def __init__(self, coordinator: HiveRoomCoordinator, store: Any) -> None:
        super().__init__(coordinator)
        self._store          = store
        self._attr_unique_id = f"room_{coordinator.room_id}_boost_duration"
        self._attr_name      = f"{coordinator.room_name} Boost Duration"

    @property
    def device_info(self):
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
