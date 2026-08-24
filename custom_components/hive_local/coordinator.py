"""Central coordinator for Hive Local v5.

Single instance per config entry. Manages:
- All registered devices (TRVs and receivers) and their MQTT connections
- All rooms and their member relationships
- Boiler demand — drives the receiver when any room calls for heat
- Entity registry — hides/restores TRV climate entities based on room membership
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate.const import HVACAction
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntryHider
from homeassistant.helpers.event import async_call_later, async_track_state_change_event

from .const import (
    BOILER_MIN_OFF_DELAY, CONF_BOILER_ENTITY, DEVICE_TYPE_RECEIVER, DEVICE_TYPE_TRV,
    DOMAIN, EVENT_ROOM_ADDED, EVENT_ROOM_REMOVED, EVENT_ROOM_UPDATED,
    TRV_DEMAND_THRESHOLD, uid_device,
)
from .mqtt import HiveDeviceMqtt
from .room import HiveRoom
from .store import HiveLocalStore

_LOGGER = logging.getLogger(__name__)


class HiveLocalCoordinator:
    """Single coordinator managing all devices and rooms."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        store: HiveLocalStore,
        boiler_entity: str | None,
    ) -> None:
        self.hass          = hass
        self.entry_id      = entry_id
        self.store         = store
        self.boiler_entity = boiler_entity

        self._devices: dict[str, HiveDeviceMqtt] = {}   # device_id → mqtt handler
        self._rooms:   dict[str, HiveRoom]        = {}   # room_id   → room

        self._boiler_demand:  bool = False
        self._receiver_demand_state: dict[str, bool] = {}  # receiver_id → last demand
        self._unsub_boiler:   list = []
        self._boiler_off_timer = None   # pending hold-off before switching boiler off
        self._listeners:      list = []

        # Global frost protection (Open-Meteo — fires boiler independently of rooms)
        self._frost_enabled:  bool       = False
        self._frost_threshold:float      = 2.0
        self._frost_weather:  str | None = None
        self._frost_active:   bool       = False

    # ── Accessors ──────────────────────────────────────────────────────────────

    def get_device_mqtt(self, device_id: str) -> HiveDeviceMqtt | None:
        return self._devices.get(device_id)

    def get_room(self, room_id: str) -> HiveRoom | None:
        return self._rooms.get(room_id)

    def all_devices(self) -> dict[str, HiveDeviceMqtt]:
        return dict(self._devices)

    def all_rooms(self) -> dict[str, HiveRoom]:
        return dict(self._rooms)

    def room_for_device(self, device_id: str) -> HiveRoom | None:
        room_id = self.store.room_for_device(device_id)
        return self._rooms.get(room_id) if room_id else None

    def device_is_in_room(self, device_id: str) -> bool:
        return self.store.room_for_device(device_id) is not None

    def add_listener(self, listener) -> None:
        self._listeners.append(listener)

    def _notify(self) -> None:
        for listener in self._listeners:
            try:
                listener()
            except Exception as exc:
                _LOGGER.error("Coordinator listener error: %s", exc)

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def async_setup(self) -> None:
        """Load all devices and rooms from storage and set up MQTT."""
        _LOGGER.info("Hive Local coordinator starting up")

        # Set up devices
        for device_id, device_data in self.store.get_all_devices().items():
            await self._setup_device(device_id, device_data)

        # Set up rooms
        for room_id, room_data in self.store.get_all_rooms().items():
            await self._setup_room(room_id, room_data)

        _LOGGER.info(
            "Coordinator ready: %d device(s), %d room(s)",
            len(self._devices), len(self._rooms)
        )

    async def async_unload(self) -> None:
        if self._boiler_off_timer:
            self._boiler_off_timer()
            self._boiler_off_timer = None
        for unsub in self._unsub_boiler:
            unsub()
        for mqtt in self._devices.values():
            await mqtt.async_unload()
        for room in self._rooms.values():
            await room.async_unload()

    # ── Device management ──────────────────────────────────────────────────────

    async def async_add_device(self, device_id: str, device_data: dict) -> None:
        """Add a new device at runtime (from config flow)."""
        await self.store.async_save_device(device_id, device_data)
        await self._setup_device(device_id, device_data)
        self.hass.bus.async_fire(f"{DOMAIN}_device_added", {
            "entry_id":  self.entry_id,
            "device_id": device_id,
            "data":      device_data,
        })
        self._notify()

    async def async_remove_device(self, device_id: str) -> None:
        """Remove a device — also removes it from any room."""
        mqtt = self._devices.pop(device_id, None)
        if mqtt:
            await mqtt.async_unload()
        await self.store.async_remove_device(device_id)
        self.hass.bus.async_fire(f"{DOMAIN}_device_removed", {
            "entry_id":  self.entry_id,
            "device_id": device_id,
        })
        self._notify()

    async def _setup_device(self, device_id: str, device_data: dict) -> None:
        dtype = device_data.get("type")
        if dtype not in (DEVICE_TYPE_TRV, DEVICE_TYPE_RECEIVER):
            return  # standalone sensor — no MQTT needed

        mqtt = HiveDeviceMqtt(
            hass        = self.hass,
            device_id   = device_id,
            device_type = dtype,
            model       = device_data.get("model", "TRV"),
            topic       = device_data.get("mqtt_topic", ""),
            name        = device_data.get("name", device_id),
        )
        self._devices[device_id] = mqtt

        # Wire to boiler demand
        mqtt.add_listener(self._on_device_state_change)

        await mqtt.async_setup()

    # ── Room management ────────────────────────────────────────────────────────

    async def async_add_room(self, room_id: str, room_data: dict) -> None:
        await self.store.async_save_room(room_id, room_data)
        room = await self._setup_room(room_id, room_data)

        # Hide individual TRV climate entities
        self._set_trv_entities_hidden(room_data.get("device_ids", []), hide=True)

        self.hass.bus.async_fire(EVENT_ROOM_ADDED, {
            "entry_id": self.entry_id,
            "room_id":  room_id,
            "room":     room,
        })
        self._notify()

    async def async_update_room(
        self,
        room_id: str,
        new_device_ids: list[str],
        new_sensor_ids: list[str],
    ) -> None:
        room = self._rooms.get(room_id)
        if not room:
            return
        old_device_ids = list(room.device_ids)
        room.update_members(new_device_ids, new_sensor_ids)

        # Update storage
        room_data = self.store.get_room(room_id) or {}
        room_data["device_ids"] = new_device_ids
        room_data["sensor_ids"] = new_sensor_ids
        await self.store.async_save_room(room_id, room_data)

        # Adjust entity visibility
        removed = [d for d in old_device_ids if d not in new_device_ids]
        added   = [d for d in new_device_ids if d not in old_device_ids]
        self._set_trv_entities_hidden(removed, hide=False)
        self._set_trv_entities_hidden(added,   hide=True)

        self.hass.bus.async_fire(EVENT_ROOM_UPDATED, {
            "entry_id":  self.entry_id,
            "room_id":   room_id,
            "added":     added,
            "removed":   removed,
        })
        self._notify()

    async def async_remove_room(self, room_id: str) -> None:
        room = self._rooms.pop(room_id, None)
        if room:
            # Restore all TRV entities
            self._set_trv_entities_hidden(room.device_ids, hide=False)
            await room.async_unload()
        await self.store.async_remove_room(room_id)
        self.hass.bus.async_fire(EVENT_ROOM_REMOVED, {
            "entry_id": self.entry_id,
            "room_id":  room_id,
        })
        self._notify()

    async def _setup_room(self, room_id: str, room_data: dict) -> HiveRoom:
        room = HiveRoom(
            hass           = self.hass,
            coordinator    = self,
            room_id        = room_id,
            room_name      = room_data.get("name", room_id),
            device_ids     = room_data.get("device_ids", []),
            sensor_ids     = room_data.get("sensor_ids", []),
            schedule       = room_data.get("schedule", []),
            boost_temp     = float(room_data.get("boost_temp", 22.0)),
            boost_minutes  = int(room_data.get("boost_minutes", 30)),
            frost_temp     = float(room_data.get("frost_temp", 7.0)),
            weather_entity = room_data.get("weather_entity"),
            frost_enabled  = bool(room_data.get("frost_enabled", False)),
        )
        room.receiver_device_id = room_data.get("receiver_device_id")
        room.on_demand_enabled  = room_data.get("on_demand_enabled", True)
        room.add_listener(self._on_room_state_change)
        await room.async_setup()
        self._rooms[room_id] = room
        return room

    # ── Boiler demand ──────────────────────────────────────────────────────────

    @callback
    def _on_device_state_change(self) -> None:
        self.hass.async_create_task(
            self._evaluate_boiler(), name="hive_local_boiler_eval"
        )
        self._notify()

    @callback
    def _on_room_state_change(self) -> None:
        self.hass.async_create_task(
            self._evaluate_boiler(), name="hive_local_boiler_eval"
        )
        self._notify()

    def _trv_calling(self, mqtt) -> bool:
        """True if this TRV is currently demanding heat.

        Unavailable TRVs never vote — a valve that has dropped off the mesh
        neither holds the boiler on nor silently counts as satisfied.
        """
        if not mqtt.available:
            return False
        if mqtt.running_state == "heat" or mqtt.heat_required is True:
            return True
        return (
            mqtt.pi_heating_demand is not None
            and mqtt.pi_heating_demand > TRV_DEMAND_THRESHOLD
        )

    def _any_trv_calling(self) -> tuple[bool, list[str]]:
        """Check every on-demand-enabled TRV for heat demand.

        Returns (demand, names_calling).
        TRVs in rooms inherit the room's on_demand_enabled flag.
        Standalone TRVs use their own on_demand_enabled flag.
        Unavailable TRVs are excluded.
        """
        calling: list[str] = []
        unavailable: list[str] = []
        for device_id, device_data in self.store.get_all_devices().items():
            if device_data.get("type") != DEVICE_TYPE_TRV:
                continue
            # Check on_demand_enabled
            room_id = self.store.room_for_device(device_id)
            if room_id:
                room = self._rooms.get(room_id)
                if not room or not room.on_demand_enabled:
                    continue
            else:
                if not device_data.get("on_demand_enabled", True):
                    continue
            mqtt = self._devices.get(device_id)
            name = device_data.get("name", device_id)
            if not mqtt or not mqtt.available:
                unavailable.append(name)
                continue
            if self._trv_calling(mqtt):
                calling.append(name)
        if unavailable:
            _LOGGER.debug("TRVs excluded from demand (unavailable): %s", unavailable)
        return bool(calling), calling

    async def _evaluate_boiler(self) -> None:
        """Evaluate heat demand and signal receivers.

        Two demand paths:
        1. Per-receiver demand — each room signals its assigned receiver directly
           via MQTT. A receiver fires when any of its assigned rooms needs heat.
        2. Global fallback boiler_entity — for non-Hive receivers (HA switch/climate).
           Fires when ANY room needs heat (legacy path, still supported).
        3. Global frost protection — fires all receivers when outdoor temp too low.
        """
        frost_trigger = self.check_frost_protection()

        if frost_trigger and not self._frost_active:
            self._frost_active = True
            _LOGGER.info(
                "Global frost protection active — firing all receivers (outdoor ≤ %.1f°C)",
                self._frost_threshold,
            )
        elif not frost_trigger and self._frost_active:
            self._frost_active = False
            _LOGGER.info("Global frost protection cleared")

        # ── Per-receiver demand ────────────────────────────────────────────────
        # Build {receiver_device_id: bool} — True if any assigned room OR TRV needs heat
        receiver_demand: dict[str, bool] = {}

        # From rooms
        for room in self._rooms.values():
            if not room.receiver_device_id:
                continue
            rid = room.receiver_device_id
            needed = room.heat_required or frost_trigger
            receiver_demand[rid] = receiver_demand.get(rid, False) or needed

        # Per-TRV demand — only for on-demand enabled devices/rooms
        # (ZBMINIR2 path — separate from the global boiler_entity)
        for device_id, device_data in self.store.get_all_devices().items():
            if device_data.get("type") != DEVICE_TYPE_TRV:
                continue
            room_id = self.store.room_for_device(device_id)
            if room_id:
                room = self._rooms.get(room_id)
                if not room or not room.on_demand_enabled:
                    continue
            else:
                if not device_data.get("on_demand_enabled", True):
                    continue
            rid = device_data.get("receiver_device_id")
            if not rid and room_id:
                room = self._rooms.get(room_id)
                if room:
                    rid = room.receiver_device_id
            if not rid:
                continue
            mqtt = self._devices.get(device_id)
            if not mqtt:
                continue
            trv_heating = (
                mqtt.running_state == "heat"
                or mqtt.heat_required is True
                or mqtt.pi_heating_demand is not None and mqtt.pi_heating_demand > 0
            )
            needed = trv_heating or frost_trigger
            receiver_demand[rid] = receiver_demand.get(rid, False) or needed
            if needed:
                _LOGGER.debug(
                    "TRV %s demanding heat → receiver %s",
                    device_data.get("name", device_id), rid,
                )

        # Signal each receiver
        for receiver_id, needed in receiver_demand.items():
            mqtt = self._devices.get(receiver_id)
            if not mqtt:
                continue
            prev = self._receiver_demand_state.get(receiver_id)
            if prev == needed:
                continue
            self._receiver_demand_state[receiver_id] = needed
            try:
                if needed:
                    temp = mqtt.target_temperature or 20.0
                    await mqtt.async_set_mode_heat(temp)
                else:
                    await mqtt.async_set_mode_schedule()
                _LOGGER.info(
                    "Receiver %s → %s (demand from rooms)",
                    mqtt.name, "HEAT" if needed else "SCHEDULE",
                )
            except Exception as exc:
                _LOGGER.warning("Receiver demand failed for %s: %s", receiver_id, exc)

        # ── Global boiler_entity ───────────────────────────────────────────────
        # Fires when ANY TRV calls, ANY room calls, or frost protection is active.
        # TRVs are checked directly so a valve fires the boiler whether or not it
        # belongs to a room and whether or not a receiver is assigned.
        if not self.boiler_entity:
            return

        trv_demand, calling = self._any_trv_calling()
        room_demand = any(room.heat_required for room in self._rooms.values())
        needed = trv_demand or room_demand or frost_trigger

        if needed:
            # Cancel any pending off timer and fire immediately
            if self._boiler_off_timer:
                self._boiler_off_timer()
                self._boiler_off_timer = None
            if calling:
                _LOGGER.debug("TRVs calling for heat: %s", calling)
            await self._set_boiler(True)
            return

        # Demand clear — hold off before dropping so independent PI controllers
        # crossing zero at slightly different moments don't chatter the relay.
        if not self._boiler_demand or self._boiler_off_timer:
            return

        async def _drop(_now) -> None:
            self._boiler_off_timer = None
            again, _ = self._any_trv_calling()
            if again or any(r.heat_required for r in self._rooms.values())                     or self.check_frost_protection():
                return
            await self._set_boiler(False)

        _LOGGER.debug(
            "Demand clear — boiler off in %ss unless demand returns",
            BOILER_MIN_OFF_DELAY,
        )
        self._boiler_off_timer = async_call_later(
            self.hass, BOILER_MIN_OFF_DELAY, _drop
        )

    async def _set_boiler(self, on: bool) -> None:
        """Drive the heat-demand switch — ZBMINIR2, relay, climate, input_boolean.

        Uses turn_on / turn_off which works for switch, input_boolean, and climate
        domains alike. The domain is taken from the entity_id prefix so no extra
        config is needed when swapping between device types.
        """
        if not self.boiler_entity or on == self._boiler_demand:
            return
        self._boiler_demand = on
        domain  = self.boiler_entity.split(".")[0]
        service = "turn_on" if on else "turn_off"
        action  = "ON  → firing boiler" if on else "OFF → boiler demand cleared"
        try:
            await self.hass.services.async_call(
                domain, service,
                {ATTR_ENTITY_ID: self.boiler_entity},
                blocking=False,
            )
            _LOGGER.info("Heat demand switch %s (%s)", action, self.boiler_entity)
        except Exception as exc:
            _LOGGER.warning(
                "Heat demand switch call failed for %s: %s", self.boiler_entity, exc
            )

    def update_boiler_entity(self, entity_id: str | None) -> None:
        self.boiler_entity = entity_id

    def assign_room_receiver(self, room_id: str, receiver_device_id: str | None) -> None:
        """Assign a receiver device to a room for on-demand heat control."""
        room = self._rooms.get(room_id)
        if room:
            room.receiver_device_id = receiver_device_id
            _LOGGER.info(
                "Room %s → receiver %s", room_id, receiver_device_id or "none"
            )

    async def async_assign_device_receiver(
        self, device_id: str, receiver_device_id: str | None
    ) -> None:
        """Assign a receiver to a standalone TRV for on-demand heat control."""
        await self.store.async_set_device_receiver(device_id, receiver_device_id)
        _LOGGER.info(
            "TRV %s → receiver %s", device_id, receiver_device_id or "none"
        )

    def update_frost_protection(
        self,
        enabled: bool,
        threshold: float,
        weather_entity: str | None,
    ) -> None:
        """Update global frost protection settings (from Open-Meteo)."""
        self._frost_enabled   = enabled
        self._frost_threshold = threshold
        self._frost_weather   = weather_entity
        _LOGGER.info(
            "Global frost protection: enabled=%s threshold=%.1f°C entity=%s",
            enabled, threshold, weather_entity,
        )

    def check_frost_protection(self) -> bool:
        """Return True if outdoor temp is at or below frost threshold."""
        if not self._frost_enabled or not self._frost_weather:
            return False
        state = self.hass.states.get(self._frost_weather)
        if not state:
            return False
        try:
            outdoor = float(state.attributes.get("temperature", 99))
            return outdoor <= self._frost_threshold
        except (TypeError, ValueError):
            return False

    # ── Entity registry — hide/restore TRV climate entities ───────────────────

    def _set_trv_entities_hidden(self, device_ids: list[str], hide: bool) -> None:
        ent_reg = er.async_get(self.hass)
        for device_id in device_ids:
            uid = uid_device(device_id, "climate")
            for entry in ent_reg.entities.values():
                if entry.unique_id == uid and entry.entity_id.startswith("climate."):
                    if hide:
                        ent_reg.async_update_entity(
                            entry.entity_id,
                            hidden_by=RegistryEntryHider.INTEGRATION,
                        )
                    else:
                        if entry.hidden_by == RegistryEntryHider.INTEGRATION:
                            ent_reg.async_update_entity(
                                entry.entity_id, hidden_by=None
                            )
                    _LOGGER.info(
                        "TRV entity %s %s",
                        entry.entity_id,
                        "hidden (in room)" if hide else "restored",
                    )
                    break

    # ── Restore entity suppression on startup ──────────────────────────────────

    def restore_entity_suppression(self) -> None:
        """Re-apply entity hiding for all room members after HA restart."""
        for room_id, room in self._rooms.items():
            self._set_trv_entities_hidden(room.device_ids, hide=True)
