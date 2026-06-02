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
        _L.warning("HIVE_DIAG async_step_user called — user_input=%s", user_input)
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

    # ── Top-level menu ─────────────────────────────────────────────────────────

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Show the top-level menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options={
                "settings": "Device settings",
                "rooms": "Manage room groups",
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
        opts = entry.options
        data = entry.data

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

    # ── Room group management menu ─────────────────────────────────────────────

    async def async_step_rooms(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Room management sub-menu."""
        # Check if any rooms exist so we only show Remove when relevant
        existing = self._get_room_names()
        options: dict[str, str] = {"add_room": "Add a room group"}
        if existing:
            options["remove_room"] = "Remove a room group"

        return self.async_show_menu(step_id="rooms", menu_options=options)

    # ── Add room ───────────────────────────────────────────────────────────────

    async def async_step_add_room(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Step 1 of 2 — room name and TRV friendly names."""
        errors: dict[str, str] = {}

        if user_input is not None:
            name = user_input.get("room_name", "").strip()
            raw_trvs = user_input.get("trv_names", "").strip()

            if not name:
                errors["room_name"] = "required"
            elif not raw_trvs:
                errors["trv_names"] = "required"
            else:
                # Parse comma-separated TRV names
                self._new_room_name = name
                self._new_trv_names = [t.strip() for t in raw_trvs.split(",") if t.strip()]
                return await self.async_step_add_room_sensors()

        return self.async_show_form(
            step_id="add_room",
            data_schema=vol.Schema(
                {
                    vol.Required("room_name"): selector.TextSelector(),
                    vol.Required("trv_names"): selector.TextSelector(
                        selector.TextSelectorConfig(multiline=False)
                    ),
                }
            ),
            description_placeholders={
                "trv_names_hint": "Comma-separated Zigbee2MQTT friendly names, e.g. Living Room TRV, Living Room TRV 2"
            },
            errors=errors,
        )

    async def async_step_add_room_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Step 2 of 2 — optional extra temperature sensors, then create."""
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
                "room_name": self._new_room_name,
                "trv_count": str(len(self._new_trv_names)),
            },
        )

    async def _create_room(self) -> config_entries.FlowResult:
        """Create the room in the store and fire it live into the running hub."""
        import uuid as _uuid

        store, hub = self._get_store_and_hub()
        room_id = str(_uuid.uuid4())
        room_data = {
            "name": self._new_room_name,
            "trvs": self._new_trv_names,
            "temp_sensors": self._new_temp_sensors,
            "schedule": [],
        }

        if store:
            await store.async_save_room(room_id, room_data)

        # Fire the room_added event so the climate platform picks it up live
        self.hass.bus.async_fire(
            f"{DOMAIN}_room_added",
            {
                "entry_id": self.config_entry.entry_id,
                "room_id": room_id,
                "room_data": room_data,
            },
        )

        return self.async_create_entry(title="", data=self.config_entry.options)

    # ── Remove room ────────────────────────────────────────────────────────────

    async def async_step_remove_room(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Select a room to remove."""
        errors: dict[str, str] = {}
        room_names = self._get_room_names()

        if not room_names:
            # Shouldn't be reachable but handle gracefully
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
            errors=errors,
        )

    async def _delete_room(self, room_name: str) -> None:
        """Remove a room from the store and fire its removal event."""
        store, hub = self._get_store_and_hub()

        # Find the room_id by name
        if store:
            for room_id, rdata in list(store.get_all_rooms().items()):
                if rdata.get("name") == room_name:
                    await store.async_remove_room(room_id)
                    self.hass.bus.async_fire(
                        f"{DOMAIN}_room_removed",
                        {"entry_id": self.config_entry.entry_id, "room_id": room_id},
                    )
                    break

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _get_store_and_hub(self):
        """Return (store, hub) from hass.data if loaded, else (None, None)."""
        entry_data = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id, {})
        return entry_data.get(DATA_STORE), entry_data.get(DATA_HUB)

    def _get_room_names(self) -> list[str]:
        """Return sorted list of existing room names from the store."""
        store, _ = self._get_store_and_hub()
        if not store:
            return []
        return sorted(rdata.get("name", rid) for rid, rdata in store.get_all_rooms().items())


_L.warning("HIVE_DIAG config_flow: module load COMPLETE")
