"""Room group coordinator.

Aggregates any set of HA climate entities (Z2M TRVs, other thermostats)
into a single virtual room entity. All commands go through HA service calls
so no MQTT or integration-specific knowledge is needed.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

import homeassistant.util.dt as dt_util
from homeassistant.components.climate import HVACAction
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DEFAULT_BOOST_MINUTES, DEFAULT_BOOST_TEMP, DEFAULT_FROST_TEMP,
    DOMAIN, MODE_BOOST, MODE_MANUAL, MODE_OFF, MODE_SCHEDULE,
)
from .schedule import ScheduleManager

_LOGGER = logging.getLogger(__name__)


class HiveRoomCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Virtual coordinator for a room group of HA climate entities.

    Temperature = average of member current_temperature attributes.
    Commands   = HA service calls (climate.set_temperature etc.).
    Works with any climate entity regardless of integration.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        room_id: str,
        room_name: str,
        member_entity_ids: list[str],
        temp_sensor_entity_ids: list[str],
        store=None,
        frost_weather_entity: str | None = None,
        frost_temperature: float = 2.0,
    ) -> None:
        super().__init__(hass, _LOGGER, name=f"Hive Room {room_name}")
        self.room_id   = room_id
        self.room_name = room_name
        self._store    = store

        self._members: list[str] = list(member_entity_ids)
        self._sensors: list[str] = list(temp_sensor_entity_ids)
        self._frost_weather_entity = frost_weather_entity
        self._frost_temperature    = frost_temperature

        # State
        self._mode:          str   = MODE_MANUAL
        self._setpoint:      float = 20.0
        self._pre_boost_mode: str  = MODE_MANUAL
        self._pre_boost_sp:  float = 20.0
        self._boost_end:     datetime | None = None
        self._boost_task:    asyncio.Task | None = None

        self._schedule_mgr = ScheduleManager(
            hass, room_name,
            lambda t: hass.async_create_task(self._svc_set_temperature(t)),
        )
        self._unsubscribers: list[Callable] = []
        self.data: dict[str, Any] = {}

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def async_setup(self) -> None:
        _LOGGER.debug("Room setup: %s (%s)", self.room_name, self.room_id)
        self._subscribe()
        self._refresh()

    async def async_unload(self) -> None:
        if self._boost_task:
            self._boost_task.cancel()
        self._schedule_mgr.clear()
        self._unsubscribe()

    def _subscribe(self) -> None:
        tracked = self._members + self._sensors
        if tracked:
            self._unsubscribers.append(
                async_track_state_change_event(
                    self.hass, tracked, self._on_state_change
                )
            )

    def _unsubscribe(self) -> None:
        for unsub in self._unsubscribers:
            unsub()
        self._unsubscribers.clear()

    # ── Membership ────────────────────────────────────────────────────────────

    def update_members(
        self, member_entity_ids: list[str],
        temp_sensor_ids: list[str] | None = None
    ) -> None:
        """Update membership in-place and re-subscribe."""
        _LOGGER.info("Room %s: updating members → %s", self.room_name, member_entity_ids)
        self._unsubscribe()
        self._members = list(member_entity_ids)
        if temp_sensor_ids is not None:
            self._sensors = list(temp_sensor_ids)
        self._subscribe()
        self._refresh()

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def member_entity_ids(self) -> list[str]:
        return list(self._members)

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def setpoint(self) -> float:
        return self._setpoint

    @property
    def current_temperature(self) -> float | None:
        temps: list[float] = []
        for eid in self._sensors:
            state = self.hass.states.get(eid)
            if state and state.state not in ("unavailable", "unknown"):
                try:
                    temps.append(float(state.state))
                except ValueError:
                    pass
        for eid in self._members:
            state = self.hass.states.get(eid)
            if state and state.state not in ("unavailable", "unknown"):
                cur = state.attributes.get("current_temperature")
                if cur is not None:
                    try:
                        temps.append(float(cur))
                    except (ValueError, TypeError):
                        pass
        return round(sum(temps) / len(temps), 1) if temps else None

    @property
    def member_temperatures(self) -> dict[str, float | None]:
        """Return {entity_id: temperature} for all members."""
        result: dict[str, float | None] = {}
        for eid in self._members:
            state = self.hass.states.get(eid)
            if state:
                cur = state.attributes.get("current_temperature")
                try:
                    result[eid] = float(cur) if cur is not None else None
                except (ValueError, TypeError):
                    result[eid] = None
            else:
                result[eid] = None
        return result

    @property
    def member_detail(self) -> list[dict]:
        """Return list of {name, entity_id, temperature} for card display."""
        result = []
        for eid in self._members:
            state = self.hass.states.get(eid)
            name = (state.attributes.get("friendly_name") or eid.split(".")[-1]) if state else eid
            temp = None
            if state:
                cur = state.attributes.get("current_temperature")
                try:
                    temp = float(cur) if cur is not None else None
                except (ValueError, TypeError):
                    pass
            result.append({"entity_id": eid, "name": name, "temperature": temp})
        return result

    @property
    def outdoor_temperature(self) -> float | None:
        """Current outdoor temperature from Open-Meteo weather entity."""
        if not self._frost_weather_entity:
            return None
        state = self.hass.states.get(self._frost_weather_entity)
        if state and state.attributes:
            t = state.attributes.get("temperature")
            try:
                return float(t) if t is not None else None
            except (ValueError, TypeError):
                return None
        return None

    @property
    def frost_protection_active(self) -> bool:
        """True if outdoor temp is at or below the frost threshold."""
        outdoor = self.outdoor_temperature
        return outdoor is not None and outdoor <= self._frost_temperature

    @property
    def heat_required(self) -> bool:
        for eid in self._members:
            state = self.hass.states.get(eid)
            if state and state.attributes.get("hvac_action") == HVACAction.HEATING:
                return True
        return False

    @property
    def available(self) -> bool:
        return any(
            self.hass.states.get(eid) is not None
            for eid in self._members
        )

    @property
    def schedule_slots(self) -> list[dict]:
        """Return the current schedule slots for the card to display."""
        return list(self._schedule_mgr._schedule)

    @property
    def schedule_current_slot(self) -> int:
        """Index of the currently active schedule slot."""
        slot = self._schedule_mgr._current_slot()
        if slot is None:
            return 0
        try:
            return self._schedule_mgr._schedule.index(slot)
        except ValueError:
            return 0

    @property
    def boost_end_time(self) -> datetime | None:
        return self._boost_end

    @property
    def boost_remaining_minutes(self) -> int | None:
        if self._boost_end is None:
            return None
        rem = (self._boost_end - dt_util.utcnow()).total_seconds()
        return max(0, int(rem / 60))

    # ── Commands ───────────────────────────────────────────────────────────────

    async def async_set_mode(self, mode: str, setpoint: float | None = None) -> None:
        _LOGGER.debug("Room %s: set_mode → %s (sp=%s)", self.room_name, mode, setpoint)
        if mode == MODE_BOOST:
            await self.async_start_boost()
            return
        self._cancel_boost()
        self._mode = mode
        if mode == MODE_OFF:
            await self._svc_set_hvac("off")
        elif mode == MODE_MANUAL:
            sp = setpoint if setpoint is not None else self._setpoint
            self._setpoint = sp
            await self._svc_set_hvac("heat")
            await self._svc_set_temperature(sp)
        elif mode == MODE_SCHEDULE:
            await self._svc_set_hvac("heat")
        self._refresh()

    async def async_set_temperature(self, temp: float) -> None:
        self._setpoint = temp
        if self._mode == MODE_OFF:
            self._mode = MODE_MANUAL
        await self._svc_set_hvac("heat")
        await self._svc_set_temperature(temp)
        self._refresh()

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

        _LOGGER.info("Room %s: boost → %.1f°C for %d min", self.room_name, boost_temp, boost_mins)
        self._pre_boost_mode = self._mode if self._mode != MODE_BOOST else self._pre_boost_mode
        self._pre_boost_sp   = self._setpoint
        self._mode           = MODE_BOOST
        self._boost_end      = dt_util.utcnow() + timedelta(minutes=boost_mins)

        self._cancel_boost()
        await self._svc_set_hvac("heat")
        await self._svc_set_temperature(boost_temp)
        self._boost_task = self.hass.async_create_task(
            self._boost_timer(boost_mins * 60)
        )
        self._refresh()

    async def async_end_boost(self) -> None:
        _LOGGER.info("Room %s: ending boost → returning to %s", self.room_name, self._pre_boost_mode)
        self._cancel_boost()
        await self.async_set_mode(self._pre_boost_mode, self._pre_boost_sp)

    def _cancel_boost(self) -> None:
        if self._boost_task and not self._boost_task.done():
            self._boost_task.cancel()
        self._boost_task = None
        self._boost_end  = None

    async def _boost_timer(self, seconds: int) -> None:
        await asyncio.sleep(seconds)
        self._boost_task = None
        self._boost_end  = None
        await self.async_set_mode(self._pre_boost_mode, self._pre_boost_sp)

    async def async_set_schedule(self, schedule: list[dict]) -> None:
        _LOGGER.info("Room %s: schedule set (%d slots)", self.room_name, len(schedule))
        await self._schedule_mgr.async_set_schedule(schedule)
        self._mode = MODE_SCHEDULE
        self._refresh()

    def clear_schedule(self) -> None:
        _LOGGER.info("Room %s: schedule cleared", self.room_name)
        self._schedule_mgr.clear()
        self._mode = MODE_MANUAL
        self._refresh()

    # ── HA service helpers ─────────────────────────────────────────────────────

    async def _svc_set_temperature(self, temp: float) -> None:
        if not self._members:
            return
        _LOGGER.debug("Room %s: set_temperature → %.1f°C on %s", self.room_name, temp, self._members)
        await self.hass.services.async_call(
            "climate", "set_temperature",
            {ATTR_ENTITY_ID: self._members, ATTR_TEMPERATURE: round(temp, 1)},
            blocking=False,
        )

    async def _svc_set_hvac(self, hvac_mode: str) -> None:
        if not self._members:
            return
        await self.hass.services.async_call(
            "climate", "set_hvac_mode",
            {ATTR_ENTITY_ID: self._members, "hvac_mode": hvac_mode},
            blocking=False,
        )

    # ── Internal ───────────────────────────────────────────────────────────────

    @callback
    def _on_state_change(self, _event: Any) -> None:
        self._refresh()

    def _refresh(self) -> None:
        self.async_set_updated_data({
            "mode":                    self._mode,
            "setpoint":                self._setpoint,
            "current_temperature":     self.current_temperature,
            "member_temperatures":     self.member_temperatures,
            "member_detail":           self.member_detail,
            "heat_required":           self.heat_required,
            "available":               self.available,
            "boost_end":               self._boost_end.isoformat() if self._boost_end else None,
            "outdoor_temperature":     self.outdoor_temperature,
            "frost_protection_active": self.frost_protection_active,
        })

        # Auto-trigger frost protection if outdoor temp drops below threshold
        if self.frost_protection_active and self._mode != MODE_OFF:
            _LOGGER.info(
                "Room %s: frost protection triggered (outdoor=%.1f°C ≤ %.1f°C)",
                self.room_name,
                self.outdoor_temperature,
                self._frost_temperature,
            )
            self.hass.async_create_task(self._svc_set_hvac("heat"))
            self.hass.async_create_task(
                self._svc_set_temperature(max(self._frost_temperature + 3.0, 7.0))
            )


