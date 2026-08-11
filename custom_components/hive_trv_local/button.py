"""Button platform — device boost buttons and group boost/end-boost buttons."""
from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ENTRY_TYPE, DATA_BOILER, DOMAIN,
    ENTRY_TYPE_GROUPS, ENTRY_TYPE_RECEIVER,
    EVENT_ROOM_ADDED, EVENT_ROOM_REMOVED,
    MODEL_SLR2,
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

    if entry_type == ENTRY_TYPE_RECEIVER:
        coordinator: HiveDeviceCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        entities = [HiveHeatingBoostButton(coordinator)]
        if coordinator.model == MODEL_SLR2:
            entities.append(HiveWaterBoostButton(coordinator))
        async_add_entities(entities)

    elif entry_type == ENTRY_TYPE_GROUPS:
        boiler_mgr  = hass.data[DOMAIN][entry.entry_id][DATA_BOILER]
        _entities: dict[str, list] = {}

        @callback
        def _on_room_added(event: Any) -> None:
            if event.data.get("entry_id") != entry.entry_id:
                return
            room_id = event.data.get("room_id")
            rc      = event.data.get("coordinator")
            if rc and room_id not in _entities:
                es = [HiveRoomBoostButton(rc, boiler_mgr), HiveRoomEndBoostButton(rc, boiler_mgr)]
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


# ── Device buttons ─────────────────────────────────────────────────────────────

class HiveHeatingBoostButton(HiveDeviceEntity, ButtonEntity):
    _attr_icon = "mdi:rocket-launch"

    def __init__(self, coordinator: HiveDeviceCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry_id}_boost_heating"
        self._attr_name      = f"{coordinator.device_name} Boost Heating"

    async def async_press(self) -> None:
        await self.coordinator.async_heating_boost()


class HiveWaterBoostButton(HiveDeviceEntity, ButtonEntity):
    _attr_icon = "mdi:water-boiler"

    def __init__(self, coordinator: HiveDeviceCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry_id}_boost_water"
        self._attr_name      = f"{coordinator.device_name} Boost Water"

    async def async_press(self) -> None:
        await self.coordinator.async_water_boost()


# ── Group buttons ──────────────────────────────────────────────────────────────

class HiveRoomBoostButton(CoordinatorEntity[HiveRoomCoordinator], ButtonEntity):
    _attr_icon            = "mdi:rocket-launch"
    _attr_has_entity_name = True

    def __init__(self, coordinator: HiveRoomCoordinator, boiler_mgr: Any) -> None:
        super().__init__(coordinator)
        self._boiler_mgr     = boiler_mgr
        self._attr_unique_id = f"room_{coordinator.room_id}_boost"
        self._attr_name      = f"{coordinator.room_name} Boost"

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, f"room_{self.coordinator.room_id}")}}

    @property
    def available(self) -> bool:
        return self.coordinator.available

    async def async_press(self) -> None:
        await self.coordinator.async_start_boost()


class HiveRoomEndBoostButton(CoordinatorEntity[HiveRoomCoordinator], ButtonEntity):
    _attr_icon            = "mdi:stop-circle-outline"
    _attr_has_entity_name = True

    def __init__(self, coordinator: HiveRoomCoordinator, boiler_mgr: Any) -> None:
        super().__init__(coordinator)
        self._boiler_mgr     = boiler_mgr
        self._attr_unique_id = f"room_{coordinator.room_id}_end_boost"
        self._attr_name      = f"{coordinator.room_name} End Boost"

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, f"room_{self.coordinator.room_id}")}}

    @property
    def available(self) -> bool:
        return self.coordinator.available and self.coordinator.mode == "boost"

    async def async_press(self) -> None:
        await self.coordinator.async_end_boost()
