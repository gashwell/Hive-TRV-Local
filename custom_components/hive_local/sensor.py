"""Sensor platform — battery, heating demand, running state, boost remaining."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DATA_COORDINATOR, DEVICE_TYPE_RECEIVER, DEVICE_TYPE_TRV,
    DOMAIN, uid_device,
)
from .coordinator import HiveLocalCoordinator
from .mqtt import HiveDeviceMqtt

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: HiveLocalCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    entities: list[SensorEntity] = []

    for device_id, device_data in coordinator.store.get_all_devices().items():
        dtype = device_data.get("type")
        mqtt  = coordinator.get_device_mqtt(device_id)
        if not mqtt:
            continue
        if dtype == DEVICE_TYPE_TRV:
            entities += [
                HiveBatterySensor(device_id, device_data, mqtt),
                HiveDemandSensor(device_id,  device_data, mqtt),
            ]
        elif dtype == DEVICE_TYPE_RECEIVER:
            entities += [HiveRunningStateSensor(device_id, device_data, mqtt)]

    async_add_entities(entities)

    @callback
    def _on_device_added(event: Any) -> None:
        if event.data.get("entry_id") != entry.entry_id:
            return
        device_id   = event.data.get("device_id")
        device_data = event.data.get("data", {})
        dtype = device_data.get("type")
        mqtt  = coordinator.get_device_mqtt(device_id)
        if not mqtt:
            return
        new: list = []
        if dtype == DEVICE_TYPE_TRV:
            new += [HiveBatterySensor(device_id, device_data, mqtt),
                    HiveDemandSensor(device_id,  device_data, mqtt)]
        elif dtype == DEVICE_TYPE_RECEIVER:
            new += [HiveRunningStateSensor(device_id, device_data, mqtt)]
        if new:
            async_add_entities(new)

    entry.async_on_unload(hass.bus.async_listen(f"{DOMAIN}_device_added", _on_device_added))


class _HiveDeviceSensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, device_id: str, device_data: dict, mqtt: HiveDeviceMqtt) -> None:
        self._device_id   = device_id
        self._device_data = device_data
        self._mqtt        = mqtt

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._device_data.get("name", self._device_id),
            model=self._device_data.get("model", self._device_data.get("type", "TRV")),
            manufacturer="Hive",
        )

    async def async_added_to_hass(self) -> None:
        self._mqtt.add_listener(self._handle_update)

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        return self._mqtt.available


class HiveBatterySensor(_HiveDeviceSensor):
    _attr_device_class  = SensorDeviceClass.BATTERY
    _attr_state_class   = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, device_id: str, device_data: dict, mqtt: HiveDeviceMqtt) -> None:
        super().__init__(device_id, device_data, mqtt)
        self._attr_unique_id = uid_device(device_id, "battery")
        self._attr_name      = f"{device_data.get('name', device_id)} Battery"

    @property
    def native_value(self) -> int | None:
        return self._mqtt.battery


class HiveDemandSensor(_HiveDeviceSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:fire"

    def __init__(self, device_id: str, device_data: dict, mqtt: HiveDeviceMqtt) -> None:
        super().__init__(device_id, device_data, mqtt)
        self._attr_unique_id = uid_device(device_id, "demand")
        self._attr_name      = f"{device_data.get('name', device_id)} Heating Demand"

    @property
    def native_value(self) -> int | None:
        return self._mqtt.pi_heating_demand


class HiveRunningStateSensor(_HiveDeviceSensor):
    _attr_icon = "mdi:radiator"

    def __init__(self, device_id: str, device_data: dict, mqtt: HiveDeviceMqtt) -> None:
        super().__init__(device_id, device_data, mqtt)
        self._attr_unique_id = uid_device(device_id, "running_state")
        self._attr_name      = f"{device_data.get('name', device_id)} Running State"

    @property
    def native_value(self) -> str:
        return self._mqtt.running_state
