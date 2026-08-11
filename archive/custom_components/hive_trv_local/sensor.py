"""Sensor platform — battery, heating demand, running state, boost remaining."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass, SensorEntity, SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ENTRY_TYPE, DOMAIN, ENTRY_TYPE_RECEIVER, ENTRY_TYPE_TRV, MODEL_SLR2,
)
from .coordinator import HiveDeviceCoordinator
from .entity import HiveDeviceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entry_type = entry.data.get(CONF_ENTRY_TYPE)
    if entry_type not in (ENTRY_TYPE_TRV, ENTRY_TYPE_RECEIVER):
        return

    coordinator: HiveDeviceCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities = []

    if entry_type == ENTRY_TYPE_TRV:
        entities += [
            HiveBatterySensor(coordinator),
            HiveDemandSensor(coordinator),
        ]
    else:
        # Receiver
        entities += [
            HiveRunningStateSensor(coordinator, "heat"),
            HiveBoostRemainingSensor(coordinator, "heat"),
        ]
        if coordinator.model == MODEL_SLR2:
            entities += [
                HiveRunningStateSensor(coordinator, "water"),
                HiveBoostRemainingSensor(coordinator, "water"),
            ]

    async_add_entities(entities)


class HiveBatterySensor(HiveDeviceEntity, SensorEntity):
    """Battery level sensor for TRVs."""
    _attr_device_class  = SensorDeviceClass.BATTERY
    _attr_state_class   = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator: HiveDeviceCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry_id}_battery"
        self._attr_name      = f"{coordinator.device_name} Battery"

    def _handle_coordinator_update(self) -> None:
        self._attr_native_value = self.coordinator.battery
        self.async_write_ha_state()


class HiveDemandSensor(HiveDeviceEntity, SensorEntity):
    """Heating demand percentage sensor for TRVs."""
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:fire"

    def __init__(self, coordinator: HiveDeviceCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry_id}_demand"
        self._attr_name      = f"{coordinator.device_name} Heating Demand"

    def _handle_coordinator_update(self) -> None:
        self._attr_native_value = self.coordinator.pi_heating_demand
        self.async_write_ha_state()


class HiveRunningStateSensor(HiveDeviceEntity, SensorEntity):
    """Running state (heating/idle) sensor for receivers."""
    _attr_icon = "mdi:fire"

    def __init__(self, coordinator: HiveDeviceCoordinator, channel: str) -> None:
        super().__init__(coordinator)
        self._channel        = channel
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry_id}_running_state_{channel}"
        self._attr_name      = f"{coordinator.device_name} {'Heating' if channel == 'heat' else 'Water'} State"

    def _handle_coordinator_update(self) -> None:
        self._attr_native_value = (
            self.coordinator.running_state_heat
            if self._channel == "heat"
            else self.coordinator.running_state_water
        )
        self.async_write_ha_state()


class HiveBoostRemainingSensor(HiveDeviceEntity, SensorEntity):
    """Boost remaining minutes sensor for receivers."""
    _attr_native_unit_of_measurement = "min"
    _attr_icon = "mdi:timer-outline"

    def __init__(self, coordinator: HiveDeviceCoordinator, channel: str) -> None:
        super().__init__(coordinator)
        self._channel        = channel
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry_id}_boost_remaining_{channel}"
        self._attr_name      = f"{coordinator.device_name} {'Heating' if channel == 'heat' else 'Water'} Boost Remaining"

    def _handle_coordinator_update(self) -> None:
        self._attr_native_value = (
            self.coordinator.heat_boost_remaining
            if self._channel == "heat"
            else self.coordinator.water_boost_remaining
        )
        self.async_write_ha_state()
