"""Button platform — boost buttons for devices and rooms."""
from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DATA_COORDINATOR, DEVICE_TYPE_RECEIVER, DEVICE_TYPE_TRV,
    DOMAIN, MODE_BOOST, uid_device, uid_room,
)
from .coordinator import HiveLocalCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: HiveLocalCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    entities: list[ButtonEntity] = []

    # Device boost buttons
    for device_id, device_data in coordinator.store.get_all_devices().items():
        if device_data.get("type") in (DEVICE_TYPE_TRV, DEVICE_TYPE_RECEIVER):
            mqtt = coordinator.get_device_mqtt(device_id)
            if mqtt:
                entities.append(HiveDeviceBoostButton(coordinator, device_id, device_data))

    # Room boost buttons
    for room_id, room in coordinator.all_rooms().items():
        entities += [
            HiveRoomBoostButton(coordinator, room_id, room),
            HiveRoomEndBoostButton(coordinator, room_id, room),
        ]

    async_add_entities(entities)

    @callback
    def _on_device_added(event: Any) -> None:
        if event.data.get("entry_id") != entry.entry_id:
            return
        device_id   = event.data.get("device_id")
        device_data = event.data.get("data", {})
        if device_data.get("type") in (DEVICE_TYPE_TRV, DEVICE_TYPE_RECEIVER):
            async_add_entities([HiveDeviceBoostButton(coordinator, device_id, device_data)])

    @callback
    def _on_room_added(event: Any) -> None:
        if event.data.get("entry_id") != entry.entry_id:
            return
        room_id = event.data.get("room_id")
        room    = event.data.get("room")
        if room:
            async_add_entities([
                HiveRoomBoostButton(coordinator, room_id, room),
                HiveRoomEndBoostButton(coordinator, room_id, room),
            ])

    entry.async_on_unload(hass.bus.async_listen(f"{DOMAIN}_device_added", _on_device_added))
    entry.async_on_unload(hass.bus.async_listen(f"{DOMAIN}_room_added",   _on_room_added))


class HiveDeviceBoostButton(ButtonEntity):
    _attr_icon            = "mdi:rocket-launch"
    _attr_has_entity_name = True

    def __init__(self, coordinator: HiveLocalCoordinator, device_id: str, device_data: dict) -> None:
        self._coordinator  = coordinator
        self._device_id    = device_id
        self._device_data  = device_data
        self._attr_unique_id = uid_device(device_id, "boost")
        self._attr_name      = f"{device_data.get('name', device_id)} Boost"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._device_data.get("name", self._device_id),
            manufacturer="Hive",
        )

    async def async_press(self) -> None:
        mqtt = self._coordinator.get_device_mqtt(self._device_id)
        if mqtt:
            await mqtt.async_boost()


class HiveRoomBoostButton(ButtonEntity):
    _attr_icon            = "mdi:rocket-launch"
    _attr_has_entity_name = True

    def __init__(self, coordinator: HiveLocalCoordinator, room_id: str, room: Any) -> None:
        self._coordinator = coordinator
        self._room_id     = room_id
        self._room        = room
        self._attr_unique_id = uid_room(room_id, "boost")
        self._attr_name      = f"{room.room_name} Boost"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"room_{self._room_id}")},
            name=self._room.room_name,
        )

    async def async_press(self) -> None:
        await self._room.async_start_boost()


class HiveRoomEndBoostButton(ButtonEntity):
    _attr_icon            = "mdi:stop-circle-outline"
    _attr_has_entity_name = True

    def __init__(self, coordinator: HiveLocalCoordinator, room_id: str, room: Any) -> None:
        self._coordinator = coordinator
        self._room_id     = room_id
        self._room        = room
        self._attr_unique_id = uid_room(room_id, "end_boost")
        self._attr_name      = f"{room.room_name} End Boost"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"room_{self._room_id}")},
            name=self._room.room_name,
        )

    @property
    def available(self) -> bool:
        return self._room.mode == MODE_BOOST

    async def async_press(self) -> None:
        await self._room.async_end_boost()
