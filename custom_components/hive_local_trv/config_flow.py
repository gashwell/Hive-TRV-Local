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
        DATA_STORE,
        DEFAULT_ENABLE_DIAGNOSTICS,
        DEFAULT_Z2M_BASE_TOPIC,
        DOMAIN,
    )
    _L.warning("HIVE_DIAG config_flow: const OK")
except Exception as exc:
    _L.error("HIVE_DIAG config_flow: const FAILED: %s", exc, exc_info=True)
    raise


class HiveLocalTRVConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow — single step: Z2M base topic only."""

    VERSION = CONFIG_VERSION

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
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
                _L.error("HIVE_DIAG async_step_user FAILED: %s", exc, exc_info=True)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_Z2M_BASE_TOPIC, default=DEFAULT_Z2M_BASE_TOPIC): selector.TextSelector(),
            }),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> "HiveLocalTRVOptionsFlow":
        return HiveLocalTRVOptionsFlow()


class HiveLocalTRVOptionsFlow(config_entries.OptionsFlow):
    """Options flow — device settings and group management."""

    def __init__(self) -> None:
        self._new_room_name:    str       = ""
        self._new_member_ids:   list[str] = []
        self._new_temp_sensors: list[str] = []
        self._edit_room_id:     str       = ""
        self._edit_room_name:   str       = ""

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _store(self):
        return self.hass.data.get(DOMAIN, {}).get(
            self.config_entry.entry_id, {}
        ).get(DATA_STORE)

    def _all_rooms(self) -> dict[str, dict]:
        s = self._store()
        return s.get_all_rooms() if s else {}

    def _grouped_entity_ids(self, exclude_room_id: str | None = None) -> set[str]:
        """Entity IDs already assigned to any group (optionally excluding one)."""
        grouped: set[str] = set()
        for rid, rdata in self._all_rooms().items():
            if rid == exclude_room_id:
                continue
            grouped.update(rdata.get("members", []))
        return grouped

    # ── Top-level menu ─────────────────────────────────────────────────────────

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options={
                "settings": "Device settings",
                "groups":   "Manage room groups",
            },
        )

    # ── Device settings ────────────────────────────────────────────────────────

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    **self.config_entry.options,
                    CONF_BOILER_ENTITY:      user_input.get(CONF_BOILER_ENTITY) or None,
                    CONF_PERSON_ENTITIES:    user_input.get(CONF_PERSON_ENTITIES) or [],
                    CONF_ENABLE_DIAGNOSTICS: user_input.get(CONF_ENABLE_DIAGNOSTICS, DEFAULT_ENABLE_DIAGNOSTICS),
                },
            )
        opts = self.config_entry.options
        data = self.config_entry.data
        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema({
                vol.Optional(CONF_BOILER_ENTITY,
                    description={"suggested_value": opts.get(CONF_BOILER_ENTITY) or data.get(CONF_BOILER_ENTITY)}
                ): selector.EntitySelector(selector.EntitySelectorConfig(
                    domain=["climate", "switch", "input_boolean"]
                )),
                vol.Optional(CONF_PERSON_ENTITIES,
                    description={"suggested_value": opts.get(CONF_PERSON_ENTITIES) or data.get(CONF_PERSON_ENTITIES, [])}
                ): selector.EntitySelector(selector.EntitySelectorConfig(domain="person", multiple=True)),
                vol.Optional(CONF_ENABLE_DIAGNOSTICS,
                    default=opts.get(CONF_ENABLE_DIAGNOSTICS, data.get(CONF_ENABLE_DIAGNOSTICS, DEFAULT_ENABLE_DIAGNOSTICS))
                ): selector.BooleanSelector(),
            }),
        )

    # ── Group management menu ──────────────────────────────────────────────────

    async def async_step_groups(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        rooms = self._all_rooms()
        options: dict[str, str] = {"create_group": "Create a new room group"}
        if rooms:
            options["edit_group"]   = "Edit a room group (add / remove members)"
            options["remove_group"] = "Remove a room group"
        return self.async_show_menu(step_id="groups", menu_options=options)

    # ── Create group — step 1: name ────────────────────────────────────────────

    async def async_step_create_group(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input.get("room_name", "").strip()
            if not name:
                errors["room_name"] = "required"
            else:
                self._new_room_name = name
                return await self.async_step_create_group_devices()
        return self.async_show_form(
            step_id="create_group",
            data_schema=vol.Schema({vol.Required("room_name"): selector.TextSelector()}),
            errors=errors,
        )

    # ── Create group — step 2: member selection ────────────────────────────────

    async def async_step_create_group_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Pick member climate entities — any thermostat HA knows about.

        Already-grouped entities are excluded so one device = one group.
        """
        errors: dict[str, str] = {}
        already_grouped = self._grouped_entity_ids()

        if user_input is not None:
            chosen = user_input.get("member_ids") or []
            if not chosen:
                errors["member_ids"] = "required"
            else:
                self._new_member_ids = chosen
                return await self.async_step_create_group_sensors()

        return self.async_show_form(
            step_id="create_group_devices",
            data_schema=vol.Schema({
                vol.Required("member_ids"): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="climate",
                        multiple=True,
                        # Exclude already-grouped entities
                        exclude_entities=list(already_grouped),
                    )
                ),
            }),
            description_placeholders={"room_name": self._new_room_name},
            errors=errors,
        )

    # ── Create group — step 3: optional extra sensors ─────────────────────────

    async def async_step_create_group_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        if user_input is not None:
            self._new_temp_sensors = user_input.get("temp_sensors") or []
            return await self._do_create_group()
        return self.async_show_form(
            step_id="create_group_sensors",
            data_schema=vol.Schema({
                vol.Optional("temp_sensors"): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor", device_class="temperature", multiple=True
                    )
                ),
            }),
            description_placeholders={
                "room_name":  self._new_room_name,
                "member_count": str(len(self._new_member_ids)),
            },
        )

    async def _do_create_group(self) -> config_entries.FlowResult:
        import uuid as _uuid
        store = self._store()
        room_id   = str(_uuid.uuid4())
        room_data = {
            "name":         self._new_room_name,
            "members":      self._new_member_ids,   # HA entity IDs
            "temp_sensors": self._new_temp_sensors,
            "schedule":     [],
        }
        if store:
            await store.async_save_room(room_id, room_data)
        self.hass.bus.async_fire(f"{DOMAIN}_room_added", {
            "entry_id":  self.config_entry.entry_id,
            "room_id":   room_id,
            "room_data": room_data,
        })
        return self.async_create_entry(title="", data=self.config_entry.options)

    # ── Edit group — step 1: pick group ────────────────────────────────────────

    async def async_step_edit_group(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        rooms = self._all_rooms()
        if not rooms:
            return self.async_create_entry(title="", data=self.config_entry.options)
        if user_input is not None:
            chosen_name = user_input.get("room_name")
            for rid, rdata in rooms.items():
                if rdata.get("name") == chosen_name:
                    self._edit_room_id   = rid
                    self._edit_room_name = chosen_name
                    break
            return await self.async_step_edit_group_members()
        room_names = sorted(rd.get("name", rid) for rid, rd in rooms.items())
        return self.async_show_form(
            step_id="edit_group",
            data_schema=vol.Schema({
                vol.Required("room_name"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=room_names, mode=selector.SelectSelectorMode.DROPDOWN)
                ),
            }),
        )

    # ── Edit group — step 2: add/remove members ────────────────────────────────

    async def async_step_edit_group_members(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Show EntitySelector — current members pre-selected, ungrouped available."""
        errors: dict[str, str] = {}
        rooms = self._all_rooms()
        current_room    = rooms.get(self._edit_room_id, {})
        current_members = current_room.get("members", [])
        # Entities available: currently in this room OR not in any room
        other_grouped   = self._grouped_entity_ids(exclude_room_id=self._edit_room_id)

        if user_input is not None:
            new_members = user_input.get("member_ids") or []
            if not new_members:
                errors["member_ids"] = "required"
            else:
                await self._do_edit_group(current_members, new_members)
                return self.async_create_entry(title="", data=self.config_entry.options)

        return self.async_show_form(
            step_id="edit_group_members",
            data_schema=vol.Schema({
                vol.Required("member_ids", default=current_members): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="climate",
                        multiple=True,
                        exclude_entities=list(other_grouped),
                    )
                ),
            }),
            description_placeholders={
                "room_name":       self._edit_room_name,
                "current_members": ", ".join(current_members) if current_members else "none",
            },
            errors=errors,
        )

    async def _do_edit_group(self, old_members: list[str], new_members: list[str]) -> None:
        store = self._store()
        rooms = self._all_rooms()
        room_data = dict(rooms.get(self._edit_room_id, {}))
        room_data["members"] = new_members
        if store:
            await store.async_save_room(self._edit_room_id, room_data)
        added   = [m for m in new_members if m not in old_members]
        removed = [m for m in old_members if m not in new_members]
        self.hass.bus.async_fire(f"{DOMAIN}_room_members_changed", {
            "entry_id":     self.config_entry.entry_id,
            "room_id":      self._edit_room_id,
            "added_trvs":   added,
            "removed_trvs": removed,
        })

    # ── Remove group ───────────────────────────────────────────────────────────

    async def async_step_remove_group(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        rooms = self._all_rooms()
        if not rooms:
            return self.async_create_entry(title="", data=self.config_entry.options)
        if user_input is not None:
            chosen = user_input.get("room_name")
            if chosen:
                await self._do_remove_group(chosen)
            return self.async_create_entry(title="", data=self.config_entry.options)
        room_names = sorted(rd.get("name", rid) for rid, rd in rooms.items())
        return self.async_show_form(
            step_id="remove_group",
            data_schema=vol.Schema({
                vol.Required("room_name"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=room_names, mode=selector.SelectSelectorMode.DROPDOWN)
                ),
            }),
        )

    async def _do_remove_group(self, room_name: str) -> None:
        store = self._store()
        if not store:
            return
        for room_id, rdata in list(self._all_rooms().items()):
            if rdata.get("name") == room_name:
                freed = rdata.get("members", [])
                await store.async_remove_room(room_id)
                self.hass.bus.async_fire(f"{DOMAIN}_room_removed", {
                    "entry_id":   self.config_entry.entry_id,
                    "room_id":    room_id,
                    "freed_trvs": freed,
                })
                break


_L.warning("HIVE_DIAG config_flow: module load COMPLETE")
