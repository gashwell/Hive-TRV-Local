"""Switch platform — TRV boolean controls."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DEVICE_TYPE_TRV, DOMAIN, uid_device
from .coordinator import HiveLocalCoordinator
from .mqtt import HiveDeviceMqtt

_SWITCHES: list[dict] = [
    {
        "key":     "window_open_feature",
        "name":    "Window Open Detection",
        "uid_sfx": "window_open_feature",
        "icon_on": "mdi:window-open",
        "icon_off":"mdi:window-closed",
        "cat":     EntityCategory.CONFIG,
        "setter":  "async_set_window_open_feature",
    },
    {
        "key":     "window_open_external",
        "name":    "Window Open",
        "uid_sfx": "window_open_external",
        "icon_on": "mdi:window-open-variant",
        "icon_off":"mdi:window-closed-variant",
        "cat":     None,
        "setter":  "async_set_window_open_external",
    },
    {
        "key":     "heat_available",
        "name":    "Heat Available",
        "uid_sfx": "heat_available",
        "icon_on": "mdi:radiator",
        "icon_off":"mdi:radiator-off",
        "cat":     EntityCategory.CONFIG,
        "setter":  "async_set_heat_available",
    },
    {
        "key":     "radiator_covered",
        "name":    "Radiator Covered (Room Sensor Mode)",
        "uid_sfx": "radiator_covered",
        "icon_on": "mdi:wall",
        "icon_off":"mdi:radiator",
        "cat":     EntityCategory.CONFIG,
        "setter":  "async_set_radiator_covered",
    },
    {
        "key":     "adaptation_run_settings",
        "name":    "Auto Adaptation Run (Night)",
        "uid_sfx": "adaptation_run_settings",
        "icon_on": "mdi:cog-sync",
        "icon_off":"mdi:cog",
        "cat":     EntityCategory.CONFIG,
        "setter":  "async_set_adaptation_run_settings",
    },
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: HiveLocalCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    entities: list[SwitchEntity] = []

    for device_id, device_data in coordinator.store.get_all_devices().items():
        if device_data.get("type") != DEVICE_TYPE_TRV:
            continue
        mqtt = coordinator.get_device_mqtt(device_id)
        if not mqtt:
            continue
        for spec in _SWITCHES:
            entities.append(HiveTRVSwitch(device_id, device_data, mqtt, spec))

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
        async_add_entities([
            HiveTRVSwitch(device_id, device_data, mqtt, spec)
            for spec in _SWITCHES
        ])

    entry.async_on_unload(hass.bus.async_listen(f"{DOMAIN}_device_added", _on_device_added))


class HiveTRVSwitch(SwitchEntity):
    """Switch entity for a single TRV boolean property."""

    _attr_has_entity_name = True

    def __init__(
        self,
        device_id: str,
        device_data: dict,
        mqtt: HiveDeviceMqtt,
        spec: dict,
    ) -> None:
        self._device_id   = device_id
        self._device_data = device_data
        self._mqtt        = mqtt
        self._spec        = spec

        self._attr_unique_id       = uid_device(device_id, spec["uid_sfx"])
        self._attr_name            = f"{device_data.get('name', device_id)} {spec['name']}"
        self._attr_entity_category = spec.get("cat")

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

    @property
    def is_on(self) -> bool | None:
        return getattr(self._mqtt, self._spec["key"], None)

    @property
    def icon(self) -> str:
        return self._spec["icon_on"] if self.is_on else self._spec["icon_off"]

    async def async_turn_on(self, **kwargs: Any) -> None:
        setter = getattr(self._mqtt, self._spec["setter"])
        await setter(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        setter = getattr(self._mqtt, self._spec["setter"])
        await setter(False)
