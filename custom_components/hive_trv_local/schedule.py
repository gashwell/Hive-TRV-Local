"""Weekly schedule manager for room groups."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, time

import homeassistant.util.dt as dt_util
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class ScheduleManager:
    """Applies a weekly heating schedule by tracking the current slot."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        apply_temp: Callable[[float], None],
    ) -> None:
        self._hass        = hass
        self._name        = name
        self._apply       = apply_temp
        self._schedule:   list[dict] = []
        self._task:       asyncio.Task | None = None

    async def async_set_schedule(self, schedule: list[dict]) -> None:
        self.clear()
        self._schedule = list(schedule)
        if self._schedule:
            self._task = self._hass.async_create_task(self._run())

    def clear(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._task    = None
        self._schedule = []

    async def advance_to_next(self) -> None:
        """Skip to the next scheduled slot immediately."""
        slot = self._next_slot()
        if slot:
            self._apply(slot["temperature"])

    def _current_slot(self) -> dict | None:
        if not self._schedule:
            return None
        now     = dt_util.now()
        dow     = now.weekday()
        now_t   = now.time().replace(second=0, microsecond=0)
        current = None
        for slot in self._schedule:
            if dow not in slot.get("days", []):
                continue
            slot_t = time(*[int(x) for x in slot["time"].split(":")])
            if slot_t <= now_t:
                if current is None or slot_t > time(
                    *[int(x) for x in current["time"].split(":")]
                ):
                    current = slot
        return current

    def _next_slot(self) -> dict | None:
        if not self._schedule:
            return None
        now   = dt_util.now()
        dow   = now.weekday()
        now_t = now.time().replace(second=0, microsecond=0)
        best  = None
        best_delta = None
        for slot in self._schedule:
            for d in slot.get("days", []):
                day_offset = (d - dow) % 7
                slot_t = time(*[int(x) for x in slot["time"].split(":")])
                if day_offset == 0 and slot_t <= now_t:
                    day_offset = 7
                from datetime import timedelta
                delta = timedelta(days=day_offset) - timedelta(
                    hours=now_t.hour, minutes=now_t.minute
                ) + timedelta(hours=slot_t.hour, minutes=slot_t.minute)
                if best_delta is None or delta < best_delta:
                    best_delta = delta
                    best = slot
        return best

    async def _run(self) -> None:
        while self._schedule:
            slot = self._current_slot()
            if slot:
                try:
                    self._apply(slot["temperature"])
                except Exception as exc:
                    _LOGGER.warning("Schedule apply failed for %s: %s", self._name, exc)
            # Wake at the next slot boundary
            next_slot = self._next_slot()
            if next_slot:
                now  = dt_util.now()
                dow  = now.weekday()
                slot_t = time(*[int(x) for x in next_slot["time"].split(":")])
                from datetime import timedelta
                days = next_slot["days"]
                day_offset = min((d - dow) % 7 for d in days)
                if day_offset == 0 and slot_t <= now.time():
                    day_offset = 7
                target = now.replace(
                    hour=slot_t.hour, minute=slot_t.minute,
                    second=0, microsecond=0
                ) + timedelta(days=day_offset)
                wait = (target - now).total_seconds()
                await asyncio.sleep(max(wait, 30))
            else:
                await asyncio.sleep(3600)
