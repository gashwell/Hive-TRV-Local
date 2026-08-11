"""Room coordinator for Hive Local v5.

A room groups one or more TRVs (and optional standalone temperature sensors)
into a single virtual heating zone. The room:

- Reports average current temperature across all sources
- Fans out set_temperature and mode commands to all member TRVs
- Manages its own weekly schedule (time/temp slots)
- Manages boost (timed, returns to previous mode)
- Triggers boiler demand when any member is heating
- Hides individual TRV climate entities while they are members
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.components.climate.const import HVACAction, HVACMode
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util.dt import now as ha_now

from .const import (
    DEFAULT_BOOST_MINUTES, DEFAULT_BOOST_TEMP, DEFAULT_FROST_TEMP,
    DEFAULT_TARGET_TEMP, MODE_BOOST, MODE_MANUAL, MODE_OFF, MODE_SCHEDULE,
)

if TYPE_CHECKING:
    from .coordinator import HiveLocalCoordinator

_LOGGER = logging.getLogger(__name__)


class HiveRoom:
    """Manages a heating zone — one or more TRVs + optional sensors."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: "HiveLocalCoordinator",
        room_id: str,
        room_name: str,
        device_ids: list[str],       # TRV device IDs
        sensor_ids: list[str],       # standalone sensor device IDs
        schedule: list[dict],        # [{days, time, temperature}]
        boost_temp: float            = DEFAULT_BOOST_TEMP,
        boost_minutes: int           = DEFAULT_BOOST_MINUTES,
        frost_temp: float            = DEFAULT_FROST_TEMP,
        weather_entity: str | None   = None,
        frost_enabled: bool          = False,
    ) -> None:
        self.hass        = hass
        self.coordinator = coordinator
        self.room_id     = room_id
        self.room_name   = room_name
        self.device_ids  = list(device_ids)
        self.sensor_ids  = list(sensor_ids)

        # Schedule
        self._schedule: list[dict] = list(schedule)
        self._mode: str            = MODE_SCHEDULE if schedule else MODE_MANUAL
        self._setpoint: float      = DEFAULT_TARGET_TEMP

        # Boost
        self._boost_temp:    float          = boost_temp
        self._boost_minutes: int            = boost_minutes
        self._boost_end:     datetime | None = None
        self._pre_boost_mode: str           = MODE_MANUAL
        self._pre_boost_temp: float         = DEFAULT_TARGET_TEMP
        self._boost_task: asyncio.Task | None = None

        # Frost protection
        self._frost_temp:     float     = frost_temp
        self._weather_entity: str | None = weather_entity
        self._frost_enabled:  bool      = frost_enabled

        # Receiver — device_id of the registered receiver this room controls
        self.receiver_device_id: str | None = None

        # Listeners (notify HA entities of state change)
        self._listeners: list = []

        # Schedule tick
        self._unsub_schedule = None

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def setpoint(self) -> float:
        return self._setpoint

    @property
    def current_temperature(self) -> float | None:
        """Average temperature across all TRV members and standalone sensors."""
        temps: list[float] = []

        # From TRV device coordinators
        for device_id in self.device_ids:
            mqtt = self.coordinator.get_device_mqtt(device_id)
            if mqtt and mqtt.current_temperature is not None:
                temps.append(mqtt.current_temperature)

        # From standalone HA temperature sensor entities
        for device_id in self.sensor_ids:
            device_data = self.coordinator.store.get_device(device_id)
            if device_data:
                eid = device_data.get("entity_id")
                if eid:
                    state = self.hass.states.get(eid)
                    if state and state.state not in ("unavailable", "unknown"):
                        try:
                            temps.append(float(state.state))
                        except (ValueError, TypeError):
                            pass

        return round(sum(temps) / len(temps), 1) if temps else None

    @property
    def member_detail(self) -> list[dict]:
        """Per-member temperature detail for card display."""
        result = []
        for device_id in self.device_ids:
            mqtt = self.coordinator.get_device_mqtt(device_id)
            device_data = self.coordinator.store.get_device(device_id)
            name = (device_data or {}).get("name", device_id)
            result.append({
                "device_id":   device_id,
                "name":        name,
                "temperature": mqtt.current_temperature if mqtt else None,
                "demand":      mqtt.pi_heating_demand if mqtt else None,
                "battery":     mqtt.battery if mqtt else None,
                "heating":     mqtt.running_state == "heat" if mqtt else False,
            })
        return result

    @property
    def heat_required(self) -> bool:
        """True if any member TRV is actively calling for heat, or if room is boosting."""
        if self._mode == MODE_OFF:
            return False
        if self._mode == MODE_BOOST:
            return True
        for device_id in self.device_ids:
            mqtt = self.coordinator.get_device_mqtt(device_id)
            if mqtt and mqtt.running_state == "heat":
                return True
        return False

    @property
    def hvac_action(self) -> HVACAction:
        if self._mode == MODE_OFF:
            return HVACAction.OFF
        return HVACAction.HEATING if self.heat_required else HVACAction.IDLE

    @property
    def boost_remaining_minutes(self) -> int:
        if self._boost_end is None:
            return 0
        remaining = (self._boost_end - ha_now()).total_seconds() / 60
        return max(0, int(remaining))

    @property
    def boost_end_iso(self) -> str | None:
        return self._boost_end.isoformat() if self._boost_end else None

    @property
    def schedule(self) -> list[dict]:
        return list(self._schedule)

    @property
    def current_schedule_slot(self) -> dict | None:
        """Return the currently active schedule slot."""
        if not self._schedule:
            return None
        now  = ha_now()
        wday = now.weekday()  # 0=Mon
        time_now = now.hour * 60 + now.minute
        best: dict | None = None
        best_time = -1
        for slot in self._schedule:
            if wday not in slot.get("days", []):
                continue
            h, m   = map(int, slot["time"].split(":"))
            slot_t = h * 60 + m
            if slot_t <= time_now and slot_t > best_time:
                best      = slot
                best_time = slot_t
        return best

    @property
    def available(self) -> bool:
        """True if at least one member has reported state."""
        for device_id in self.device_ids:
            mqtt = self.coordinator.get_device_mqtt(device_id)
            if mqtt and mqtt.available:
                return True
        return False

    @property
    def outdoor_temperature(self) -> float | None:
        if not self._weather_entity:
            return None
        state = self.hass.states.get(self._weather_entity)
        if state:
            try:
                return float(state.attributes.get("temperature"))
            except (TypeError, ValueError):
                return None
        return None

    @property
    def frost_active(self) -> bool:
        outdoor = self.outdoor_temperature
        return (
            self._frost_enabled
            and outdoor is not None
            and outdoor <= self._frost_temp
        )

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def async_setup(self) -> None:
        """Start the schedule ticker and apply initial state."""
        self._unsub_schedule = async_track_time_interval(
            self.hass, self._schedule_tick, timedelta(minutes=1)
        )
        # Immediately apply current schedule slot if in schedule mode
        if self._mode == MODE_SCHEDULE:
            await self._apply_schedule_slot()
        _LOGGER.info("Room %s setup complete (%d TRV(s))", self.room_name, len(self.device_ids))

    async def async_unload(self) -> None:
        if self._unsub_schedule:
            self._unsub_schedule()
        if self._boost_task and not self._boost_task.done():
            self._boost_task.cancel()

    def add_listener(self, listener) -> None:
        self._listeners.append(listener)

    def _notify(self) -> None:
        for listener in self._listeners:
            try:
                listener()
            except Exception as exc:
                _LOGGER.error("Room listener error: %s", exc)

    # ── Commands ───────────────────────────────────────────────────────────────

    async def async_set_temperature(self, temperature: float) -> None:
        self._setpoint = temperature
        self._mode     = MODE_MANUAL
        await self._fan_out_temperature(temperature)
        self._notify()

    async def async_set_mode(self, mode: str) -> None:
        if mode == MODE_SCHEDULE:
            self._mode = MODE_SCHEDULE
            await self._apply_schedule_slot()
        elif mode == MODE_MANUAL:
            self._mode = MODE_MANUAL
            await self._fan_out_temperature(self._setpoint)
        elif mode == MODE_OFF:
            self._mode = MODE_OFF
            await self._fan_out_off()
        elif mode == MODE_BOOST:
            await self.async_start_boost()
            return
        self._notify()

    async def async_start_boost(
        self,
        temperature: float | None = None,
        duration: int | None = None,
    ) -> None:
        self._pre_boost_mode = self._mode
        self._pre_boost_temp = self._setpoint
        temp = temperature or self._boost_temp
        dur  = duration    or self._boost_minutes
        self._mode     = MODE_BOOST
        self._setpoint = temp
        self._boost_end = ha_now() + timedelta(minutes=dur)

        await self._fan_out_boost(temp, dur)

        if self._boost_task and not self._boost_task.done():
            self._boost_task.cancel()
        self._boost_task = self.hass.async_create_task(
            self._boost_countdown(dur), name=f"hive_local_boost_{self.room_id}"
        )
        _LOGGER.info("Room %s: boost started %.1f°C for %d min", self.room_name, temp, dur)
        self._notify()

    async def async_end_boost(self) -> None:
        if self._boost_task and not self._boost_task.done():
            self._boost_task.cancel()
        self._boost_end = None
        self._mode      = self._pre_boost_mode
        self._setpoint  = self._pre_boost_temp
        await self.async_set_mode(self._mode)
        _LOGGER.info("Room %s: boost ended → %s", self.room_name, self._mode)

    async def _boost_countdown(self, minutes: int) -> None:
        await asyncio.sleep(minutes * 60)
        await self.async_end_boost()

    async def async_set_schedule(self, schedule: list[dict]) -> None:
        self._schedule = list(schedule)
        self._mode     = MODE_SCHEDULE if schedule else MODE_MANUAL
        if self._mode == MODE_SCHEDULE:
            await self._apply_schedule_slot()
        self._notify()

    def clear_schedule(self) -> None:
        self._schedule = []
        self._mode     = MODE_MANUAL
        self._notify()

    # ── Schedule engine ────────────────────────────────────────────────────────

    @callback
    def _schedule_tick(self, _now: datetime) -> None:
        if self._mode != MODE_SCHEDULE:
            return
        self.hass.async_create_task(
            self._apply_schedule_slot(), name=f"hive_local_sched_{self.room_id}"
        )
        # Check frost protection
        if self.frost_active and self._mode != MODE_OFF:
            _LOGGER.info(
                "Room %s: frost protection active (outdoor=%.1f°C)",
                self.room_name, self.outdoor_temperature
            )
            self.hass.async_create_task(
                self._fan_out_temperature(max(self._frost_temp + 2.0, 7.0))
            )

    async def _apply_schedule_slot(self) -> None:
        slot = self.current_schedule_slot
        if slot and slot.get("temperature"):
            temp = float(slot["temperature"])
            if temp != self._setpoint:
                self._setpoint = temp
                await self._fan_out_temperature(temp)
                self._notify()

    # ── Fan-out to member TRVs ─────────────────────────────────────────────────

    async def _fan_out_temperature(self, temperature: float) -> None:
        for device_id in self.device_ids:
            mqtt = self.coordinator.get_device_mqtt(device_id)
            if mqtt:
                try:
                    await mqtt.async_set_mode_heat(temperature)
                except Exception as exc:
                    _LOGGER.warning("Fan-out temp failed for %s: %s", device_id, exc)

    async def _fan_out_off(self) -> None:
        for device_id in self.device_ids:
            mqtt = self.coordinator.get_device_mqtt(device_id)
            if mqtt:
                try:
                    await mqtt.async_set_mode_off()
                except Exception as exc:
                    _LOGGER.warning("Fan-out off failed for %s: %s", device_id, exc)

    async def _fan_out_boost(self, temperature: float, duration: int) -> None:
        for device_id in self.device_ids:
            mqtt = self.coordinator.get_device_mqtt(device_id)
            if mqtt:
                try:
                    await mqtt.async_boost(duration, temperature)
                except Exception as exc:
                    _LOGGER.warning("Fan-out boost failed for %s: %s", device_id, exc)

    # ── Member management ──────────────────────────────────────────────────────

    def update_members(
        self,
        device_ids: list[str],
        sensor_ids: list[str],
    ) -> None:
        self.device_ids = list(device_ids)
        self.sensor_ids = list(sensor_ids)
        self._notify()

    def update_boost_defaults(self, temp: float, minutes: int) -> None:
        self._boost_temp    = temp
        self._boost_minutes = minutes

    def update_schedule(self, schedule: list[dict]) -> None:
        self._schedule = list(schedule)
        if schedule and self._mode == MODE_MANUAL:
            self._mode = MODE_SCHEDULE
