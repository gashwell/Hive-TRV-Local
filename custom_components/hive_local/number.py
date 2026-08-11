"""Number platform — boost temp/duration defaults and frost protection temp."""
from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DATA_COORDINATOR, DEFAULT_BOOST_MINUTES, DEFAULT_BOOST_TEMP,
    DEFAULT_FROST_TEMP, DEVICE_TYPE_RECEIVER, DEVICE_TYPE_TRV,
    DOMAIN, MAX_BOOST_MINUTES, uid_device, uid_room,
)
from .coordinator import HiveLocalCoordinator

_DEFAULT_BOOST_TEMP_DEVICE = 25.0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: HiveLocalCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    entities: list[NumberEntity] = []

    for device_id, device_data in coordinator.store.get_all_devices().items():
        if device_data.get("type") in (DEVICE_TYPE_TRV, DEVICE_TYPE_RECEIVER):
            mqtt = coordinator.get_device_mqtt(device_id)
            if mqtt:
                entities += [
                    HiveDeviceBoostTempNumber(coordinator,     device_id, device_data),
                    HiveDeviceBoostDurationNumber(coordinator, device_id, device_data),
                    HiveDeviceFrostTempNumber(coordinator,     device_id, device_data),
                    HiveRegulationOffsetNumber(coordinator,    device_id, device_data),
                    HiveMaxSetpointLimitNumber(coordinator,    device_id, device_data),
                    HiveAlgorithmScaleNumber(coordinator,      device_id, device_data),
                ]

    for room_id, room in coordinator.all_rooms().items():
        entities += [
            HiveRoomBoostTempNumber(coordinator,     room_id, room),
            HiveRoomBoostDurationNumber(coordinator, room_id, room),
        ]

    async_add_entities(entities)

    @callback
    def _on_device_added(event: Any) -> None:
        if event.data.get("entry_id") != entry.entry_id:
            return
        device_id   = event.data.get("device_id")
        device_data = event.data.get("data", {})
        if device_data.get("type") in (DEVICE_TYPE_TRV, DEVICE_TYPE_RECEIVER):
            new = [
                HiveDeviceBoostTempNumber(coordinator,     device_id, device_data),
                HiveDeviceBoostDurationNumber(coordinator, device_id, device_data),
                HiveDeviceFrostTempNumber(coordinator,     device_id, device_data),
            ]
            if device_data.get("type") == DEVICE_TYPE_TRV:
                new += [
                    HiveRegulationOffsetNumber(coordinator,    device_id, device_data),
                    HiveMaxSetpointLimitNumber(coordinator,    device_id, device_data),
                    HiveAlgorithmScaleNumber(coordinator,      device_id, device_data),
                ]
            async_add_entities(new)

    @callback
    def _on_room_added(event: Any) -> None:
        if event.data.get("entry_id") != entry.entry_id:
            return
        room_id = event.data.get("room_id")
        room    = event.data.get("room")
        if room:
            async_add_entities([
                HiveRoomBoostTempNumber(coordinator,     room_id, room),
                HiveRoomBoostDurationNumber(coordinator, room_id, room),
            ])

    entry.async_on_unload(hass.bus.async_listen(f"{DOMAIN}_device_added", _on_device_added))
    entry.async_on_unload(hass.bus.async_listen(f"{DOMAIN}_room_added",   _on_room_added))


# ── Device number entities ─────────────────────────────────────────────────────

class _HiveDeviceRestoreNumber(RestoreNumber):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode            = NumberMode.SLIDER
    _coordinator_attr: str
    _default: float

    def __init__(self, coordinator: HiveLocalCoordinator, device_id: str, device_data: dict) -> None:
        self._coordinator  = coordinator
        self._device_id    = device_id
        self._device_data  = device_data
        self._state: float = self._default

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._device_data.get("name", self._device_id),
            manufacturer="Hive",
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        nd = await self.async_get_last_number_data()
        ls = await self.async_get_last_state()
        if nd and ls and ls.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            self._state = nd.native_value or self._default
        mqtt = self._coordinator.get_device_mqtt(self._device_id)
        if mqtt:
            setattr(mqtt, self._coordinator_attr, self._state)

    @property
    def native_value(self) -> float:
        return self._state

    async def async_set_native_value(self, value: float) -> None:
        self._state = value
        mqtt = self._coordinator.get_device_mqtt(self._device_id)
        if mqtt:
            setattr(mqtt, self._coordinator_attr, value)
        self.async_write_ha_state()


class HiveDeviceBoostTempNumber(_HiveDeviceRestoreNumber):
    _attr_native_min_value = 12.0
    _attr_native_max_value = 32.0
    _attr_native_step      = 0.5
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_icon             = "mdi:thermometer-high"
    _coordinator_attr      = "boost_temperature"
    _default               = _DEFAULT_BOOST_TEMP_DEVICE

    def __init__(self, coordinator, device_id, device_data):
        super().__init__(coordinator, device_id, device_data)
        self._attr_unique_id = uid_device(device_id, "boost_temp")
        self._attr_name      = f"{device_data.get('name', device_id)} Boost Temperature"
        self._state          = self._default


class HiveDeviceBoostDurationNumber(_HiveDeviceRestoreNumber):
    _attr_native_min_value = 15
    _attr_native_max_value = MAX_BOOST_MINUTES
    _attr_native_step      = 5
    _attr_native_unit_of_measurement = "min"
    _attr_icon             = "mdi:timer-outline"
    _coordinator_attr      = "boost_duration"
    _default               = float(DEFAULT_BOOST_MINUTES)

    def __init__(self, coordinator, device_id, device_data):
        super().__init__(coordinator, device_id, device_data)
        self._attr_unique_id = uid_device(device_id, "boost_duration")
        self._attr_name      = f"{device_data.get('name', device_id)} Boost Duration"
        self._state          = self._default


class HiveDeviceFrostTempNumber(_HiveDeviceRestoreNumber):
    _attr_native_min_value = 4.0
    _attr_native_max_value = 16.0
    _attr_native_step      = 0.5
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_icon             = "mdi:snowflake-thermometer"
    _coordinator_attr      = "frost_temperature"
    _default               = DEFAULT_FROST_TEMP

    def __init__(self, coordinator, device_id, device_data):
        super().__init__(coordinator, device_id, device_data)
        self._attr_unique_id = uid_device(device_id, "frost_temp")
        self._attr_name      = f"{device_data.get('name', device_id)} Frost Protection"
        self._state          = self._default


# ── Room number entities ───────────────────────────────────────────────────────

class HiveRoomBoostTempNumber(NumberEntity):
    _attr_native_min_value = 5.0
    _attr_native_max_value = 32.0
    _attr_native_step      = 0.5
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_mode             = NumberMode.SLIDER
    _attr_icon             = "mdi:thermometer-high"
    _attr_entity_category  = EntityCategory.CONFIG
    _attr_has_entity_name  = True

    def __init__(self, coordinator: HiveLocalCoordinator, room_id: str, room: Any) -> None:
        self._coordinator = coordinator
        self._room_id     = room_id
        self._room        = room
        self._attr_unique_id = uid_room(room_id, "boost_temp")
        self._attr_name      = f"{room.room_name} Boost Temperature"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"room_{self._room_id}")},
            name=self._room.room_name,
        )

    @property
    def native_value(self) -> float:
        t, _ = self._coordinator.store.get_room_boost_defaults(self._room_id)
        return t

    async def async_set_native_value(self, value: float) -> None:
        _, m = self._coordinator.store.get_room_boost_defaults(self._room_id)
        await self._coordinator.store.async_set_room_boost_defaults(self._room_id, value, m)
        self._room.update_boost_defaults(value, m)
        self.async_write_ha_state()


class HiveRegulationOffsetNumber(_HiveDeviceRestoreNumber):
    """Regulation setpoint offset — calibration offset -2.5 to 2.5°C."""
    _attr_native_min_value = -2.5
    _attr_native_max_value =  2.5
    _attr_native_step      =  0.1
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_icon             = "mdi:thermometer-chevron-up"
    _coordinator_attr      = "regulation_setpoint_offset"
    _default               = 0.0

    def __init__(self, coordinator, device_id, device_data):
        super().__init__(coordinator, device_id, device_data)
        self._attr_unique_id = uid_device(device_id, "regulation_offset")
        self._attr_name      = f"{device_data.get('name', device_id)} Temperature Calibration"
        self._state          = self._default


class HiveMaxSetpointLimitNumber(_HiveDeviceRestoreNumber):
    """Maximum heat setpoint limit — upper bound for target temp."""
    _attr_native_min_value = 5.0
    _attr_native_max_value = 35.0
    _attr_native_step      = 0.5
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_icon             = "mdi:thermometer-chevron-up"
    _coordinator_attr      = "max_heat_setpoint_limit"
    _default               = 32.0

    def __init__(self, coordinator, device_id, device_data):
        super().__init__(coordinator, device_id, device_data)
        self._attr_unique_id = uid_device(device_id, "max_setpoint_limit")
        self._attr_name      = f"{device_data.get('name', device_id)} Max Temperature Limit"
        self._state          = self._default


class HiveAlgorithmScaleNumber(_HiveDeviceRestoreNumber):
    """Algorithm scale factor — 1=aggressive, 10=slow."""
    _attr_native_min_value = 1
    _attr_native_max_value = 10
    _attr_native_step      = 1
    _attr_native_unit_of_measurement = None
    _attr_icon             = "mdi:speedometer"
    _coordinator_attr      = "algorithm_scale_factor"
    _default               = 5.0

    def __init__(self, coordinator, device_id, device_data):
        super().__init__(coordinator, device_id, device_data)
        self._attr_unique_id = uid_device(device_id, "algorithm_scale_factor")
        self._attr_name      = f"{device_data.get('name', device_id)} Control Aggressiveness"
        self._state          = self._default

    async def async_set_native_value(self, value: float) -> None:
        self._state = value
        mqtt = self._coordinator.get_device_mqtt(self._device_id)
        if mqtt:
            await mqtt.async_set_algorithm_scale_factor(int(value))
        self.async_write_ha_state()


class HiveRoomBoostDurationNumber(NumberEntity):
    _attr_native_min_value = 5
    _attr_native_max_value = MAX_BOOST_MINUTES
    _attr_native_step      = 5
    _attr_native_unit_of_measurement = "min"
    _attr_mode             = NumberMode.SLIDER
    _attr_icon             = "mdi:timer-outline"
    _attr_entity_category  = EntityCategory.CONFIG
    _attr_has_entity_name  = True

    def __init__(self, coordinator: HiveLocalCoordinator, room_id: str, room: Any) -> None:
        self._coordinator = coordinator
        self._room_id     = room_id
        self._room        = room
        self._attr_unique_id = uid_room(room_id, "boost_duration")
        self._attr_name      = f"{room.room_name} Boost Duration"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"room_{self._room_id}")},
            name=self._room.room_name,
        )

    @property
    def native_value(self) -> int:
        _, m = self._coordinator.store.get_room_boost_defaults(self._room_id)
        return m

    async def async_set_native_value(self, value: float) -> None:
        t, _ = self._coordinator.store.get_room_boost_defaults(self._room_id)
        await self._coordinator.store.async_set_room_boost_defaults(self._room_id, t, int(value))
        self._room.update_boost_defaults(t, int(value))
        self.async_write_ha_state()
