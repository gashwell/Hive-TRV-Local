"""Persistent storage for Hive TRV Local v2.

Single versioned schema. All fields defined at v1.
Migration path is explicit via _async_migrate().
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DEFAULT_BOOST_MINUTES, DEFAULT_BOOST_TEMP, DOMAIN, SCHEMA_VERSION

_LOGGER = logging.getLogger(__name__)
_STORAGE_VERSION = 1


def _empty() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        # {room_id: {name, members:[entity_id], temp_sensors:[], schedule:[],
        #             boost_temperature, boost_duration}}
        "rooms": {},
    }


class HiveTRVStorage:
    """Versioned JSON storage for room groups and their configuration."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store = Store(
            hass, _STORAGE_VERSION,
            f"{DOMAIN}.{entry_id}",
            atomic_writes=True,
        )
        self._data: dict[str, Any] = _empty()

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def async_load(self) -> None:
        stored = await self._store.async_load()
        if stored is None:
            self._data = _empty()
        else:
            self._data = {**_empty(), **stored}
            await self._async_migrate()

    async def async_save(self) -> None:
        await self._store.async_save(self._data)

    async def _async_migrate(self) -> None:
        version = self._data.get("schema_version", 1)
        if version == SCHEMA_VERSION:
            return
        # Future: if version < 2: ...
        self._data["schema_version"] = SCHEMA_VERSION
        await self.async_save()
        _LOGGER.info("Migrated storage to schema v%s", SCHEMA_VERSION)

    # ── Rooms ──────────────────────────────────────────────────────────────────

    def get_all_rooms(self) -> dict[str, dict]:
        return dict(self._data.get("rooms", {}))

    def get_room(self, room_id: str) -> dict | None:
        return self._data.get("rooms", {}).get(room_id)

    async def async_save_room(self, room_id: str, data: dict) -> None:
        self._data.setdefault("rooms", {})[room_id] = data
        await self.async_save()

    async def async_remove_room(self, room_id: str) -> None:
        self._data.get("rooms", {}).pop(room_id, None)
        await self.async_save()

    async def async_set_room_schedule(self, room_id: str, schedule: list) -> None:
        room = self._data.get("rooms", {}).get(room_id)
        if room is not None:
            room["schedule"] = schedule
            await self.async_save()

    # ── Room boost defaults ────────────────────────────────────────────────────

    def get_room_boost_temperature(self, room_id: str) -> float:
        return float(self._data.get("rooms", {}).get(room_id, {})
                     .get("boost_temperature", DEFAULT_BOOST_TEMP))

    def get_room_boost_duration(self, room_id: str) -> int:
        return int(self._data.get("rooms", {}).get(room_id, {})
                   .get("boost_duration", DEFAULT_BOOST_MINUTES))

    async def async_set_room_boost_defaults(
        self, room_id: str, temperature: float, duration: int
    ) -> None:
        room = self._data.get("rooms", {}).get(room_id)
        if room is not None:
            room["boost_temperature"] = temperature
            room["boost_duration"]    = duration
            await self.async_save()
