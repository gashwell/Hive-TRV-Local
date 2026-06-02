"""Config flow for Hive Local TRV."""
from __future__ import annotations

import logging
from typing import Any

_L = logging.getLogger("custom_components.hive_local_trv.config_flow")
_L.warning("HIVE_DIAG config_flow: module import started")

try:
    import voluptuous as vol
    from homeassistant import config_entries
    from homeassistant.core import callback
    from homeassistant.helpers import selector
    _L.warning("HIVE_DIAG config_flow: imports OK")
except Exception as exc:
    _L.error("HIVE_DIAG config_flow: import FAILED: %s", exc, exc_info=True)
    raise

try:
    from .const import (
        CONF_BOILER_ENTITY,
        CONF_ENABLE_DIAGNOSTICS,
        CONF_PERSON_ENTITIES,
        CONF_Z2M_BASE_TOPIC,
        CONFIG_VERSION,
        DATA_HUB,
        DATA_STORE,
        DEFAULT_ENABLE_DIAGNOSTICS,
        DEFAULT_Z2M_BASE_TOPIC,
        DOMAIN,
    )
    _L.warning("HIVE_DIAG config_flow: const OK — DOMAIN=%s", DOMAIN)
except Exception as exc:
    _L.error("HIVE_DIAG config_flow: const FAILED: %s", exc, exc_info=True)
    raise

_L.warning("HIVE_DIAG config_flow: defining flow class")


class HiveLocalTRVConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow — single step: Z2M base topic only."""

    VERSION = CONFIG_VERSION

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Show setup form or process submission."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                base = user_input[CONF_Z2M_BASE_TOPIC].strip().rstrip("/")
                await self.async_set_unique_id(base)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Hive TRVs",
                    data={
                        CONF_Z2M_BASE_TOPIC: base,
                        CONF_BOILER_ENTITY: None,
                        CONF_PERSON_ENTITIES: [],
                        CONF_ENABLE_DIAGNOSTICS: DEFAULT_ENABLE_DIAGNOSTICS,
                    },
                )
            except Exception as exc:
                _L.error("HIVE_DIAG async_step_user: FAILED: %s", exc, exc_info=True)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_Z2M_BASE_TOPIC,
                        default=DEFAULT_Z2M_BASE_TOPIC,
                    ): selector.TextSelector(),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "HiveLocalTRVOptionsFlow":
        """Return the options flow handler."""
        return HiveLocalTRVOptionsFlow()


class HiveLocalTRVOptionsFlow(config_entries.OptionsFlow):
    """Options flow with menu: device settings or room group management."""

    def __init__(self) -> None:
        """Initialise."""
        self._new_room_name: str = ""
        self._new_trv_names: list[str] = []
        self._new_temp_sensors: list[str] = []

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _get_store_and_hub(self):
        """Return (store, hub) from hass.data if loaded."""
        ed = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id, {})
        return ed.get(DATA_STORE), ed.get(DATA_HUB)

    def _get_room_names(self) -> list[str]:
        """Return sorted list of existing room names."""
        store, _ = self._get_store_and_hub()
        if not store:
            return []
        return sorted(rd.get("name", rid) for rid, rd in store.get_all_rooms().items())

    def _get_all_trv_names(self) -> list[str]:
        """All TRV and thermostat friendly names known to the hub."""
        _, hub = self._get_store_and_hub()
        if not hub:
            return []
        # hub.coordinators is keyed by Z2M friendly name
        return sorted(hub.coordinators.keys())

    def _get_grouped_trv_names(self) -> set[str]:
        """TRV friendly names that are already assigned to a room group."""
        store, _ = self._get_store_and_hub()
        if not store:
            return set()
        grouped: set[str] = set()
        for room_data in store.get_all_rooms().values():
            grouped.update(room_data.get("trvs", []))
        return grouped

    def _get_available_trv_names(self) -> list[str]:
        """TRVs not yet in any group — available for a new room."""
        all_trvs = self._get_all_trv_names()
        grouped  = self._get_grouped_trv_names()
        return [t for t in all_trvs if t not in grouped]

    # ── Top-level menu ─────────────────────────────────────────────────────────

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Show the top-level menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options={
                "settings": "Device settings",
                "rooms":    "Manage room groups",
            },
        )

    # ── Device settings ────────────────────────────────────────────────────────

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Boiler entity, geofencing persons, diagnostics toggle."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    **self.config_entry.options,
                    CONF_BOILER_ENTITY: user_input.get(CONF_BOILER_ENTITY) or None,
                    CONF_PERSON_ENTITIES: user_input.get(CONF_PERSON_ENTITIES) or [],
                    CONF_ENABLE_DIAGNOSTICS: user_input.get(
                        CONF_ENABLE_DIAGNOSTICS, DEFAULT_ENABLE_DIAGNOSTICS
                    ),
                },
            )

        entry = self.config_entry
        opts  = entry.options
        data  = entry.data

        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_BOILER_ENTITY,
                        description={"suggested_value": opts.get(CONF_BOILER_ENTITY) or data.get(CONF_BOILER_ENTITY)},
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["climate", "switch", "input_boolean"]
                        )
                    ),
                    vol.Optional(
                        CONF_PERSON_ENTITIES,
                        description={"suggested_value": opts.get(CONF_PERSON_ENTITIES) or data.get(CONF_PERSON_ENTITIES, [])},
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="person", multiple=True)
                    ),
                    vol.Optional(
                        CONF_ENABLE_DIAGNOSTICS,
                        default=opts.get(CONF_ENABLE_DIAGNOSTICS, data.get(CONF_ENABLE_DIAGNOSTICS, DEFAULT_ENABLE_DIAGNOSTICS)),
                    ): selector.BooleanSelector(),
                }
            ),
        )

    # ── Room management menu ───────────────────────────────────────────────────

    async def async_step_rooms(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Room management sub-menu."""
        options: dict[str, str] = {}

        available = self._get_available_trv_names()
        if available:
            options["add_room"] = "Add a room group"

        existing = self._get_room_names()
        if existing:
            options["remove_room"] = "Remove a room group"

        if not options:
            # No TRVs discovered yet and no rooms — show an informational form
            return self.async_show_form(
                step_id="rooms",
                data_schema=vol.Schema({}),
                description_placeholders={
                    "status": "No TRVs have been discovered yet. "
                              "Wait for Zigbee2MQTT to publish device data and try again."
                },
            )

        return self.async_show_menu(step_id="rooms", menu_options=options)

    # ── Add room — step 1: name ────────────────────────────────────────────────

    async def async_step_add_room(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Step 1 — room name."""
        errors: dict[str, str] = {}

        if user_input is not None:
            name = user_input.get("room_name", "").strip()
            if not name:
                errors["room_name"] = "required"
            else:
                self._new_room_name = name
                return await self.async_step_add_room_trvs()

        return self.async_show_form(
            step_id="add_room",
            data_schema=vol.Schema(
                {
                    vol.Required("room_name"): selector.TextSelector(),
                }
            ),
            errors=errors,
        )

    # ── Add room — step 2: TRV selection ──────────────────────────────────────

    async def async_step_add_room_trvs(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Step 2 — pick TRVs from a dropdown of available devices.

        Only shows devices not already assigned to another group.
        """
        errors: dict[str, str] = {}
        available = self._get_available_trv_names()

        if not available:
            # All TRVs are already grouped — shouldn't normally be reachable
            return self.async_abort(reason="no_devices_available")

        if user_input is not None:
            chosen = user_input.get("trv_names") or []
            if not chosen:
                errors["trv_names"] = "required"
            else:
                self._new_trv_names = chosen
                return await self.async_step_add_room_sensors()

        return self.async_show_form(
            step_id="add_room_trvs",
            data_schema=vol.Schema(
                {
                    vol.Required("trv_names"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=available,
                            multiple=True,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
            description_placeholders={"room_name": self._new_room_name},
            errors=errors,
        )

    # ── Add room — step 3: optional temperature sensors ───────────────────────

    async def async_step_add_room_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Step 3 — optional extra temperature sensors, then create the room."""
        if user_input is not None:
            self._new_temp_sensors = user_input.get("temp_sensors") or []
            return await self._create_room()

        return self.async_show_form(
            step_id="add_room_sensors",
            data_schema=vol.Schema(
                {
                    vol.Optional("temp_sensors"): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor",
                            device_class="temperature",
                            multiple=True,
                        )
                    ),
                }
            ),
            description_placeholders={
                "room_name":  self._new_room_name,
                "trv_count":  str(len(self._new_trv_names)),
                "trv_names":  ", ".join(self._new_trv_names),
            },
        )

    async def _create_room(self) -> config_entries.FlowResult:
        """Persist the room and fire it live into the running hub."""
        import uuid as _uuid

        store, _ = self._get_store_and_hub()
        room_id   = str(_uuid.uuid4())
        room_data = {
            "name":         self._new_room_name,
            "trvs":         self._new_trv_names,
            "temp_sensors": self._new_temp_sensors,
            "schedule":     [],
        }

        if store:
            await store.async_save_room(room_id, room_data)

        self.hass.bus.async_fire(
            f"{DOMAIN}_room_added",
            {
                "entry_id":  self.config_entry.entry_id,
                "room_id":   room_id,
                "room_data": room_data,
            },
        )

        return self.async_create_entry(title="", data=self.config_entry.options)

    # ── Remove room ────────────────────────────────────────────────────────────

    async def async_step_remove_room(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Select a room to remove."""
        room_names = self._get_room_names()

        if not room_names:
            return self.async_create_entry(title="", data=self.config_entry.options)

        if user_input is not None:
            chosen = user_input.get("room_name")
            if chosen:
                await self._delete_room(chosen)
            return self.async_create_entry(title="", data=self.config_entry.options)

        return self.async_show_form(
            step_id="remove_room",
            data_schema=vol.Schema(
                {
                    vol.Required("room_name"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=room_names,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def _delete_room(self, room_name: str) -> None:
        """Remove a room from the store and fire its removal event."""
        store, _ = self._get_store_and_hub()
        if not store:
            return
        for room_id, rdata in list(store.get_all_rooms().items()):
            if rdata.get("name") == room_name:
                await store.async_remove_room(room_id)
                self.hass.bus.async_fire(
                    f"{DOMAIN}_room_removed",
                    {"entry_id": self.config_entry.entry_id, "room_id": room_id},
                )
                break


_L.warning("HIVE_DIAG config_flow: module load COMPLETE")
