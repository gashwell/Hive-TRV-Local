"""Hive TRV Local v3."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_BOOST_DURATION, ATTR_BOOST_TEMPERATURE, ATTR_SCHEDULE,
    CONF_BOILER_ENTITY, CONF_ENABLE_DIAGNOSTICS,
    CONFIG_VERSION, DATA_BOILER, DATA_STORE,
    DEFAULT_BOOST_MINUTES, DEFAULT_BOOST_TEMP,
    DOMAIN, ENTRY_DEFAULTS, EVENT_ROOM_ADDED, EVENT_ROOM_REMOVED,
    EVENT_ROOM_UPDATED, PLATFORMS,
    SERVICE_ADVANCE_SCHEDULE, SERVICE_BOOST, SERVICE_CLEAR_SCHEDULE,
    SERVICE_END_BOOST, SERVICE_SET_SCHEDULE,
)

_LOGGER = logging.getLogger(f"custom_components.{DOMAIN}")

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register Hive TRV card JS files with the HA frontend."""
    from pathlib import Path
    from homeassistant.components.frontend import add_extra_js_url
    from homeassistant.components.http import StaticPathConfig

    for card_file in ("hive-trv-card.js", "hive-trv-group-card.js"):
        card_path = Path(__file__).parent / card_file
        if card_path.exists():
            url_path = f"/{DOMAIN}/{card_file}"
            await hass.http.async_register_static_paths([
                StaticPathConfig(url_path, str(card_path), True)
            ])
            add_extra_js_url(hass, url_path)
    _LOGGER.info("Hive TRV cards registered")
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.info("Migrating config entry v%s → v%s", entry.version, CONFIG_VERSION)
    hass.config_entries.async_update_entry(
        entry, data={**ENTRY_DEFAULTS, **entry.data}, version=CONFIG_VERSION,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    from .boiler import BoilerDemandManager
    from .storage import HiveTRVStorage

    effective     = {**ENTRY_DEFAULTS, **entry.data}
    boiler_entity = (entry.options or {}).get(CONF_BOILER_ENTITY, effective.get(CONF_BOILER_ENTITY))

    _LOGGER.info("Setting up Hive TRV Local v3 (boiler=%s)", boiler_entity)

    store = HiveTRVStorage(hass, entry.entry_id)
    await store.async_load()

    rooms: dict[str, Any] = {}
    boiler_mgr = BoilerDemandManager(hass, boiler_entity, lambda: rooms)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        DATA_STORE:  store,
        DATA_BOILER: boiler_mgr,
        "rooms":     rooms,
    }

    persisted = store.get_all_rooms()
    _LOGGER.info("Loading %d persisted room group(s)", len(persisted))
    for room_id, room_data in persisted.items():
        await _create_room(hass, entry, store, boiler_mgr, rooms, room_id, room_data)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    def _on_room_added(event: Any) -> None:
        if event.data.get("entry_id") != entry.entry_id:
            return
        if "coordinator" in event.data:
            return
        room_id   = event.data.get("room_id")
        room_data = event.data.get("room_data")
        if not room_id or not room_data:
            _LOGGER.warning("EVENT_ROOM_ADDED missing room_id or room_data")
            return
        _LOGGER.info("Room added: %s (%s)", room_data.get("name"), room_id)
        hass.async_create_task(
            _create_room(hass, entry, store, boiler_mgr, rooms, room_id, room_data),
            name=f"hive_trv_create_room_{room_id}",
        )

    @callback
    def _on_room_updated(event: Any) -> None:
        if event.data.get("entry_id") != entry.entry_id:
            return
        room_id     = event.data.get("room_id")
        new_members = event.data.get("new_members", [])
        _LOGGER.info("Room updated: %s → %d member(s)", room_id, len(new_members))
        if room_id in rooms:
            rooms[room_id].update_members(new_members)
            boiler_mgr.unsubscribe_all()
            for rc in rooms.values():
                boiler_mgr.subscribe_members(rc.member_entity_ids)

    @callback
    def _on_room_removed(event: Any) -> None:
        if event.data.get("entry_id") != entry.entry_id:
            return
        room_id = event.data.get("room_id")
        _LOGGER.info("Room removed: %s", room_id)
        rc = rooms.pop(room_id, None)
        if rc:
            hass.async_create_task(rc.async_unload(), name=f"hive_trv_unload_room_{room_id}")
        boiler_mgr.unsubscribe_all()
        for r in rooms.values():
            boiler_mgr.subscribe_members(r.member_entity_ids)

    entry.async_on_unload(hass.bus.async_listen(EVENT_ROOM_ADDED,   _on_room_added))
    entry.async_on_unload(hass.bus.async_listen(EVENT_ROOM_UPDATED, _on_room_updated))
    entry.async_on_unload(hass.bus.async_listen(EVENT_ROOM_REMOVED, _on_room_removed))

    if not hass.services.has_service(DOMAIN, SERVICE_BOOST):
        _register_services(hass)

    entry.async_on_unload(entry.add_update_listener(_on_options_updated))
    _LOGGER.info("Hive TRV Local v3 setup complete (%d room(s))", len(rooms))
    return True


async def _on_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    old_boiler = (entry.data or {}).get(CONF_BOILER_ENTITY)
    new_boiler = (entry.options or {}).get(CONF_BOILER_ENTITY)
    old_diag   = (entry.data or {}).get(CONF_ENABLE_DIAGNOSTICS, False)
    new_diag   = (entry.options or {}).get(CONF_ENABLE_DIAGNOSTICS, False)
    if old_boiler != new_boiler or old_diag != new_diag:
        _LOGGER.info("Settings changed — reloading")
        await hass.config_entries.async_reload(entry.entry_id)
    else:
        _LOGGER.debug("Options updated (group change) — no reload needed")


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        ed = hass.data[DOMAIN].pop(entry.entry_id, {})
        for rc in ed.get("rooms", {}).values():
            await rc.async_unload()
        if bm := ed.get(DATA_BOILER):
            bm.unsubscribe_all()
        _LOGGER.info("Hive TRV Local v3 unloaded")
    return ok


async def _create_room(
    hass: HomeAssistant, entry: ConfigEntry, store: Any,
    boiler_mgr: Any, rooms: dict, room_id: str, room_data: dict,
) -> Any:
    from .room import HiveRoomCoordinator
    name = room_data.get("name", room_id)
    _LOGGER.info("Creating room: %s (%s) members=%s", name, room_id, room_data.get("members", []))
    rc = HiveRoomCoordinator(
        hass, room_id=room_id, room_name=name,
        member_entity_ids=room_data.get("members", []),
        temp_sensor_entity_ids=room_data.get("temp_sensors", []),
        store=store,
    )
    await rc.async_setup()
    rooms[room_id] = rc
    if room_data.get("schedule"):
        await rc.async_set_schedule(room_data["schedule"])
    boiler_mgr.subscribe_members(rc.member_entity_ids)
    rc.async_add_listener(lambda: hass.async_create_task(boiler_mgr.async_evaluate()))
    hass.bus.async_fire(EVENT_ROOM_ADDED, {
        "entry_id": entry.entry_id, "room_id": room_id, "coordinator": rc,
    })
    _LOGGER.info("Room ready: %s | %d member(s)", name, len(rc.member_entity_ids))
    return rc


def _room_for_entity_id(hass: HomeAssistant, entity_id: str) -> Any:
    ent_reg = er.async_get(hass)
    entry   = ent_reg.async_get(entity_id)
    if entry is None:
        _LOGGER.warning("Service call: entity not found: %s", entity_id)
        return None
    uid = entry.unique_id or ""
    if uid.startswith("room_") and uid.endswith("_climate"):
        room_id = uid[len("room_"):-len("_climate")]
        for ed in hass.data.get(DOMAIN, {}).values():
            rc = ed.get("rooms", {}).get(room_id)
            if rc is not None:
                return rc
    _LOGGER.warning("Service call: no coordinator for %s (uid=%s)", entity_id, uid)
    return None


def _register_services(hass: HomeAssistant) -> None:
    import voluptuous as vol

    async def _boost(call: ServiceCall) -> None:
        rc = _room_for_entity_id(hass, call.data["entity_id"])
        if rc:
            await rc.async_start_boost(call.data.get(ATTR_BOOST_TEMPERATURE), call.data.get(ATTR_BOOST_DURATION))

    async def _end_boost(call: ServiceCall) -> None:
        rc = _room_for_entity_id(hass, call.data["entity_id"])
        if rc:
            await rc.async_end_boost()

    async def _set_schedule(call: ServiceCall) -> None:
        rc = _room_for_entity_id(hass, call.data["entity_id"])
        if not rc:
            return
        schedule = call.data[ATTR_SCHEDULE]
        await rc.async_set_schedule(schedule)
        for ed in hass.data.get(DOMAIN, {}).values():
            s = ed.get(DATA_STORE)
            if s and rc.room_id in ed.get("rooms", {}):
                await s.async_set_room_schedule(rc.room_id, schedule)

    async def _clear_schedule(call: ServiceCall) -> None:
        rc = _room_for_entity_id(hass, call.data["entity_id"])
        if rc:
            rc.clear_schedule()

    async def _advance(call: ServiceCall) -> None:
        rc = _room_for_entity_id(hass, call.data["entity_id"])
        if rc:
            await rc._schedule_mgr.advance_to_next()

    _EID = vol.Schema({vol.Required("entity_id"): str})
    _BOOST_S = vol.Schema({
        vol.Required("entity_id"): str,
        vol.Optional(ATTR_BOOST_TEMPERATURE, default=DEFAULT_BOOST_TEMP): vol.Coerce(float),
        vol.Optional(ATTR_BOOST_DURATION, default=DEFAULT_BOOST_MINUTES): vol.All(int, vol.Range(min=1, max=1440)),
    })
    _SCHED_S = vol.Schema({
        vol.Required("entity_id"): str,
        vol.Required(ATTR_SCHEDULE): [vol.Schema({
            vol.Required("days"): [vol.All(int, vol.Range(min=0, max=6))],
            vol.Required("time"): str,
            vol.Required("temperature"): vol.Coerce(float),
        })],
    })
    hass.services.async_register(DOMAIN, SERVICE_BOOST,            _boost,          _BOOST_S)
    hass.services.async_register(DOMAIN, SERVICE_END_BOOST,        _end_boost,      _EID)
    hass.services.async_register(DOMAIN, SERVICE_SET_SCHEDULE,     _set_schedule,   _SCHED_S)
    hass.services.async_register(DOMAIN, SERVICE_CLEAR_SCHEDULE,   _clear_schedule, _EID)
    hass.services.async_register(DOMAIN, SERVICE_ADVANCE_SCHEDULE, _advance,        _EID)
