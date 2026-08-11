"""Room group coordinator — aggregates any HA climate entities into a single virtual entity.

Members can be any climate entity HA knows about — Hive TRVs, Z2M thermostats,
generic climate integrations, etc. Temperature and commands go through the HA
state machine and service layer rather than directly to Z2M coordinators.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
import homeassistant.util.dt as dt_util

from .const import (
    DEFAULT_BOOST_MINUTES,
    DEFAULT_BOOST_TEMP,
    DEFAULT_FROST_TEMP,
    MODE_BOOST,
    MODE_MANUAL,
    MODE_OFF,
    MODE_SCHEDULE,
)
from .schedule import ScheduleManager

_LOGGER = logging.getLogger(__name__)

# HA climate service constants
_CLIMATE_DOMAIN        = "climate"
_SVC_SET_TEMPERATURE   = "set_temperature"
_SVC_SET_HVAC_MODE     = "set_hvac_mode"
_SVC_SET_PRESET_MODE   = "set_preset_mode"
_ATTR_HVAC_MODE        = "hvac_mode"
_ATTR_PRESET_MODE      = "preset_mode"
_ATTR_CURRENT_TEMP     = "current_temperature"


class HiveRoomCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Virtual coordinator for a room group of climate entities.

    Works with any HA climate entity — Hive TRVs, Z2M thermostats,
    or any other integration. Commands are issued as HA service calls.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        room_id: str,
        room_name: str,
        member_entity_ids: list[str],
        temp_sensor_entity_ids: list[str],
        store=None,
    ) -> None:
        super().__init__(hass, _LOGGER, name=f"Hive Room {room_name}")
        self.room_id   = room_id
        self.room_name = room_name
        self._store    = store

        self._member_ids  = list(member_entity_ids)
        self._sensor_ids  = list(temp_sensor_entity_ids)

        self._mode: str               = MODE_MANUAL
        self._setpoint: float         = 20.0
        self._pre_boost_mode: str     = MODE_MANUAL
        self._pre_boost_setpoint: float = 20.0
        self._boost_end: datetime | None = None
        self._boost_task: asyncio.Task | None = None

        self._schedule_mgr = ScheduleManager(
            hass, room_name,
            lambda temp: self.hass.async_create_task(self._apply_temperature(temp))
        )

        self._unsubscribers: list[Callable] = []
        self.data: dict[str, Any] = {}

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def async_setup(self) -> None:
        """Subscribe to member entity and sensor state changes."""
        all_tracked = self._member_ids + self._sensor_ids
        if all_tracked:
            self._unsubscribers.append(
                async_track_state_change_event(
                    self.hass, all_tracked, self._on_state_update
                )
            )
        self._refresh_data()

    async def async_unload(self) -> None:
        if self._boost_task:
            self._boost_task.cancel()
        self._schedule_mgr.clear()
        for unsub in self._unsubscribers:
            unsub()
        self._unsubscribers.clear()

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def setpoint(self) -> float:
        return self._setpoint

    @property
    def current_temperature(self) -> float | None:
        """Average temperature across all members and extra sensors."""
        temps: list[float] = []

        # Extra temperature sensors (higher quality sources first)
        for eid in self._sensor_ids:
            state = self.hass.states.get(eid)
            if state and state.state not in ("unavailable", "unknown"):
                try:
                    temps.append(float(state.state))
                except ValueError:
                    pass

        # Member climate entities
        for eid in self._member_ids:
            state = self.hass.states.get(eid)
            if state and state.state not in ("unavailable", "unknown"):
                cur = state.attributes.get(_ATTR_CURRENT_TEMP)
                if cur is not None:
                    try:
                        temps.append(float(cur))
                    except ValueError:
                        pass

        return round(sum(temps) / len(temps), 1) if temps else None

    @property
    def member_temperatures(self) -> dict[str, float | None]:
        """Per-member current temperatures, keyed by entity_id."""
        result: dict[str, float | None] = {}
        for eid in self._member_ids:
            state = self.hass.states.get(eid)
            if state:
                cur = state.attributes.get(_ATTR_CURRENT_TEMP)
                try:
                    result[eid] = float(cur) if cur is not None else None
                except ValueError:
                    result[eid] = None
            else:
                result[eid] = None
        return result

    @property
    def heat_required(self) -> bool:
        """True if any member is currently heating."""
        from homeassistant.components.climate import HVACAction
        for eid in self._member_ids:
            state = self.hass.states.get(eid)
            if state:
                action = state.attributes.get("hvac_action", "")
                if action == HVACAction.HEATING:
                    return True
        return False

    @property
    def boost_end_time(self) -> datetime | None:
        return self._boost_end

    @property
    def boost_remaining_minutes(self) -> int | None:
        if self._boost_end is None:
            return None
        remaining = (self._boost_end - dt_util.utcnow()).total_seconds()
        return max(0, int(remaining / 60))

    @property
    def member_trv_names(self) -> list[str]:
        """Return member entity IDs (renamed for compatibility)."""
        return list(self._member_ids)

    @property
    def member_entity_ids(self) -> list[str]:
        return list(self._member_ids)

    @property
    def temp_sensor_ids(self) -> list[str]:
        return list(self._sensor_ids)

    # ── Mode commands ─────────────────────────────────────────────────────────

    async def async_set_mode(self, mode: str, setpoint: float | None = None) -> None:
        if mode == MODE_BOOST:
            await self.async_start_boost()
            return
        if self._boost_task and not self._boost_task.done():
            self._boost_task.cancel()
            self._boost_task = None
            self._boost_end  = None

        self._mode = mode
        if mode == MODE_OFF:
            await self._apply_hvac_mode("off")
        elif mode == MODE_MANUAL:
            sp = setpoint or self._setpoint
            self._setpoint = sp
            await self._apply_hvac_mode("heat")
            await self._apply_temperature(sp)
        elif mode == MODE_SCHEDULE:
            await self._apply_hvac_mode("heat")
        self._refresh_data()

    async def async_set_temperature(self, temp: float) -> None:
        self._setpoint = temp
        if self._mode == MODE_OFF:
            self._mode = MODE_MANUAL
        await self._apply_hvac_mode("heat")
        await self._apply_temperature(temp)
        self._refresh_data()

    # ── Boost ─────────────────────────────────────────────────────────────────

    async def async_start_boost(
        self,
        temperature: float | None = None,
        duration_minutes: int | None = None,
    ) -> None:
        if temperature is None and self._store:
            boost_temp = self._store.get_room_boost_temperature(self.room_id)
        else:
            boost_temp = temperature if temperature is not None else DEFAULT_BOOST_TEMP
        if duration_minutes is None and self._store:
            boost_mins = self._store.get_room_boost_duration(self.room_id)
        else:
            boost_mins = duration_minutes if duration_minutes is not None else DEFAULT_BOOST_MINUTES

        self._pre_boost_mode     = self._mode if self._mode != MODE_BOOST else self._pre_boost_mode
        self._pre_boost_setpoint = self._setpoint
        self._mode    = MODE_BOOST
        self._boost_end = dt_util.utcnow() + __import__("datetime").timedelta(minutes=boost_mins)

        if self._boost_task and not self._boost_task.done():
            self._boost_task.cancel()

        await self._apply_hvac_mode("heat")
        await self._apply_temperature(boost_temp)
        self._boost_task = self.hass.async_create_task(self._boost_timer(boost_mins * 60))
        self._refresh_data()
        _LOGGER.info("Room %s boost: %.1f °C for %d min", self.room_name, boost_temp, boost_mins)

    async def async_end_boost(self) -> None:
        if self._boost_task and not self._boost_task.done():
            self._boost_task.cancel()
        self._boost_task = None
        self._boost_end  = None
        await self.async_set_mode(self._pre_boost_mode, self._pre_boost_setpoint)

    async def _boost_timer(self, seconds: int) -> None:
        await asyncio.sleep(seconds)
        self._boost_task = None
        self._boost_end  = None
        await self.async_set_mode(self._pre_boost_mode, self._pre_boost_setpoint)

    # ── Schedule ──────────────────────────────────────────────────────────────

    async def async_set_schedule(self, schedule: list[dict]) -> None:
        await self._schedule_mgr.async_set_schedule(schedule)

    def clear_schedule(self) -> None:
        self._schedule_mgr.clear()

    # ── HA service calls ──────────────────────────────────────────────────────

    async def _apply_temperature(self, temp: float) -> None:
        """Set target temperature on all member climate entities."""
        if not self._member_ids:
            return
        await self.hass.services.async_call(
            _CLIMATE_DOMAIN,
            _SVC_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: self._member_ids, ATTR_TEMPERATURE: temp},
            blocking=False,
        )

    async def _apply_hvac_mode(self, hvac_mode: str) -> None:
        """Set HVAC mode on all member climate entities."""
        if not self._member_ids:
            return
        await self.hass.services.async_call(
            _CLIMATE_DOMAIN,
            _SVC_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: self._member_ids, _ATTR_HVAC_MODE: hvac_mode},
            blocking=False,
        )

    # ── State tracking ────────────────────────────────────────────────────────

    @callback
    def _on_state_update(self, _event: Any) -> None:
        self._refresh_data()

    def _refresh_data(self) -> None:
        self.async_set_updated_data({
            "mode":                self._mode,
            "setpoint":            self._setpoint,
            "current_temperature": self.current_temperature,
            "member_temperatures": self.member_temperatures,
            "heat_required":       self.heat_required,
            "boost_end":           self._boost_end.isoformat() if self._boost_end else None,
        })
