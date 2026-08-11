"""Hive Local v5 — fully local Hive heating control via Zigbee2MQTT."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_DURATION_MINUTES, ATTR_SCHEDULE, ATTR_TEMPERATURE,
    CONF_BOILER_ENTITY, CONF_Z2M_BASE_TOPIC, DATA_COORDINATOR, DATA_STORE,
    DEFAULT_BOOST_MINUTES, DEFAULT_BOOST_TEMP, DOMAIN, PLATFORMS,
    SVC_DEVICE_BOOST, SVC_DEVICE_END_BOOST,
    SVC_ROOM_BOOST, SVC_ROOM_CLEAR_SCHEDULE,
    SVC_ROOM_END_BOOST, SVC_ROOM_SET_SCHEDULE,
)
from .coordinator import HiveLocalCoordinator
from .store import HiveLocalStore

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register Lovelace cards."""
    from pathlib import Path
    from homeassistant.components.frontend import add_extra_js_url
    from homeassistant.components.http import StaticPathConfig

    for card in ("hive-local-device-card.js", "hive-local-room-card.js"):
        path = Path(__file__).parent / card
        if path.exists():
            url = f"/{DOMAIN}/{card}"
            await hass.http.async_register_static_paths(
                [StaticPathConfig(url, str(path), True)]
            )
            add_extra_js_url(hass, url)
            _LOGGER.debug("Registered card: %s", url)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    opts   = entry.options or {}
    data   = entry.data    or {}
    merged = {**data, **opts}

    store = HiveLocalStore(hass, entry.entry_id)
    await store.async_load()

    coordinator = HiveLocalCoordinator(
        hass          = hass,
        entry_id      = entry.entry_id,
        store         = store,
        boiler_entity = merged.get(CONF_BOILER_ENTITY),
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
        DATA_STORE:       store,
    }

    await coordinator.async_setup()

    # Start Z2M bridge device auto-discovery
    from .discovery import HiveDiscovery
    base_topic = merged.get(CONF_Z2M_BASE_TOPIC, "zigbee2mqtt")
    discovery  = HiveDiscovery(hass, coordinator, base_topic)
    await discovery.async_setup()
    hass.data[DOMAIN][entry.entry_id]["discovery"] = discovery

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Re-apply entity suppression for rooms that existed before this boot
    coordinator.restore_entity_suppression()

    _register_services(hass, coordinator)

    entry.async_on_unload(entry.add_update_listener(_on_options_updated))
    _LOGGER.info("Hive Local v5 ready")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        ed = hass.data[DOMAIN].pop(entry.entry_id, {})
        if disc := ed.get("discovery"):
            await disc.async_unload()
        c: HiveLocalCoordinator | None = ed.get(DATA_COORDINATOR)
        if c:
            await c.async_unload()
    return ok


async def _on_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload only if Z2M topic changed; boiler entity is updated live."""
    old = entry.data.get(CONF_Z2M_BASE_TOPIC)
    new = (entry.options or {}).get(CONF_Z2M_BASE_TOPIC)
    if old != new:
        _LOGGER.info("Z2M base topic changed — reloading")
        await hass.config_entries.async_reload(entry.entry_id)


def _coordinator(hass: HomeAssistant) -> HiveLocalCoordinator | None:
    for ed in hass.data.get(DOMAIN, {}).values():
        c = ed.get(DATA_COORDINATOR)
        if c:
            return c
    return None


def _room_for_entity(hass: HomeAssistant, entity_id: str):
    """Resolve a room climate entity_id to its HiveRoom."""
    from homeassistant.helpers import entity_registry as er
    from .const import uid_room
    ent_reg = er.async_get(hass)
    entry   = ent_reg.async_get(entity_id)
    if not entry:
        return None
    uid = entry.unique_id or ""
    # uid format: hive_local_room_{room_id}_climate
    prefix = f"{DOMAIN}_room_"
    suffix = "_climate"
    if uid.startswith(prefix) and uid.endswith(suffix):
        room_id = uid[len(prefix):-len(suffix)]
        c = _coordinator(hass)
        return c.get_room(room_id) if c else None
    return None


def _register_services(hass: HomeAssistant, coordinator: HiveLocalCoordinator) -> None:
    import voluptuous as vol

    if hass.services.has_service(DOMAIN, SVC_ROOM_BOOST):
        return

    async def room_boost(call: ServiceCall) -> None:
        room = _room_for_entity(hass, call.data["entity_id"])
        if room:
            await room.async_start_boost(
                call.data.get(ATTR_TEMPERATURE),
                call.data.get(ATTR_DURATION_MINUTES),
            )

    async def room_end_boost(call: ServiceCall) -> None:
        room = _room_for_entity(hass, call.data["entity_id"])
        if room:
            await room.async_end_boost()

    async def room_set_schedule(call: ServiceCall) -> None:
        room = _room_for_entity(hass, call.data["entity_id"])
        if room:
            schedule = call.data[ATTR_SCHEDULE]
            await room.async_set_schedule(schedule)
            c = _coordinator(hass)
            if c:
                await c.store.async_set_room_schedule(room.room_id, schedule)

    async def room_clear_schedule(call: ServiceCall) -> None:
        room = _room_for_entity(hass, call.data["entity_id"])
        if room:
            room.clear_schedule()

    _EID = vol.Schema({vol.Required("entity_id"): str})
    _BOOST = vol.Schema({
        vol.Required("entity_id"):  str,
        vol.Optional(ATTR_TEMPERATURE,      default=DEFAULT_BOOST_TEMP):    vol.Coerce(float),
        vol.Optional(ATTR_DURATION_MINUTES, default=DEFAULT_BOOST_MINUTES): vol.All(int, vol.Range(min=1, max=360)),
    })
    _SCHED = vol.Schema({
        vol.Required("entity_id"): str,
        vol.Required(ATTR_SCHEDULE): [vol.Schema({
            vol.Required("days"):        [vol.All(int, vol.Range(min=0, max=6))],
            vol.Required("time"):        str,
            vol.Required("temperature"): vol.Coerce(float),
        })],
    })

    hass.services.async_register(DOMAIN, SVC_ROOM_BOOST,          room_boost,          _BOOST)
    hass.services.async_register(DOMAIN, SVC_ROOM_END_BOOST,       room_end_boost,      _EID)
    hass.services.async_register(DOMAIN, SVC_ROOM_SET_SCHEDULE,    room_set_schedule,   _SCHED)
    hass.services.async_register(DOMAIN, SVC_ROOM_CLEAR_SCHEDULE,  room_clear_schedule, _EID)
