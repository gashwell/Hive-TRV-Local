"""Climate platform — individual TRV entities and room group entities.

Grouped TRVs suppress their own climate entity (controlled by the group).
Sensor entities (battery, temperature, demand) remain visible.
Member suppression/restoration happens live via bus events.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity, ClimateEntityFeature, HVACAction, HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_HUB, DATA_STORE, DOMAIN, MODE_BOOST, MODE_MANUAL, MODE_OFF, MODE_SCHEDULE
from .coordinator import HiveTRVCoordinator, HiveTRVHub
from homeassistant.helpers import entity_registry as er

from .entity import HiveTRVEntity
from .room import HiveRoomCoordinator


def _disable_entity(hass, entity_id: str) -> None:
    """Disable a TRV climate entity when it joins a group."""
    reg = er.async_get(hass)
    entry = reg.async_get(entity_id)
    if entry and entry.disabled_by is None:
        reg.async_update_entity(entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION)


def _enable_entity(hass, entity_id: str) -> None:
    """Re-enable a TRV climate entity when it leaves a group."""
    reg = er.async_get(hass)
    entry = reg.async_get(entity_id)
    if entry and entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION:
        reg.async_update_entity(entity_id, disabled_by=None)


def _entity_id_for_coord(coord: HiveTRVCoordinator) -> str:
    """Derive the HA entity_id that this TRV's climate entity would have."""
    slug = coord.friendly_name.lower().replace(" ", "_").replace("-", "_")
    return f"climate.{slug}"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate entities. Grouped TRVs are suppressed."""
    hub: HiveTRVHub   = hass.data[DOMAIN][entry.entry_id][DATA_HUB]
    store             = hass.data[DOMAIN][entry.entry_id][DATA_STORE]

    _trv_entities:  dict[str, HiveTRVClimate]  = {}   # keyed by friendly_name
    _room_entities: dict[str, HiveRoomClimate] = {}   # keyed by room_id

    def _grouped_entity_ids() -> set[str]:
        """HA entity_ids of TRVs already in any group."""
        if not store:
            return set()
        grouped: set[str] = set()
        for rdata in store.get_all_rooms().values():
            grouped.update(rdata.get("members", []))
            grouped.update(rdata.get("trvs", []))   # legacy key
        return grouped

    def _friendly_name_for_entity_id(entity_id: str) -> str | None:
        """Reverse-lookup friendly_name from entity_id for Hive TRVs."""
        for name, coord in hub.coordinators.items():
            if _entity_id_for_coord(coord) == entity_id:
                return name
        return None

    # ── Individual Hive TRVs ──────────────────────────────────────────────────

    def _add_trv(coord: HiveTRVCoordinator) -> None:
        eid = _entity_id_for_coord(coord)
        if eid in _grouped_entity_ids():
            return
        if coord.friendly_name not in _trv_entities:
            e = HiveTRVClimate(coord)
            _trv_entities[coord.friendly_name] = e
            async_add_entities([e])

    def _remove_trv(friendly_name: str) -> None:
        e = _trv_entities.pop(friendly_name, None)
        if e:
            hass.async_create_task(e.async_remove())

    hub.register_add_entities("climate", _add_trv, _remove_trv)

    # Disable entities for TRVs already in groups on this startup
    for e in list(_trv_entities.values()):
        if _entity_id_for_coord(e.coordinator) in _grouped_entity_ids():
            _disable_entity(hass, e.entity_id)
            _trv_entities.pop(e.coordinator.friendly_name, None)

    # ── Room groups ────────────────────────────────────────────────────────────

    @callback
    def _on_room_added(event: Any) -> None:
        if event.data.get("entry_id") != entry.entry_id:
            return
        room_id    = event.data.get("room_id")
        room_coord = event.data.get("coordinator")
        if not room_coord:
            return   # __init__.py fires again with coordinator — wait for that

        if room_id not in _room_entities:
            e = HiveRoomClimate(room_coord)
            _room_entities[room_id] = e
            async_add_entities([e])

        # Suppress individual climate entities for grouped Hive TRVs
        for eid in room_coord.member_entity_ids:
            fname = _friendly_name_for_entity_id(eid)
            if fname and fname in _trv_entities:
                ind = _trv_entities.pop(fname)
                hass.async_create_task(ind.async_remove())

    @callback
    def _on_room_removed(event: Any) -> None:
        room_id    = event.data.get("room_id")
        freed_eids = event.data.get("freed_trvs", [])

        e = _room_entities.pop(room_id, None)
        if e:
            hass.async_create_task(e.async_remove())

        # Re-enable OUR entity for each TRV leaving the group
        for eid in freed_eids:
            fname = _fname_for_z2m_eid(eid) or _friendly_name_for_entity_id(eid)
            if fname:
                coord = hub.get_coordinator(fname)
                if coord:
                    our_eid = _entity_id_for_coord(coord)
                    if fname not in _trv_entities:
                        entity = HiveTRVClimate(coord)
                        _trv_entities[fname] = entity
                        async_add_entities([entity])
                    _enable_entity(hass, our_eid)

    @callback
    def _on_room_members_changed(event: Any) -> None:
        if event.data.get("entry_id") != entry.entry_id:
            return
        room_id      = event.data.get("room_id")
        added_eids   = event.data.get("added_trvs", [])
        removed_eids = event.data.get("removed_trvs", [])

        # Disable OUR entity for newly added Z2M members
        for eid in added_eids:
            fname = _fname_for_z2m_eid(eid) or _friendly_name_for_entity_id(eid)
            if fname:
                coord = hub.get_coordinator(fname)
                if coord:
                    _trv_entities.pop(fname, None)
                    _disable_entity(hass, _entity_id_for_coord(coord))

        # Re-enable OUR entity for removed Z2M members
        for eid in removed_eids:
            fname = _fname_for_z2m_eid(eid) or _friendly_name_for_entity_id(eid)
            if fname:
                coord = hub.get_coordinator(fname)
                if coord:
                    our_eid = _entity_id_for_coord(coord)
                    if fname not in _trv_entities:
                        entity = HiveTRVClimate(coord)
                        _trv_entities[fname] = entity
                        async_add_entities([entity])
                    _enable_entity(hass, our_eid)

        room_e = _room_entities.get(room_id)
        if room_e:
            room_e.async_write_ha_state()

    entry.async_on_unload(hass.bus.async_listen(f"{DOMAIN}_room_added",           _on_room_added))
    entry.async_on_unload(hass.bus.async_listen(f"{DOMAIN}_room_removed",         _on_room_removed))
    entry.async_on_unload(hass.bus.async_listen(f"{DOMAIN}_room_members_changed", _on_room_members_changed))


# ── Individual Hive TRV climate ────────────────────────────────────────────────

class HiveTRVClimate(HiveTRVEntity, ClimateEntity):
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

    def __init__(self, coordinator: HiveTRVCoordinator) -> None:
        super().__init__(coordinator, "climate")
        self._attr_name = None

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
        return HVACAction.HEATING if self.coordinator.heat_required else HVACAction.IDLE

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
        await self.coordinator.async_set_mode(MODE_OFF if hvac_mode == HVACMode.OFF else MODE_MANUAL)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self.coordinator.async_set_mode(preset_mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        if (t := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self.coordinator.async_set_manual_temperature(float(t))

    async def async_turn_on(self)  -> None: await self.coordinator.async_set_mode(MODE_MANUAL)
    async def async_turn_off(self) -> None: await self.coordinator.async_set_mode(MODE_OFF)


# ── Room group climate ─────────────────────────────────────────────────────────

class HiveRoomClimate(CoordinatorEntity[HiveRoomCoordinator], ClimateEntity):
    """Climate entity for a room group — controls any mix of thermostats."""

    _attr_temperature_unit        = UnitOfTemperature.CELSIUS
    _attr_hvac_modes              = [HVACMode.HEAT, HVACMode.OFF]
    _attr_min_temp                = 5.0
    _attr_max_temp                = 32.0
    _attr_target_temperature_step = 0.5
    _attr_has_entity_name         = True
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: HiveRoomCoordinator) -> None:
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
        return HVACAction.HEATING if self.coordinator.heat_required else HVACAction.IDLE

    @property
    def preset_mode(self) -> str | None:
        m = self.coordinator.mode
        return None if m == MODE_OFF else m

    @property
    def current_temperature(self) -> float | None:
        return self.coordinator.current_temperature

    @property
    def target_temperature(self) -> float | None:
        return self.coordinator.setpoint

    @property
    def extra_state_attributes(self) -> dict:
        attrs: dict = {
            "members":           self.coordinator.member_entity_ids,
            "member_count":      len(self.coordinator.member_entity_ids),
            "member_temperatures": self.coordinator.member_temperatures,
            "heat_required":     self.coordinator.heat_required,
            "mode":              self.coordinator.mode,
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

    async def async_turn_on(self)  -> None: await self.coordinator.async_set_mode(MODE_MANUAL)
    async def async_turn_off(self) -> None: await self.coordinator.async_set_mode(MODE_OFF)
