"""Sensor platform — battery and heating demand."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_HUB, DOMAIN
from .coordinator import HiveTRVCoordinator, HiveTRVHub
from .entity import HiveTRVEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    hub: HiveTRVHub = hass.data[DOMAIN][entry.entry_id][DATA_HUB]
    _entities: dict[str, list] = {}

    def _add(coord: HiveTRVCoordinator) -> None:
        if coord.friendly_name not in _entities:
            es = [HiveBatterySensor(coord), HiveDemandSensor(coord)]
            _entities[coord.friendly_name] = es
            async_add_entities(es)

    def _remove(name: str) -> None:
        for e in _entities.pop(name, []):
            hass.async_create_task(e.async_remove())

    hub.register_add_entities("sensor", _add, _remove)


class HiveBatterySensor(HiveTRVEntity, SensorEntity):
    _attr_name = "Battery"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class  = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coord: HiveTRVCoordinator) -> None:
        super().__init__(coord, "battery")

    @property
    def native_value(self) -> int | None:
        return self.coordinator.battery


class HiveDemandSensor(HiveTRVEntity, SensorEntity):
    _attr_name = "Heating Demand"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:radiator"

    def __init__(self, coord: HiveTRVCoordinator) -> None:
        super().__init__(coord, "pi_heating_demand")

    @property
    def native_value(self) -> int | None:
        return self.coordinator.pi_heating_demand
