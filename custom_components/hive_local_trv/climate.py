"""Climate platform — individual TRV entities and room group entities.

Grouped TRVs suppress their own climate entity (it is managed by the group).
Their sensor entities (battery, temperature, demand) remain visible.
When a TRV is moved into or out of a group the climate entity is
added/removed dynamically without a restart.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_HUB, DATA_STORE, DOMAIN, MODE_BOOST, MODE_MANUAL, MODE_OFF, MODE_SCHEDULE
from .coordinator import HiveTRVCoordinator, HiveTRVHub
from .entity import HiveTRVEntity
from .room import HiveRoomCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate entities, suppressing individual entities for grouped TRVs."""
    hub: HiveTRVHub = hass.data[DOMAIN][entry.entry_id][DATA_HUB]
    store = hass.data[DOMAIN][entry.entry_id][DATA_STORE]

    _trv_entities: dict[str, HiveTRVClimate]  = {}
    _room_entities: dict[str, HiveRoomClimate] = {}

    def _grouped_trv_names() -> set[str]:
        """Return the set of TRV names currently assigned to any room group."""
        if not store:
            return set()
        grouped: set[str] = set()
        for rdata in store.get_all_rooms().values():
            grouped.update(rdata.get("trvs", []))
        return grouped

    # ── Individual TRVs ───────────────────────────────────────────────────────

    def _add_trv(coord: HiveTRVCoordinator) -> None:
        """Register a climate entity only if the TRV is not in a group."""
        if coord.friendly_name in _grouped_trv_names():
            return  # managed by its room group — suppress individual climate
        if coord.friendly_name not in _trv_entities:
            e = HiveTRVClimate(coord)
            _trv_entities[coord.friendly_name] = e
            async_add_entities([e])

    def _remove_trv(friendly_name: str) -> None:
        e = _trv_entities.pop(friendly_name, None)
        if e:
            hass.async_create_task(e.async_remove())

    hub.register_add_entities("climate", _add_trv, _remove_trv)

    # ── Room groups ────────────────────────────────────────────────────────────

    @callback
    def _on_room_added(event: Any) -> None:
        if event.data.get("entry_id") != entry.entry_id:
            return
        room_id    = event.data["room_id"]
        room_coord = event.data.get("coordinator")
        if not room_coord:
            return

        # Register the group climate entity
        if room_id not in _room_entities:
            e = HiveRoomClimate(room_coord)
            _room_entities[room_id] = e
            async_add_entities([e])

        # Suppress individual climate entities for newly grouped TRVs
        for name in room_coord.member_trv_names:
            if name in _trv_entities:
                ind = _trv_entities.pop(name)
                hass.async_create_task(ind.async_remove())

    @callback
    def _on_room_removed(event: Any) -> None:
        room_id   = event.data.get("room_id")
        freed_trvs = event.data.get("freed_trvs", [])
        e = _room_entities.pop(room_id, None)
        if e:
            hass.async_create_task(e.async_remove())

        # Re-register individual climate entities for TRVs released from the group
        for name in freed_trvs:
            coord = hub.get_coordinator(name)
            if coord and name not in _trv_entities:
                entity = HiveTRVClimate(coord)
                _trv_entities[name] = entity
                async_add_entities([entity])

    @callback
    def _on_room_members_changed(event: Any) -> None:
        """Handle members being added to or removed from an existing group."""
        if event.data.get("entry_id") != entry.entry_id:
            return
        room_id        = event.data.get("room_id")
        added_trvs     = event.data.get("added_trvs", [])
        removed_trvs   = event.data.get("removed_trvs", [])

        # Suppress climate entities for newly added members
        for name in added_trvs:
            if name in _trv_entities:
                ind = _trv_entities.pop(name)
                hass.async_create_task(ind.async_remove())

        # Restore climate entities for removed members
        for name in removed_trvs:
            coord = hub.get_coordinator(name)
            if coord and name not in _trv_entities:
                entity = HiveTRVClimate(coord)
                _trv_entities[name] = entity
                async_add_entities([entity])

        # Refresh the room climate entity so it reflects new membership
        room_e = _room_entities.get(room_id)
        if room_e:
            room_e.async_write_ha_state()

    entry.async_on_unload(
        hass.bus.async_listen(f"{DOMAIN}_room_added",           _on_room_added)
    )
    entry.async_on_unload(
        hass.bus.async_listen(f"{DOMAIN}_room_removed",         _on_room_removed)
    )
    entry.async_on_unload(
        hass.bus.async_listen(f"{DOMAIN}_room_members_changed", _on_room_members_changed)
    )


# ── Individual TRV climate entity ─────────────────────────────────────────────

class HiveTRVClimate(HiveTRVEntity, ClimateEntity):
    """Climate entity for a single ungrouped Hive TRV."""

    _attr_temperature_unit          = UnitOfTemperature.CELSIUS
    _attr_hvac_modes                = [HVACMode.HEAT, HVACMode.OFF]
    _attr_min_temp                  = 5.0
    _attr_max_temp                  = 32.0
    _attr_target_temperature_step   = 0.5
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: HiveTRVCoordinator) -> None:
        """Initialise."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.ieee_address}_climate"
        self._attr_name      = None  # device name IS the entity name

    @property
    def preset_modes(self) -> list[str]:
        return [MODE_MANUAL, MODE_SCHEDULE, MODE_BOOST]

    @property
    def hvac_mode(self) -> HVACMode:
        return HVACMode.OFF if self.coordinator.mode == MODE_OFF else HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction:
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        return (HVACAction.HEATING if self.coordinator.heat_required else HVACAction.IDLE)

    @property
    def preset_mode(self) -> str | None:
        m = self.coordinator.mode
        return None if m == MODE_OFF else m

    @property
    def current_temperature(self) -> float | None:
        return self.coordinator.local_temperature

    @property
    def target_temperature(self) -> float | None:
        return self.coordinator.setpoint

    @property
    def extra_state_attributes(self) -> dict:
        attrs: dict = {
            "mode":             self.coordinator.mode,
            "pi_heating_demand": self.coordinator.pi_heating_demand,
            "heat_required":    self.coordinator.heat_required,
            "battery":          self.coordinator.battery,
        }
        if self.coordinator.mode == MODE_BOOST:
            attrs["boost_ends"] = self.coordinator.boost_end_time
        return {k: v for k, v in attrs.items() if v is not None}

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        m = MODE_OFF if hvac_mode == HVACMode.OFF else MODE_MANUAL
        await self.coordinator.async_set_mode(m)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self.coordinator.async_set_mode(preset_mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        if (t := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self.coordinator.async_set_manual_temperature(float(t))

    async def async_turn_on(self)  -> None:
        await self.coordinator.async_set_mode(MODE_MANUAL)

    async def async_turn_off(self) -> None:
        await self.coordinator.async_set_mode(MODE_OFF)


# ── Room group climate entity ──────────────────────────────────────────────────

class HiveRoomClimate(CoordinatorEntity[HiveRoomCoordinator], ClimateEntity):
    """Climate entity representing a room group.

    - Temperature: average of all member TRVs (+ any extra sensors)
    - Mode / boost / schedule: fanned out to all member TRVs simultaneously
    - Individual TRV sensor entities remain available for per-device temperature
    """

    _attr_temperature_unit        = UnitOfTemperature.CELSIUS
    _attr_hvac_modes              = [HVACMode.HEAT, HVACMode.OFF]
    _attr_min_temp                = 5.0
    _attr_max_temp                = 32.0
    _attr_target_temperature_step = 0.5
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_has_entity_name = True

    def __init__(self, coordinator: HiveRoomCoordinator) -> None:
        """Initialise."""
        super().__init__(coordinator)
        self._attr_unique_id = f"room_{coordinator.room_id}_climate"
        self._attr_name      = coordinator.room_name

    @property
    def device_info(self) -> dict:
        return {
            "identifiers": {(DOMAIN, f"room_{self.coordinator.room_id}")},
            "name":        f"{self.coordinator.room_name} (Room Group)",
            "model":       "Room Group",
            "manufacturer":"Hive Home Local",
        }

    @property
    def preset_modes(self) -> list[str]:
        return [MODE_MANUAL, MODE_SCHEDULE, MODE_BOOST]

    @property
    def hvac_mode(self) -> HVACMode:
        return HVACMode.OFF if self.coordinator.mode == MODE_OFF else HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction:
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        return (HVACAction.HEATING if self.coordinator.heat_required else HVACAction.IDLE)

    @property
    def preset_mode(self) -> str | None:
        m = self.coordinator.mode
        return None if m == MODE_OFF else m

    @property
    def current_temperature(self) -> float | None:
        """Average temperature across all group members and extra sensors."""
        return self.coordinator.current_temperature

    @property
    def target_temperature(self) -> float | None:
        return self.coordinator.setpoint

    @property
    def extra_state_attributes(self) -> dict:
        attrs: dict = {
            "members":      self.coordinator.member_trv_names,
            "member_count": len(self.coordinator.member_trv_names),
            "heat_required": self.coordinator.heat_required,
            "mode":         self.coordinator.mode,
        }
        if self.coordinator.mode == MODE_BOOST:
            attrs["boost_ends"]              = self.coordinator.boost_end_time
            attrs["boost_remaining_minutes"] = self.coordinator.boost_remaining_minutes
        return {k: v for k, v in attrs.items() if v is not None}

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        m = MODE_OFF if hvac_mode == HVACMode.OFF else MODE_MANUAL
        await self.coordinator.async_set_mode(m)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self.coordinator.async_set_mode(preset_mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        if (t := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self.coordinator.async_set_temperature(float(t))

    async def async_turn_on(self)  -> None:
        await self.coordinator.async_set_mode(MODE_MANUAL)

    async def async_turn_off(self) -> None:
        await self.coordinator.async_set_mode(MODE_OFF)
