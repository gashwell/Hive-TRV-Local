"""Persistent storage for Hive Local v5.

Stores device registry and room definitions in HA's .storage directory.
Schema is versioned so future migrations are straightforward.

Schema v1:
{
  "schema_version": 1,
  "devices": {
    "<device_id>": {
      "type":        "trv" | "receiver" | "sensor",
      "name":        "Living Room TRV",
      "mqtt_topic":  "zigbee2mqtt/Living Room TRV",  # TRV/receiver only
      "entity_id":   "sensor.living_room_temp",       # sensor type only
      "model":       "SLR1",                          # receiver only
      "show_water":  false,                           # receiver SLR2 only
      "receiver_device_id": "<device_id>"             # TRV only — on-demand receiver
    }
  },
  "rooms": {
    "<room_id>": {
      "name":             "Living Room",
      "device_ids":       ["<trv_id>", "<trv_id2>"],
      "sensor_ids":       ["<sensor_device_id>"],
      "schedule":         [
        {"days": [0,1,2,3,4], "time": "06:30", "temperature": 21.0},
        ...
      ],
      "boost_temp":       22.0,
      "boost_minutes":    30,
      "frost_temp":       7.0,
      "weather_entity":   "weather.home",   # optional Open-Meteo
      "frost_enabled":    false
    }
  }
}
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)


class HiveLocalStore:
    """Manages persistent storage for devices and rooms."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}")
        self._data: dict[str, Any] = {
            "schema_version": STORAGE_VERSION,
            "devices": {},
            "rooms":   {},
        }

    async def async_load(self) -> None:
        """Load persisted data, migrate schema if needed."""
        stored = await self._store.async_load()
        if stored:
            self._data = stored
            _LOGGER.debug(
                "Loaded store: %d device(s), %d room(s)",
                len(self._data.get("devices", {})),
                len(self._data.get("rooms", {})),
            )

    async def async_save(self) -> None:
        await self._store.async_save(self._data)

    # ── Devices ───────────────────────────────────────────────────────────────

    def get_all_devices(self) -> dict[str, dict]:
        return dict(self._data.get("devices", {}))

    def get_device(self, device_id: str) -> dict | None:
        return self._data["devices"].get(device_id)

    async def async_save_device(self, device_id: str, data: dict) -> None:
        self._data.setdefault("devices", {})[device_id] = data
        await self.async_save()

    async def async_remove_device(self, device_id: str) -> None:
        self._data.setdefault("devices", {}).pop(device_id, None)
        await self.async_save()

    # ── Rooms ─────────────────────────────────────────────────────────────────

    def get_all_rooms(self) -> dict[str, dict]:
        return dict(self._data.get("rooms", {}))

    def get_room(self, room_id: str) -> dict | None:
        return self._data["rooms"].get(room_id)

    async def async_save_room(self, room_id: str, data: dict) -> None:
        self._data.setdefault("rooms", {})[room_id] = data
        await self.async_save()

    async def async_remove_room(self, room_id: str) -> None:
        self._data.setdefault("rooms", {}).pop(room_id, None)
        await self.async_save()

    async def async_set_room_schedule(self, room_id: str, schedule: list) -> None:
        if room_id in self._data.get("rooms", {}):
            self._data["rooms"][room_id]["schedule"] = schedule
            await self.async_save()

    def get_room_boost_defaults(self, room_id: str) -> tuple[float, int]:
        """Return (boost_temp, boost_minutes) for a room."""
        room = self.get_room(room_id) or {}
        return (
            float(room.get("boost_temp", 22.0)),
            int(room.get("boost_minutes", 30)),
        )

    async def async_set_room_boost_defaults(
        self, room_id: str, temp: float, minutes: int
    ) -> None:
        if room_id in self._data.get("rooms", {}):
            self._data["rooms"][room_id]["boost_temp"]    = temp
            self._data["rooms"][room_id]["boost_minutes"] = minutes
            await self.async_save()

    def devices_in_room(self, room_id: str) -> list[str]:
        room = self.get_room(room_id) or {}
        return list(room.get("device_ids", []))

    def room_for_device(self, device_id: str) -> str | None:
        """Return room_id that contains this device_id, or None."""
        for room_id, room in self._data.get("rooms", {}).items():
            if device_id in room.get("device_ids", []):
                return room_id
        return None

    async def async_set_device_receiver(
        self, device_id: str, receiver_device_id: str | None
    ) -> None:
        """Set (or clear) the receiver assigned to a TRV device."""
        devices = self._data.setdefault("devices", {})
        if device_id in devices:
            devices[device_id]["receiver_device_id"] = receiver_device_id
            await self.async_save()

    def get_device_receiver(self, device_id: str) -> str | None:
        d = self.get_device(device_id) or {}
        return d.get("receiver_device_id")
