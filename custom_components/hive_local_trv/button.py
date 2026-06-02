"""Button platform — TRV calibration buttons + room group boost/end-boost buttons."""
from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_HUB, DOMAIN
from .coordinator import HiveTRVCoordinator, HiveTRVHub
from .entity import HiveTRVEntity
from .room import HiveRoomCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    hub: HiveTRVHub = hass.data[DOMAIN][entry.entry_id][DATA_HUB]

    # ── Per-TRV buttons ───────────────────────────────────────────────────────
    _trv_entities: dict[str, list] = {}

    def _add_trv(coord: HiveTRVCoordinator) -> None:
        if coord.friendly_name not in _trv_entities:
            es = [HiveAdaptationButton(coord), HiveMountingButton(coord)]
            _trv_entities[coord.friendly_name] = es
            async_add_entities(es)

    def _remove_trv(name: str) -> None:
        for e in _trv_entities.pop(name, []):
            hass.async_create_task(e.async_remove())

    hub.register_add_entities("button", _add_trv, _remove_trv)

    # ── Per-room-group buttons ────────────────────────────────────────────────
    _room_entities: dict[str, list] = {}

    @callback
    def _on_room_added(event: Any) -> None:
        if event.data.get("entry_id") != entry.entry_id:
            return
        room_id   = event.data.get("room_id")
        room_coord = event.data.get("coordinator")
        if room_coord and room_id and room_id not in _room_entities:
            es = [
                HiveRoomBoostButton(room_coord),
                HiveRoomEndBoostButton(room_coord),
            ]
            _room_entities[room_id] = es
            async_add_entities(es)

    @callback
    def _on_room_removed(event: Any) -> None:
        room_id = event.data.get("room_id")
        for e in _room_entities.pop(room_id, []):
            hass.async_create_task(e.async_remove())

    entry.async_on_unload(hass.bus.async_listen(f"{DOMAIN}_room_added",   _on_room_added))
    entry.async_on_unload(hass.bus.async_listen(f"{DOMAIN}_room_removed", _on_room_removed))


# ── Individual TRV buttons ─────────────────────────────────────────────────────

class HiveAdaptationButton(HiveTRVEntity, ButtonEntity):
    _attr_name = "Run Adaptation"
    _attr_icon = "mdi:cog-sync"

    def __init__(self, coord: HiveTRVCoordinator) -> None:
        super().__init__(coord, "adaptation_run")

    async def async_press(self) -> None:
        await self.coordinator.async_trigger_adaptation_run()


class HiveMountingButton(HiveTRVEntity, ButtonEntity):
    _attr_name = "Enter Mounting Mode"
    _attr_icon = "mdi:wrench"

    def __init__(self, coord: HiveTRVCoordinator) -> None:
        super().__init__(coord, "mounting_mode")

    async def async_press(self) -> None:
        await self.coordinator.async_set_mounted(False)


# ── Room group buttons ─────────────────────────────────────────────────────────

class HiveRoomBoostButton(CoordinatorEntity[HiveRoomCoordinator], ButtonEntity):
    """One-press boost for the entire room group at the stored default temperature/duration."""

    _attr_icon = "mdi:rocket-launch"
    _attr_has_entity_name = True

    def __init__(self, coordinator: HiveRoomCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"room_{coordinator.room_id}_boost"
        self._attr_name      = f"{coordinator.room_name} Boost"

    @property
    def device_info(self) -> dict:
        return {"identifiers": {(DOMAIN, f"room_{self.coordinator.room_id}")}}

    async def async_press(self) -> None:
        await self.coordinator.async_start_boost()


class HiveRoomEndBoostButton(CoordinatorEntity[HiveRoomCoordinator], ButtonEntity):
    """Cancel an active boost on the entire room group."""

    _attr_icon = "mdi:stop-circle-outline"
    _attr_has_entity_name = True

    def __init__(self, coordinator: HiveRoomCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"room_{coordinator.room_id}_end_boost"
        self._attr_name      = f"{coordinator.room_name} End Boost"

    @property
    def device_info(self) -> dict:
        return {"identifiers": {(DOMAIN, f"room_{self.coordinator.room_id}")}}

    @property
    def available(self) -> bool:
        """Only available when a boost is active."""
        return self.coordinator.mode == "boost"

    async def async_press(self) -> None:
        await self.coordinator.async_end_boost()
