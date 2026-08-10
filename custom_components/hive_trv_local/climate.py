"""Climate platform — device TRV/receiver entities and room group entities."""
from __future__ import annotations

import logging
from math import floor
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity, ClimateEntityFeature, HVACAction, HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ENTRY_TYPE, DATA_STORE, DOMAIN,
    ENTRY_TYPE_GROUPS, ENTRY_TYPE_RECEIVER, ENTRY_TYPE_TRV,
    EVENT_ROOM_ADDED, EVENT_ROOM_REMOVED,
    MODE_BOOST, MODE_MANUAL, MODE_OFF, MODE_SCHEDULE,
    MODEL_SLR2,
)
from .coordinator import HiveDeviceCoordinator
from .entity import HiveDeviceEntity
from .room import HiveRoomCoordinator

_LOGGER = logging.getLogger(__name__)

_GROUP_PRESETS  = [MODE_MANUAL, MODE_SCHEDULE, MODE_BOOST]
_GROUP_FEATURES = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.PRESET_MODE
    | ClimateEntityFeature.TURN_ON
    | ClimateEntityFeature.TURN_OFF
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entry_type = entry.data.get(CONF_ENTRY_TYPE)

    if entry_type in (ENTRY_TYPE_TRV, ENTRY_TYPE_RECEIVER):
        coordinator: HiveDeviceCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        entities: list = [HiveDeviceClimate(coordinator, entry)]
        async_add_entities(entities)

    elif entry_type == ENTRY_TYPE_GROUPS:
        _entities: dict[str, HiveRoomClimate] = {}

        @callback
        def _on_room_added(event: Any) -> None:
            if event.data.get("entry_id") != entry.entry_id:
                return
            room_id = event.data.get("room_id")
            rc      = event.data.get("coordinator")
            if rc and room_id not in _entities:
                e = HiveRoomClimate(rc)
                _entities[room_id] = e
                async_add_entities([e])

        @callback
        def _on_room_removed(event: Any) -> None:
            if event.data.get("entry_id") != entry.entry_id:
                return
            e = _entities.pop(event.data.get("room_id"), None)
            if e:
                hass.async_create_task(e.async_remove())

        entry.async_on_unload(hass.bus.async_listen(EVENT_ROOM_ADDED,   _on_room_added))
        entry.async_on_unload(hass.bus.async_listen(EVENT_ROOM_REMOVED, _on_room_removed))


# ── Device climate entity ──────────────────────────────────────────────────────

class HiveDeviceClimate(HiveDeviceEntity, ClimateEntity):
    """Climate entity for an individual Hive TRV or receiver device."""

    _attr_temperature_unit        = UnitOfTemperature.CELSIUS
    _attr_min_temp                = 5.0
    _attr_max_temp                = 32.0
    _attr_target_temperature_step = 0.5

    def __init__(self, coordinator: HiveDeviceCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry_id}_climate"
        self._attr_name = coordinator.device_name

        if coordinator.show_heat_schedule and not coordinator.is_trv:
            self._attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.AUTO]
        else:
            self._attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]

        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )
        self._from_temp = False

    def _handle_coordinator_update(self) -> None:
        self._attr_current_temperature = self.coordinator.current_temperature
        self._attr_target_temperature  = self.coordinator.target_temperature
        self._attr_hvac_mode           = self.coordinator.hvac_mode
        self._attr_hvac_action         = self.coordinator.hvac_action
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp:
            self._attr_target_temperature = temp
        hvac = kwargs.get("hvac_mode")
        if hvac:
            self._from_temp = True
            await self.async_set_hvac_mode(hvac)
            return
        if temp:
            await self.coordinator.async_set_temperature(temp)
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        self._attr_hvac_mode = hvac_mode
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.async_set_hvac_mode_off()
        elif hvac_mode == HVACMode.AUTO:
            await self.coordinator.async_set_hvac_mode_auto()
        elif hvac_mode == HVACMode.HEAT:
            target = (
                self._attr_target_temperature
                or (floor((self.coordinator.current_temperature or 20) * 2) / 2)
            )
            await self.coordinator.async_set_hvac_mode_heat(target, self._from_temp)
        self._from_temp = False
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        target = self._attr_target_temperature or 20.0
        await self.coordinator.async_set_hvac_mode_heat(target)

    async def async_turn_off(self) -> None:
        await self.coordinator.async_set_hvac_mode_off()


# ── Room group climate entity ──────────────────────────────────────────────────

class HiveRoomClimate(CoordinatorEntity[HiveRoomCoordinator], ClimateEntity):
    """Virtual climate entity for a room group."""

    _attr_temperature_unit        = UnitOfTemperature.CELSIUS
    _attr_hvac_modes              = [HVACMode.HEAT, HVACMode.OFF]
    _attr_min_temp                = 5.0
    _attr_max_temp                = 32.0
    _attr_target_temperature_step = 0.5
    _attr_has_entity_name         = True
    _attr_supported_features      = _GROUP_FEATURES

    def __init__(self, coordinator: HiveRoomCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"room_{coordinator.room_id}_climate"
        self._attr_name      = coordinator.room_name

    @property
    def device_info(self):
        return {
            "identifiers":  {(DOMAIN, f"room_{self.coordinator.room_id}")},
            "name":         self.coordinator.room_name,
            "model":        "Room Group",
            "manufacturer": "Hive TRV Local",
        }

    @property
    def available(self) -> bool:
        return self.coordinator.available

    @property
    def hvac_mode(self) -> HVACMode:
        return HVACMode.OFF if self.coordinator.mode == MODE_OFF else HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction:
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        return HVACAction.HEATING if self.coordinator.heat_required else HVACAction.IDLE

    @property
    def preset_modes(self) -> list[str]:
        return _GROUP_PRESETS

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
            "members":               self.coordinator.member_entity_ids,
            "member_count":          len(self.coordinator.member_entity_ids),
            "member_temperatures":   self.coordinator.member_temperatures,
            "heat_required":         self.coordinator.heat_required,
            "mode":                  self.coordinator.mode,
            "schedule":              self.coordinator.schedule_slots,
            "schedule_current_slot": self.coordinator.schedule_current_slot,
        }
        if self.coordinator.mode == MODE_BOOST:
            attrs["boost_ends"]             = self.coordinator.boost_end_time
            attrs["boost_remaining_minutes"]= self.coordinator.boost_remaining_minutes
        return {k: v for k, v in attrs.items() if v is not None}

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        await self.coordinator.async_set_mode(
            MODE_OFF if hvac_mode == HVACMode.OFF else MODE_MANUAL
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self.coordinator.async_set_mode(preset_mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        if (t := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self.coordinator.async_set_temperature(float(t))

    async def async_turn_on(self)  -> None:
        await self.coordinator.async_set_mode(MODE_MANUAL)

    async def async_turn_off(self) -> None:
        await self.coordinator.async_set_mode(MODE_OFF)
