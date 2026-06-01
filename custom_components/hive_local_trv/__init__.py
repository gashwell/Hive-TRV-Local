"""Hive Local TRV integration — DIAGNOSTIC BUILD v0.0.6."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

_L = logging.getLogger("custom_components.hive_local_trv")
_L.warning("HIVE_DIAG __init__: module import started")

try:
    import voluptuous as vol
    _L.warning("HIVE_DIAG __init__: voluptuous OK")
except Exception as _e:
    _L.error("HIVE_DIAG __init__: voluptuous FAILED: %s", _e)
    raise

try:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant, ServiceCall
    from homeassistant.helpers import config_validation as cv
    from homeassistant.helpers.typing import ConfigType
    _L.warning("HIVE_DIAG __init__: homeassistant core OK")
except Exception as _e:
    _L.error("HIVE_DIAG __init__: homeassistant core FAILED: %s", _e, exc_info=True)
    raise

try:
    from .const import (
        ATTR_BOOST_DURATION,
        ATTR_BOOST_TEMPERATURE,
        ATTR_DEPARTURE,
        ATTR_RETURN,
        ATTR_ROOM_NAME,
        ATTR_ROOM_SENSORS,
        ATTR_ROOM_TRVS,
        ATTR_SCHEDULE,
        CONF_BOILER_ENTITY,
        CONF_PERSON_ENTITIES,
        CONF_Z2M_BASE_TOPIC,
        DATA_HUB,
        DATA_STORE,
        DEFAULT_BOOST_MINUTES,
        DEFAULT_BOOST_TEMP,
        DOMAIN,
        LOGGER,
        MIN_HA_VERSION,
        PLATFORMS,
        SERVICE_ADVANCE_SCHEDULE,
        SERVICE_ADD_ROOM,
        SERVICE_BOOST,
        SERVICE_CANCEL_HOLIDAY,
        SERVICE_CLEAR_SCHEDULE,
        SERVICE_END_BOOST,
        SERVICE_REMOVE_ROOM,
        SERVICE_SET_HOLIDAY,
        SERVICE_SET_SCHEDULE,
    )
    _L.warning("HIVE_DIAG __init__: const OK — DOMAIN=%s PLATFORMS=%s", DOMAIN, PLATFORMS)
except Exception as _e:
    _L.error("HIVE_DIAG __init__: const FAILED: %s", _e, exc_info=True)
    raise

try:
    from .coordinator import HiveTRVHub
    _L.warning("HIVE_DIAG __init__: coordinator OK")
except Exception as _e:
    _L.error("HIVE_DIAG __init__: coordinator FAILED: %s", _e, exc_info=True)
    raise

try:
    from .holiday import HolidayManager
    from .presence import PresenceManager
    from .room import HiveRoomCoordinator
    from .schedule import ScheduleManager
    from .storage import HiveTRVStore
    _L.warning("HIVE_DIAG __init__: all sub-modules OK")
except Exception as _e:
    _L.error("HIVE_DIAG __init__: sub-module FAILED: %s", _e, exc_info=True)
    raise

try:
    CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
    _L.warning("HIVE_DIAG __init__: CONFIG_SCHEMA OK")
except Exception as _e:
    _L.error("HIVE_DIAG __init__: CONFIG_SCHEMA FAILED: %s", _e, exc_info=True)
    raise

# ── Service schemas ─────────────────────────────────────────────────────────
try:
    _BOOST_SCHEMA = vol.Schema({
        vol.Required("entity_id"): str,
        vol.Optional(ATTR_BOOST_TEMPERATURE, default=DEFAULT_BOOST_TEMP): vol.Coerce(float),
        vol.Optional(ATTR_BOOST_DURATION, default=DEFAULT_BOOST_MINUTES): vol.All(int, vol.Range(min=1, max=1440)),
    })
    _END_BOOST_SCHEMA        = vol.Schema({vol.Required("entity_id"): str})
    _SET_SCHEDULE_SCHEMA     = vol.Schema({
        vol.Required("entity_id"): str,
        vol.Required(ATTR_SCHEDULE): [vol.Schema({
            vol.Required("days"):        [vol.All(int, vol.Range(min=0, max=6))],
            vol.Required("time"):        str,
            vol.Required("temperature"): vol.Coerce(float),
        })],
    })
    _CLEAR_SCHEDULE_SCHEMA   = vol.Schema({vol.Required("entity_id"): str})
    _ADVANCE_SCHEDULE_SCHEMA = vol.Schema({vol.Required("entity_id"): str})
    _SET_HOLIDAY_SCHEMA      = vol.Schema({
        vol.Required(ATTR_DEPARTURE): str,
        vol.Required(ATTR_RETURN):    str,
    })
    _CANCEL_HOLIDAY_SCHEMA   = vol.Schema({})
    _ADD_ROOM_SCHEMA         = vol.Schema({
        vol.Required(ATTR_ROOM_NAME):                     str,
        vol.Required(ATTR_ROOM_TRVS):                     [str],
        vol.Optional(ATTR_ROOM_SENSORS, default=[]):       [str],
    })
    _REMOVE_ROOM_SCHEMA      = vol.Schema({vol.Required(ATTR_ROOM_NAME): str})
    _L.warning("HIVE_DIAG __init__: service schemas OK")
except Exception as _e:
    _L.error("HIVE_DIAG __init__: service schema FAILED: %s", _e, exc_info=True)
    raise

_L.warning("HIVE_DIAG __init__: module load COMPLETE")


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Integration setup — called before any config entry."""
    _L.warning("HIVE_DIAG async_setup called")
    # Removed awesomeversion dependency — it's not always available
    # as a standalone import in all HA environments
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hive TRV from a config entry."""
    _L.warning(
        "HIVE_DIAG async_setup_entry: entry_id=%s data=%s options=%s",
        entry.entry_id, dict(entry.data), dict(entry.options),
    )

    base_topic = (
        entry.options.get(CONF_Z2M_BASE_TOPIC)
        or entry.data.get(CONF_Z2M_BASE_TOPIC, "zigbee2mqtt")
    )
    boiler_entity = (
        entry.options.get(CONF_BOILER_ENTITY)
        or entry.data.get(CONF_BOILER_ENTITY)
    )
    person_ids = (
        entry.options.get(CONF_PERSON_ENTITIES)
        or entry.data.get(CONF_PERSON_ENTITIES)
        or []
    )
    _L.warning(
        "HIVE_DIAG async_setup_entry: base=%s boiler=%s persons=%s",
        base_topic, boiler_entity, person_ids,
    )

    try:
        store = HiveTRVStore(hass, entry.entry_id)
        await store.async_load()
        _L.warning("HIVE_DIAG async_setup_entry: store OK")
    except Exception as exc:
        _L.error("HIVE_DIAG async_setup_entry: store FAILED: %s", exc, exc_info=True)
        return False

    try:
        hub = HiveTRVHub(hass, base_topic, boiler_entity)
        await hub.async_setup()
        _L.warning("HIVE_DIAG async_setup_entry: hub OK")
    except Exception as exc:
        _L.error("HIVE_DIAG async_setup_entry: hub FAILED: %s", exc, exc_info=True)
        return False

    holiday_mgr  = HolidayManager(hass, store, hub)
    presence_mgr = PresenceManager(hass, person_ids, hub, holiday_mgr)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        DATA_HUB:       hub,
        DATA_STORE:     store,
        "holiday_mgr":  holiday_mgr,
        "presence_mgr": presence_mgr,
    }

    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        _L.warning("HIVE_DIAG async_setup_entry: platforms OK — %s", PLATFORMS)
    except Exception as exc:
        _L.error("HIVE_DIAG async_setup_entry: platforms FAILED: %s", exc, exc_info=True)
        return False

    for room_id, room_data in store.get_all_rooms().items():
        await _create_room_coordinator(hass, entry, hub, store, room_id, room_data)

    await holiday_mgr.async_setup()
    await presence_mgr.async_setup()

    if not hass.services.has_service(DOMAIN, SERVICE_BOOST):
        _register_services(hass)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    _L.warning("HIVE_DIAG async_setup_entry: COMPLETE")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        ed = hass.data[DOMAIN].pop(entry.entry_id, {})
        if hub := ed.get(DATA_HUB):
            await hub.async_unload()
        if pm := ed.get("presence_mgr"):
            await pm.async_unload()
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def _create_room_coordinator(hass, entry, hub, store, room_id, room_data):
    room_coord = HiveRoomCoordinator(
        hass,
        room_id=room_id,
        room_name=room_data["name"],
        trv_friendly_names=room_data.get("trvs", []),
        temp_sensor_entity_ids=room_data.get("temp_sensors", []),
        get_trv_coordinator=hub.get_coordinator,
    )
    await room_coord.async_setup()
    hub.register_room_coordinator(room_id, room_coord)
    if room_data.get("schedule"):
        await room_coord.async_set_schedule(room_data["schedule"])
    room_coord.async_add_listener(
        lambda: hass.async_create_task(hub.async_evaluate_boiler_demand())
    )
    hass.bus.async_fire(
        f"{DOMAIN}_room_added",
        {"entry_id": entry.entry_id, "room_id": room_id, "coordinator": room_coord},
    )
    return room_coord


def _register_services(hass: HomeAssistant) -> None:
    _L.warning("HIVE_DIAG _register_services called")

    def _hub_store():
        entries = hass.data.get(DOMAIN, {})
        if not entries:
            return None, None, None, None
        ed = next(iter(entries.values()))
        return ed[DATA_HUB], ed[DATA_STORE], ed.get("holiday_mgr"), ed.get("presence_mgr")

    def _target(entity_id: str):
        for ed in hass.data.get(DOMAIN, {}).values():
            hub = ed[DATA_HUB]
            for coord in hub.coordinators.values():
                slug = coord.friendly_name.lower().replace(" ", "_")
                if f"climate.{slug}" == entity_id:
                    return coord
            for rc in hub._room_coordinators.values():
                slug = rc.room_name.lower().replace(" ", "_")
                if f"climate.{slug}_room" == entity_id:
                    return rc
        return None

    async def _boost(call: ServiceCall) -> None:
        t = _target(call.data["entity_id"])
        if t:
            await t.async_start_boost(
                call.data.get(ATTR_BOOST_TEMPERATURE, DEFAULT_BOOST_TEMP),
                call.data.get(ATTR_BOOST_DURATION, DEFAULT_BOOST_MINUTES),
            )

    async def _end_boost(call: ServiceCall) -> None:
        t = _target(call.data["entity_id"])
        if t: await t.async_end_boost()

    async def _set_schedule(call: ServiceCall) -> None:
        t = _target(call.data["entity_id"])
        if not t: return
        hub, store, *_ = _hub_store()
        schedule = call.data[ATTR_SCHEDULE]
        if isinstance(t, HiveRoomCoordinator):
            await t.async_set_schedule(schedule)
            if store: await store.async_set_room_schedule(t.room_id, schedule)
        else:
            mgr = ScheduleManager(hass, t.friendly_name, t.async_set_temperature)
            await mgr.async_set_schedule(schedule)
            if store: await store.async_set_trv_schedule(t.friendly_name, schedule)

    async def _clear_schedule(call: ServiceCall) -> None:
        t = _target(call.data["entity_id"])
        if t and hasattr(t, "_schedule_mgr") and t._schedule_mgr: t._schedule_mgr.clear()

    async def _advance_schedule(call: ServiceCall) -> None:
        t = _target(call.data["entity_id"])
        if t:
            mgr = getattr(t, "_schedule_mgr", None)
            if mgr: await mgr.advance_to_next()

    async def _set_holiday(call: ServiceCall) -> None:
        hub, store, holiday_mgr, _ = _hub_store()
        if not holiday_mgr: return
        import homeassistant.util.dt as dt_util
        try:
            dep = dt_util.as_utc(datetime.fromisoformat(call.data[ATTR_DEPARTURE]))
            ret = dt_util.as_utc(datetime.fromisoformat(call.data[ATTR_RETURN]))
        except (ValueError, KeyError) as exc:
            LOGGER.error("set_holiday: %s", exc)
            return
        await holiday_mgr.async_set_holiday(dep, ret)

    async def _cancel_holiday(call: ServiceCall) -> None:
        _, _, holiday_mgr, _ = _hub_store()
        if holiday_mgr: await holiday_mgr.async_cancel_holiday()

    async def _add_room(call: ServiceCall) -> None:
        hub, store, *_ = _hub_store()
        if not hub: return
        room_id = str(uuid.uuid4())
        room_data = {
            "name": call.data[ATTR_ROOM_NAME],
            "trvs": call.data[ATTR_ROOM_TRVS],
            "temp_sensors": call.data.get(ATTR_ROOM_SENSORS, []),
            "schedule": [],
        }
        await store.async_save_room(room_id, room_data)
        for eid, ed in hass.data.get(DOMAIN, {}).items():
            if ed[DATA_HUB] is hub:
                entry = hass.config_entries.async_get_entry(eid)
                if entry:
                    await _create_room_coordinator(hass, entry, hub, store, room_id, room_data)
                break

    async def _remove_room(call: ServiceCall) -> None:
        hub, store, *_ = _hub_store()
        if not hub: return
        name = call.data[ATTR_ROOM_NAME]
        for room_id, rc in list(hub._room_coordinators.items()):
            if rc.room_name == name:
                await rc.async_unload()
                hub.unregister_room_coordinator(room_id)
                await store.async_remove_room(room_id)
                hass.bus.async_fire(f"{DOMAIN}_room_removed", {"room_id": room_id})
                return

    hass.services.async_register(DOMAIN, SERVICE_BOOST,            _boost,            _BOOST_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_END_BOOST,        _end_boost,        _END_BOOST_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_SET_SCHEDULE,     _set_schedule,     _SET_SCHEDULE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_CLEAR_SCHEDULE,   _clear_schedule,   _CLEAR_SCHEDULE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_ADVANCE_SCHEDULE, _advance_schedule, _ADVANCE_SCHEDULE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_SET_HOLIDAY,      _set_holiday,      _SET_HOLIDAY_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_CANCEL_HOLIDAY,   _cancel_holiday,   _CANCEL_HOLIDAY_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_ADD_ROOM,         _add_room,         _ADD_ROOM_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_REMOVE_ROOM,      _remove_room,      _REMOVE_ROOM_SCHEMA)
    _L.warning("HIVE_DIAG _register_services: all %d services registered", 9)
