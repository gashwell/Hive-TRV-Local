"""Config flow for Hive TRV Local v4.

Three entry types share one domain:
  - TRV device    (multi-instance, one per physical TRV)
  - Receiver      (multi-instance, one per SLR1/SLR2/OTR1)
  - Groups        (single instance — room group manager)

The initial setup shows a menu: Add TRV / Add Receiver / Manage Groups.
Each creates a separate config entry. This is similar to how andrew-codechimp's
integration works per device, but extended with the group management layer.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er, selector

from .const import (
    CONF_BOILER_ENTITY, CONF_DEVICE_NAME, CONF_ENABLE_DIAG,
    CONF_ENTRY_TYPE, CONF_MODEL, CONF_MQTT_TOPIC,
    CONF_SHOW_HEAT_SCHED, CONF_SHOW_WATER_SCHED,
    CONFIG_VERSION_DEVICE, CONFIG_VERSION_GROUPS,
    DATA_BOILER, DATA_STORE, DOMAIN,
    ENTRY_TYPE_GROUPS, ENTRY_TYPE_RECEIVER, ENTRY_TYPE_TRV,
    EVENT_ROOM_ADDED, EVENT_ROOM_REMOVED, EVENT_ROOM_UPDATED,
    MODEL_OTR1, MODEL_SLR1, MODEL_SLR2, RECEIVER_MODELS,
)

_LOGGER = logging.getLogger(f"custom_components.{DOMAIN}.config_flow")


# ── Main config flow (entry point) ─────────────────────────────────────────────

class HiveTRVLocalConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Entry-point flow — shows menu to add TRV, receiver, or group manager."""

    VERSION = CONFIG_VERSION_DEVICE

    def __init__(self) -> None:
        super().__init__()
        self._trv_topic: str = ""
        self._trv_name:  str = ""
        self._recv_topic: str = ""
        self._recv_name:  str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        return self.async_show_menu(
            step_id="user",
            menu_options={
                "add_trv":      "Add a TRV",
                "add_receiver": "Add a receiver (SLR1 / SLR2 / OTR1)",
                "setup_groups": "Set up room group manager",
            },
        )

    # ── Add TRV ────────────────────────────────────────────────────────────────

    async def async_step_add_trv(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Step 1 — browse and select a Z2M climate entity or enter topic manually."""
        errors: dict = {}

        # Build list of already-registered TRV topics so we can exclude them
        already_registered: set[str] = set()
        for entry in self._async_current_entries():
            if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_TRV:
                already_registered.add(entry.data.get(CONF_MQTT_TOPIC, ""))

        # Discover Z2M MQTT climate entities from the entity registry
        from homeassistant.helpers import entity_registry as er, device_registry as dr
        ent_reg = er.async_get(self.hass)
        dev_reg = dr.async_get(self.hass)

        # Build options: {topic: "Friendly Name (topic)"}
        # Z2M sets unique_id = topic for its climate entities
        z2m_options: dict[str, str] = {}
        for entry in ent_reg.entities.values():
            if entry.entity_id.split(".")[0] != "climate":
                continue
            if entry.platform != "mqtt":
                continue
            uid = entry.unique_id or ""
            # Exclude our own group entities
            if uid.startswith("room_") and uid.endswith("_climate"):
                continue
            # uid is typically the Z2M topic e.g. "zigbee2mqtt/Living Room TRV"
            topic = uid
            if topic in already_registered:
                continue
            # Get friendly name from entity or device
            friendly = entry.name or entry.original_name or ""
            if not friendly and entry.device_id:
                dev = dev_reg.async_get(entry.device_id)
                friendly = (dev.name_by_user or dev.name or "") if dev else ""
            label = f"{friendly} ({topic})" if friendly else topic
            z2m_options[topic] = label

        if user_input is not None:
            selected = user_input.get("z2m_entity", "").strip()
            manual   = user_input.get(CONF_MQTT_TOPIC, "").strip()
            topic    = selected or manual
            if not topic:
                errors["z2m_entity"] = "required"
            else:
                # Store topic and move to name confirmation step
                self._trv_topic = topic
                # Pre-fill name from the options dict if available
                self._trv_name  = z2m_options.get(topic, "").split(" (")[0] or topic.split("/")[-1]
                return await self.async_step_add_trv_confirm()

        schema: dict = {}
        if z2m_options:
            schema[vol.Optional("z2m_entity")] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=k, label=v)
                        for k, v in sorted(z2m_options.items(), key=lambda x: x[1])
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        # Always show manual entry as fallback
        schema[vol.Optional(CONF_MQTT_TOPIC)] = selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
        )

        count = len(z2m_options)
        return self.async_show_form(
            step_id="add_trv",
            data_schema=vol.Schema(schema),
            description_placeholders={
                "count": str(count),
                "hint": (
                    f"{count} Z2M TRV(s) available. Select one or enter a topic manually below."
                    if count > 0 else
                    "No Z2M TRVs detected yet. Enter the full MQTT topic manually, "
                    "e.g. zigbee2mqtt/Living Room TRV"
                ),
            },
            errors=errors,
        )

    async def async_step_add_trv_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Step 2 — confirm or edit the device name."""
        errors: dict = {}

        if user_input is not None:
            name = user_input.get(CONF_DEVICE_NAME, "").strip()
            if not name:
                errors[CONF_DEVICE_NAME] = "required"
            else:
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_ENTRY_TYPE:  ENTRY_TYPE_TRV,
                        CONF_MQTT_TOPIC:  self._trv_topic,
                        CONF_DEVICE_NAME: name,
                        CONF_MODEL:       "TRV",
                    },
                )

        return self.async_show_form(
            step_id="add_trv_confirm",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_DEVICE_NAME,
                    description={"suggested_value": self._trv_name},
                ): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                ),
            }),
            description_placeholders={
                "topic": self._trv_topic,
            },
            errors=errors,
        )

    # ── Add Receiver ───────────────────────────────────────────────────────────

    async def async_step_add_receiver(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Step 1 — browse and select a Z2M climate entity for the receiver."""
        errors: dict = {}

        already_registered: set[str] = set()
        for entry in self._async_current_entries():
            if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_RECEIVER:
                already_registered.add(entry.data.get(CONF_MQTT_TOPIC, ""))

        from homeassistant.helpers import entity_registry as er, device_registry as dr
        ent_reg = er.async_get(self.hass)
        dev_reg = dr.async_get(self.hass)

        z2m_options: dict[str, str] = {}
        for entry in ent_reg.entities.values():
            if entry.entity_id.split(".")[0] != "climate":
                continue
            if entry.platform != "mqtt":
                continue
            uid = entry.unique_id or ""
            if uid.startswith("room_") and uid.endswith("_climate"):
                continue
            topic = uid
            if topic in already_registered:
                continue
            friendly = entry.name or entry.original_name or ""
            if not friendly and entry.device_id:
                dev = dev_reg.async_get(entry.device_id)
                friendly = (dev.name_by_user or dev.name or "") if dev else ""
            label = f"{friendly} ({topic})" if friendly else topic
            z2m_options[topic] = label

        if user_input is not None:
            selected = user_input.get("z2m_entity", "").strip()
            manual   = user_input.get(CONF_MQTT_TOPIC, "").strip()
            topic    = selected or manual
            if not topic:
                errors["z2m_entity"] = "required"
            else:
                self._recv_topic = topic
                self._recv_name  = z2m_options.get(topic, "").split(" (")[0] or topic.split("/")[-1]
                return await self.async_step_add_receiver_confirm()

        schema: dict = {}
        if z2m_options:
            schema[vol.Optional("z2m_entity")] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=k, label=v)
                        for k, v in sorted(z2m_options.items(), key=lambda x: x[1])
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        schema[vol.Optional(CONF_MQTT_TOPIC)] = selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
        )

        count = len(z2m_options)
        return self.async_show_form(
            step_id="add_receiver",
            data_schema=vol.Schema(schema),
            description_placeholders={
                "count": str(count),
                "hint": (
                    f"{count} Z2M device(s) available. Select one or enter a topic manually."
                    if count > 0 else
                    "No Z2M devices detected yet. Enter the full MQTT topic manually, "
                    "e.g. zigbee2mqtt/Hive Receiver"
                ),
            },
            errors=errors,
        )

    async def async_step_add_receiver_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Step 2 — confirm name and select model."""
        errors: dict = {}

        if user_input is not None:
            name  = user_input.get(CONF_DEVICE_NAME, "").strip()
            model = user_input.get(CONF_MODEL, MODEL_SLR1)
            if not name:
                errors[CONF_DEVICE_NAME] = "required"
            else:
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_ENTRY_TYPE:      ENTRY_TYPE_RECEIVER,
                        CONF_MQTT_TOPIC:      self._recv_topic,
                        CONF_DEVICE_NAME:     name,
                        CONF_MODEL:           model,
                        CONF_SHOW_HEAT_SCHED: user_input.get(CONF_SHOW_HEAT_SCHED, True),
                        CONF_SHOW_WATER_SCHED:user_input.get(CONF_SHOW_WATER_SCHED, True),
                    },
                )

        return self.async_show_form(
            step_id="add_receiver_confirm",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_DEVICE_NAME,
                    description={"suggested_value": self._recv_name},
                ): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                ),
                vol.Required(CONF_MODEL, default=MODEL_SLR1): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=RECEIVER_MODELS,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_SHOW_HEAT_SCHED, default=True): selector.BooleanSelector(),
                vol.Optional(CONF_SHOW_WATER_SCHED, default=True): selector.BooleanSelector(),
            }),
            description_placeholders={
                "topic": self._recv_topic,
            },
            errors=errors,
        )

    # ── Setup Groups ───────────────────────────────────────────────────────────

    async def async_step_setup_groups(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Create the single group manager entry (only one allowed)."""
        # Check if groups entry already exists
        for entry in self._async_current_entries():
            if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_GROUPS:
                return self.async_abort(reason="groups_already_configured")

        return self.async_create_entry(
            title="Room Groups",
            data={
                CONF_ENTRY_TYPE:    ENTRY_TYPE_GROUPS,
                CONF_BOILER_ENTITY: None,
                CONF_ENABLE_DIAG:   False,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        entry_type = config_entry.data.get(CONF_ENTRY_TYPE)
        if entry_type in (ENTRY_TYPE_TRV, ENTRY_TYPE_RECEIVER):
            return HiveDeviceOptionsFlow()
        return HiveGroupsOptionsFlow()


# ── Device options flow ────────────────────────────────────────────────────────

class HiveDeviceOptionsFlow(config_entries.OptionsFlow):
    """Options for a TRV or receiver device entry."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        entry_type = self.config_entry.data.get(CONF_ENTRY_TYPE)
        errors: dict = {}

        if user_input is not None:
            return self.async_create_entry(title="", data={
                **self.config_entry.data,
                CONF_DEVICE_NAME:     user_input.get(CONF_DEVICE_NAME, self.config_entry.title),
                CONF_MQTT_TOPIC:      user_input.get(CONF_MQTT_TOPIC, ""),
                CONF_SHOW_HEAT_SCHED: user_input.get(CONF_SHOW_HEAT_SCHED, True),
                CONF_SHOW_WATER_SCHED:user_input.get(CONF_SHOW_WATER_SCHED, True),
            })

        data = self.config_entry.data
        schema = {
            vol.Required(CONF_DEVICE_NAME, default=data.get(CONF_DEVICE_NAME, "")): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
            vol.Required(CONF_MQTT_TOPIC, default=data.get(CONF_MQTT_TOPIC, "")): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
        }
        if entry_type == ENTRY_TYPE_RECEIVER:
            schema[vol.Optional(CONF_SHOW_HEAT_SCHED,  default=data.get(CONF_SHOW_HEAT_SCHED,  True))] = selector.BooleanSelector()
            schema[vol.Optional(CONF_SHOW_WATER_SCHED, default=data.get(CONF_SHOW_WATER_SCHED, True))] = selector.BooleanSelector()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
            errors=errors,
        )


# ── Groups options flow ────────────────────────────────────────────────────────

class HiveGroupsOptionsFlow(config_entries.OptionsFlow):
    """Options flow for the group manager entry."""

    def __init__(self) -> None:
        self._room_name:    str       = ""
        self._members:      list[str] = []
        self._sensors:      list[str] = []
        self._edit_room_id: str       = ""
        self._edit_name:    str       = ""

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _store(self):
        return self.hass.data.get(DOMAIN, {}).get(
            self.config_entry.entry_id, {}
        ).get(DATA_STORE)

    def _all_rooms(self) -> dict:
        s = self._store()
        return s.get_all_rooms() if s else {}

    def _grouped_eids(self, exclude: str | None = None) -> set[str]:
        grouped: set[str] = set()
        for rid, rd in self._all_rooms().items():
            if rid == exclude:
                continue
            grouped.update(rd.get("members", []))
        return grouped

    def _registered_trv_entity_ids(self) -> list[str]:
        """Return climate entity IDs from registered TRV device entries.

        This is the definitive fix — we look at OUR OWN config entries
        for ENTRY_TYPE_TRV and get the entity_id from the entity registry
        using their unique_id pattern.
        """
        ent_reg = er.async_get(self.hass)
        result  = []
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data.get(CONF_ENTRY_TYPE) != ENTRY_TYPE_TRV:
                continue
            # Our climate entity unique_id = f"{DOMAIN}_{entry.entry_id}_climate"
            uid = f"{DOMAIN}_{entry.entry_id}_climate"
            for e in ent_reg.entities.values():
                if e.unique_id == uid and e.entity_id.startswith("climate."):
                    result.append(e.entity_id)
                    break
        _LOGGER.debug("Registered TRV entities: %s", result)
        return sorted(result)

    def _no_rooms_entry(self) -> config_entries.FlowResult:
        return self.async_create_entry(title="", data=self.config_entry.options)

    # ── Top menu ───────────────────────────────────────────────────────────────

    async def async_step_init(self, _=None) -> config_entries.FlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options={
                "settings":     "Settings (boiler, diagnostics)",
                "groups":       "Manage room groups",
            },
        )

    # ── Settings ───────────────────────────────────────────────────────────────

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        if user_input is not None:
            ed = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id, {})
            if bm := ed.get(DATA_BOILER):
                bm.update_boiler_entity(user_input.get(CONF_BOILER_ENTITY) or None)
            return self.async_create_entry(title="", data={
                **self.config_entry.options,
                CONF_BOILER_ENTITY: user_input.get(CONF_BOILER_ENTITY) or None,
                CONF_ENABLE_DIAG:   user_input.get(CONF_ENABLE_DIAG, False),
            })

        opts = {**self.config_entry.data, **(self.config_entry.options or {})}
        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_BOILER_ENTITY,
                    description={"suggested_value": opts.get(CONF_BOILER_ENTITY)},
                ): selector.EntitySelector(selector.EntitySelectorConfig(
                    domain=["climate", "switch", "input_boolean"]
                )),
                vol.Optional(
                    CONF_ENABLE_DIAG,
                    default=opts.get(CONF_ENABLE_DIAG, False),
                ): selector.BooleanSelector(),
            }),
        )

    # ── Groups menu ────────────────────────────────────────────────────────────

    async def async_step_groups(self, _=None) -> config_entries.FlowResult:
        return self.async_show_menu(
            step_id="groups",
            menu_options={
                "create_group": "Create a new room group",
                "edit_group":   "Edit group members",
                "set_schedule": "Set a heating schedule",
                "remove_group": "Remove a room group",
            },
        )

    # ── Create group ───────────────────────────────────────────────────────────

    async def async_step_create_group(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        errors: dict = {}
        if user_input is not None:
            name = user_input.get("room_name", "").strip()
            if not name:
                errors["room_name"] = "required"
            else:
                self._room_name = name
                return await self.async_step_create_group_members()
        return self.async_show_form(
            step_id="create_group",
            data_schema=vol.Schema({vol.Required("room_name"): selector.TextSelector()}),
            errors=errors,
        )

    async def async_step_create_group_members(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        errors: dict = {}
        registered = self._registered_trv_entity_ids()
        grouped    = self._grouped_eids()
        available  = [e for e in registered if e not in grouped]

        if user_input is not None:
            chosen = user_input.get("member_ids") or []
            if not chosen:
                errors["member_ids"] = "required"
            else:
                self._members = chosen
                return await self.async_step_create_group_sensors()

        return self.async_show_form(
            step_id="create_group_members",
            data_schema=vol.Schema({
                vol.Required("member_ids"): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="climate",
                        multiple=True,
                        include_entities=available if available else None,
                    )
                ),
            }),
            description_placeholders={
                "room_name": self._room_name,
                "count":     str(len(available)),
            },
            errors=errors,
        )

    async def async_step_create_group_sensors(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        if user_input is not None:
            self._sensors = user_input.get("temp_sensors") or []
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
                "room_name":    self._room_name,
                "member_count": str(len(self._members)),
            },
        )

    async def _do_create_group(self) -> config_entries.FlowResult:
        store   = self._store()
        room_id = str(uuid.uuid4())
        data    = {
            "name":         self._room_name,
            "members":      self._members,
            "temp_sensors": self._sensors,
            "schedule":     [],
        }
        if store:
            await store.async_save_room(room_id, data)

        # Suppress individual climate entities for grouped TRVs
        self._suppress_member_entities(self._members, hide=True)

        self.hass.bus.async_fire(EVENT_ROOM_ADDED, {
            "entry_id":  self.config_entry.entry_id,
            "room_id":   room_id,
            "room_data": data,
        })
        return self.async_create_entry(title="", data=self.config_entry.options)

    # ── Edit group ─────────────────────────────────────────────────────────────

    async def async_step_edit_group(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        rooms = self._all_rooms()
        if not rooms:
            return self._no_rooms_entry()

        if user_input is not None:
            for rid, rd in rooms.items():
                if rd.get("name") == user_input.get("room_name"):
                    self._edit_room_id = rid
                    self._edit_name    = user_input["room_name"]
                    break
            return await self.async_step_edit_group_members()

        return self.async_show_form(
            step_id="edit_group",
            data_schema=vol.Schema({
                vol.Required("room_name"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=sorted(rd.get("name", rid) for rid, rd in rooms.items()),
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
        )

    async def async_step_edit_group_members(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        errors: dict = {}
        current       = self._all_rooms().get(self._edit_room_id, {}).get("members", [])
        registered    = self._registered_trv_entity_ids()
        other_grouped = self._grouped_eids(exclude=self._edit_room_id)
        available     = [e for e in registered if e not in other_grouped]
        selectable    = sorted(set(current) | set(available))

        if user_input is not None:
            new_members = user_input.get("member_ids") or []
            if not new_members:
                errors["member_ids"] = "required"
            else:
                store = self._store()
                rd    = dict(self._all_rooms().get(self._edit_room_id, {}))
                rd["members"] = new_members
                if store:
                    await store.async_save_room(self._edit_room_id, rd)

                # Restore entities that left, suppress entities that joined
                removed = [m for m in current if m not in new_members]
                added   = [m for m in new_members if m not in current]
                self._suppress_member_entities(removed, hide=False)
                self._suppress_member_entities(added, hide=True)

                self.hass.bus.async_fire(EVENT_ROOM_UPDATED, {
                    "entry_id":        self.config_entry.entry_id,
                    "room_id":         self._edit_room_id,
                    "new_members":     new_members,
                    "added_members":   added,
                    "removed_members": removed,
                })
                return self.async_create_entry(title="", data=self.config_entry.options)

        return self.async_show_form(
            step_id="edit_group_members",
            data_schema=vol.Schema({
                vol.Required("member_ids", default=current): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="climate",
                        multiple=True,
                        include_entities=selectable if selectable else None,
                    )
                ),
            }),
            description_placeholders={"room_name": self._edit_name},
            errors=errors,
        )

    # ── Set schedule ───────────────────────────────────────────────────────────

    async def async_step_set_schedule(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        rooms = self._all_rooms()
        if not rooms:
            return self._no_rooms_entry()

        if user_input is not None:
            for rid, rd in rooms.items():
                if rd.get("name") == user_input.get("room_name"):
                    self._edit_room_id = rid
                    self._edit_name    = user_input["room_name"]
                    break
            return await self.async_step_set_schedule_preset()

        return self.async_show_form(
            step_id="set_schedule",
            data_schema=vol.Schema({
                vol.Required("room_name"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=sorted(rd.get("name", rid) for rid, rd in rooms.items()),
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
        )

    async def async_step_set_schedule_preset(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        PRESETS = {
            "comfort": [
                {"days": [0,1,2,3,4], "time": "06:30", "temperature": 21.0},
                {"days": [0,1,2,3,4], "time": "09:00", "temperature": 18.0},
                {"days": [0,1,2,3,4], "time": "17:00", "temperature": 21.0},
                {"days": [0,1,2,3,4], "time": "22:30", "temperature": 16.0},
                {"days": [5,6],       "time": "08:00", "temperature": 21.0},
                {"days": [5,6],       "time": "23:00", "temperature": 16.0},
            ],
            "eco": [
                {"days": [0,1,2,3,4], "time": "07:00", "temperature": 19.0},
                {"days": [0,1,2,3,4], "time": "09:00", "temperature": 16.0},
                {"days": [0,1,2,3,4], "time": "17:30", "temperature": 19.0},
                {"days": [0,1,2,3,4], "time": "22:30", "temperature": 16.0},
                {"days": [5,6],       "time": "08:30", "temperature": 19.0},
                {"days": [5,6],       "time": "23:00", "temperature": 16.0},
            ],
        }
        if user_input is not None:
            preset   = user_input.get("preset", "keep")
            store    = self._store()
            current  = self._all_rooms().get(self._edit_room_id, {}).get("schedule", [])
            schedule = [] if preset == "clear" else PRESETS.get(preset, current)
            if store and preset != "keep":
                await store.async_set_room_schedule(self._edit_room_id, schedule)
            ed = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id, {})
            rc = ed.get("rooms", {}).get(self._edit_room_id)
            if rc:
                if schedule:
                    self.hass.async_create_task(rc.async_set_schedule(schedule))
                else:
                    rc.clear_schedule()
            return self.async_create_entry(title="", data=self.config_entry.options)

        n = len(self._all_rooms().get(self._edit_room_id, {}).get("schedule", []))
        return self.async_show_form(
            step_id="set_schedule_preset",
            data_schema=vol.Schema({
                vol.Required("preset", default="comfort"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value="comfort", label="Comfort — 21°C days, 16°C nights"),
                            selector.SelectOptionDict(value="eco",     label="Eco — 19°C days, 16°C nights"),
                            selector.SelectOptionDict(value="keep",    label=f"Keep existing ({n} slots)"),
                            selector.SelectOptionDict(value="clear",   label="Clear (manual mode)"),
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
            description_placeholders={"room_name": self._edit_name},
        )

    # ── Remove group ───────────────────────────────────────────────────────────

    async def async_step_remove_group(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        rooms = self._all_rooms()
        if not rooms:
            return self._no_rooms_entry()

        if user_input is not None:
            chosen = user_input.get("room_name")
            if chosen:
                store = self._store()
                for rid, rd in list(rooms.items()):
                    if rd.get("name") == chosen:
                        if store:
                            await store.async_remove_room(rid)
                        # Restore all member climate entities
                        self._suppress_member_entities(rd.get("members", []), hide=False)
                        self.hass.bus.async_fire(EVENT_ROOM_REMOVED, {
                            "entry_id":      self.config_entry.entry_id,
                            "room_id":       rid,
                            "freed_members": rd.get("members", []),
                        })
                        break
            return self.async_create_entry(title="", data=self.config_entry.options)

        return self.async_show_form(
            step_id="remove_group",
            data_schema=vol.Schema({
                vol.Required("room_name"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=sorted(rd.get("name", rid) for rid, rd in rooms.items()),
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
        )

    # ── Entity suppression ─────────────────────────────────────────────────────

    def _suppress_member_entities(self, entity_ids: list[str], hide: bool) -> None:
        """Hide or restore individual TRV climate entities.

        When a TRV joins a group its individual climate entity is hidden
        (hidden_by = HIDDEN_BY_INTEGRATION). When it leaves the group the
        entity is restored.
        """
        from homeassistant.helpers import entity_registry as er
        from homeassistant.helpers.entity_registry import RegistryEntryHider

        ent_reg = er.async_get(self.hass)
        for entity_id in entity_ids:
            entry = ent_reg.async_get(entity_id)
            if entry is None:
                continue
            if hide:
                ent_reg.async_update_entity(
                    entity_id,
                    hidden_by=RegistryEntryHider.INTEGRATION,
                )
            else:
                # Only restore if we were the ones who hid it
                if entry.hidden_by == RegistryEntryHider.INTEGRATION:
                    ent_reg.async_update_entity(entity_id, hidden_by=None)
            _LOGGER.info(
                "Entity %s %s", entity_id, "hidden (in group)" if hide else "restored (left group)"
            )

