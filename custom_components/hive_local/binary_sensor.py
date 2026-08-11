"""Binary sensor platform — heat required, mounted mode, preheat, window open internal."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DEVICE_TYPE_TRV, DOMAIN, uid_device
from .coordinator import HiveLocalCoordinator
from .mqtt import HiveDeviceMqtt

_BINARY_SENSORS: list[dict] = [
    {
        "key":     "heat_required",
        "name":    "Heat Required",
        "uid_sfx": "heat_required",
        "device_class": BinarySensorDeviceClass.HEAT,
        "cat":     None,
    },
    {
        "key":     "mounted_mode_active",
        "name":    "In Mounting Mode",
        "uid_sfx": "mounted_mode_active",
        "device_class": None,
        "cat":     EntityCategory.DIAGNOSTIC,
    },
    {
        "key":     "preheat_status",
        "name":    "Preheating",
        "uid_sfx": "preheat_status",
        "device_class": BinarySensorDeviceClass.HEAT,
        "cat":     EntityCategory.DIAGNOSTIC,
    },
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: HiveLocalCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    entities: list = []

    for device_id, device_data in coordinator.store.get_all_devices().items():
        if device_data.get("type") != DEVICE_TYPE_TRV:
            continue
        mqtt = coordinator.get_device_mqtt(device_id)
        if not mqtt:
            continue
        for spec in _BINARY_SENSORS:
            entities.append(HiveTRVBinarySensor(device_id, device_data, mqtt, spec))
        # Text/enum sensors that fit better here
        entities.append(HiveTRVWindowInternalSensor(device_id, device_data, mqtt))
        entities.append(HiveTRVAdaptationStatusSensor(device_id, device_data, mqtt))
        entities.append(HiveTRVSystemStatusSensor(device_id, device_data, mqtt))

    async_add_entities(entities)

    @callback
    def _on_device_added(event: Any) -> None:
        if event.data.get("entry_id") != entry.entry_id:
            return
        device_id   = event.data.get("device_id")
        device_data = event.data.get("data", {})
        if device_data.get("type") != DEVICE_TYPE_TRV:
            return
        mqtt = coordinator.get_device_mqtt(device_id)
        if not mqtt:
            return
        new: list = [
            HiveTRVBinarySensor(device_id, device_data, mqtt, spec)
            for spec in _BINARY_SENSORS
        ]
        new.append(HiveTRVWindowInternalSensor(device_id, device_data, mqtt))
        new.append(HiveTRVAdaptationStatusSensor(device_id, device_data, mqtt))
        new.append(HiveTRVSystemStatusSensor(device_id, device_data, mqtt))
        async_add_entities(new)

    entry.async_on_unload(hass.bus.async_listen(f"{DOMAIN}_device_added", _on_device_added))


class _HiveBase:
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


class HiveTRVBinarySensor(_HiveBase, BinarySensorEntity):
    def __init__(self, device_id, device_data, mqtt, spec):
        super().__init__(device_id, device_data, mqtt)
        self._spec                   = spec
        self._attr_unique_id         = uid_device(device_id, spec["uid_sfx"])
        self._attr_name              = f"{device_data.get('name', device_id)} {spec['name']}"
        self._attr_device_class      = spec.get("device_class")
        self._attr_entity_category   = spec.get("cat")

    @property
    def is_on(self) -> bool | None:
        return getattr(self._mqtt, self._spec["key"], None)


class HiveTRVWindowInternalSensor(_HiveBase, SensorEntity):
    """Window open internal state (enum, read-only)."""
    _attr_icon = "mdi:window-open-variant"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, device_id, device_data, mqtt):
        super().__init__(device_id, device_data, mqtt)
        self._attr_unique_id = uid_device(device_id, "window_open_internal")
        self._attr_name      = f"{device_data.get('name', device_id)} Window Open Status"

    @property
    def native_value(self) -> str | None:
        return self._mqtt.window_open_internal


class HiveTRVAdaptationStatusSensor(_HiveBase, SensorEntity):
    """Adaptation run status (enum, read-only)."""
    _attr_icon = "mdi:cog-sync-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, device_id, device_data, mqtt):
        super().__init__(device_id, device_data, mqtt)
        self._attr_unique_id = uid_device(device_id, "adaptation_run_status")
        self._attr_name      = f"{device_data.get('name', device_id)} Adaptation Run Status"

    @property
    def native_value(self) -> str | None:
        return self._mqtt.adaptation_run_status


class HiveTRVSystemStatusSensor(_HiveBase, SensorEntity):
    """System status / error codes (text, read-only)."""
    _attr_icon = "mdi:information-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, device_id, device_data, mqtt):
        super().__init__(device_id, device_data, mqtt)
        self._attr_unique_id = uid_device(device_id, "system_status_code")
        self._attr_name      = f"{device_data.get('name', device_id)} System Status"

    @property
    def native_value(self) -> str | None:
        return self._mqtt.system_status_code
