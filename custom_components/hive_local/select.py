"""Select platform — TRV orientation, keypad, programming mode, adaptation."""
from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DEVICE_TYPE_TRV, DOMAIN, uid_device
from .coordinator import HiveLocalCoordinator
from .mqtt import HiveDeviceMqtt

_SELECTS: list[dict] = [
    {
        "key":     "thermostat_orientation",
        "name":    "Orientation",
        "uid_sfx": "orientation",
        "options": ["vertical", "horizontal"],
        "icon":    "mdi:rotate-90",
        "cat":     EntityCategory.CONFIG,
        "setter":  "async_set_thermostat_orientation",
    },
    {
        "key":     "viewing_direction",
        "name":    "Display Direction",
        "uid_sfx": "viewing_direction",
        "options": ["normal", "upside-down"],
        "icon":    "mdi:flip-vertical",
        "cat":     EntityCategory.CONFIG,
        "setter":  "async_set_viewing_direction",
    },
    {
        "key":     "keypad_lockout",
        "name":    "Keypad Lock",
        "uid_sfx": "keypad_lockout",
        "options": ["unlock", "lock"],
        "icon":    "mdi:lock",
        "cat":     EntityCategory.CONFIG,
        "setter":  "async_set_keypad_lockout",
    },
    {
        "key":     "programming_operation_mode",
        "name":    "Programming Mode",
        "uid_sfx": "programming_mode",
        "options": ["setpoint", "schedule", "schedule_with_preheat", "eco"],
        "icon":    "mdi:calendar-clock",
        "cat":     EntityCategory.CONFIG,
        "setter":  "async_set_programming_operation_mode",
    },
    {
        "key":     "adaptation_run_control",
        "name":    "Adaptation Run",
        "uid_sfx": "adaptation_run_control",
        "options": ["idle", "initiate_adaptation", "cancel_adaptation"],
        "icon":    "mdi:tune",
        "cat":     EntityCategory.CONFIG,
        "setter":  "async_set_adaptation_run_control",
    },
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: HiveLocalCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    entities: list[SelectEntity] = []

    for device_id, device_data in coordinator.store.get_all_devices().items():
        if device_data.get("type") != DEVICE_TYPE_TRV:
            continue
        mqtt = coordinator.get_device_mqtt(device_id)
        if not mqtt:
            continue
        for spec in _SELECTS:
            entities.append(HiveTRVSelect(device_id, device_data, mqtt, spec))

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
            HiveTRVSelect(device_id, device_data, mqtt, spec)
            for spec in _SELECTS
        ])

    entry.async_on_unload(hass.bus.async_listen(f"{DOMAIN}_device_added", _on_device_added))


class HiveTRVSelect(SelectEntity):
    """Select entity for a single TRV configurable property."""

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

        self._attr_unique_id    = uid_device(device_id, spec["uid_sfx"])
        self._attr_name         = f"{device_data.get('name', device_id)} {spec['name']}"
        self._attr_options      = spec["options"]
        self._attr_icon         = spec.get("icon")
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
    def current_option(self) -> str | None:
        return getattr(self._mqtt, self._spec["key"], None)

    async def async_select_option(self, option: str) -> None:
        setter = getattr(self._mqtt, self._spec["setter"])
        await setter(option)
