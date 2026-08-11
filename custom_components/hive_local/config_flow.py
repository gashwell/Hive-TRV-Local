"""Config flow for Hive Local v5.

Single config entry. All device and room management is in the options flow.
Setup just asks for Z2M base topic.
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
    CONF_BOILER_ENTITY, CONF_ENABLE_DIAG, CONF_Z2M_BASE_TOPIC,
    DATA_COORDINATOR, DEFAULT_Z2M_TOPIC, DEVICE_TYPE_RECEIVER,
    DEVICE_TYPE_SENSOR, DEVICE_TYPE_TRV, DOMAIN,
    MODEL_OTR1, MODEL_SLR1, MODEL_SLR2, RECEIVER_MODELS,
)

_LOGGER = logging.getLogger(__name__)


class HiveLocalConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Initial setup — just the Z2M base topic."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(
                title="Hive Local",
                data={
                    CONF_Z2M_BASE_TOPIC: user_input.get(
                        CONF_Z2M_BASE_TOPIC, DEFAULT_Z2M_TOPIC
                    ).strip(),
                    CONF_BOILER_ENTITY:  None,
                    CONF_ENABLE_DIAG:    False,
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_Z2M_BASE_TOPIC,
                    default=DEFAULT_Z2M_TOPIC,
                ): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                ),
            }),
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: config_entries.ConfigEntry) -> "HiveLocalOptionsFlow":
        return HiveLocalOptionsFlow()


class HiveLocalOptionsFlow(config_entries.OptionsFlow):
    """Full management — devices, rooms, settings."""

    def __init__(self) -> None:
        # Device wizard state
        self._dev_type:    str  = DEVICE_TYPE_TRV
        self._dev_topic:   str  = ""
        self._dev_name:    str  = ""
        self._dev_model:   str  = MODEL_SLR1
        self._dev_id:      str  = ""
        # Room wizard state
        self._room_name:   str        = ""
        self._room_id:     str        = ""
        self._room_devs:   list[str]  = []
        self._room_sensors:list[str]  = []
        self._edit_room_id:str        = ""

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _coordinator(self):
        return self.hass.data.get(DOMAIN, {}).get(
            self.config_entry.entry_id, {}
        ).get(DATA_COORDINATOR)

    def _store(self):
        c = self._coordinator()
        return c.store if c else None

    def _z2m_base(self) -> str:
        opts = self.config_entry.options or {}
        data = self.config_entry.data or {}
        return opts.get(CONF_Z2M_BASE_TOPIC, data.get(CONF_Z2M_BASE_TOPIC, DEFAULT_Z2M_TOPIC))

    def _all_devices(self) -> dict:
        s = self._store()
        return s.get_all_devices() if s else {}

    def _all_rooms(self) -> dict:
        s = self._store()
        return s.get_all_rooms() if s else {}

    def _ungrouped_trv_ids(self, exclude_room: str | None = None) -> list[str]:
        """Return TRV device IDs not currently in any room (optionally excluding one room)."""
        s = self._store()
        if not s:
            return []
        all_grouped: set[str] = set()
        for rid, rd in s.get_all_rooms().items():
            if rid == exclude_room:
                continue
            all_grouped.update(rd.get("device_ids", []))
        return [
            did for did, dd in s.get_all_devices().items()
            if dd.get("type") == DEVICE_TYPE_TRV and did not in all_grouped
        ]

    def _discovered_z2m_topics(self) -> dict[str, str]:
        """Return {topic: label} for Z2M MQTT climate entities not already registered."""
        ent_reg = er.async_get(self.hass)
        existing_topics = {
            d.get("mqtt_topic", "")
            for d in self._all_devices().values()
            if d.get("mqtt_topic")
        }
        result: dict[str, str] = {}
        for entry in ent_reg.entities.values():
            if entry.platform != "mqtt":
                continue
            if not entry.entity_id.startswith("climate."):
                continue
            uid = entry.unique_id or ""
            if uid.startswith(f"{DOMAIN}_") and uid.endswith("_climate"):
                continue  # our own room entity
            topic = uid
            if topic in existing_topics:
                continue
            name = entry.name or entry.original_name or topic.split("/")[-1]
            result[topic] = f"{name} ({topic})"
        return result

    def _no_rooms_result(self) -> config_entries.FlowResult:
        return self.async_create_entry(title="", data=self.config_entry.options or {})

    # ── Top-level menu ─────────────────────────────────────────────────────────

    async def async_step_init(self, _=None) -> config_entries.FlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options={
                "manage_devices": "Devices — add, remove TRVs, receivers, sensors",
                "manage_rooms":   "Rooms — create and manage heating zones",
                "settings":       "Settings — boiler, Z2M topic, diagnostics",
            },
        )

    # ── Settings ───────────────────────────────────────────────────────────────

    async def async_step_settings(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        if user_input is not None:
            c = self._coordinator()
            if c:
                c.update_boiler_entity(user_input.get(CONF_BOILER_ENTITY) or None)
            new_opts = {
                **(self.config_entry.options or {}),
                CONF_Z2M_BASE_TOPIC: user_input.get(CONF_Z2M_BASE_TOPIC, DEFAULT_Z2M_TOPIC),
                CONF_BOILER_ENTITY:  user_input.get(CONF_BOILER_ENTITY) or None,
                CONF_ENABLE_DIAG:    user_input.get(CONF_ENABLE_DIAG, False),
            }
            return self.async_create_entry(title="", data=new_opts)

        merged = {**(self.config_entry.data or {}), **(self.config_entry.options or {})}
        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_Z2M_BASE_TOPIC,
                    default=merged.get(CONF_Z2M_BASE_TOPIC, DEFAULT_Z2M_TOPIC),
                ): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                ),
                vol.Optional(
                    CONF_BOILER_ENTITY,
                    description={"suggested_value": merged.get(CONF_BOILER_ENTITY)},
                ): selector.EntitySelector(selector.EntitySelectorConfig(
                    domain=["climate", "switch", "input_boolean"]
                )),
                vol.Optional(
                    CONF_ENABLE_DIAG,
                    default=merged.get(CONF_ENABLE_DIAG, False),
                ): selector.BooleanSelector(),
            }),
        )

    # ── Device management menu ─────────────────────────────────────────────────

    async def async_step_manage_devices(self, _=None) -> config_entries.FlowResult:
        return self.async_show_menu(
            step_id="manage_devices",
            menu_options={
                "add_trv":       "Add a TRV",
                "add_receiver":  "Add a receiver (SLR1 / SLR2 / OTR1)",
                "add_sensor":    "Add a temperature sensor",
                "remove_device": "Remove a device",
            },
        )

    # ── Add TRV ────────────────────────────────────────────────────────────────

    async def async_step_add_trv(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        """Step 1: browse discovered Z2M devices or enter topic manually."""
        errors: dict = {}
        discovered = self._discovered_z2m_topics()

        if user_input is not None:
            selected = (user_input.get("z2m_entity") or "").strip()
            manual   = (user_input.get("mqtt_topic")  or "").strip()
            topic    = selected or manual
            if not topic:
                errors["z2m_entity"] = "required"
            else:
                self._dev_topic = topic
                self._dev_name  = discovered.get(topic, "").split(" (")[0] or topic.split("/")[-1]
                self._dev_type  = DEVICE_TYPE_TRV
                return await self.async_step_confirm_device()

        schema: dict = {}
        if discovered:
            schema[vol.Optional("z2m_entity")] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=k, label=v)
                        for k, v in sorted(discovered.items(), key=lambda x: x[1])
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        schema[vol.Optional("mqtt_topic")] = selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
        )
        return self.async_show_form(
            step_id="add_trv",
            data_schema=vol.Schema(schema),
            description_placeholders={
                "count": str(len(discovered)),
                "hint":  (
                    f"{len(discovered)} TRV(s) detected in Z2M. Select one or enter the topic manually."
                    if discovered else
                    f"No Z2M TRVs detected yet. Enter the full topic manually, e.g. {self._z2m_base()}/Living Room TRV"
                ),
            },
            errors=errors,
        )

    # ── Add Receiver ───────────────────────────────────────────────────────────

    async def async_step_add_receiver(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        """Step 1: browse or enter topic."""
        errors: dict = {}
        discovered = self._discovered_z2m_topics()

        if user_input is not None:
            selected = (user_input.get("z2m_entity") or "").strip()
            manual   = (user_input.get("mqtt_topic")  or "").strip()
            topic    = selected or manual
            if not topic:
                errors["z2m_entity"] = "required"
            else:
                self._dev_topic = topic
                self._dev_name  = discovered.get(topic, "").split(" (")[0] or topic.split("/")[-1]
                self._dev_type  = DEVICE_TYPE_RECEIVER
                return await self.async_step_receiver_model()

        schema: dict = {}
        if discovered:
            schema[vol.Optional("z2m_entity")] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=k, label=v)
                        for k, v in sorted(discovered.items(), key=lambda x: x[1])
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        schema[vol.Optional("mqtt_topic")] = selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
        )
        return self.async_show_form(
            step_id="add_receiver",
            data_schema=vol.Schema(schema),
            description_placeholders={
                "hint": (
                    f"{len(discovered)} device(s) detected. Select your receiver or enter its topic manually."
                    if discovered else
                    f"Enter the full receiver topic, e.g. {self._z2m_base()}/Hive Receiver"
                ),
            },
            errors=errors,
        )

    async def async_step_receiver_model(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        if user_input is not None:
            self._dev_model = user_input.get("model", MODEL_SLR1)
            return await self.async_step_confirm_device()
        return self.async_show_form(
            step_id="receiver_model",
            data_schema=vol.Schema({
                vol.Required("model", default=MODEL_SLR1): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=RECEIVER_MODELS,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
            description_placeholders={"topic": self._dev_topic},
        )

    # ── Add Sensor ─────────────────────────────────────────────────────────────

    async def async_step_add_sensor(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        errors: dict = {}
        if user_input is not None:
            entity_id = user_input.get("sensor_entity", "").strip()
            name      = user_input.get("sensor_name", "").strip()
            if not entity_id:
                errors["sensor_entity"] = "required"
            elif not name:
                errors["sensor_name"] = "required"
            else:
                device_id = str(uuid.uuid4())[:8]
                data = {
                    "type":      DEVICE_TYPE_SENSOR,
                    "name":      name,
                    "entity_id": entity_id,
                }
                c = self._coordinator()
                if c:
                    await c.async_add_device(device_id, data)
                return self.async_create_entry(title="", data=self.config_entry.options or {})

        return self.async_show_form(
            step_id="add_sensor",
            data_schema=vol.Schema({
                vol.Required("sensor_entity"): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor", device_class="temperature"
                    )
                ),
                vol.Required("sensor_name"): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                ),
            }),
            errors=errors,
        )

    # ── Confirm device (shared by TRV and receiver) ────────────────────────────

    async def async_step_confirm_device(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        errors: dict = {}
        if user_input is not None:
            name = user_input.get("device_name", "").strip()
            if not name:
                errors["device_name"] = "required"
            else:
                device_id = str(uuid.uuid4())[:8]
                data: dict = {
                    "type":       self._dev_type,
                    "name":       name,
                    "mqtt_topic": self._dev_topic,
                }
                if self._dev_type == DEVICE_TYPE_RECEIVER:
                    data["model"] = self._dev_model
                c = self._coordinator()
                if c:
                    await c.async_add_device(device_id, data)
                return self.async_create_entry(title="", data=self.config_entry.options or {})

        return self.async_show_form(
            step_id="confirm_device",
            data_schema=vol.Schema({
                vol.Required(
                    "device_name",
                    description={"suggested_value": self._dev_name},
                ): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                ),
            }),
            description_placeholders={
                "topic": self._dev_topic,
                "type":  "TRV" if self._dev_type == DEVICE_TYPE_TRV else f"Receiver ({self._dev_model})",
            },
        )

    # ── Remove Device ──────────────────────────────────────────────────────────

    async def async_step_remove_device(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        devices = self._all_devices()
        if not devices:
            return self._no_rooms_result()

        if user_input is not None:
            device_id = user_input.get("device_id")
            if device_id:
                c = self._coordinator()
                if c:
                    await c.async_remove_device(device_id)
            return self.async_create_entry(title="", data=self.config_entry.options or {})

        return self.async_show_form(
            step_id="remove_device",
            data_schema=vol.Schema({
                vol.Required("device_id"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(
                                value=did,
                                label=f"{dd.get('name', did)} ({dd.get('type', '?')})"
                            )
                            for did, dd in sorted(devices.items(), key=lambda x: x[1].get("name", ""))
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
        )

    # ── Room management menu ───────────────────────────────────────────────────

    async def async_step_manage_rooms(self, _=None) -> config_entries.FlowResult:
        return self.async_show_menu(
            step_id="manage_rooms",
            menu_options={
                "create_room": "Create a new room",
                "edit_room":   "Edit room members",
                "remove_room": "Remove a room",
            },
        )

    # ── Create Room ────────────────────────────────────────────────────────────

    async def async_step_create_room(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        errors: dict = {}
        if user_input is not None:
            name = user_input.get("room_name", "").strip()
            if not name:
                errors["room_name"] = "required"
            else:
                self._room_name = name
                return await self.async_step_room_members()
        return self.async_show_form(
            step_id="create_room",
            data_schema=vol.Schema({
                vol.Required("room_name"): selector.TextSelector()
            }),
            errors=errors,
        )

    async def async_step_room_members(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        """Pick TRVs for this room from registered ungrouped TRVs."""
        errors: dict = {}
        ungrouped = self._ungrouped_trv_ids()
        devices   = self._all_devices()

        # Build options: {device_id: name}
        options = [
            selector.SelectOptionDict(
                value=did,
                label=devices[did].get("name", did)
            )
            for did in ungrouped if did in devices
        ]

        if user_input is not None:
            chosen = user_input.get("device_ids") or []
            if not chosen:
                errors["device_ids"] = "required"
            else:
                self._room_devs = chosen
                return await self.async_step_room_sensors()

        return self.async_show_form(
            step_id="room_members",
            data_schema=vol.Schema({
                vol.Required("device_ids"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options if options else [],
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
            }),
            description_placeholders={
                "room_name": self._room_name,
                "count":     str(len(ungrouped)),
                "hint":      (
                    f"{len(ungrouped)} TRV(s) available."
                    if ungrouped else
                    "No ungrouped TRVs available. Add TRVs first via Manage Devices."
                ),
            },
            errors=errors,
        )

    async def async_step_room_sensors(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        """Optionally pick standalone temperature sensors for this room."""
        if user_input is not None:
            self._room_sensors = user_input.get("sensor_ids") or []
            return await self._do_create_room()

        # Get registered sensor devices
        devices = self._all_devices()
        sensor_options = [
            selector.SelectOptionDict(
                value=did,
                label=devices[did].get("name", did)
            )
            for did, dd in devices.items()
            if dd.get("type") == DEVICE_TYPE_SENSOR
        ]

        schema: dict = {}
        if sensor_options:
            schema[vol.Optional("sensor_ids")] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=sensor_options,
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                )
            )

        return self.async_show_form(
            step_id="room_sensors",
            data_schema=vol.Schema(schema) if schema else vol.Schema({}),
            description_placeholders={
                "room_name": self._room_name,
                "hint": (
                    "Select any temperature sensors to include in room temperature averaging."
                    if sensor_options else
                    "No standalone sensors registered. You can add them later via Manage Devices."
                ),
            },
        )

    async def _do_create_room(self) -> config_entries.FlowResult:
        room_id   = str(uuid.uuid4())
        room_data = {
            "name":         self._room_name,
            "device_ids":   self._room_devs,
            "sensor_ids":   self._room_sensors,
            "schedule":     [],
            "boost_temp":   22.0,
            "boost_minutes":30,
            "frost_temp":   7.0,
            "frost_enabled":False,
        }
        c = self._coordinator()
        if c:
            await c.async_add_room(room_id, room_data)
        return self.async_create_entry(title="", data=self.config_entry.options or {})

    # ── Edit Room ──────────────────────────────────────────────────────────────

    async def async_step_edit_room(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        rooms = self._all_rooms()
        if not rooms:
            return self._no_rooms_result()

        if user_input is not None:
            self._edit_room_id = user_input.get("room_id", "")
            return await self.async_step_edit_room_members()

        return self.async_show_form(
            step_id="edit_room",
            data_schema=vol.Schema({
                vol.Required("room_id"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(
                                value=rid, label=rd.get("name", rid)
                            )
                            for rid, rd in sorted(
                                rooms.items(), key=lambda x: x[1].get("name", "")
                            )
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
        )

    async def async_step_edit_room_members(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        errors: dict = {}
        room_data   = self._all_rooms().get(self._edit_room_id, {})
        current_devs = room_data.get("device_ids", [])
        current_sens = room_data.get("sensor_ids", [])

        # TRVs available = ungrouped + current room's members
        ungrouped = self._ungrouped_trv_ids(exclude_room=self._edit_room_id)
        available = sorted(set(current_devs) | set(ungrouped))
        devices   = self._all_devices()

        trv_options = [
            selector.SelectOptionDict(value=did, label=devices[did].get("name", did))
            for did in available if did in devices
        ]
        sensor_options = [
            selector.SelectOptionDict(value=did, label=devices[did].get("name", did))
            for did, dd in devices.items()
            if dd.get("type") == DEVICE_TYPE_SENSOR
        ]

        if user_input is not None:
            new_devs = user_input.get("device_ids") or []
            new_sens = user_input.get("sensor_ids")  or []
            if not new_devs:
                errors["device_ids"] = "required"
            else:
                c = self._coordinator()
                if c:
                    await c.async_update_room(self._edit_room_id, new_devs, new_sens)
            if not errors:
                return self.async_create_entry(title="", data=self.config_entry.options or {})

        schema: dict = {
            vol.Required("device_ids", default=current_devs): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=trv_options,
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
        }
        if sensor_options:
            schema[vol.Optional("sensor_ids", default=current_sens)] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=sensor_options,
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                )
            )

        return self.async_show_form(
            step_id="edit_room_members",
            data_schema=vol.Schema(schema),
            description_placeholders={
                "room_name": room_data.get("name", self._edit_room_id)
            },
            errors=errors,
        )

    # ── Remove Room ────────────────────────────────────────────────────────────

    async def async_step_remove_room(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        rooms = self._all_rooms()
        if not rooms:
            return self._no_rooms_result()

        if user_input is not None:
            room_id = user_input.get("room_id")
            if room_id:
                c = self._coordinator()
                if c:
                    await c.async_remove_room(room_id)
            return self.async_create_entry(title="", data=self.config_entry.options or {})

        return self.async_show_form(
            step_id="remove_room",
            data_schema=vol.Schema({
                vol.Required("room_id"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(
                                value=rid, label=rd.get("name", rid)
                            )
                            for rid, rd in sorted(
                                rooms.items(), key=lambda x: x[1].get("name", "")
                            )
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
        )
