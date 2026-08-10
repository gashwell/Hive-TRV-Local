"""Config flow for Hive TRV Local v3.

Member selection uses Z2M MQTT topics directly — no entity registry detection.
The user types or picks Z2M device topics (e.g. zigbee2mqtt/Living Room TRV)
and we resolve them to HA entity IDs at group creation time.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import mqtt
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_BOILER_ENTITY, CONF_ENABLE_DIAGNOSTICS, CONF_Z2M_BASE_TOPIC,
    CONFIG_VERSION, DATA_BOILER, DATA_STORE, DOMAIN,
    ENTRY_DEFAULTS, EVENT_ROOM_ADDED, EVENT_ROOM_REMOVED, EVENT_ROOM_UPDATED,
)

_LOGGER = logging.getLogger(f"custom_components.{DOMAIN}.config_flow")


class HiveTRVLocalConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Single-instance config flow."""

    VERSION = CONFIG_VERSION

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(
                title="Hive TRV Local",
                data={
                    **ENTRY_DEFAULTS,
                    CONF_Z2M_BASE_TOPIC: user_input.get(CONF_Z2M_BASE_TOPIC, "zigbee2mqtt"),
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Optional(CONF_Z2M_BASE_TOPIC, default="zigbee2mqtt"): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                ),
            }),
            description_placeholders={
                "info": "Enter your Zigbee2MQTT base topic. "
                        "Default is 'zigbee2mqtt'. "
                        "Configure room groups after installation via Configure."
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "HiveTRVLocalOptionsFlow":
        return HiveTRVLocalOptionsFlow()


class HiveTRVLocalOptionsFlow(config_entries.OptionsFlow):
    """Options flow — settings and group management."""

    def __init__(self) -> None:
        self._room_name:    str       = ""
        self._members:      list[str] = []  # Z2M topics
        self._sensors:      list[str] = []  # HA sensor entity IDs
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

    def _grouped_topics(self, exclude: str | None = None) -> set[str]:
        grouped: set[str] = set()
        for rid, rd in self._all_rooms().items():
            if rid == exclude:
                continue
            grouped.update(rd.get("mqtt_topics", []))
        return grouped

    def _base_topic(self) -> str:
        return (self.config_entry.options or self.config_entry.data).get(
            CONF_Z2M_BASE_TOPIC, "zigbee2mqtt"
        )

    async def _discovered_z2m_topics(self) -> list[str]:
        """Return Z2M device topics by querying hass.states for MQTT climate entities.

        Looks at all climate entities in hass.states and returns those whose
        entity_id is registered on the mqtt platform — no model filtering.
        Also returns the raw topic from the entity's unique_id where available.
        """
        from homeassistant.helpers import entity_registry as er
        base = self._base_topic()
        ent_reg = er.async_get(self.hass)
        topics: list[str] = []
        seen: set[str] = set()

        for entry in ent_reg.entities.values():
            if entry.entity_id.split(".")[0] != "climate":
                continue
            if entry.platform != "mqtt":
                continue
            # Exclude our own group entities
            uid = entry.unique_id or ""
            if uid.startswith("room_") and uid.endswith("_climate"):
                continue
            # Z2M unique_ids are typically the topic: "zigbee2mqtt/DeviceName"
            # Extract device name from uid if it starts with our base topic
            if uid.startswith(f"{base}/"):
                topic = uid  # full topic e.g. "zigbee2mqtt/Living Room TRV"
            else:
                # Fall back to constructing from the entity_id slug
                topic = f"{base}/{entry.entity_id.replace('climate.', '').replace('_', ' ')}"
            if topic not in seen:
                seen.add(topic)
                topics.append(topic)

        # Also check states for any that slipped through
        for entity_id, state in self.hass.states.items():
            if not entity_id.startswith("climate."):
                continue
            ent = ent_reg.async_get(entity_id)
            if not ent or ent.platform != "mqtt":
                continue
            uid = ent.unique_id or ""
            if uid.startswith("room_") and uid.endswith("_climate"):
                continue
            if uid.startswith(f"{base}/") and uid not in seen:
                seen.add(uid)
                topics.append(uid)

        _LOGGER.warning("Z2M topic discovery: found %d topic(s): %s", len(topics), topics)
        return sorted(topics)

    def _topic_to_entity_id(self, topic: str) -> str | None:
        """Resolve a Z2M topic to a HA climate entity_id via the entity registry."""
        from homeassistant.helpers import entity_registry as er
        ent_reg = er.async_get(self.hass)
        # Z2M sets unique_id = topic for climate entities
        for entry in ent_reg.entities.values():
            if entry.entity_id.split(".")[0] != "climate":
                continue
            if (entry.unique_id or "") == topic:
                return entry.entity_id
        # Fallback: try topic as unique_id without base
        device_name = topic.split("/", 1)[-1] if "/" in topic else topic
        for entry in ent_reg.entities.values():
            if entry.entity_id.split(".")[0] != "climate":
                continue
            uid = entry.unique_id or ""
            if device_name.lower() in uid.lower():
                return entry.entity_id
        return None

    def _topics_to_entity_ids(self, topics: list[str]) -> list[str]:
        """Convert a list of Z2M topics to HA entity IDs, logging any failures."""
        result = []
        for topic in topics:
            eid = self._topic_to_entity_id(topic)
            if eid:
                result.append(eid)
                _LOGGER.info("Topic resolved: %s → %s", topic, eid)
            else:
                _LOGGER.warning(
                    "Topic %s could not be resolved to a climate entity — "
                    "check Z2M is running and the device has been seen at least once",
                    topic,
                )
        return result

    def _no_rooms_entry(self) -> config_entries.FlowResult:
        return self.async_create_entry(title="", data=self.config_entry.options)

    # ── Top-level menu ─────────────────────────────────────────────────────────

    async def async_step_init(self, _=None) -> config_entries.FlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options={
                "settings": "Settings (boiler, Z2M topic, diagnostics)",
                "groups":   "Manage room groups",
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
                CONF_BOILER_ENTITY:      user_input.get(CONF_BOILER_ENTITY) or None,
                CONF_ENABLE_DIAGNOSTICS: user_input.get(CONF_ENABLE_DIAGNOSTICS, False),
                CONF_Z2M_BASE_TOPIC:     user_input.get(CONF_Z2M_BASE_TOPIC, "zigbee2mqtt"),
            })

        opts = {**self.config_entry.data, **(self.config_entry.options or {})}
        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_Z2M_BASE_TOPIC,
                    description={"suggested_value": opts.get(CONF_Z2M_BASE_TOPIC, "zigbee2mqtt")},
                ): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                ),
                vol.Optional(
                    CONF_BOILER_ENTITY,
                    description={"suggested_value": opts.get(CONF_BOILER_ENTITY)},
                ): selector.EntitySelector(selector.EntitySelectorConfig(
                    domain=["climate", "switch", "input_boolean"]
                )),
                vol.Optional(
                    CONF_ENABLE_DIAGNOSTICS,
                    default=opts.get(CONF_ENABLE_DIAGNOSTICS, False),
                ): selector.BooleanSelector(),
            }),
        )

    # ── Group management menu ──────────────────────────────────────────────────

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
            data_schema=vol.Schema({
                vol.Required("room_name"): selector.TextSelector(),
            }),
            errors=errors,
        )

    async def async_step_create_group_members(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        errors: dict = {}
        base            = self._base_topic()
        discovered      = await self._discovered_z2m_topics()
        grouped_topics  = self._grouped_topics()
        available       = [t for t in discovered if t not in grouped_topics]

        if user_input is not None:
            raw = user_input.get("mqtt_topics", "")
            # Accept comma-separated topics entered manually or selected from list
            topics = [t.strip() for t in raw.replace("\n", ",").split(",") if t.strip()]
            if not topics:
                errors["mqtt_topics"] = "required"
            else:
                self._members = topics
                return await self.async_step_create_group_sensors()

        # Show available topics as a helper hint
        hint_lines = "\n".join(f"• {t}" for t in available) if available else f"None detected yet — Z2M base topic: {base}"

        return self.async_show_form(
            step_id="create_group_members",
            data_schema=vol.Schema({
                vol.Required("mqtt_topics"): selector.TextSelector(
                    selector.TextSelectorConfig(
                        multiline=True,
                        type=selector.TextSelectorType.TEXT,
                    )
                ),
            }),
            description_placeholders={
                "room_name":  self._room_name,
                "base_topic": base,
                "hint":       hint_lines,
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
        store    = self._store()
        room_id  = str(uuid.uuid4())
        # Resolve topics to entity IDs now
        entities = self._topics_to_entity_ids(self._members)
        data = {
            "name":         self._room_name,
            "mqtt_topics":  self._members,   # store raw topics for display/edit
            "members":      entities,         # resolved entity IDs for control
            "temp_sensors": self._sensors,
            "schedule":     [],
        }
        if store:
            await store.async_save_room(room_id, data)
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
        room_data     = self._all_rooms().get(self._edit_room_id, {})
        current_topics = room_data.get("mqtt_topics", [])
        base           = self._base_topic()

        if user_input is not None:
            raw    = user_input.get("mqtt_topics", "")
            topics = [t.strip() for t in raw.replace("\n", ",").split(",") if t.strip()]
            if not topics:
                errors["mqtt_topics"] = "required"
            else:
                entities = self._topics_to_entity_ids(topics)
                store = self._store()
                rd    = dict(room_data)
                rd["mqtt_topics"] = topics
                rd["members"]     = entities
                if store:
                    await store.async_save_room(self._edit_room_id, rd)
                self.hass.bus.async_fire(EVENT_ROOM_UPDATED, {
                    "entry_id":    self.config_entry.entry_id,
                    "room_id":     self._edit_room_id,
                    "new_members": entities,
                })
                return self.async_create_entry(title="", data=self.config_entry.options)

        return self.async_show_form(
            step_id="edit_group_members",
            data_schema=vol.Schema({
                vol.Required(
                    "mqtt_topics",
                    description={"suggested_value": ", ".join(current_topics)},
                ): selector.TextSelector(
                    selector.TextSelectorConfig(
                        multiline=True,
                        type=selector.TextSelectorType.TEXT,
                    )
                ),
            }),
            description_placeholders={
                "room_name":  self._edit_name,
                "base_topic": base,
            },
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
